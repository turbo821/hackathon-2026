// Вкладка «Фактические платежи»: периоды, фильтры, итоги по валютам.

import { api } from '../api.js';
import { PAYMENT_FILTERS } from '../config.js';
import { $, escapeHtml, onAction, setTableMessage } from '../utils/dom.js';
import { formatDate, formatMoney, todayIso } from '../utils/format.js';
import { showToast } from '../ui/toast.js';

const TBODY = 'payments-table-body';
const COLUMNS = 6;

let currentFilter = 'all';
let requestCounter = 0;

function statusOf(o) {
    switch (o.state) {
        case 'paid':
            return ['status-paid', `Оплачено ${formatDate(o.paid_at)}`];
        case 'paid_late':
            return ['status-late', `Оплачено ${formatDate(o.paid_at)} · опоздание ${o.overdue_days} дн.`];
        case 'overdue':
            return ['status-overdue', `Просрочка ${o.overdue_days} дн.`];
        default:
            return ['status-unpaid', o.days_until_due === 0 ? 'Срок сегодня' : `Через ${o.days_until_due} дн.`];
    }
}

function actionCell(o, maxDate) {
    if (o.status !== 'paid') {
        return `<button class="btn btn-sm" data-action="pay" data-id="${o.id}">Оплатить</button>`;
    }
    return `
        <div class="row-actions">
            <input type="date" class="input-field input-sm" value="${o.paid_at || ''}" max="${maxDate}"
                   title="Фактическая дата оплаты" data-action="paid-date" data-id="${o.id}">
            <button class="btn btn-secondary btn-sm" data-action="unpay" data-id="${o.id}">Отменить</button>
        </div>`;
}

function renderTable(items) {
    if (!items.length) {
        setTableMessage(TBODY, COLUMNS, 'Нет платежей по этому фильтру');
        return;
    }
    const maxDate = todayIso();
    $(TBODY).innerHTML = items.map((o) => {
        const [cls, text] = statusOf(o);
        const ended = o.payment_ended_at ? '<div class="muted">платёж прекращён</div>' : '';
        return `
            <tr>
                <td>${escapeHtml(o.marked_by || '—')}</td>
                <td>${escapeHtml(o.name)}${ended}</td>
                <td>${formatMoney(o.amount, o.currency)}</td>
                <td>${formatDate(o.due_date)}</td>
                <td><span class="status ${cls}">${escapeHtml(text)}</span></td>
                <td>${actionCell(o, maxDate)}</td>
            </tr>`;
    }).join('');
}

function renderSummary(summary) {
    for (const c of summary.currencies) {
        const key = c.currency.toLowerCase();
        const amountEl = $(`sum-${key}`);
        if (!amountEl) continue;
        amountEl.textContent = formatMoney(c.unpaid, c.currency);
        $(`over-${key}`).textContent = Number(c.overdue) > 0
            ? `из них просрочено ${formatMoney(c.overdue, c.currency)}`
            : '';
    }
}

export async function loadPayments() {
    const requestId = ++requestCounter;
    setTableMessage(TBODY, COLUMNS, 'Загрузка…');
    try {
        const [items, summary] = await Promise.all([
            api('/payment-occurrences', { params: PAYMENT_FILTERS[currentFilter] }),
            api('/payments/summary'),
        ]);
        if (requestId !== requestCounter) return; // ответ на устаревший фильтр
        renderTable(items);
        renderSummary(summary);
    } catch (e) {
        if (requestId === requestCounter) setTableMessage(TBODY, COLUMNS, e.message);
    }
}

async function updateOccurrence(id, body, successMessage) {
    try {
        await api(`/payment-occurrences/${id}`, { method: 'PATCH', body });
        showToast(successMessage);
    } catch (e) {
        showToast(e.message, 'error');
    }
    loadPayments();
}

function setFilter(filter, button) {
    currentFilter = filter in PAYMENT_FILTERS ? filter : 'all';
    document.querySelectorAll('#payment-filters .filter-btn').forEach((btn) => {
        btn.classList.toggle('active', btn === button);
    });
    loadPayments();
}

export function initPayments() {
    $('payment-filters').addEventListener('click', (event) => {
        const button = event.target.closest('.filter-btn');
        if (button) setFilter(button.dataset.filter, button);
    });

    const tbody = $(TBODY);
    onAction(tbody, 'click', {
        pay: (id) => updateOccurrence(id, { status: 'paid' }, 'Оплата отмечена'),
        unpay: (id) => updateOccurrence(id, { status: 'unpaid' }, 'Отметка об оплате снята'),
    });
    onAction(tbody, 'change', {
        'paid-date': (id, input) => {
            if (!input.value) {
                loadPayments(); // дату стёрли — вернуть прежнюю
                return;
            }
            updateOccurrence(id, { paid_at: input.value }, 'Дата оплаты исправлена');
        },
    });
}
