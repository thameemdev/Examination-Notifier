import json
import logging
from typing import Dict, Any, Optional
from utils.config import Config
from utils.logging import get_logger

logger = get_logger("gemini_client")

class GeminiClient:
    """
    Client for interacting with Google's Gemini LLM API to extract 
    and summarize notification documents.
    """

    def __init__(self, api_key: str = Config.GEMINI_API_KEY):
        self.api_key = api_key
        self.enabled = bool(api_key)
        self.model_name = "gemini-1.5-flash"
        
        if self.enabled:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"Gemini Client initialized successfully using model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Google Generative AI: {e}")
                self.enabled = False
        else:
            logger.info("Gemini API key not found. AI features will be disabled (falling back to regex parser).")

    def analyze_pdf_text(self, pdf_text: str, notice_title: str) -> Optional[Dict[str, Any]]:
        """
        Sends extracted PDF text to Gemini to generate summary and extract dates.
        Returns a dict of extracted information, or None if disabled/failed.
        """
        if not self.enabled:
            return None

        # Truncate text if it is excessively long to save token limits
        truncated_text = pdf_text[:8000]
        
        prompt = f"""
You are an expert academic notice processor for Mahatma Gandhi University.
Given the following notification title and extracted text from a PDF, extract and structure the information as requested below.

Notification Title: {notice_title}

Extracted PDF Text:
---
{truncated_text}
---

Your response MUST be a JSON object with the following fields:
1. "summary": A string containing exactly 3-5 bullet points summarizing the notice. Format each bullet on a new line starting with a '-' bullet.
2. "exam_dates": An array of strings representing any exam start dates, exam schedules, or date ranges found in the notice. (e.g. ["2026-06-22"])
3. "fee_deadline": A string indicating the last date to submit examination fees. If there are multiple deadlines (e.g. without fine, with fine), clearly mention them in a single string. (e.g. "2026-07-05 without fine, 2026-07-10 with fine")
4. "hall_ticket_date": A string indicating when hall tickets will be released.
5. "revaluation_deadline": A string indicating the revaluation/scrutiny submission deadline.
6. "result_publication_date": A string indicating the date results are published.
7. "semester": A string indicating the semester number (e.g. "I Semester", "IV Semester", "X Semester").
8. "programme": A string indicating the academic programme(s) affected.
9. "important_changes": A string listing any critical changes, postponements, cancellations, or rescheduled examinations. Highlight dates of cancelled/rescheduled exams.

Use YYYY-MM-DD date format where possible. If a field is not mentioned or cannot be found, use null.
Do not include any markdown format blocks other than the JSON itself.
"""
        try:
            # We request JSON response format from Gemini
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            result_json = response.text.strip()
            # Clean possible markdown JSON wrappers if the model still outputs them
            if result_json.startswith("```json"):
                result_json = result_json[7:]
            if result_json.endswith("```"):
                result_json = result_json[:-3]
            result_json = result_json.strip()
            
            data = json.loads(result_json)
            logger.info("Successfully analyzed PDF text via Gemini API.")
            return data
            
        except Exception as e:
            logger.error(f"Error querying Gemini API: {e}")
            return None
