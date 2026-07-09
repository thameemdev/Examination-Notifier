import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse
from typing import List, Dict, Any, Optional
from scraper.base import BaseScraper
from utils.logging import get_logger

logger = get_logger("mgu_scraper")

class MGUScraper(BaseScraper):
    """
    Scraper for Mahatma Gandhi University (MGU) examination category pages.
    """
    
    # Easily add/remove categories to monitor
    MONITORED_PAGES = {
        "Exam Notifications": "https://www.mgu.ac.in/exam-category/exam-notifications/",
        "Theory Timetables": "https://www.mgu.ac.in/exam-category/time-table-for-theory-examinations/",
        "Practical Timetables": "https://www.mgu.ac.in/exam-category/time-table-for-practicals/",
        "Project/Viva-Voce": "https://www.mgu.ac.in/exam-category/time-table-for-project-evaluationviva-voce/",
        "Examination Orders": "https://www.mgu.ac.in/exam-category/examination-orders/",
        "Rank/Position Notifications": "https://www.mgu.ac.in/exam-category/rank-position-notifications/"
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    @property
    def university_name(self) -> str:
        return "Mahatma Gandhi University"

    def _normalize_date(self, date_str: str) -> str:
        """Converts date string like '19 - June - 2026' or '08 - June - 2026' to 'YYYY-MM-DD'."""
        try:
            cleaned = "".join(date_str.split()) # Remove spaces
            # Clean string, replace long dashes
            cleaned = cleaned.replace("–", "-").replace("—", "-")
            # Parse format like '19-June-2026'
            dt = datetime.strptime(cleaned, "%d-%B-%Y")
            return dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.debug(f"Could not parse date string '{date_str}': {e}. Using current date as fallback.")
            return datetime.now().strftime("%Y-%m-%d")

    def _classify_by_title(self, title: str, category_source: str) -> str:
        """Helper to classify notifications by looking at title and source page."""
        t = title.lower()
        if "result" in t:
            return "Result"
        elif "revised" in t and ("time table" in t or "timetable" in t):
            return "Revised Time Table"
        elif "time table" in t or "timetable" in t:
            if "practical" in t or "viva" in t or "project" in t:
                return "Practical Time Table"
            return "Time Table"
        elif "postpone" in t:
            return "Postponement"
        elif "reschedule" in t:
            return "Rescheduled"
        elif "cancel" in t:
            return "Cancellation"
        elif "extend" in t:
            return "Extension"
        elif "fee" in t:
            return "Fee Notification"
        elif "hall ticket" in t or "admit card" in t:
            return "Hall Ticket"
        elif "revaluation" in t or "scrutiny" in t:
            return "Revaluation"
        elif "circular" in t:
            return "Circular"
        elif "order" in t:
            return "Examination Order"
            
        # Fallback to category page name
        if category_source == "Theory Timetables":
            return "Time Table"
        elif category_source == "Practical Timetables":
            return "Practical Time Table"
        elif category_source == "Examination Orders":
            return "Examination Order"
        
        return "General Examination Notice"

    def scrape(self) -> List[Dict[str, Any]]:
        """Scrapes all monitored MGU pages and returns notifications list."""
        all_notices = []
        
        with httpx.Client(headers=self.HEADERS, follow_redirects=True, timeout=30.0, verify=False) as client:
            for cat_name, url in self.MONITORED_PAGES.items():
                logger.info(f"Scraping category page: {cat_name} -> {url}")
                try:
                    response = client.get(url)
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch {url}. Status code: {response.status_code}")
                        continue
                        
                    soup = BeautifulSoup(response.text, "html.parser")
                    # Find all exam notifications
                    nbx_blocks = soup.find_all("div", class_="exam-nbx")
                    logger.info(f"Found {len(nbx_blocks)} notification items on page {cat_name}")
                    
                    for block in nbx_blocks:
                        try:
                            # 1. Extract Title
                            h3_tag = block.find("h3")
                            if not h3_tag:
                                continue
                            title = h3_tag.text.strip()
                            
                            # 2. Extract Date
                            span_tag = block.find("span")
                            raw_date = span_tag.text.strip() if span_tag else ""
                            pub_date = self._normalize_date(raw_date)
                            
                            # 3. Extract Links
                            a_tag = block.find("a", class_="read-more")
                            if not a_tag:
                                continue
                            
                            href = a_tag.get("href", "").strip()
                            # Clean the URL
                            href = urllib.parse.unquote(href)
                            
                            # Standardize link paths
                            if href.startswith("/"):
                                href = f"https://www.mgu.ac.in{href}"
                                
                            # Check if PDF
                            pdf_url = None
                            if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
                                # Clean potential query params from PDF URL to get standard file format
                                if "?" in href:
                                    href = href.split("?")[0]
                                pdf_url = href
                                
                            category = self._classify_by_title(title, cat_name)
                            
                            all_notices.append({
                                "title": title,
                                "url": href,
                                "published_date": pub_date,
                                "pdf_url": pdf_url,
                                "category": category,
                                "raw_content": title  # Text representation of notice
                            })
                            
                        except Exception as item_err:
                            logger.error(f"Error parsing item block in {cat_name}: {item_err}")
                            
                except Exception as page_err:
                    logger.error(f"Error reading category page {cat_name} ({url}): {page_err}")
                    
        logger.info(f"Total MGU notifications scraped: {len(all_notices)}")
        return all_notices
