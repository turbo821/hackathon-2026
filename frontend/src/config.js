// Константы панели: адрес API и подписи для интерфейса.

// Относительный адрес по умолчанию: запрос уходит на тот же origin, где открыта
// страница, а nginx (в Docker) или dev-сервер Vite проксирует /api в бэкенд.
export const API_URL = (import.meta.env.VITE_API_URL || '/api/v1').replace(/\/+$/, '');

// На бэкенде роль владельца называется superadmin, в интерфейсе — owner
export const ROLE_LABELS = { superadmin: 'owner', admin: 'admin', user: 'user' };

export const PERIOD_LABELS = {
    monthly: 'Ежемесячно',
    quarterly: 'Ежеквартально',
    yearly: 'Ежегодно',
};

export const CURRENCY_SIGNS = { RUB: '₽', USD: '$', EUR: '€' };

// Кнопки-фильтры над таблицей → параметры GET /payment-occurrences
export const PAYMENT_FILTERS = {
    all: {},
    unpaid: { state: 'pending' },  // ждут оплаты, срок не прошёл
    overdue: { state: 'overdue' }, // не оплачены после срока
    paid: { status: 'paid' },      // оплачены (вовремя и с опозданием)
};
