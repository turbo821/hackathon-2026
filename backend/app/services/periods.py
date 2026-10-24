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

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.timeutils import add_months, today

logger = get_logger(__name__)

# Предохранитель от бесконечного цикла (100 лет помесячно)
MAX_PERIODS = 1200


def due_dates(rp: RecurringPayment):
    """Генератор дат оплаты: первая дата и далее с шагом периода."""
    for k in range(MAX_PERIODS):
        yield add_months(rp.first_due_date, k * rp.months_step, rp.anchor_day)


def ensure_occurrences(
    db: Session, rp: RecurringPayment, on: date | None = None
) -> list[PaymentOccurrence]:
    """Досоздаёт недостающие периоды платежа.

    Идём от первой даты и останавливаемся на первом неоплаченном периоде
    со сроком сегодня или позже: прошлые периоды уже созданы и оплачены,
    текущий — ждёт оплаты, а следующий появится, как только текущий закроют.
    """
    if not rp.is_active:
        return []

    on = on or today()
    if rp.id is None:
        db.flush()

    existing = {
        o.due_date: o
        for o in db.scalars(
            select(PaymentOccurrence).where(
                PaymentOccurrence.recurring_payment_id == rp.id
            )
        )
    }

    created = []

    for due in due_dates(rp):
        occ = existing.get(due)
        if occ is None:
            occ = _create_occurrence(db, rp, due)
            if occ is not None:
                created.append(occ)
            else:
                # Параллельно создал другой процесс — забираем его запись
                occ = db.scalars(
                    select(PaymentOccurrence).where(
                        PaymentOccurrence.recurring_payment_id == rp.id,
                        PaymentOccurrence.due_date == due,
                    )
                ).one()
            existing[due] = occ
        if due >= on and occ.status == STATUS_UNPAID:
            break
    if created:
        logger.info(
            f"Платёж #{rp.id} «{rp.name}»: создано периодов {len(created)} "
            f"({created[0].due_date} … {created[-1].due_date})"
        )
    return created

def _create_occurrence(db: Session, rp: RecurringPayment, due: date) -> PaymentOccurrence | None:
    """Создаёт период в savepoint: дубль (unique-constraint) не ломает транзакцию."""
    occ = PaymentOccurrence(
        recurring_payment_id=rp.id,
        name=rp.name,
        amount=rp.amount,
        currency=rp.currency,
        due_date=due,
        status=STATUS_UNPAID,
    )
    try:
        with db.begin_nested():
            db.add(occ)
        return occ
    except IntegrityError:
        logger.warning(f"Период {due} для платежа #{rp.id} уже создан другим процессом")
        return None

def ensure_all_occurrences(db: Session, on: date | None = None) -> int:
    """Досоздаёт периоды для всех активных платежей. Возвращает число новых."""
    # TODO(каркас → реализация): обойти активные платежи и вызвать ensure_occurrences.
    return 0
