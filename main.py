import argparse
import asyncio
import sys
from utils.config import Config
from utils.logging import get_logger
from database.db_manager import DBManager
from services.telegram_client import TelegramClient
from bot.bot_manager import BotManager
from scheduler.runner import run_notifiers

logger = get_logger("main")

def parse_args():
    parser = argparse.ArgumentParser(description="MGU AI & ML Examination Notifier Engine")
    parser.add_argument(
        "--mode", 
        choices=["cron", "daemon"], 
        help="Bot execution mode. 'cron' runs scraper once and processes commands. 'daemon' runs a 24/7 bot loop."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Overwrite mode if flag is provided
    if args.mode:
        Config.RUN_MODE = args.mode
        
    logger.info(f"Starting application in '{Config.RUN_MODE}' mode...")
    
    # Validate configuration
    try:
        Config.validate()
    except ValueError as val_err:
        logger.critical(f"Config Validation Error: {val_err}")
        print(f"CRITICAL CONFIG ERROR: {val_err}", file=sys.stderr)
        sys.exit(1)
        
    db = DBManager()
    telegram_client = TelegramClient()
    bot_manager = BotManager(db, telegram_client)
    
    if Config.RUN_MODE == "daemon":
        # Daemon Mode runs persistent polling
        try:
            bot_manager.run_polling_daemon()
        except KeyboardInterrupt:
            logger.info("Daemon execution stopped by user (Ctrl+C).")
        except Exception as e:
            logger.critical(f"Daemon process crashed: {e}")
            sys.exit(1)
    else:
        # Cron Mode runs scraper once
        try:
            asyncio.run(run_notifiers())
        except Exception as e:
            logger.critical(f"Scraper execution failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
