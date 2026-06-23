import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    # Default chat/channel ID where notifications are sent if no user-specific subscription is active or for general channel updates
    CHAT_ID: str = os.getenv("CHAT_ID", "")
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "10"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "mgu_notifier.db"))
    LOG_DIR: str = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
    
    # Run Mode: 'cron' or 'daemon'
    RUN_MODE: str = os.getenv("RUN_MODE", "cron").lower()
    
    # Course Filter Keywords
    TARGET_COURSE_KEYWORDS = [
        "Integrated M.Sc",
        "Computer Science",
        "Artificial Intelligence",
        "Machine Learning",
        "AI & ML",
        "Artificial Intelligence & Machine Learning",
        "Integrated Computer Science"
    ]
    
    # General Exam Keywords that apply to everyone
    GENERAL_EXAM_KEYWORDS = [
        "all examinations",
        "all exams",
        "all pg examinations",
        "all ug examinations",
        "all pg/ug examinations",
        "all the examinations scheduled",
        "examinations scheduled on",
        "examinations postponed",
        "examinations rescheduled",
        "examinations cancelled",
        "university holiday"
    ]
    
    # General Integrated Program Keywords
    INTEGRATED_PROGRAM_KEYWORDS = [
        "integrated programme",
        "integrated programmes",
        "integrated m.a",
        "integrated m.sc",
        "integrated ms",
        "integrated ma",
        "integrated courses"
    ]

    @classmethod
    def validate(cls):
        """Validate critical configuration elements."""
        errors = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required in environment.")
        if not cls.CHAT_ID:
            errors.append("CHAT_ID is required in environment (fallback channel).")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)
        
        if errors:
            raise ValueError("\n".join(errors))
