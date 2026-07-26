"""Модуль управления валютами и конвертацией."""

from __future__ import annotations

from dataclasses import dataclass

from current_api import ExchangeRateResult, current_api
from database import TravelWalletDB


@dataclass
class CountryCurrencyInfo:
    """Информация о стране и её валюте."""

    country: str
    currency: str
    currency_name: str


@dataclass
class ConversionResult:
    """Результат конвертации суммы между валютами."""

    home_amount: float
    destination_amount: float
    exchange_rate: float


class CurrencyManager:
    """Менеджер валют: справочник стран и конвертация."""

    def __init__(self, db: TravelWalletDB) -> None:
        self.db = db

    @staticmethod
    def normalize_country_name(country: str) -> str:
        """
        Приводит название страны к единому формату.

        Примеры:
        латвия -> Латвия
        ЛАТВИЯ -> Латвия
        латвия   -> Латвия
        """
        return country.strip().capitalize()

    def resolve_country(self, country_input: str) -> CountryCurrencyInfo | None:
        """
        Определяет валюту по названию страны.

        Поддерживает:
        - полный ввод: Латвия
        - маленькие буквы: латвия
        - большие буквы: ЛАТВИЯ
        - частичное совпадение: латв
        """

        query = self.normalize_country_name(country_input)

        if not query:
            return None

        # Сначала пробуем точное совпадение
        row = self.db.get_currency_by_country(query)

        if row:
            return CountryCurrencyInfo(
                country=row["country"],
                currency=row["currency"],
                currency_name=row["currency_name"],
            )

        # Если точного совпадения нет,
        # ищем по части названия
        query_lower = query.lower()

        for country_row in self.db.get_all_countries():
            country_name = country_row["country"].lower()

            if query_lower in country_name:
                return CountryCurrencyInfo(
                    country=country_row["country"],
                    currency=country_row["currency"],
                    currency_name=country_row["currency_name"],
                )

        return None

    def fetch_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
    ) -> ExchangeRateResult:
        """Получает курс валют через API."""
        return current_api.get_exchange_rate(
            from_currency,
            to_currency,
        )

    def convert_home_to_destination(
        self,
        home_amount: float,
        exchange_rate: float,
    ) -> ConversionResult:
        """
        Конвертирует сумму из домашней валюты
        в валюту путешествия.
        """

        destination_amount = home_amount * exchange_rate

        return ConversionResult(
            home_amount=home_amount,
            destination_amount=destination_amount,
            exchange_rate=exchange_rate,
        )

    def convert_destination_to_home(
        self,
        destination_amount: float,
        exchange_rate: float,
    ) -> float:
        """
        Конвертирует сумму из валюты путешествия
        в домашнюю валюту.
        """

        if exchange_rate == 0:
            return 0.0

        return destination_amount / exchange_rate

    @staticmethod
    def format_amount(
        amount: float,
        currency: str,
    ) -> str:
        """Форматирует сумму для отображения пользователю."""

        if currency in (
            "JPY",
            "KRW",
            "VND",
            "IDR",
            "UZS",
        ):
            return f"{amount:,.0f} {currency}".replace(",", " ")

        return f"{amount:,.2f} {currency}".replace(",", " ")