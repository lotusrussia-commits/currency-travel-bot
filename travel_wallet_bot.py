"""
Travel Wallet Bot — точка входа.

Запуск Telegram-бота и регистрация обработчиков.
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from currency_manager import CurrencyManager
from database import TravelWalletDB
from travel_wallet_bot_trip import build_trip_creation_handler
from travel_wallet_bot_utils import (
    BTN_BALANCE,
    BTN_HISTORY,
    BTN_MAIN_MENU,
    BTN_MY_TRIPS,
    build_change_rate_handler,
    build_expense_handler,
    handle_trip_switch,
    help_command,
    show_balance,
    show_history,
    show_my_trips,
    start_command,
)

# Настройка логирования.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_application(token: str, db_path: str = "travel_wallet.db") -> Application:
    """
    Создаёт и настраивает экземпляр Telegram Application.

    Инициализирует базу данных и регистрирует все обработчики.
    """
    db = TravelWalletDB(db_path)
    currency_manager = CurrencyManager(db)

    application = Application.builder().token(token).build()
    application.bot_data["db"] = db
    application.bot_data["currency"] = currency_manager

    # Команды.
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Диалоги (ConversationHandler — регистрировать до общих MessageHandler).
    application.add_handler(build_trip_creation_handler(db, currency_manager))
    application.add_handler(build_change_rate_handler(db, currency_manager))
    application.add_handler(build_expense_handler(db, currency_manager))

    # Кнопки главного меню.
    application.add_handler(
        MessageHandler(filters.Regex(f"^{BTN_MY_TRIPS}$"), show_my_trips)
    )
    application.add_handler(
        MessageHandler(filters.Regex(f"^{BTN_BALANCE}$"), show_balance)
    )
    application.add_handler(
        MessageHandler(filters.Regex(f"^{BTN_HISTORY}$"), show_history)
    )
    application.add_handler(
        MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), start_command)
    )

    # Переключение активного путешествия по ID.
    application.add_handler(
        MessageHandler(filters.Regex(r"^\d+$"), handle_trip_switch)
    )

    return application


def main() -> None:
    """Запуск бота."""
    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("Переменная окружения BOT_TOKEN не задана. См. .env.example")
        sys.exit(1)

    db_path = os.getenv("DB_PATH", "travel_wallet.db")

    logger.info("Запуск Travel Wallet Bot...")
    application = create_application(token, db_path)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
