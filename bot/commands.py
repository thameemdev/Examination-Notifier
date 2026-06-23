import logging
from typing import List, Dict, Any, Tuple, Optional
from database.db_manager import DBManager
from services.telegram_client import TelegramClient
from utils.logging import get_logger

logger = get_logger("bot_commands")

class CommandHandler:
    """
    Handles command processing and execution for the Telegram Bot.
    """

    def __init__(self, db: DBManager, telegram_client: TelegramClient):
        self.db = db
        self.telegram = telegram_client

    def handle_command(self, chat_id: int, command: str, args: List[str], username: Optional[str] = None) -> str:
        """
        Routes and processes bot commands. Returns the response text.
        """
        cmd = command.lower().strip()
        logger.info(f"Processing command '{cmd}' from chat {chat_id} (args: {args})")

        if cmd == "start":
            return self._cmd_start(chat_id, username)
        elif cmd == "help":
            return self._cmd_help()
        elif cmd == "latest":
            return self._cmd_latest()
        elif cmd == "results":
            return self._cmd_results()
        elif cmd == "timetable":
            return self._cmd_timetable()
        elif cmd == "notifications":
            return self._cmd_notifications()
        elif cmd == "highpriority":
            return self._cmd_highpriority()
        elif cmd == "status":
            return self._cmd_status()
        elif cmd == "search":
            return self._cmd_search(args)
        elif cmd == "subscribe":
            return self._cmd_subscribe(chat_id, username)
        elif cmd == "unsubscribe":
            return self._cmd_unsubscribe(chat_id)
        else:
            return "Unknown command. Type /help to see the list of available commands."

    def _cmd_start(self, chat_id: int, username: Optional[str]) -> str:
        self.db.subscribe_chat(chat_id, username)
        return (
            "🎓 <b>Welcome to MGU AI & ML Examination Notifier Bot!</b>\n\n"
            "This bot automatically monitors Mahatma Gandhi University examination "
            "portals and alerts you immediately about notifications regarding:\n"
            "• <i>Integrated M.Sc Computer Science - AI & ML</i>\n"
            "• <i>General rescheduled, postponed, or cancelled exams</i>\n\n"
            "You have been <b>automatically subscribed</b> to receive immediate push alerts.\n\n"
            "<b>Available Commands:</b>\n"
            "/latest - Get latest 5 announcements\n"
            "/results - Get recent exam results\n"
            "/timetable - Get theory timetables\n"
            "/notifications - Get category-wise exam notices\n"
            "/highpriority - Show recent high priority alerts\n"
            "/search &lt;keyword&gt; - Search notifications database\n"
            "/status - View system and subscription status\n"
            "/unsubscribe - Stop receiving automatic push alerts\n"
            "/subscribe - Resume receiving automatic alerts"
        )

    def _cmd_help(self) -> str:
        return (
            "📚 <b>MGU AI & ML Notifier Help Guide</b>\n\n"
            "Here are the commands you can use to query exam notifications:\n"
            "/latest - Displays the last 5 relevant updates.\n"
            "/results - Displays published results for AI & ML.\n"
            "/timetable - Displays timetables for examinations.\n"
            "/notifications - General examination notices.\n"
            "/highpriority - Displays recent emergency alerts (postponements, etc.).\n"
            "/search &lt;keyword&gt; - Searches the title and text of updates. (e.g. /search IV Sem)\n"
            "/status - Shows bot uptime and database numbers.\n"
            "/subscribe - Enroll to receive automated alerts.\n"
            "/unsubscribe - Remove yourself from push alerts."
        )

    def _cmd_subscribe(self, chat_id: int, username: Optional[str]) -> str:
        new_sub = self.db.subscribe_chat(chat_id, username)
        if new_sub:
            return "✅ <b>Successfully Subscribed!</b> You will receive instant notifications for MGU AI & ML examination updates."
        else:
            return "ℹ️ You are <b>already subscribed</b> to automated alerts."

    def _cmd_unsubscribe(self, chat_id: int) -> str:
        removed = self.db.unsubscribe_chat(chat_id)
        if removed:
            return "🔕 <b>Successfully Unsubscribed.</b> You will no longer receive automated push alerts. You can still query commands manually."
        else:
            return "ℹ️ You were not in the subscriber list."

    def _cmd_latest(self) -> str:
        notices = self.db.get_latest_notifications(limit=5)
        if not notices:
            return "No recent notifications found in the database."
        return self._format_notices_list("Latest Notifications", notices)

    def _cmd_results(self) -> str:
        notices = self.db.get_latest_notifications(limit=5, category="Result")
        if not notices:
            return "No recent exam results found for your course."
        return self._format_notices_list("Recent Results", notices)

    def _cmd_timetable(self) -> str:
        notices = self.db.get_latest_notifications(limit=5, category="Time Table")
        # Check revised time tables too
        revised = self.db.get_latest_notifications(limit=5, category="Revised Time Table")
        all_tt = (notices + revised)[:5]
        if not all_tt:
            return "No recent timetables found in the database."
        return self._format_notices_list("Recent Timetables", all_tt)

    def _cmd_notifications(self) -> str:
        # Category: General Exam Notice
        notices = self.db.get_latest_notifications(limit=5, category="General Examination Notice")
        if not notices:
            return "No recent general notices found in database."
        return self._format_notices_list("Recent General Notices", notices)

    def _cmd_highpriority(self) -> str:
        notices = self.db.get_latest_notifications(limit=5)
        # Filter for priority items manually based on priority patterns
        from filters.course_filter import CourseFilter
        priority_notices = [n for n in notices if CourseFilter.is_high_priority(n["title"])]
        if not priority_notices:
            return "No recent high-priority alerts found."
        return self._format_notices_list("High-Priority Alerts", priority_notices[:5])

    def _cmd_status(self) -> str:
        subs = self.db.get_subscribers()
        total_notices = len(self.db.get_latest_notifications(limit=100000))
        return (
            "⚙️ <b>Bot System Status</b>\n\n"
            f"• <b>Status:</b> Running (Healthy)\n"
            f"• <b>Active Subscribers:</b> {len(subs)}\n"
            f"• <b>Total Database Notices:</b> {total_notices}\n"
            f"• <b>Target Course:</b> Integrated M.Sc Computer Science - AI & ML\n"
            f"• <b>Scraping Frequency:</b> Every 10 Minutes (GHA)\n"
            f"• <b>Current Local Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _cmd_search(self, args: List[str]) -> str:
        if not args:
            return "⚠️ Please specify a keyword to search. Usage: /search &lt;keyword&gt;"
        keyword = " ".join(args)
        results = self.db.search_notifications(keyword, limit=5)
        if not results:
            return f"No results found matching keyword: <b>'{keyword}'</b>"
        return self._format_notices_list(f"Search Results for '{keyword}'", results)

    def _format_notices_list(self, header: str, notices: List[Dict[str, Any]]) -> str:
        """Helper to format list of notices into pretty HTML."""
        lines = [f"📅 <b>{header}</b>\n"]
        for i, n in enumerate(notices, 1):
            category = n.get("category", "Notice")
            pub_date = n.get("published_date", "Date unknown")
            title = n.get("title")
            url = n.get("url")
            
            lines.append(
                f"{i}. <b>[{category}]</b> ({pub_date})\n"
                f"   {title}\n"
                f"   🔗 <a href='{url}'>Open Notice Link</a>\n"
            )
        return "\n".join(lines)
