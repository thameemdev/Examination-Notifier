import asyncio
import hashlib
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add project root to python path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.config import Config
from utils.logging import scheduler_logger, notifications_logger, get_logger
from database.db_manager import DBManager
from scraper.mgu_scraper import MGUScraper
from scraper.result_monitor import ResultMonitor
from parsers.pdf_parser import PDFParser
from parsers.ai_parser import AIParser
from filters.course_filter import CourseFilter
from services.telegram_client import TelegramClient
from services.gemini_client import GeminiClient
from bot.bot_manager import BotManager

logger = get_logger("runner")

def compute_content_hash(notice: Dict[str, Any]) -> str:
    """Computes a SHA256 hash of a notification details to detect revisions."""
    payload = f"{notice.get('title')}|{notice.get('url')}|{notice.get('category')}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

async def notify_all_subscribers(telegram_client: TelegramClient, db: DBManager, 
                                 notice: Dict[str, Any], metadata: Dict[str, Any], 
                                 is_high_priority: bool, is_update: bool = False) -> None:
    """Sends notifications to all registered bot subscribers and the default channel."""
    # Retrieve subscribers from database
    subscribers = db.get_subscribers()
    chat_ids = list(subscribers.keys())
    
    # Ensure default CHAT_ID is included in targets
    default_chat = Config.CHAT_ID.strip()
    if default_chat and default_chat not in chat_ids:
        chat_ids.append(default_chat)
        
    logger.info(f"Delivering notification to {len(chat_ids)} targets (priority: {is_high_priority}, update: {is_update})")
    
    for cid in chat_ids:
        try:
            if is_high_priority:
                telegram_client.send_high_priority_alert(cid, notice, metadata)
            else:
                telegram_client.send_notification(cid, notice, metadata, is_update=is_update)
            # Add short delay between dispatches to comply with Telegram rate limits
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to deliver message to subscriber {cid}: {e}")

async def process_notification_item(notice: Dict[str, Any], db: DBManager, 
                                    pdf_parser: PDFParser, ai_parser: AIParser, 
                                    telegram_client: TelegramClient) -> None:
    """
    Downloads PDFs, runs filters, extracts AI/regex summaries, 
    and dispatches Telegram alerts for a scraped announcement.
    """
    url = notice.get("url")
    title = notice.get("title")
    category = notice.get("category")
    published_date = notice.get("published_date")
    
    # Check database
    existing_notice = db.get_notification_by_url(url)
    content_hash = compute_content_hash(notice)
    
    pdf_url = notice.get("pdf_url")
    pdf_text = None
    pdf_hash = None
    
    # Handle PDF downloading & parsing
    if pdf_url:
        existing_pdf = db.get_pdf_by_url(pdf_url)
        if existing_pdf:
            pdf_text = existing_pdf["extracted_text"]
            pdf_hash = existing_pdf["pdf_hash"]
        else:
            extracted_text, sha_hash = pdf_parser.download_and_extract(pdf_url)
            if extracted_text and sha_hash:
                pdf_text = extracted_text
                pdf_hash = sha_hash
                # Extract details using AI/Regex and save
                analysis = ai_parser.parse_notice_content(pdf_text, title)
                db.add_pdf(pdf_url, pdf_hash, pdf_text, analysis["summary"], 
                           analysis, analysis)
                logger.info(f"Saved new PDF record for {pdf_url}")
                
    # Define relevance checks
    is_relevant, match_reason = CourseFilter.check_relevance(title, notice.get("raw_content", ""), pdf_text, url, category=category)
    is_priority = CourseFilter.is_high_priority(title, pdf_text)
    
    # Define default metadata in case of no PDF
    metadata = {
        "summary": "- General university notification.\n- Check details using link source.",
        "exam_dates": [],
        "fee_deadline": "Not specified",
        "hall_ticket_date": "Not specified",
        "revaluation_deadline": "Not specified",
        "result_publication_date": "Not specified",
        "semester": "Not specified",
        "programme": "Not specified",
        "important_changes": "None"
    }
    
    if pdf_url:
        pdf_record = db.get_pdf_by_url(pdf_url)
        if pdf_record:
            metadata = pdf_record["important_dates"]
            # If AI summary is in the outer column:
            metadata["summary"] = pdf_record["summary"] or metadata.get("summary")

    if not existing_notice:
        # Case A: Brand New Notification
        if is_relevant:
            notifications_logger.info(f"[NEW RELEVANT NOTICE] {title} (Reason: {match_reason})")
            db.add_notification(title, url, published_date, category, content_hash, 
                                 notice.get("raw_content", ""), pdf_hash, "SENT")
            await notify_all_subscribers(telegram_client, db, notice, metadata, is_priority)
        else:
            logger.debug(f"[SKIPPED IRRELEVANT] {title}")
            db.add_notification(title, url, published_date, category, content_hash, 
                                 notice.get("raw_content", ""), pdf_hash, "SKIPPED")
            
    else:
        # Case B: Already Seen. Check for updates/changes
        has_changed = False
        update_reason = []
        
        # 1. Content details change
        if existing_notice["sha256_hash"] != content_hash:
            has_changed = True
            update_reason.append("Announcement title/category details modified.")
            
        # 2. PDF file replaced
        if pdf_hash and existing_notice["pdf_hash"] != pdf_hash:
            has_changed = True
            update_reason.append("PDF attachment updated with new file.")
            
        if has_changed:
            notifications_logger.info(f"[UPDATED NOTICE DETECTED] {title}. Changes: {', '.join(update_reason)}")
            
            # Recalculate PDF text if PDF updated
            if pdf_url and "PDF" in "".join(update_reason):
                extracted_text, sha_hash = pdf_parser.download_and_extract(pdf_url)
                if extracted_text and sha_hash:
                    pdf_text = extracted_text
                    pdf_hash = sha_hash
                    analysis = ai_parser.parse_notice_content(pdf_text, title)
                    db.add_pdf(pdf_url, pdf_hash, pdf_text, analysis["summary"], analysis, analysis)
                    # Refresh metadata
                    metadata = analysis
            
            # Recheck relevance
            is_relevant, match_reason = CourseFilter.check_relevance(title, notice.get("raw_content", ""), pdf_text, url, category=category)
            is_priority = CourseFilter.is_high_priority(title, pdf_text)
            
            status = "SENT" if is_relevant else "SKIPPED"
            db.update_notification(title, url, published_date, category, content_hash, 
                                    notice.get("raw_content", ""), pdf_hash, status)
            
            if is_relevant:
                await notify_all_subscribers(telegram_client, db, notice, metadata, is_priority, is_update=True)
        else:
            logger.debug(f"[NO CHANGE] {title}")

async def run_notifiers() -> None:
    """Main function that orchestrates the scraping and notification run."""
    scheduler_logger.info("========================================")
    scheduler_logger.info("MGU Exam Notifier Run Started")
    scheduler_logger.info("========================================")
    
    # Validate environment configuration
    try:
        Config.validate()
    except ValueError as val_err:
        scheduler_logger.critical(f"Configuration validation failed:\n{val_err}")
        print(f"CRITICAL CONFIG ERROR: {val_err}", file=sys.stderr)
        return

    # Initialize Core DB and Clients
    db = DBManager()
    telegram_client = TelegramClient()
    gemini_client = GeminiClient()
    bot_manager = BotManager(db, telegram_client)
    
    pdf_parser = PDFParser()
    ai_parser = AIParser(gemini_client)
    
    db.add_db_log("INFO", "scheduler", "Scraper execution initialized.")

    # 1. Process Bot Updates (Commands like /subscribe)
    if Config.RUN_MODE == "cron":
        await bot_manager.process_updates_once()

    # 2. Run Scrapers
    mgu_scraper = MGUScraper()
    result_monitor = ResultMonitor()
    
    logger.info("Starting MGU Web category scraping...")
    web_notices = mgu_scraper.scrape()
    logger.info(f"Retrieved {len(web_notices)} notifications from web category scraper.")
    
    logger.info("Starting MGU Result portal scraping...")
    result_notices = result_monitor.scrape()
    logger.info(f"Retrieved {len(result_notices)} options from results monitor.")
    
    all_items = web_notices + result_notices
    logger.info(f"Processing total of {len(all_items)} scraped items...")
    
    # Process items sequentially to avoid request flooding
    for item in all_items:
        try:
            await process_notification_item(item, db, pdf_parser, ai_parser, telegram_client)
        except Exception as item_err:
            logger.error(f"Failed to process notice '{item.get('title')}': {item_err}")
            
    db.add_db_log("INFO", "scheduler", f"Scraper execution completed. Processed {len(all_items)} items.")
    scheduler_logger.info("MGU Exam Notifier Run Completed Successfully.")

if __name__ == "__main__":
    asyncio.run(run_notifiers())
