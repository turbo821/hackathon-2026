// Вход и выход.

import { api } from './api.js';
import { clearSession, setToken, setUser } from './state.js';
import { $, hide, show } from './utils/dom.js';

let afterLogin = () => {};

function showLoginError(text) {
    const el = $('login-error');
    el.textContent = text;
    el.classList.remove('hidden');
}

async function handleLogin(event) {
    event.preventDefault();
    hide('login-error');

    const email = $('email').value.trim();
    const password = $('password').value;
    if (!email || !password) {
        showLoginError('Введите почту и пароль');
        return;
    }

    const btn = $('login-btn');
    btn.disabled = true;
    try {
        const data = await api('/auth/login', { method: 'POST', body: { email, password } });
        setToken(data.access_token);
        setUser(data.user);
        $('password').value = '';
        afterLogin();
    } catch (e) {
        showLoginError(e.message);
    } finally {
        btn.disabled = false;
    }
}

async function handleLogout(event) {
    event.preventDefault();
    try {
        await api('/auth/logout', { method: 'POST' });
    } catch {
        // токен мог уже истечь — всё равно выходим
    }
    resetSession();
}

// Забыть пользователя и вернуться к форме входа
export function resetSession() {
    clearSession();
    for (const id of ['dashboard-screen', 'main-nav', 'logout-btn', 'user-role',
                      'payment-modal', 'user-modal', 'confirm-modal']) {
        hide(id);
    }
    show('login-screen');
}

// Восстановить сессию по сохранённому токену. true — пользователь вошёл.
export async function restoreSession() {
    try {
        setUser(await api('/auth/me'));
        return true;
    } catch (e) {
        // 401 уже обработан в api(); здесь — например, сервер недоступен
        if (e.status !== 401) showLoginError(e.message);
        return false;
    }
}

export function initAuth({ onLogin }) {
    afterLogin = onLogin;
    $('login-form').addEventListener('submit', handleLogin);
    $('logout-btn').addEventListener('click', handleLogout);
}
