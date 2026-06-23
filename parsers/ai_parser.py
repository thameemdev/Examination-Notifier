import re
from typing import Dict, Any, List
from services.gemini_client import GeminiClient
from utils.logging import get_logger

logger = get_logger("ai_parser")

class AIParser:
    """
    Orchestrates PDF text extraction parsing.
    Queries Gemini Client if enabled; otherwise falls back to a rule-based
    regex parser to maintain system fault-tolerance and offline capabilities.
    """

    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client

    def parse_notice_content(self, pdf_text: str, notice_title: str) -> Dict[str, Any]:
        """
        Parses notification content. First attempts Gemini analysis,
        and falls back to Regex if Gemini is disabled or fails.
        """
        # 1. Try Gemini
        if self.gemini_client.enabled:
            logger.info("Attempting AI extraction using Gemini API...")
            ai_data = self.gemini_client.analyze_pdf_text(pdf_text, notice_title)
            if ai_data:
                # Ensure all required keys exist
                formatted = self._format_ai_response(ai_data)
                logger.info("AI extraction succeeded.")
                return formatted
            logger.warning("AI extraction returned empty or failed. Falling back to Regex parser.")

        # 2. Regex Fallback
        logger.info("Running regex-based information extraction...")
        return self._parse_regex(pdf_text, notice_title)

    def _format_ai_response(self, ai_data: Dict[str, Any]) -> Dict[str, Any]:
        """Formats the response from Gemini to match our database expectations."""
        return {
            "summary": ai_data.get("summary") or "No summary available.",
            "exam_dates": ai_data.get("exam_dates") or [],
            "fee_deadline": ai_data.get("fee_deadline") or "Not specified",
            "hall_ticket_date": ai_data.get("hall_ticket_date") or "Not specified",
            "revaluation_deadline": ai_data.get("revaluation_deadline") or "Not specified",
            "result_publication_date": ai_data.get("result_publication_date") or "Not specified",
            "semester": ai_data.get("semester") or "Not specified",
            "programme": ai_data.get("programme") or "Not specified",
            "important_changes": ai_data.get("important_changes") or "None detected"
        }

    def _parse_regex(self, text: str, title: str) -> Dict[str, Any]:
        """Rule-based regex extractor as backup if Gemini is unavailable."""
        combined_text = f"{title}\n{text}"
        
        # 1. Detect Semester
        semester = "Not specified"
        sem_patterns = [
            r"([I|V|X|L|C]+)\s+Semester",
            r"([1-9]th|[1-9]st|[1-9]nd|[1-9]rd)\s+Semester",
            r"Semester\s+([I|V|X|L|C]+)",
            r"Semester\s+([1-9]+)"
        ]
        for pattern in sem_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                semester = match.group(0).strip()
                break

        # 2. Extract Dates (DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY)
        dates = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b", combined_text)
        # Standardize dates to YYYY-MM-DD
        std_dates = []
        for date_str in dates:
            # Replace dots/slashes with dashes
            replaced = date_str.replace(".", "-").replace("/", "-")
            try:
                # Parse depending on position
                parts = replaced.split("-")
                if len(parts) == 3:
                    # Assume DD-MM-YYYY
                    dt = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    std_dates.append(dt)
            except Exception:
                pass
        
        # Deduplicate standard dates
        std_dates = list(set(std_dates))

        # 3. Detect Deadlines & Exam Dates
        fee_deadline = "Not specified"
        exam_dates_list = []
        
        # Search for fee submission text
        fee_matches = re.findall(r"(?:last date for|fee without fine|fine of|submission of fee|fee upto)\b.*?\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b", combined_text, re.IGNORECASE)
        if fee_matches:
            fee_deadline = f"Last date detected: {', '.join(set(fee_matches))}"
            
        # Search for exam schedule dates
        exam_schedule_matches = re.findall(r"(?:commence on|scheduled to begin on|examination starting on|exams from)\b.*?\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b", combined_text, re.IGNORECASE)
        for date_str in exam_schedule_matches:
            replaced = date_str.replace(".", "-").replace("/", "-")
            parts = replaced.split("-")
            if len(parts) == 3:
                std_dt = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                exam_dates_list.append(std_dt)
                
        if not exam_dates_list and std_dates:
            # Fallback: add all unique standard dates found
            exam_dates_list = std_dates[:2]

        # 4. Detect Program
        programme = "Not specified"
        if "Artificial Intelligence" in combined_text or "AI & ML" in combined_text:
            programme = "Integrated M.Sc Programme in Computer Science – AI & ML"
        elif "Computer Science" in combined_text:
            programme = "M.Sc Computer Science / Integrated Computer Science"
        elif "Integrated" in combined_text:
            programme = "Integrated Programme"

        # 5. Classify Important Changes
        important_changes = "None detected"
        change_keywords = ["postpone", "reschedule", "cancel", "revised", "date change", "extend"]
        changes_found = []
        for line in combined_text.split("\n"):
            if any(kw in line.lower() for kw in change_keywords):
                cleaned_line = line.strip()
                if len(cleaned_line) > 10:
                    changes_found.append(cleaned_line[:120] + ("..." if len(cleaned_line) > 120 else ""))
        if changes_found:
            important_changes = "- " + "\n- ".join(set(changes_found[:3]))

        # 6. Generate Bullet Summary
        bullets = []
        # Bullet 1: Announcement Type
        bullets.append(f"Examination update published by MG University: {title[:80]}.")
        # Bullet 2: Semester/Course context
        if semester != "Not specified":
            bullets.append(f"Affects students enrolled in {semester}.")
        if programme != "Not specified":
            bullets.append(f"Course context: {programme}.")
        # Bullet 3: Important dates context
        if fee_deadline != "Not specified":
            bullets.append(f"Fee submission deadline: {fee_deadline}.")
        if exam_dates_list:
            bullets.append(f"Key dates highlighted in PDF text: {', '.join(exam_dates_list)}.")
            
        summary = "\n".join(f"- {b}" for b in bullets[:4])

        return {
            "summary": summary,
            "exam_dates": exam_dates_list,
            "fee_deadline": fee_deadline,
            "hall_ticket_date": "Refer to notice details",
            "revaluation_deadline": "Not specified",
            "result_publication_date": "Not specified",
            "semester": semester,
            "programme": programme,
            "important_changes": important_changes
        }
