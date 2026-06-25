import re
from typing import Tuple, List, Optional
from utils.config import Config
from utils.logging import get_logger


logger = get_logger("course_filter")

class CourseFilter:
    """
    Applies filtering rules on scraped notifications and parsed PDF texts to 
    determine if they apply to the target course or general university updates.
    Also handles priority classification.
    """

    # High Priority triggers (case insensitive regex search patterns)
    HIGH_PRIORITY_PATTERNS = [
        r"postponed?\b",
        r"rescheduled?\b",
        r"cancelled?\b",
        r"revised\s+(?:time\s*table|timetable)",
        r"last\s+date\s+extended?\b",
        r"hall\s+tickets?\s+released?\b",
        r"emergency\s+notice",
        r"university\s+holiday"
    ]

    @classmethod
    def check_relevance(cls, title: str, webpage_content: str, pdf_text: Optional[str] = None, url: Optional[str] = None) -> Tuple[bool, str]:
        """
        Determines if a notification is relevant based on the title, webpage content, pdf text, and URL.
        Returns a tuple: (is_relevant: bool, match_reason: str).
        """
        pdf_txt = pdf_text or ""
        combined_text = f"{title}\n{webpage_content}\n{pdf_txt}".lower()
        
        # 0. Check if notification is from course-specific results portal (course 430)
        if url and "index/3/430" in url:
            reason = "From course-specific (ID 430) results portal."
            logger.info(f"Notification marked RELEVANT: {reason}")
            return True, reason

        # 1. Check for "ALL Examinations" keywords
        for keyword in Config.GENERAL_EXAM_KEYWORDS:
            if keyword.lower() in combined_text:
                reason = f"Matches general examination scope: '{keyword}'"
                logger.info(f"Notification marked RELEVANT: {reason}")
                return True, reason

        # 2. Check for "ALL Integrated M.A / M.Sc Programmes"
        for keyword in Config.INTEGRATED_PROGRAM_KEYWORDS:
            if keyword.lower() in combined_text:
                reason = f"Matches general Integrated Programmes scope: '{keyword}'"
                logger.info(f"Notification marked RELEVANT: {reason}")
                return True, reason

        # 3. Direct abbreviation matches for target course (highly specific)
        ai_ml_abbrevs = ["ai & ml", "ai and ml", "ai &ml", "ai&ml", "ai/ml"]
        for abbrev in ai_ml_abbrevs:
            if abbrev in combined_text:
                reason = f"Direct target course abbreviation match: '{abbrev}'"
                logger.info(f"Notification marked RELEVANT: {reason}")
                return True, reason

        # 4. Check for specific Target Course matches using combination check
        # We require a combination of (integrated) AND (computer science) AND (artificial intelligence or machine learning or data science)
        has_integrated = any(term in combined_text for term in ["integrated m.sc", "integrated m sc", "integrated msc", "integrated computer", "integrated pg"])
        has_cs = "computer science" in combined_text
        has_ai_ml = any(term in combined_text for term in ["artificial intelligence", "machine learning", "data science"])
        
        if has_integrated and has_cs and has_ai_ml:
            reason = "Specific target course combination match (Integrated M.Sc CS AI/ML)."
            logger.info(f"Notification marked RELEVANT: {reason}")
            return True, reason

        logger.debug("Notification marked IRRELEVANT (no target keywords or general scopes matched).")
        return False, ""

    @classmethod
    def is_high_priority(cls, title: str, pdf_text: Optional[str] = None) -> bool:
        """
        Detects if a notice warrants a High Priority Alert (e.g. cancellations, postponements).
        """
        pdf_txt = pdf_text or ""
        combined_text = f"{title}\n{pdf_txt}".lower()
        
        for pattern in cls.HIGH_PRIORITY_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                logger.info(f"Notification classified as HIGH PRIORITY due to pattern: {pattern}")
                return True
                
        return False
