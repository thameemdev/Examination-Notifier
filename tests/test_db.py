import os
import tempfile
import pytest
from database.db_manager import DBManager

@pytest.fixture
def temp_db():
    """Creates a temporary database for testing."""
    fd, path = tempfile.mkstemp()
    yield DBManager(db_path=path)
    os.close(fd)
    os.unlink(path)

def test_init_db(temp_db):
    """Verifies tables are created correctly."""
    # Try inserting setting
    temp_db.set_setting("test_key", "test_value")
    assert temp_db.get_setting("test_key") == "test_value"

def test_add_get_notification(temp_db):
    """Tests adding and fetching a notification."""
    title = "Test Announcement"
    url = "https://www.mgu.ac.in/test-url"
    pub_date = "2026-06-23"
    category = "Circular"
    content_hash = "abcdef123456"
    text = "Detailed test content."
    pdf_hash = "pdf_hash_val"
    status = "SENT"

    success = temp_db.add_notification(
        title, url, pub_date, category, content_hash, text, pdf_hash, status
    )
    assert success is True

    # Duplicate should fail
    dup = temp_db.add_notification(
        title, url, pub_date, category, content_hash, text, pdf_hash, status
    )
    assert dup is False

    # Fetch by URL
    notice = temp_db.get_notification_by_url(url)
    assert notice is not None
    assert notice["title"] == title
    assert notice["sha256_hash"] == content_hash

    # Fetch by hash
    notice_by_hash = temp_db.get_notification_by_hash(content_hash)
    assert notice_by_hash is not None
    assert notice_by_hash["url"] == url

def test_update_notification(temp_db):
    """Tests updating an existing notification."""
    url = "https://www.mgu.ac.in/test-update"
    temp_db.add_notification(
        "Old Title", url, "2026-06-20", "Circular", "old_hash", "text", "pdf_hash", "SENT"
    )

    # Update
    updated = temp_db.update_notification(
        "New Title", url, "2026-06-21", "Time Table", "new_hash", "new text", "new_pdf_hash", "UPDATED"
    )
    assert updated is True

    notice = temp_db.get_notification_by_url(url)
    assert notice["title"] == "New Title"
    assert notice["category"] == "Time Table"
    assert notice["sha256_hash"] == "new_hash"
    assert notice["status"] == "UPDATED"

def test_subscriptions(temp_db):
    """Tests bot subscriber registrations."""
    chat_1 = 1234567
    chat_2 = 7654321

    # Initially empty
    assert temp_db.get_subscribers() == {}

    # Subscribe
    assert temp_db.subscribe_chat(chat_1, "user_one") is True
    assert temp_db.subscribe_chat(chat_1, "user_one") is False  # Duplicate subscribe

    temp_db.subscribe_chat(chat_2, "user_two")

    subs = temp_db.get_subscribers()
    assert str(chat_1) in subs
    assert subs[str(chat_1)] == "user_one"
    assert str(chat_2) in subs
    assert subs[str(chat_2)] == "user_two"

    # Unsubscribe
    assert temp_db.unsubscribe_chat(chat_1) is True
    assert temp_db.unsubscribe_chat(chat_1) is False  # Already unsubscribed

    subs_after = temp_db.get_subscribers()
    assert str(chat_1) not in subs_after
    assert str(chat_2) in subs_after
