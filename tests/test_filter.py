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

    # User reported false match: BPES Integrated Programme
    r3, _ = CourseFilter.check_relevance(
        "Fee cum TimeTable Notification- IV Semester BPES (Four Year Integrated Programme – 2023, 2022, 2021, 2020, 2019 & 2018 Admissions Reappearance / 2017 & 2016 Admissions Mercy Chance) Degree Examinations, June 2026",
        ""
    )
    assert r3 is False

    # User reported false match: B.Ed rescheduled exams
    r4, _ = CourseFilter.check_relevance(
        "II Semester B.Ed Examinations scheduled on 08.06.2026 and 10.06.2026 have been rescheduled",
        ""
    )
    assert r4 is False

    # User reported false match: IMCA timetable containing AI paper in PDF
    r5, _ = CourseFilter.check_relevance(
        "TimeTable- VIII Semester IMCA (2022 Admission Regular/ 2021 & 2020 Admission Supplementary) Degree Examinations, June 2026",
        "",
        "Day 1: Knowledge Management\nDay 2: Artificial Intelligence"
    )
    assert r5 is False

    # User reported false match: M.Sc CSS Artificial Intelligence (2 year regular, non-integrated)
    r6, _ = CourseFilter.check_relevance(
        "II Semester M.Sc. (CSS) degree examinations (2025,2024,2023,2022,2021,2020,2019 Admissions)",
        "",
        "Course: M.Sc. ARTIFICIAL INTELLIGENCE\nSubject: AI010201 Advanced Machine Learning"
    )
    assert r6 is False

def test_results_portal_bypass():
    """Tests that any results scraped from target course 430 page are automatically relevant."""
    r, reason = CourseFilter.check_relevance(
        "II Semester M.Sc. (CSS) degree examinations (2025 Admissions)",
        "",
        "",
        url="https://pareeksha.mgu.ac.in/Pareeksha/index.php/Public/PareekshaResultView_ctrl/index/3/430?exam_id=537"
    )
    assert r is True
    assert "results portal" in reason

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

def test_postponement_relevance_filtering():
    """Tests refinement of postponement notifications depending on PDF content."""
    # 1. Postponed exam that lists specific other courses in PDF (MBA, MCA) but not our course
    r1, reason1 = CourseFilter.check_relevance(
        title="18628/EA 1/1/2019/EA 1- All the examinations scheduled on 26.06.2026 have been postponed and rescheduled",
        webpage_content="Check notices details.",
        pdf_text="Sl.No. Name of the Examination Scheduled Date Rescheduled Date\n1. IV Semester MBA (2024 Admission Regular)\n2. V Semester MCA (2011 Admission Onwards)",
        category="Postponement"
    )
    assert r1 is False
    assert "lists other courses" in reason1

    # 2. Postponed exam that lists our course in PDF
    r2, reason2 = CourseFilter.check_relevance(
        title="18628/EA 1/1/2019/EA 1- All the examinations scheduled on 22.06.2026 have been postponed and rescheduled",
        webpage_content="Check notices details.",
        pdf_text="Sl.No. Name of the Examination Scheduled Date Rescheduled Date\n1. III Semester MCA\n2. II Semester Integrated M.Sc Computer Science - Artificial Intelligence & Machine Learning",
        category="Postponement"
    )
    assert r2 is True
    assert "explicitly lists target course" in reason2

    # 3. Universal postponement (heavy rain) where no specific courses are listed in PDF
    r3, reason3 = CourseFilter.check_relevance(
        title="All examinations scheduled on 22.06.2026 are postponed",
        webpage_content="Due to heavy rain.",
        pdf_text="It is hereby notified that all examinations scheduled on 22.06.2026 are postponed. The rescheduled dates will be announced later.",
        category="Postponement"
    )
    assert r3 is True
    assert "General postponement notice" in reason3
