import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.config import Config
from utils.logging import get_logger


logger = get_logger("telegram_client")

class TelegramClient:
    """
    Client for sending formatted HTML alerts to Telegram chats and channels
    using the Telegram Bot API.
    """

    def __init__(self, token: str = Config.BOT_TOKEN):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.enabled = bool(token)
        if not self.enabled:
            logger.warning("Telegram Bot Token is missing. Bot notification delivery will be skipped.")

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Sends a raw text message to a specific chat ID."""
        if not self.enabled:
            return False
            
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        
        try:
            # We use a short timeout for network resilience
            response = httpx.post(self.api_url, json=payload, timeout=15.0)
            if response.status_code == 200:
                logger.info(f"Message successfully sent to Telegram chat {chat_id}.")
                return True
            else:
                logger.error(f"Failed to send Telegram message to {chat_id}. Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Network error sending Telegram message to {chat_id}: {e}")
            return False

    def send_notification(self, chat_id: str, notice: Dict[str, Any], metadata: Dict[str, Any], 
                          is_update: bool = False) -> bool:
        """
        Formats and sends a standard exam notification message.
        """
        # Determine prefix for new vs updated notices
        prefix = "♻️ Updated Notification" if is_update else "🎓 MG University Update"
        
        # Prepare dates string
        fee_dl = metadata.get("fee_deadline", "Not specified")
        ex_dts = metadata.get("exam_dates", [])
        ex_dts_str = ", ".join(ex_dts) if ex_dts else "Not specified"
        ht_dt = metadata.get("hall_ticket_date", "Not specified")
        rv_dl = metadata.get("revaluation_deadline", "Not specified")
        rs_pub = metadata.get("result_publication_date", "Not specified")
        
        important_dates = (
            f"• <b>Fee Deadline:</b> {fee_dl}\n"
            f"• <b>Exam Commencement:</b> {ex_dts_str}\n"
            f"• <b>Hall Ticket Date:</b> {ht_dt}\n"
            f"• <b>Revaluation Deadline:</b> {rv_dl}\n"
            f"• <b>Result Publication Date:</b> {rs_pub}"
        )
        
        detected_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build HTML Message
        message = (
            f"🎓 <b>{prefix}</b>\n\n"
            f"<b>Category:</b> {notice.get('category', 'Notice')}\n"
            f"<b>Course:</b> Integrated M.Sc Computer Science (AI & ML)\n"
            f"<b>Semester:</b> {metadata.get('semester', 'Not specified')}\n\n"
            f"<b>Title:</b> {notice.get('title')}\n\n"
            f"<b>Summary:</b>\n{metadata.get('summary', 'No summary available.')}\n\n"
            f"<b>Important Dates:</b>\n{important_dates}\n\n"
            f"<b>Source:</b> <a href='{notice.get('url')}'>Click here to open link</a>\n"
            f"<i>Detected At: {detected_time}</i>"
        )
        
        return self.send_message(chat_id, message)

    def send_high_priority_alert(self, chat_id: str, notice: Dict[str, Any], 
                                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Formats and sends a High Priority Alert message (postponements, cancellations, etc.).
        """
        # Formulate impact and action based on details
        title = notice.get("title", "")
        category = notice.get("category", "General Alert")
        
        impact = "Applies to all scheduled examinations." if "all" in title.lower() else "Applies to specific scheduled examinations. Verify course relevance."
        action = "Check revised timetable details."
        
        if "cancel" in title.lower():
            impact = "Examinations have been cancelled."
            action = "Await official announcement on rescheduled dates."
        elif "postpone" in title.lower():
            impact = "Examinations have been postponed."
            action = "Check for revised dates and schedules."
        elif "hall ticket" in title.lower():
            impact = "Hall Tickets have been released."
            action = "Download hall tickets from pareeksha portal immediately."
            
        detected_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = (
            f"🚨 <b>MG UNIVERSITY HIGH PRIORITY ALERT</b>\n\n"
            f"<b>Category:</b> {category}\n"
            f"<b>Title:</b> {title}\n\n"
            f"<b>Impact:</b> {impact}\n"
            f"<b>Action Required:</b> {action}\n\n"
            f"<b>URL:</b> <a href='{notice.get('url')}'>Click here to view notice</a>\n"
            f"<i>Detected Time: {detected_time}</i>"
        )
        
        return self.send_message(chat_id, message)
