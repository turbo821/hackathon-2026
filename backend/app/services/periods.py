"""Генерация периодов (PaymentOccurrence) — ЗАГЛУШКА этапа «каркас».

Контракт зафиксирован, реализация — следующий этап. Что здесь должно быть
(правила из кейса):

- у каждого периода своя дата и своя отметка «Оплачено / Не оплачено»;
- новый период не стирает прошлые оплаты;
- просрочка не останавливает следующие периоды;
- нет такого числа в месяце → последний день месяца (см. app.timeutils.add_months);
- период создаётся только для активного платежа.

Период — самостоятельная запись: name, amount и currency копируются из шаблона
(слепок), payment_ended_at = None. Благодаря этому список периодов читается
по одной таблице, без JOIN с recurring_payments.

Пока реализация не готова, функции ничего не создают: списки платежей
приходят пустыми, а тесты на периоды помечены как ожидающие
(tests/test_domain_logic.py).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment

logger = get_logger(__name__)

# Предохранитель от бесконечного цикла (100 лет помесячно)
MAX_PERIODS = 1200


def due_dates(rp: RecurringPayment):
    """Генератор дат оплаты платежа."""
    # TODO(каркас → реализация): отдавать даты по правилам выше.
    return iter(())


def ensure_occurrences(db: Session, rp: RecurringPayment, on: date | None = None) -> list[PaymentOccurrence]:
    """Досоздаёт недостающие периоды платежа.

    Каждый период копирует поля шаблона (name, amount, currency) и получает
    payment_ended_at = None. Возвращает список созданных периодов;
    коммит делает вызывающий код.
    """
    # TODO(каркас → реализация): создать PaymentOccurrence для всех дат
    # от first_due_date до первого неоплаченного периода со сроком сегодня или позже.
    logger.debug(f"periods.ensure_occurrences: заглушка, платёж #{getattr(rp, 'id', None)}")
    return []


def ensure_all_occurrences(db: Session, on: date | None = None) -> int:
    """Досоздаёт периоды для всех активных платежей. Возвращает число новых."""
    # TODO(каркас → реализация): обойти активные платежи и вызвать ensure_occurrences.
    return 0
