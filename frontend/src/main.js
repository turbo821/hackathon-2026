// Invoice Keeper — точка входа панели.
// Здесь только сборка: подключаем стили, вешаем обработчики, восстанавливаем сессию.

import './styles/main.css';

import { onUnauthorized } from './api.js';
import { initAuth, resetSession, restoreSession } from './auth.js';
import { initDashboard, showDashboard } from './dashboard.js';
import { initPayments } from './pages/payments.js';
import { initRecurring } from './pages/recurring.js';
import { initUsers } from './pages/users.js';
import { session } from './state.js';
import { initConfirm } from './ui/confirm.js';
import { showToast } from './ui/toast.js';

// Токен истёк или отозван — возвращаем на форму входа
onUnauthorized((message) => {
    resetSession();
    showToast(message, 'error');
});

initConfirm();
initAuth({ onLogin: showDashboard });
initDashboard();
initPayments();
initRecurring();
initUsers();

async function start() {
    if (session.token && (await restoreSession())) showDashboard();
}

start();
