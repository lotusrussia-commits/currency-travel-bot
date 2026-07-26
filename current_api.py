"""Модуль для получения курсов валют через внешнее API.

Все HTTP-запросы к API курсов валют выполняются только через этот модуль.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Бесплатное API без ключа (поддерживает RUB, CNY и др.).
API_BASE_URL = "https://open.er-api.com/v6/latest"
REQUEST_TIMEOUT = 10


@dataclass
class ExchangeRateResult:
    """Результат запроса курса валют."""

    success: bool
    rate: float | None = None
    from_currency: str | None = None
    to_currency: str | None = None
    error_message: str | None = None


class CurrentAPI:
    """Клиент для получения актуальных курсов валют."""

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = REQUEST_TIMEOUT) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> ExchangeRateResult:
        """
        Получает курс обмена from_currency -> to_currency.

        При недоступности API возвращает ExchangeRateResult с success=False
        без выброса исключений.
        """
        from_currency = from_currency.upper().strip()
        to_currency = to_currency.upper().strip()

        if from_currency == to_currency:
            return ExchangeRateResult(
                success=True,
                rate=1.0,
                from_currency=from_currency,
                to_currency=to_currency,
            )

        try:
            response = requests.get(
                f"{self.base_url}/{from_currency}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("result") != "success":
                return ExchangeRateResult(
                    success=False,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    error_message="Сервис курсов валют вернул ошибку.",
                )

            rates = data.get("rates", {})
            rate = rates.get(to_currency)
            if rate is None:
                return ExchangeRateResult(
                    success=False,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    error_message=(
                        f"Курс {from_currency} → {to_currency} не найден в ответе API."
                    ),
                )

            return ExchangeRateResult(
                success=True,
                rate=float(rate),
                from_currency=from_currency,
                to_currency=to_currency,
            )

        except requests.Timeout:
            logger.warning(
                "Таймаут при запросе курса %s -> %s", from_currency, to_currency
            )
            return ExchangeRateResult(
                success=False,
                from_currency=from_currency,
                to_currency=to_currency,
                error_message=(
                    "Сервис курсов валют не отвечает. Попробуйте позже "
                    "или задайте курс вручную через «⚙ Изменить курс»."
                ),
            )
        except requests.RequestException as exc:
            logger.warning("Ошибка API курсов валют: %s", exc)
            return ExchangeRateResult(
                success=False,
                from_currency=from_currency,
                to_currency=to_currency,
                error_message=(
                    "Не удалось получить курс валют. Проверьте интернет "
                    "или задайте курс вручную через «⚙ Изменить курс»."
                ),
            )
        except (ValueError, KeyError) as exc:
            logger.warning("Некорректный ответ API: %s", exc)
            return ExchangeRateResult(
                success=False,
                from_currency=from_currency,
                to_currency=to_currency,
                error_message="Получен некорректный ответ от сервиса курсов валют.",
            )


# Глобальный экземпляр для использования в проекте.
current_api = CurrentAPI()
