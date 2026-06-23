from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    """
    Abstract Base Class for all University Exam Website Scrapers.
    To support a new university, implement a subclass of BaseScraper
    and implement the `scrape` method.
    """
    
    @property
    @abstractmethod
    def university_name(self) -> str:
        """Returns the name of the university this scraper belongs to."""
        pass
        
    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        Runs the scraper and returns a list of dictionaries representing notices.
        
        Each notice dict must have the following structure:
        {
            "title": str,                # The title of the notification
            "url": str,                  # Permanent link to the notice/details
            "published_date": str,       # Date published as string (YYYY-MM-DD or formatted)
            "pdf_url": Optional[str],    # URL to the main PDF attachment if available
            "category": str,             # Classified category (e.g. Result, Time Table)
            "raw_content": str           # Optional full description or content
        }
        """
        pass
