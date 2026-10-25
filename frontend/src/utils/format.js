// Форматирование денег и дат для отображения.

import { CURRENCY_SIGNS } from '../config.js';

export function formatMoney(amount, currency) {
    const n = Number(amount) || 0;
    const s = n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return `${s} ${CURRENCY_SIGNS[currency] || currency}`;
}

// '2026-10-25' или '2026-10-25T10:00:00+00:00' → '25.10.2026'
export function formatDate(iso) {
    if (!iso) return '—';
    const [y, m, d] = iso.slice(0, 10).split('-');
    return `${d}.${m}.${y}`;
}

// Сегодняшняя дата в локальном поясе браузера в формате YYYY-MM-DD
export function todayIso() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
}
