import os
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
from scraper.base import BaseScraper
from utils.logging import get_logger

logger = get_logger("result_monitor")

class ResultMonitor(BaseScraper):
    """
    Scraper for the MGU Results Portal.
    Monitors the page for new exam result publications for the course (ID 430).
    """

    RESULTS_URL = "https://pareeksha.mgu.ac.in/Pareeksha/index.php/Public/PareekshaResultView_ctrl/index/3/430"

    @property
    def university_name(self) -> str:
        return "Mahatma Gandhi University Results"

    def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrapes the results portal.
        Tries to use Playwright first, and falls back to BeautifulSoup if Playwright fails.
        """
        logger.info(f"Checking results portal: {self.RESULTS_URL}")
        
        # 1. Attempt Playwright Scrape (dynamic)
        try:
            return self._scrape_playwright()
        except Exception as e:
            logger.warning(f"Playwright results scrape failed: {e}. Falling back to BeautifulSoup...")
            
        # 2. Attempt BeautifulSoup Scrape (static fallback)
        try:
            return self._scrape_bs4()
        except Exception as e:
            logger.error(f"BeautifulSoup fallback results scrape failed: {e}")
            
        return []

    def _scrape_playwright(self) -> List[Dict[str, Any]]:
        """Scrapes the results portal using Playwright."""
        from playwright.sync_api import sync_playwright
        
        logger.info("Initializing Playwright...")
        notices = []
        
        with sync_playwright() as p:
            # Run headless
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            logger.info(f"Navigating to {self.RESULTS_URL} via Playwright...")
            # Navigate and wait for network idle to make sure all scripts run
            page.goto(self.RESULTS_URL, wait_until="networkidle", timeout=30000)
            
            # Wait for the select option elements
            page.wait_for_selector("select#exam_id", timeout=15000)
            
            # Extract dropdown options
            options = page.eval_on_selector_all(
                "select#exam_id option",
                "options => options.map(o => ({ value: o.value, text: o.innerText }))"
            )
            
            browser.close()
            
            logger.info(f"Playwright found {len(options)} exam result options.")
            notices = self._parse_options_list(options)
            
        return notices

    def _scrape_bs4(self) -> List[Dict[str, Any]]:
        """Scrapes the results portal using standard HTTPX and BeautifulSoup."""
        logger.info(f"Navigating to {self.RESULTS_URL} via HTTPX...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = httpx.get(
            self.RESULTS_URL, 
            headers=headers, 
            verify=False, 
            timeout=20.0, 
            follow_redirects=True
        )
        
        if response.status_code != 200:
            logger.error(f"Static fetch failed with status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        select_tag = soup.find("select", {"id": "exam_id"})
        
        if not select_tag:
            logger.warning("Could not find select#exam_id element in static HTML.")
            return []
            
        options = []
        for opt in select_tag.find_all("option"):
            options.append({
                "value": opt.get("value", ""),
                "text": opt.text.strip()
            })
            
        logger.info(f"BS4 static parser found {len(options)} exam result options.")
        return self._parse_options_list(options)

    def _parse_options_list(self, options: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Parses raw dropdown options into standard notification dictionaries."""
        notices = []
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        for opt in options:
            val = opt.get("value", "").strip()
            text = opt.get("text", "").strip()
            
            # Skip empty placeholder options like "--- Select Examination ---"
            if not val or "select" in text.lower():
                continue
                
            # Create a unique URL for this specific exam result option
            unique_url = f"{self.RESULTS_URL}?exam_id={val}"
            
            # The result announcement title
            title = f"Result Published: {text}"
            
            notices.append({
                "title": title,
                "url": unique_url,
                "published_date": current_date, # Date discovered
                "pdf_url": None,
                "category": "Result",
                "raw_content": f"Results have been announced on the Mahatma Gandhi University Pareeksha portal for: {text}."
            })
            
        return notices
