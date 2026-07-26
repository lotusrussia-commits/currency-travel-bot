"""Обработчики создания путешествия (ConversationHandler)."""

from __future__ import annotations

import logging

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from currency_manager import CurrencyManager
from database import TravelWalletDB
from travel_wallet_bot_utils import (
    BTN_CREATE_TRIP,
    BTN_MAIN_MENU,
    get_main_menu_keyboard,
)

logger = logging.getLogger(__name__)

# Состояния диалога создания путешествия.
HOME_COUNTRY, DESTINATION_COUNTRY, INITIAL_AMOUNT = range(3)


class TripCreationHandler:
    """Класс с обработчиками пошагового создания путешествия."""

    def __init__(self, db: TravelWalletDB, currency_manager: CurrencyManager) -> None:
        self.db = db
        self.currency = currency_manager

    async def start_creation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает диалог создания путешествия."""
        if not update.effective_user or not update.message:
            return ConversationHandler.END

        user_id = update.effective_user.id
        self.db.ensure_user(user_id)
        context.user_data.clear()

        await update.message.reply_text(
            "🌍 *Создание путешествия*\n\n"
            "Шаг 1 из 3\n"
            "Введите *страну отправления*.\n\n"
            "Например: `Россия`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[BTN_MAIN_MENU]], resize_keyboard=True
            ),
        )
        return HOME_COUNTRY

    async def receive_home_country(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает страну отправления и определяет домашнюю валюту."""
        if not update.message or not update.message.text:
            return HOME_COUNTRY

        country_info = self.currency.resolve_country(update.message.text)
        if not country_info:
            await update.message.reply_text(
                "❌ Страна не найдена в справочнике.\n"
                "Попробуйте ещё раз, например: `Россия`, `США`, `Германия`.",
                parse_mode="Markdown",
            )
            return HOME_COUNTRY

        context.user_data["home_country"] = country_info.country
        context.user_data["home_currency"] = country_info.currency

        await update.message.reply_text(
            f"✅ Страна отправления: *{country_info.country}*\n"
            f"💱 Валюта: *{country_info.currency}* — {country_info.currency_name}\n\n"
            "Шаг 2 из 3\n"
            "Введите *страну назначения*.\n\n"
            "Например: `Китай`",
            parse_mode="Markdown",
        )
        return DESTINATION_COUNTRY

    async def receive_destination_country(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает страну назначения, определяет валюту и запрашивает курс."""
        if not update.message or not update.message.text:
            return DESTINATION_COUNTRY

        country_info = self.currency.resolve_country(update.message.text)
        if not country_info:
            await update.message.reply_text(
                "❌ Страна не найдена в справочнике.\n"
                "Попробуйте ещё раз, например: `Китай`, `Япония`, `Турция`.",
                parse_mode="Markdown",
            )
            return DESTINATION_COUNTRY

        home_currency = context.user_data.get("home_currency")
        if not home_currency:
            await update.message.reply_text(
                "⚠️ Сессия создания сброшена. Начните заново через меню."
            )
            return ConversationHandler.END

        context.user_data["destination_country"] = country_info.country
        context.user_data["destination_currency"] = country_info.currency

        rate_result = self.currency.fetch_exchange_rate(
            home_currency, country_info.currency
        )

        if not rate_result.success or rate_result.rate is None:
            await update.message.reply_text(
                f"✅ Страна назначения: *{country_info.country}*\n"
                f"💱 Валюта: *{country_info.currency}* — {country_info.currency_name}\n\n"
                f"⚠️ {rate_result.error_message}\n\n"
                "Создание путешествия прервано. Попробуйте позже.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
            context.user_data.clear()
            return ConversationHandler.END

        context.user_data["exchange_rate"] = rate_result.rate

        await update.message.reply_text(
            f"✅ Страна назначения: *{country_info.country}*\n"
            f"💱 Валюта: *{country_info.currency}* — {country_info.currency_name}\n\n"
            f"📈 Актуальный курс:\n"
            f"`1 {home_currency} = {rate_result.rate:.4f} {country_info.currency}`\n\n"
            "Шаг 3 из 3\n"
            f"Введите *начальную сумму* в {home_currency}.\n\n"
            "Например: `150000`",
            parse_mode="Markdown",
        )
        return INITIAL_AMOUNT

    async def receive_initial_amount(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает начальную сумму, конвертирует и сохраняет путешествие."""
        if not update.effective_user or not update.message or not update.message.text:
            return INITIAL_AMOUNT

        text = update.message.text.replace(",", ".").replace(" ", "")
        try:
            home_amount = float(text)
            if home_amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введите корректную положительную сумму.\n"
                "Например: `150000` или `150000.50`",
                parse_mode="Markdown",
            )
            return INITIAL_AMOUNT

        home_country = context.user_data.get("home_country")
        home_currency = context.user_data.get("home_currency")
        destination_country = context.user_data.get("destination_country")
        destination_currency = context.user_data.get("destination_currency")
        exchange_rate = context.user_data.get("exchange_rate")

        if not all(
            [
                home_country,
                home_currency,
                destination_country,
                destination_currency,
                exchange_rate,
            ]
        ):
            await update.message.reply_text(
                "⚠️ Сессия создания сброшена. Начните заново через меню.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        conversion = self.currency.convert_home_to_destination(
            home_amount, float(exchange_rate)
        )

        trip_name = f"{home_country} → {destination_country}"
        user_id = update.effective_user.id

        trip_id = self.db.create_trip(
            user_id=user_id,
            name=trip_name,
            home_country=str(home_country),
            home_currency=str(home_currency),
            destination_country=str(destination_country),
            destination_currency=str(destination_currency),
            exchange_rate=float(exchange_rate),
            home_balance=conversion.home_amount,
            destination_balance=conversion.destination_amount,
        )

        # Записываем начальный депозит в историю.
        self.db.add_transaction(
            trip_id=trip_id,
            amount=conversion.home_amount,
            currency=str(home_currency),
            description="Начальный баланс",
        )

        home_fmt = self.currency.format_amount(conversion.home_amount, str(home_currency))
        dest_fmt = self.currency.format_amount(
            conversion.destination_amount, str(destination_currency)
        )

        await update.message.reply_text(
            f"🎉 *Путешествие создано!*\n\n"
            f"🧳 {trip_name}\n"
            f"📈 Курс: `1 {home_currency} = {exchange_rate:.4f} {destination_currency}`\n\n"
            f"💰 Баланс:\n"
            f"• {home_fmt}\n"
            f"• {dest_fmt}\n\n"
            "Используйте меню для управления бюджетом.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )

        context.user_data.clear()
        logger.info("Trip %s created for user %s", trip_id, user_id)
        return ConversationHandler.END

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет создание путешествия."""
        context.user_data.clear()
        if update.message:
            await update.message.reply_text(
                "Создание путешествия отменено.",
                reply_markup=get_main_menu_keyboard(),
            )
        return ConversationHandler.END


def build_trip_creation_handler(
    db: TravelWalletDB,
    currency_manager: CurrencyManager,
) -> ConversationHandler:
    """Создаёт ConversationHandler для пошагового создания путешествия."""
    handler = TripCreationHandler(db, currency_manager)

    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{BTN_CREATE_TRIP}$"), handler.start_creation),
        ],
        states={
            HOME_COUNTRY: [
                MessageHandler(
                    filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.receive_home_country),
            ],
            DESTINATION_COUNTRY: [
                MessageHandler(
                    filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.receive_destination_country
                ),
            ],
            INITIAL_AMOUNT: [
                MessageHandler(
                    filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.receive_initial_amount
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handler.cancel),
            MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel),
        ],
        allow_reentry=True,
    )
