import pytest
from filters.course_filter import CourseFilter

def test_course_relevance_matches():
    """Tests that relevant notifications are correctly detected."""
    # 1. Direct course name matches
    r1, _ = CourseFilter.check_relevance(
        "Exam notifications for Integrated M.Sc Computer Science - Artificial Intelligence & Machine Learning", 
        "Details inside."
    )
    assert r1 is True

    # 2. AI & ML keywords
    r2, _ = CourseFilter.check_relevance(
        "Announcements for AI & ML examination batch", 
        "Important dates."
    )
    assert r2 is True

    # 3. General exam matches
    r3, _ = CourseFilter.check_relevance(
        "All examinations scheduled on 22.06.2026 are postponed", 
        "Due to heavy rain."
    )
    assert r3 is True

    # 4. Integrated Program matches
    r4, _ = CourseFilter.check_relevance(
        "Fee schedule for Integrated M.Sc programmes", 
        "Fee Details."
    )
    assert r4 is True

def test_course_relevance_ignores():
    """Tests that irrelevant notifications are correctly ignored."""
    # B.Tech Electronics
    r1, _ = CourseFilter.check_relevance(
        "Time Table for IV Semester B.Tech Electronics and Communication Examination", 
        "Syllabus and time details."
    )
    assert r1 is False

    # MA History
    r2, _ = CourseFilter.check_relevance(
        "Results published for MA History Second Semester", 
        "Pass percentage details."
    )
    assert r2 is False

def test_high_priority_detection():
    """Tests detection of high-priority emergency notifications."""
    # Postponed
    assert CourseFilter.is_high_priority("Examinations scheduled on monday have been postponed") is True
    # Cancelled
    assert CourseFilter.is_high_priority("Tenth Semester Law Exams Cancelled") is True
    # Revised Timetable
    assert CourseFilter.is_high_priority("Revised Time Table for Integrated M.Sc AI & ML") is True
    # Regular notice
    assert CourseFilter.is_high_priority("General instructions for examination registration") is False
