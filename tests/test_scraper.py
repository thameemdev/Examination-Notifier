import pytest
from scraper.mgu_scraper import MGUScraper

@pytest.fixture
def scraper():
    return MGUScraper()

def test_normalize_date(scraper):
    """Tests normalisation of date formats from MGU pages."""
    assert scraper._normalize_date("19 - June - 2026") == "2026-06-19"
    assert scraper._normalize_date("05 - May - 2026") == "2026-05-05"
    assert scraper._normalize_date("01 - January - 2025") == "2025-01-01"

def test_classify_by_title(scraper):
    """Tests notification category classification from titles."""
    assert scraper._classify_by_title("Results Published: IV Sem Integrated M.Sc", "Exam Notifications") == "Result"
    assert scraper._classify_by_title("Revised Time Table for Exams", "Theory Timetables") == "Revised Time Table"
    assert scraper._classify_by_title("Postponement of scheduled BHM exams", "Exam Notifications") == "Postponement"
    assert scraper._classify_by_title("Last Date Extended for Fee Submission", "Exam Notifications") == "Extension"
    assert scraper._classify_by_title("Fee Notification for III Sem", "Exam Notifications") == "Fee Notification"
    assert scraper._classify_by_title("Hall Ticket Released", "Exam Notifications") == "Hall Ticket"
    assert scraper._classify_by_title("Regular notifications text", "Examination Orders") == "Examination Order"
