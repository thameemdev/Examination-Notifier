import asyncio
import logging
from typing import Optional
from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler as TelegramCommandHandler,
    MessageHandler,
    filters as TelegramFilters,
    ContextTypes
)
from database.db_manager import DBManager
from bot.commands import CommandHandler
from services.telegram_client import TelegramClient
from utils.config import Config
from utils.logging import get_logger

logger = get_logger("bot_manager")

class BotManager:
    """
    Manages the Telegram Bot execution modes.
    1. Cron Mode: Fetches updates via get_updates, processes them once, and exits.
    2. Daemon Mode: Starts a continuous polling event loop.
    """

    def __init__(self, db: DBManager, telegram_client: TelegramClient):
        self.db = db
        self.telegram = telegram_client
        self.handler = CommandHandler(self.db, self.telegram)

    # --- Cron Mode (Serverless Update Processing) ---

    async def process_updates_once(self) -> None:
        """
        Polls for new updates, handles commands, sends responses, and updates offset.
        Designed to be run once in cron scripts.
        """
        if not Config.BOT_TOKEN:
            logger.error("BOT_TOKEN is missing. Cannot process updates.")
            return

        logger.info("Starting serverless Telegram update processing...")
        bot = Bot(token=Config.BOT_TOKEN)
        
        # Get last update offset from DB
        last_offset_str = self.db.get_setting("last_update_offset")
        offset = int(last_offset_str) + 1 if last_offset_str else None
        
        try:
            # Fetch updates
            logger.debug(f"Fetching updates from Telegram with offset={offset}...")
            updates = await bot.get_updates(offset=offset, timeout=10)
            logger.info(f"Retrieved {len(updates)} pending updates from Telegram.")
            
            max_update_id = offset - 1 if offset else 0
            
            for update in updates:
                max_update_id = max(max_update_id, update.update_id)
                await self._process_single_update(bot, update)
                
            # Store new offset in database settings
            if updates:
                self.db.set_setting("last_update_offset", str(max_update_id))
                logger.info(f"Database settings updated: last_update_offset = {max_update_id}")
                
        except Exception as e:
            logger.error(f"Error fetching or processing updates in Cron mode: {e}")

    async def _process_single_update(self, bot: Bot, update: Update) -> None:
        """Processes a single fetched Update object."""
        if not update.message or not update.message.text:
            return
            
        chat_id = update.message.chat_id
        text = update.message.text.strip()
        username = update.message.from_user.username if update.message.from_user else None
        
        if not text.startswith("/"):
            # Ignore messages that are not commands
            return
            
        # Parse command and arguments
        parts = text[1:].split()
        command = parts[0]
        args = parts[1:]
        
        # Run command handler
        response = self.handler.handle_command(chat_id, command, args, username)
        
        # Send reply
        try:
            await bot.send_message(
                chat_id=chat_id, 
                text=response, 
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.info(f"Sent reply to command '{command}' in chat {chat_id}")
        except Exception as err:
            logger.error(f"Failed to send reply to chat {chat_id}: {err}")

    # --- Daemon Mode (Continuous Polling) ---

    def run_polling_daemon(self) -> None:
        """
        Starts a continuous polling loop for bot updates.
        Useful when hosted on a server 24/7.
        """
        if not Config.BOT_TOKEN:
            logger.error("BOT_TOKEN is missing. Cannot start daemon.")
            return

        logger.info("Initializing bot polling daemon...")
        
        # Initialize python-telegram-bot application
        app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
        
        # Register command handlers
        commands_list = [
            "start", "help", "latest", "results", "timetable", 
            "notifications", "highpriority", "status", 
            "subscribe", "unsubscribe", "search"
        ]
        
        # Helper wrapper to map CommandHandler functions into PTB handlers
        async def generic_ptb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message or not update.message.text:
                return
            chat_id = update.message.chat_id
            text = update.message.text.strip()
            username = update.message.from_user.username if update.message.from_user else None
            
            parts = text[1:].split()
            command = parts[0]
            # Strip bot username suffix if present (e.g. /start@mgu_notifier_bot)
            if "@" in command:
                command = command.split("@")[0]
            args = parts[1:]
            
            response = self.handler.handle_command(chat_id, command, args, username)
            await update.message.reply_text(
                response, 
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        for cmd in commands_list:
            app.add_handler(TelegramCommandHandler(cmd, generic_ptb_handler))
            
        # Fallback handler for unknown commands/messages
        async def unknown_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message and update.message.text:
                await update.message.reply_text(
                    "Command not recognized. Type /help to see available commands."
                )

        app.add_handler(MessageHandler(TelegramFilters.TEXT & (~TelegramFilters.COMMAND), unknown_message_handler))
        
        # Run standard polling event loop
        logger.info("Starting polling daemon. Press Ctrl+C to exit.")
        app.run_polling()
