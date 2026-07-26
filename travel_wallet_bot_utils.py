"""Меню, баланс, история расходов и вспомогательные обработчики."""

from __future__ import annotations

import logging
from datetime import datetime

import sqlite3

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

logger = logging.getLogger(__name__)

# Тексты кнопок главного меню.
BTN_CREATE_TRIP = "🌍 Создать путешествие"
BTN_MY_TRIPS = "🧳 Мои путешествия"
BTN_BALANCE = "💰 Баланс"
BTN_HISTORY = "📊 История расходов"
BTN_CHANGE_RATE = "⚙ Изменить курс"
BTN_MAIN_MENU = "◀️ Главное меню"
BTN_ADD_EXPENSE = "➖ Записать расход"

# Состояния диалогов.
CHANGE_RATE, EXPENSE_AMOUNT, EXPENSE_DESCRIPTION = range(100, 103)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""
    keyboard = [
        [BTN_CREATE_TRIP, BTN_MY_TRIPS],
        [BTN_BALANCE, BTN_HISTORY],
        [BTN_CHANGE_RATE],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_balance_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для экрана баланса."""
    keyboard = [
        [BTN_ADD_EXPENSE],
        [BTN_MAIN_MENU],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start — регистрация и главное меню."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    db: TravelWalletDB = context.bot_data["db"]
    db.ensure_user(user.id)

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "✈️ *Travel Wallet Bot* — ваш помощник для управления "
        "бюджетом в путешествии.\n\n"
        "Создайте путешествие, следите за балансом в двух валютах "
        "и записывайте расходы.\n\n"
        "Выберите действие в меню 👇",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    if not update.message:
        return

    await update.message.reply_text(
        "📖 *Справка*\n\n"
        f"{BTN_CREATE_TRIP} — пошаговое создание поездки\n"
        f"{BTN_MY_TRIPS} — список и переключение поездок\n"
        f"{BTN_BALANCE} — текущий баланс и запись расхода\n"
        f"{BTN_HISTORY} — история транзакций\n"
        f"{BTN_CHANGE_RATE} — ручное изменение курса\n\n"
        "Команды: /start, /help, /cancel",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


def require_active_trip(user_id: int, db: TravelWalletDB) -> sqlite3.Row | None:
    """Возвращает активное путешествие или None."""
    return db.get_active_trip(user_id)


async def show_my_trips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список путешествий пользователя."""
    if not update.effective_user or not update.message:
        return

    db: TravelWalletDB = context.bot_data["db"]
    currency: CurrencyManager = context.bot_data["currency"]
    user_id = update.effective_user.id

    trips = db.get_user_trips(user_id)
    if not trips:
        await update.message.reply_text(
            "🧳 У вас пока нет путешествий.\n"
            f"Нажмите «{BTN_CREATE_TRIP}», чтобы создать первое.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    lines = ["🧳 *Ваши путешествия:*\n"]
    for trip in trips:
        active_mark = " ✅" if trip["is_active"] else ""
        home_fmt = currency.format_amount(trip["home_balance"], trip["home_currency"])
        dest_fmt = currency.format_amount(
            trip["destination_balance"], trip["destination_currency"]
        )
        lines.append(
            f"*{trip['id']}.* {trip['name']}{active_mark}\n"
            f"   💰 {home_fmt} | {dest_fmt}\n"
        )

    lines.append(
        "\nЧтобы активировать путешествие, отправьте его номер (ID)."
    )

    context.user_data["awaiting_trip_switch"] = True
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


async def handle_trip_switch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключает активное путешествие по ID."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    if not context.user_data.pop("awaiting_trip_switch", False):
        return

    text = update.message.text.strip()
    if not text.isdigit():
        return

    db: TravelWalletDB = context.bot_data["db"]
    user_id = update.effective_user.id
    trip_id = int(text)

    if db.activate_trip(user_id, trip_id):
        trip = db.get_trip(trip_id)
        await update.message.reply_text(
            f"✅ Активное путешествие: *{trip['name']}*",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "❌ Путешествие не найдено. Проверьте ID в списке.",
            reply_markup=get_main_menu_keyboard(),
        )


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает баланс активного путешествия в обеих валютах."""
    if not update.effective_user or not update.message:
        return

    db: TravelWalletDB = context.bot_data["db"]
    currency: CurrencyManager = context.bot_data["currency"]
    user_id = update.effective_user.id

    trip = require_active_trip(user_id, db)
    if not trip:
        await update.message.reply_text(
            "⚠️ Нет активного путешествия.\n"
            f"Создайте его через «{BTN_CREATE_TRIP}» "
            f"или выберите в «{BTN_MY_TRIPS}».",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    home_fmt = currency.format_amount(trip["home_balance"], trip["home_currency"])
    dest_fmt = currency.format_amount(
        trip["destination_balance"], trip["destination_currency"]
    )

    await update.message.reply_text(
        f"💰 *Баланс: {trip['name']}*\n\n"
        f"🏠 Домашняя валюта ({trip['home_currency']}):\n"
        f"   *{home_fmt}*\n\n"
        f"✈️ Валюта путешествия ({trip['destination_currency']}):\n"
        f"   *{dest_fmt}*\n\n"
        f"📈 Курс: `1 {trip['home_currency']} = "
        f"{trip['exchange_rate']:.4f} {trip['destination_currency']}`\n\n"
        f"Нажмите «{BTN_ADD_EXPENSE}», чтобы записать расход.",
        parse_mode="Markdown",
        reply_markup=get_balance_keyboard(),
    )


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает историю расходов активного путешествия."""
    if not update.effective_user or not update.message:
        return

    db: TravelWalletDB = context.bot_data["db"]
    currency: CurrencyManager = context.bot_data["currency"]
    user_id = update.effective_user.id

    trip = require_active_trip(user_id, db)
    if not trip:
        await update.message.reply_text(
            "⚠️ Нет активного путешествия.\n"
            f"Создайте его через «{BTN_CREATE_TRIP}».",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    transactions = db.get_trip_transactions(trip["id"], limit=20)
    if not transactions:
        await update.message.reply_text(
            f"📊 История расходов: *{trip['name']}*\n\n"
            "Пока нет записей.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    lines = [f"📊 *История: {trip['name']}*\n"]
    for tx in transactions:
        created = _format_datetime(tx["created_at"])
        amount_fmt = currency.format_amount(abs(tx["amount"]), tx["currency"])
        sign = "➕" if tx["amount"] >= 0 else "➖"
        desc = tx["description"] or "—"
        lines.append(f"{sign} {amount_fmt} — {desc}\n   _{created}_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


def _format_datetime(iso_str: str) -> str:
    """Форматирует ISO-дату для отображения."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso_str


class ChangeRateHandler:
    """Обработчик изменения курса обмена."""

    def __init__(self, db: TravelWalletDB, currency_manager: CurrencyManager) -> None:
        self.db = db
        self.currency = currency_manager

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает диалог изменения курса."""
        if not update.effective_user or not update.message:
            return ConversationHandler.END

        trip = require_active_trip(update.effective_user.id, self.db)
        if not trip:
            await update.message.reply_text(
                "⚠️ Нет активного путешествия.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        context.user_data["change_rate_trip_id"] = trip["id"]
        await update.message.reply_text(
            f"⚙ *Изменение курса: {trip['name']}*\n\n"
            f"Текущий курс:\n"
            f"`1 {trip['home_currency']} = "
            f"{trip['exchange_rate']:.4f} {trip['destination_currency']}`\n\n"
            f"Введите новый курс "
            f"(сколько {trip['destination_currency']} за 1 {trip['home_currency']}):\n\n"
            "Например: `0.0785`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[BTN_MAIN_MENU]], resize_keyboard=True
            ),
        )
        return CHANGE_RATE

    async def receive_rate(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает новый курс и пересчитывает баланс."""
        if not update.message or not update.message.text:
            return CHANGE_RATE

        text = update.message.text.replace(",", ".").strip()
        try:
            new_rate = float(text)
            if new_rate <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введите корректный положительный курс.\n"
                "Например: `0.0785`",
                parse_mode="Markdown",
            )
            return CHANGE_RATE

        trip_id = context.user_data.get("change_rate_trip_id")
        if not trip_id:
            await update.message.reply_text(
                "⚠️ Сессия сброшена.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        trip = self.db.get_trip(int(trip_id))
        if not trip:
            await update.message.reply_text(
                "⚠️ Путешествие не найдено.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        # Пересчитываем destination_balance по новому курсу.
        new_dest_balance = trip["home_balance"] * new_rate
        self.db.update_exchange_rate(int(trip_id), new_rate)
        self.db.update_balances(int(trip_id), trip["home_balance"], new_dest_balance)

        dest_fmt = self.currency.format_amount(
            new_dest_balance, trip["destination_currency"]
        )

        await update.message.reply_text(
            f"✅ Курс обновлён!\n\n"
            f"`1 {trip['home_currency']} = {new_rate:.4f} "
            f"{trip['destination_currency']}`\n\n"
            f"💰 Баланс в валюте путешествия: *{dest_fmt}*",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
        context.user_data.pop("change_rate_trip_id", None)
        return ConversationHandler.END

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет изменение курса."""
        context.user_data.pop("change_rate_trip_id", None)
        if update.message:
            await update.message.reply_text(
                "Изменение курса отменено.",
                reply_markup=get_main_menu_keyboard(),
            )
        return ConversationHandler.END


class ExpenseHandler:
    """Обработчик записи расходов."""

    def __init__(self, db: TravelWalletDB, currency_manager: CurrencyManager) -> None:
        self.db = db
        self.currency = currency_manager

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Начинает запись расхода."""
        if not update.effective_user or not update.message:
            return ConversationHandler.END

        trip = require_active_trip(update.effective_user.id, self.db)
        if not trip:
            await update.message.reply_text(
                "⚠️ Нет активного путешествия.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        context.user_data["expense_trip_id"] = trip["id"]
        await update.message.reply_text(
            f"➖ *Запись расхода: {trip['name']}*\n\n"
            f"Введите сумму расхода в *{trip['destination_currency']}* "
            f"(валюта путешествия).\n\n"
            "Например: `1500`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[BTN_MAIN_MENU]], resize_keyboard=True
            ),
        )
        return EXPENSE_AMOUNT

    async def receive_amount(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает сумму расхода."""
        if not update.message or not update.message.text:
            return EXPENSE_AMOUNT

        text = update.message.text.replace(",", ".").replace(" ", "")
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Введите корректную положительную сумму.",
                parse_mode="Markdown",
            )
            return EXPENSE_AMOUNT

        context.user_data["expense_amount"] = amount
        await update.message.reply_text(
            "📝 Введите описание расхода.\n\n"
            "Например: `Обед в ресторане`",
            parse_mode="Markdown",
        )
        return EXPENSE_DESCRIPTION

    async def receive_description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Принимает описание и сохраняет расход."""
        if not update.message or not update.message.text:
            return EXPENSE_DESCRIPTION

        trip_id = context.user_data.get("expense_trip_id")
        amount = context.user_data.get("expense_amount")
        if not trip_id or amount is None:
            await update.message.reply_text(
                "⚠️ Сессия сброшена.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        trip = self.db.get_trip(int(trip_id))
        if not trip:
            await update.message.reply_text(
                "⚠️ Путешествие не найдено.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        description = update.message.text.strip()
        dest_currency = trip["destination_currency"]
        home_currency = trip["home_currency"]
        exchange_rate = trip["exchange_rate"]

        # Списываем из обоих балансов.
        new_dest_balance = trip["destination_balance"] - amount
        home_deduction = self.currency.convert_destination_to_home(amount, exchange_rate)
        new_home_balance = trip["home_balance"] - home_deduction

        self.db.update_balances(int(trip_id), new_home_balance, new_dest_balance)
        self.db.add_transaction(
            trip_id=int(trip_id),
            amount=-amount,
            currency=dest_currency,
            description=description,
        )

        dest_fmt = self.currency.format_amount(amount, dest_currency)
        home_fmt = self.currency.format_amount(home_deduction, home_currency)
        new_home_fmt = self.currency.format_amount(new_home_balance, home_currency)
        new_dest_fmt = self.currency.format_amount(new_dest_balance, dest_currency)

        await update.message.reply_text(
            f"✅ Расход записан!\n\n"
            f"➖ {dest_fmt} ({home_fmt})\n"
            f"📝 {description}\n\n"
            f"💰 Остаток:\n"
            f"• {new_home_fmt}\n"
            f"• {new_dest_fmt}",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )

        context.user_data.pop("expense_trip_id", None)
        context.user_data.pop("expense_amount", None)
        return ConversationHandler.END

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменяет запись расхода."""
        context.user_data.pop("expense_trip_id", None)
        context.user_data.pop("expense_amount", None)
        if update.message:
            await update.message.reply_text(
                "Запись расхода отменена.",
                reply_markup=get_main_menu_keyboard(),
            )
        return ConversationHandler.END


def build_change_rate_handler(
    db: TravelWalletDB,
    currency_manager: CurrencyManager,
) -> ConversationHandler:
    """Создаёт ConversationHandler для изменения курса."""
    handler = ChangeRateHandler(db, currency_manager)
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{BTN_CHANGE_RATE}$"), handler.start),
        ],
        states={
            CHANGE_RATE: [
                MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.receive_rate),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handler.cancel),
            MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel),
        ],
        allow_reentry=True,
    )


def build_expense_handler(
    db: TravelWalletDB,
    currency_manager: CurrencyManager,
) -> ConversationHandler:
    """Создаёт ConversationHandler для записи расходов."""
    handler = ExpenseHandler(db, currency_manager)
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{BTN_ADD_EXPENSE}$"), handler.start),
        ],
        states={
            EXPENSE_AMOUNT: [
                MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.receive_amount),
            ],
            EXPENSE_DESCRIPTION: [
                MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.receive_description
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handler.cancel),
            MessageHandler(filters.Regex(f"^{BTN_MAIN_MENU}$"), handler.cancel),
        ],
        allow_reentry=True,
    )
