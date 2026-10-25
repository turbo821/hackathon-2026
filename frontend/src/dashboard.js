// Дашборд: шапка с ролью и переключение вкладок.

import { ROLE_LABELS } from './config.js';
import { isAdmin, session } from './state.js';
import { $, hide, show, toggle } from './utils/dom.js';
import { loadPayments } from './pages/payments.js';
import { loadRecurring } from './pages/recurring.js';
import { loadUsers } from './pages/users.js';

const TABS = {
    payments: loadPayments,
    regular: loadRecurring,
    users: loadUsers,
};

export function switchTab(tabName) {
    if (!(tabName in TABS) || (tabName === 'users' && !isAdmin())) tabName = 'payments';

    document.querySelectorAll('.nav-link').forEach((link) => {
        link.classList.toggle('active', link.dataset.tab === tabName);
    });
    for (const name of Object.keys(TABS)) {
        toggle(`tab-${name}`, name === tabName);
    }
    TABS[tabName]();
}

export function showDashboard() {
    const user = session.user;
    hide('login-screen');
    show('dashboard-screen');
    show('main-nav');
    show('logout-btn');

    const roleSpan = $('user-role');
    roleSpan.textContent = `${user.username} · ${ROLE_LABELS[user.role] || user.role}`;
    roleSpan.classList.remove('hidden');

    // Кнопки администратора. Права всё равно проверяет сервер — это только интерфейс.
    toggle('add-payment-btn', isAdmin());
    toggle('add-user-btn', isAdmin());
    toggle('nav-users', isAdmin());

    switchTab('payments');
}

export function initDashboard() {
    $('main-nav').addEventListener('click', (event) => {
        const link = event.target.closest('.nav-link');
        if (!link) return;
        event.preventDefault();
        switchTab(link.dataset.tab);
    });
}
