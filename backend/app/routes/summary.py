from decimal import Decimal

from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy.orm import joinedload

from app.auth import login_required
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_PAID
from app.models.recurring_payment import CURRENCIES
from app.schemas.payments import SummaryQuerySchema, SummarySchema
from app.services.periods import ensure_all_occurrences
from app.timeutils import today

router = Blueprint(
    "summary",
    __name__,
    url_prefix="/api/v1/payments",
    description="Итоги по валютам (без конвертации)",
)


@router.route("/summary")
class Summary(MethodView):
    @login_required
    @router.arguments(SummaryQuerySchema, location="query")
    @router.response(200, SummarySchema)
    def get(self, args):
        """Получение итоговых сумм платежей по валютам

        Суммы считаются отдельно по каждой валюте (RUB, USD, EUR), конвертации нет.
        Период фильтруется по сроку оплаты (`date_from` / `date_to`);
        `on_date` — дата, на которую определяется просрочка (по умолчанию сегодня).
        """
        on = args.get("on_date") or today()
        ensure_all_occurrences(today())

        query = PaymentOccurrence.query.join(RecurringPayment).options(
            joinedload(PaymentOccurrence.recurring_payment)
        )
        if args.get("date_from"):
            query = query.filter(PaymentOccurrence.due_date >= args["date_from"])
        if args.get("date_to"):
            query = query.filter(PaymentOccurrence.due_date <= args["date_to"])

        zero = Decimal("0.00")
        totals = {
            cur: {
                "currency": cur,
                "total": zero, "paid": zero, "unpaid": zero, "overdue": zero,
                "count_total": 0, "count_paid": 0, "count_unpaid": 0, "count_overdue": 0,
            }
            for cur in CURRENCIES
        }

        for occ in query.all():
            rp = occ.recurring_payment
            t = totals[rp.currency]
            t["total"] += rp.amount
            t["count_total"] += 1
            # Статус «на дату»: оплата после on_date считается ещё не сделанной
            paid_on_date = occ.status == STATUS_PAID and (occ.paid_at is None or occ.paid_at <= on)
            if paid_on_date:
                t["paid"] += rp.amount
                t["count_paid"] += 1
            else:
                t["unpaid"] += rp.amount
                t["count_unpaid"] += 1
                if on > occ.due_date:
                    t["overdue"] += rp.amount
                    t["count_overdue"] += 1

        return {
            "date_from": args.get("date_from"),
            "date_to": args.get("date_to"),
            "on_date": on,
            "currencies": list(totals.values()),
        }
