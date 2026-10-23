"""Генерация периодов (PaymentOccurrence) для регулярных платежей.

Правила из кейса:
- у каждого периода своя дата и своя отметка «Оплачено / Не оплачено»;
- новый период не стирает прошлые оплаты;
- просрочка не останавливает следующие периоды;
- нет такого числа в месяце → последний день месяца.
"""

from datetime import date

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.timeutils import add_months, today

logger = get_logger(__name__)

# Предохранитель от бесконечного цикла (100 лет помесячно)
MAX_PERIODS = 1200


def due_dates(rp: RecurringPayment):
    """Бесконечный генератор дат оплаты платежа."""
    k = 0
    while k < MAX_PERIODS:
        yield add_months(rp.first_due_date, k * rp.months_step, rp.anchor_day)
        k += 1


def ensure_occurrences(rp: RecurringPayment, on: date | None = None) -> list[PaymentOccurrence]:
    """Досоздаёт недостающие периоды платежа.

    Генерируем все периоды от первой даты до «текущего» — первого неоплаченного
    периода со сроком сегодня или позже. Если текущий уже оплачен заранее,
    сразу появляется следующий (так в демо видно «следующий период»).
    Прошлые периоды создаются независимо от того, оплачены ли они.
    Возвращает список созданных периодов. Коммит делает вызывающий код.
    """
    if not rp.is_active:
        return []

    on = on or today()
    if rp.id is None:
        db.session.flush()
    existing = {
        o.due_date: o
        for o in PaymentOccurrence.query.filter_by(recurring_payment_id=rp.id).all()
    }
    created = []

    for due in due_dates(rp):
        occ = existing.get(due)
        if occ is None:
            occ = _create_occurrence(rp, due)
            if occ is not None:
                created.append(occ)
            else:  # параллельно создал другой процесс — берём его запись
                occ = PaymentOccurrence.query.filter_by(
                    recurring_payment_id=rp.id, due_date=due
                ).one()
            existing[due] = occ

        if due >= on and occ.status == STATUS_UNPAID:
            break

    if created:
        db.session.expire(rp, ["occurrences"])
        logger.info(
            f"Платёж #{rp.id} «{rp.name}»: создано периодов {len(created)} "
            f"({created[0].due_date} … {created[-1].due_date})"
        )
    return created


def _create_occurrence(rp: RecurringPayment, due: date) -> PaymentOccurrence | None:
    """Создаёт период в savepoint: дубль (unique-constraint) не ломает транзакцию."""
    occ = PaymentOccurrence(recurring_payment_id=rp.id, due_date=due, status=STATUS_UNPAID)
    try:
        with db.session.begin_nested():
            db.session.add(occ)
        return occ
    except IntegrityError:
        logger.warning(f"Период {due} для платежа #{rp.id} уже создан другим процессом")
        return None


def ensure_all_occurrences(on: date | None = None) -> int:
    """Досоздаёт периоды для всех активных платежей. Возвращает число новых."""
    total = 0
    for rp in RecurringPayment.query.filter_by(is_active=True).all():
        total += len(ensure_occurrences(rp, on))
    if total:
        db.session.commit()
    return total
