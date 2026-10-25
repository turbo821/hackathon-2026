// Вкладка «Регулярные»: шаблоны платежей, создание и прекращение.

import { api } from '../api.js';
import { PERIOD_LABELS } from '../config.js';
import { isAdmin } from '../state.js';
import { $, escapeHtml, hide, onAction, setTableMessage, show } from '../utils/dom.js';
import { formatDate, formatMoney, todayIso } from '../utils/format.js';
import { confirmDialog } from '../ui/confirm.js';
import { showToast } from '../ui/toast.js';

const TBODY = 'regular-table-body';
const COLUMNS = 6;

function renderRow(rp) {
    const status = rp.is_active
        ? '<span class="status status-paid">Активен</span>'
        : `<span class="status status-ended">Прекращён ${formatDate(rp.ended_at)}</span>`;
    const action = isAdmin() && rp.is_active
        ? `<button class="btn btn-secondary btn-sm btn-danger" data-action="stop" data-id="${rp.id}">Прекратить</button>`
        : '—';
    return `
        <tr>
            <td>${escapeHtml(rp.name)}</td>
            <td>${formatMoney(rp.amount, rp.currency)}</td>
            <td>${PERIOD_LABELS[rp.period] || escapeHtml(rp.period)}</td>
            <td>${formatDate(rp.first_due_date)}</td>
            <td>${status}</td>
            <td>${action}</td>
        </tr>`;
}

export async function loadRecurring() {
    setTableMessage(TBODY, COLUMNS, 'Загрузка…');
    try {
        const items = await api('/recurring-payments', {
            params: { include_inactive: $('show-inactive').checked },
        });
        if (!items.length) {
            setTableMessage(TBODY, COLUMNS, 'Регулярных платежей пока нет');
            return;
        }
        $(TBODY).innerHTML = items.map(renderRow).join('');
    } catch (e) {
        setTableMessage(TBODY, COLUMNS, e.message);
    }
}

async function stopPayment(id) {
    const confirmed = await confirmDialog({
        title: 'Прекратить платёж?',
        message: 'Напоминания прекратятся, будущие неоплаченные периоды удалятся, а история оплат сохранится.',
        confirmText: 'Прекратить',
    });
    if (!confirmed) return;

    try {
        await api(`/recurring-payments/${id}`, { method: 'DELETE' });
        showToast('Платёж прекращён');
    } catch (e) {
        showToast(e.message, 'error');
    }
    loadRecurring();
}

// ---------- Модалка создания ----------

function openModal() {
    $('new-date').value = todayIso();
    show('payment-modal');
    $('new-name').focus();
}

function closeModal() {
    hide('payment-modal');
    $('new-name').value = '';
    $('new-amount').value = '';
    $('new-date').value = '';
    $('new-currency').value = 'RUB';
    $('new-period').value = 'monthly';
}

async function createPayment() {
    const body = {
        name: $('new-name').value.trim(),
        amount: $('new-amount').value.trim(),
        currency: $('new-currency').value,
        first_due_date: $('new-date').value,
        period: $('new-period').value,
    };
    if (!body.name || !body.amount || !body.first_due_date) {
        showToast('Пожалуйста, заполните все поля!', 'error');
        return;
    }

    const btn = $('save-payment-btn');
    btn.disabled = true;
    try {
        await api('/recurring-payments', { method: 'POST', body });
        showToast('Платеж добавлен');
        closeModal();
        loadRecurring();
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

export function initRecurring() {
    $('show-inactive').addEventListener('change', loadRecurring);
    $('add-payment-btn').addEventListener('click', openModal);
    $('save-payment-btn').addEventListener('click', createPayment);
    $('cancel-payment-btn').addEventListener('click', closeModal);
    onAction($(TBODY), 'click', { stop: stopPayment });
}
