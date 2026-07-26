"""Модуль работы с SQLite-базой данных Travel Wallet Bot."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    """Возвращает текущее время в формате ISO UTC."""
    return datetime.now(timezone.utc).isoformat()


# Справочник стран и валют (заполняется при первом запуске).
COUNTRIES_CURRENCIES: list[tuple[str, str, str]] = [
    ("Россия", "RUB", "Российский рубль"),
    ("США", "USD", "Доллар США"),
    ("Китай", "CNY", "Китайский юань"),
    ("Япония", "JPY", "Японская иена"),
    ("Германия", "EUR", "Евро"),
    ("Франция", "EUR", "Евро"),
    ("Италия", "EUR", "Евро"),
    ("Испания", "EUR", "Евро"),
    ("Польша", "PLN", "Польский злотый"),
    ("Чехия", "CZK", "Чешская крона"),
    ("Великобритания", "GBP", "Фунт стерлингов"),
    ("Швейцария", "CHF", "Швейцарский франк"),
    ("Турция", "TRY", "Турецкая лира"),
    ("Канада", "CAD", "Канадский доллар"),
    ("Австралия", "AUD", "Австралийский доллар"),
    ("Индия", "INR", "Индийская рупия"),
    ("Южная Корея", "KRW", "Южнокорейская вона"),
    ("Таиланд", "THB", "Тайский бат"),
    ("Вьетнам", "VND", "Вьетнамский донг"),
    ("Индонезия", "IDR", "Индонезийская рупия"),
    ("Малайзия", "MYR", "Малайзийский рингgit"),
    ("Сингапур", "SGD", "Сингапурский доллар"),
    ("ОАЭ", "AED", "Дирham ОАЭ"),
    ("Израиль", "ILS", "Израильский шекель"),
    ("Египет", "EGP", "Египетский фунт"),
    ("Марокко", "MAD", "Марокканский дирham"),
    ("ЮАР", "ZAR", "Южноафриканский rand"),
    ("Бразилия", "BRL", "Бразильский реал"),
    ("Аргентина", "ARS", "Аргентинское песо"),
    ("Мексика", "MXN", "Мексиканское песо"),
    ("Норвегия", "NOK", "Норвежская крона"),
    ("Швеция", "SEK", "Шведская крона"),
    ("Дания", "DKK", "Датская крона"),
    ("Финляндия", "EUR", "Евро"),
    ("Нидерланды", "EUR", "Евро"),
    ("Бельгия", "EUR", "Евро"),
    ("Австрия", "EUR", "Евро"),
    ("Португалия", "EUR", "Евро"),
    ("Греция", "EUR", "Евро"),
    ("Ирландия", "EUR", "Евро"),
    ("Украина", "UAH", "Украинская гривна"),
    ("Беларусь", "BYN", "Белорусский рубль"),
    ("Казахстан", "KZT", "Казахстанский тенге"),
    ("Узбекистан", "UZS", "Узбекский сум"),
    ("Грузия", "GEL", "Грузинский лари"),
    ("Армения", "AMD", "Армянский драм"),
    ("Сербия", "RSD", "Сербский динар"),
    ("Хорватия", "EUR", "Евро"),
    ("Венгрия", "HUF", "Венгерский форинт"),
    ("Румыния", "RON", "Румынский лей"),
    ("Болгария", "BGN", "Болгарский лев"),
    ("Исландия", "ISK", "Исландская крона"),
    ("Новая Зеландия", "NZD", "Новозеландский доллар"),
    ("Филиппины", "PHP", "Филиппинское песо"),
    ("Гонконг", "HKD", "Гонконгский доллар"),
    ("Тайвань", "TWD", "Новый тайваньский доллар"),
    ("Саудовская Аравия", "SAR", "Саудовский riyal"),
    ("Кatar", "QAR", "Кatarский riyal"),
    ("Колумбия", "COP", "Колумбийское песо"),
    ("Чили", "CLP", "Чилийское песо"),
    ("Перу", "PEN", "Перuvian sol"),
    ("Латвия", "EUR", "Евро"),
]


class TravelWalletDB:
    """Класс для работы с базой данных бота управления бюджетом путешествий."""

    def __init__(self, db_path: str | Path = "travel_wallet.db") -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Создаёт подключение к SQLite с поддержкой dict-like строк."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Создаёт таблицы и заполняет справочник стран при первом запуске."""
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    active_trip_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (active_trip_id) REFERENCES trips(id)
                );

                CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    home_country TEXT NOT NULL,
                    home_currency TEXT NOT NULL,
                    destination_country TEXT NOT NULL,
                    destination_currency TEXT NOT NULL,
                    exchange_rate REAL NOT NULL,
                    home_balance REAL NOT NULL DEFAULT 0,
                    destination_balance REAL NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (trip_id) REFERENCES trips(id)
                );

                CREATE TABLE IF NOT EXISTS countries_currencies (
                    country TEXT PRIMARY KEY,
                    currency TEXT NOT NULL,
                    currency_name TEXT NOT NULL
                );
                """
            )

            count = conn.execute(
                "SELECT COUNT(*) FROM countries_currencies"
            ).fetchone()[0]
            if count == 0:
                conn.executemany(
                    """
                    INSERT INTO countries_currencies (country, currency, currency_name)
                    VALUES (?, ?, ?)
                    """,
                    COUNTRIES_CURRENCIES,
                )

    # --- Пользователи ---

    def ensure_user(self, user_id: int) -> None:
        """Регистрирует пользователя, если он ещё не существует."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (user_id, active_trip_id, created_at)
                VALUES (?, NULL, ?)
                """,
                (user_id, _utc_now()),
            )

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        """Возвращает данные пользователя."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()

    def set_active_trip(self, user_id: int, trip_id: int | None) -> None:
        """Устанавливает активное путешествие пользователя."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET active_trip_id = ? WHERE user_id = ?",
                (trip_id, user_id),
            )

    # --- Справочник стран ---

    def get_currency_by_country(self, country: str) -> sqlite3.Row | None:
        """Ищет валюту по названию страны (без учёта регистра)."""
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT * FROM countries_currencies
                WHERE LOWER(country) = LOWER(?)
                """,
                (country.strip(),),
            ).fetchone()

    def get_all_countries(self) -> list[sqlite3.Row]:
        """Возвращает список всех стран из справочника."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM countries_currencies ORDER BY country"
            ).fetchall()
            return list(rows)

    # --- Путешествия ---

    def create_trip(
        self,
        user_id: int,
        name: str,
        home_country: str,
        home_currency: str,
        destination_country: str,
        destination_currency: str,
        exchange_rate: float,
        home_balance: float,
        destination_balance: float,
    ) -> int:
        """Создаёт новое путешествие и делает его активным."""
        with self._connect() as conn:
            # Деактивируем предыдущие активные поездки пользователя.
            conn.execute(
                "UPDATE trips SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            cursor = conn.execute(
                """
                INSERT INTO trips (
                    user_id, name, home_country, home_currency,
                    destination_country, destination_currency, exchange_rate,
                    home_balance, destination_balance, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    user_id,
                    name,
                    home_country,
                    home_currency,
                    destination_country,
                    destination_currency,
                    exchange_rate,
                    home_balance,
                    destination_balance,
                    _utc_now(),
                ),
            )
            trip_id = cursor.lastrowid
            conn.execute(
                "UPDATE users SET active_trip_id = ? WHERE user_id = ?",
                (trip_id, user_id),
            )
            return int(trip_id)

    def get_trip(self, trip_id: int) -> sqlite3.Row | None:
        """Возвращает путешествие по ID."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM trips WHERE id = ?",
                (trip_id,),
            ).fetchone()

    def get_active_trip(self, user_id: int) -> sqlite3.Row | None:
        """Возвращает активное путешествие пользователя."""
        user = self.get_user(user_id)
        if not user or user["active_trip_id"] is None:
            return None
        return self.get_trip(int(user["active_trip_id"]))

    def get_user_trips(self, user_id: int) -> list[sqlite3.Row]:
        """Возвращает все путешествия пользователя."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM trips
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
            return list(rows)

    def activate_trip(self, user_id: int, trip_id: int) -> bool:
        """Активирует выбранное путешествие."""
        trip = self.get_trip(trip_id)
        if not trip or trip["user_id"] != user_id:
            return False

        with self._connect() as conn:
            conn.execute(
                "UPDATE trips SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.execute(
                "UPDATE trips SET is_active = 1 WHERE id = ?",
                (trip_id,),
            )
            conn.execute(
                "UPDATE users SET active_trip_id = ? WHERE user_id = ?",
                (trip_id, user_id),
            )
        return True

    def update_exchange_rate(self, trip_id: int, exchange_rate: float) -> None:
        """Обновляет курс обмена для путешествия."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE trips SET exchange_rate = ? WHERE id = ?",
                (exchange_rate, trip_id),
            )

    def update_balances(
        self,
        trip_id: int,
        home_balance: float,
        destination_balance: float,
    ) -> None:
        """Обновляет балансы путешествия."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE trips
                SET home_balance = ?, destination_balance = ?
                WHERE id = ?
                """,
                (home_balance, destination_balance, trip_id),
            )

    # --- Транзакции ---

    def add_transaction(
        self,
        trip_id: int,
        amount: float,
        currency: str,
        description: str = "",
    ) -> int:
        """Добавляет транзакцию и возвращает её ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO transactions (trip_id, amount, currency, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trip_id, amount, currency, description, _utc_now()),
            )
            return int(cursor.lastrowid)

    def get_trip_transactions(
        self,
        trip_id: int,
        limit: int = 20,
    ) -> list[sqlite3.Row]:
        """Возвращает историю транзакций путешествия."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM transactions
                WHERE trip_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (trip_id, limit),
            ).fetchall()
            return list(rows)

    def row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        """Преобразует sqlite3.Row в словарь."""
        if row is None:
            return None
        return dict(row)
