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
    def check_relevance(cls, title: str, webpage_content: str, pdf_text: Optional[str] = None) -> Tuple[bool, str]:
        """
        Determines if a notification is relevant based on the title, webpage content, and pdf text.
        Returns a tuple: (is_relevant: bool, match_reason: str).
        """
        pdf_txt = pdf_text or ""
        combined_text = f"{title}\n{webpage_content}\n{pdf_txt}".lower()
        
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

        # 3. Check for specific Target Course matches
        # Strong indicators (AI & ML details)
        ai_ml_keywords = ["artificial intelligence", "machine learning", "ai & ml", "ai and ml"]
        for keyword in ai_ml_keywords:
            if keyword.lower() in combined_text:
                reason = f"Specific target course match: '{keyword}'"
                logger.info(f"Notification marked RELEVANT: {reason}")
                return True, reason
                
        # Combination check: Integrated AND Computer Science
        if "integrated" in combined_text and "computer science" in combined_text:
            reason = "Integrated Computer Science programme combination match."
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
