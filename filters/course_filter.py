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
    def contains_target_course(cls, text: str) -> bool:
        """Checks if the given text contains references to the target course."""
        text_lower = text.lower()
        # Direct abbreviation matches
        ai_ml_abbrevs = ["ai & ml", "ai and ml", "ai &ml", "ai&ml", "ai/ml"]
        for abbrev in ai_ml_abbrevs:
            if abbrev in text_lower:
                return True
        
        # Specific target course combination match (Integrated M.Sc CS AI/ML or Data Science)
        has_integrated = any(term in text_lower for term in ["integrated m.sc", "integrated m sc", "integrated msc", "integrated computer", "integrated pg"])
        has_cs = "computer science" in text_lower or "computerscience" in text_lower
        has_specialization = any(term in text_lower for term in ["artificial intelligence", "machine learning", "data science"])
        
        if has_integrated and has_cs and has_specialization:
            return True
            
        return False

    @classmethod
    def check_relevance(cls, title: str, webpage_content: str, pdf_text: Optional[str] = None, url: Optional[str] = None, category: Optional[str] = None) -> Tuple[bool, str]:
        """
        Determines if a notification is relevant based on the title, webpage content, pdf text, URL, and category.
        Returns a tuple: (is_relevant: bool, match_reason: str).
        """
        pdf_txt = pdf_text or ""
        combined_text = f"{title}\n{webpage_content}\n{pdf_txt}".lower()
        
        # 0. Check if notification is from course-specific results portal (course 430)
        if url and "index/3/430" in url:
            reason = "From course-specific (ID 430) results portal."
            logger.info(f"Notification marked RELEVANT: {reason}")
            return True, reason

        # 0.5 Check for postponement/rescheduling notices
        is_postponement = False
        postpone_keywords = ["postpone", "reschedule", "rescheduled", "postponed", "rescheduling", "postponement"]
        if category and category.lower() in ["postponement", "rescheduled", "postponed"]:
            is_postponement = True
        elif any(kw in title.lower() for kw in postpone_keywords):
            is_postponement = True
        elif any(kw in webpage_content.lower() for kw in postpone_keywords):
            is_postponement = True

        if is_postponement:
            if pdf_text:
                if cls.contains_target_course(pdf_text):
                    reason = "Postponement notice explicitly lists target course in PDF."
                    logger.info(f"Notification marked RELEVANT: {reason}")
                    return True, reason
                else:
                    # Check if the PDF lists specific other courses.
                    # If it does, we are excluded. If it does not, it might be a general postponement.
                    other_courses = ["mba", "m.b.a", "mca", "m.c.a", "b.tech", "btech", "m.tech", "mtech", "bed", "b.ed", "m.ed", "med", "bhm", "b.h.m", "b.p.ed", "bped", "ll.b", "llb", "ll.m", "llm", "b.arch", "barch", "m.arch", "march"]
                    has_other_courses = any(re.search(rf"\b{re.escape(course)}\b", pdf_text.lower()) for course in other_courses)
                    
                    # Also check general courses (B.Sc, M.Sc, etc.) outside of "integrated"
                    cleaned_pdf_text = re.sub(r"integrated\s+\S+", "", pdf_text.lower())
                    other_general_courses = ["b.sc", "bsc", "m.sc", "msc", "b.a", "ba", "m.a", "ma", "b.com", "bcom", "m.com", "mcom"]
                    has_other_general = any(re.search(rf"\b{re.escape(course)}\b", cleaned_pdf_text) for course in other_general_courses)
                    
                    if has_other_courses or has_other_general:
                        logger.info("Postponement notice skipped: PDF lists other specific courses but not the target course.")
                        return False, "Postponement notice lists other courses but not target course."
                    else:
                        # No specific other courses listed; check if it matches a general postponement title
                        for keyword in Config.GENERAL_EXAM_KEYWORDS:
                            if keyword.lower() in title.lower() or keyword.lower() in webpage_content.lower():
                                reason = f"General postponement notice (no specific course exclusions found in PDF): '{keyword}'"
                                logger.info(f"Notification marked RELEVANT: {reason}")
                                return True, reason
                        return False, "Postponement notice does not affect target course."
            else:
                # No PDF text available. Check if target course is in title or webpage content.
                if cls.contains_target_course(title) or cls.contains_target_course(webpage_content):
                    reason = "Postponement notice matches target course in title or webpage content."
                    logger.info(f"Notification marked RELEVANT: {reason}")
                    return True, reason
                # Or if it matches a general postponement keyword in title/webpage content
                for keyword in Config.GENERAL_EXAM_KEYWORDS:
                    if keyword.lower() in title.lower() or keyword.lower() in webpage_content.lower():
                        reason = f"General postponement notice (no PDF): '{keyword}'"
                        logger.info(f"Notification marked RELEVANT: {reason}")
                        return True, reason
                return False, "Postponement notice does not affect target course."

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
