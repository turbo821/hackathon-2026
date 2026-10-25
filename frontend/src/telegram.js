// Иконка Telegram в шапке: вход в общий чат с привязкой аккаунта.
//
// Не привязанный пользователь получает персональную ссылку-приглашение
// (POST /auth/telegram-chat-link). Когда он вступит в чат по ней, бот увидит
// код в имени ссылки и запишет его Telegram ID — после этого кнопка «Оплачено»
// в напоминаниях будет знать, кто нажал.
// Уже привязанный пользователь просто открывает общую ссылку на чат.

import { api } from './api.js';
import { session } from './state.js';
import { $ } from './utils/dom.js';
import { showToast } from './ui/toast.js';

async function openTelegram(event) {
    // Привязан — обычная ссылка из href, ничего не перехватываем
    if (session.user?.telegram_id) return;

    event.preventDefault();
    const fallbackUrl = event.currentTarget.href;

    // Вкладку открываем сразу, синхронно с кликом: окно, открытое после
    // await, браузер посчитает всплывающим и заблокирует.
    const tab = window.open('', '_blank');

    try {
        const { url } = await api('/auth/telegram-chat-link', { method: 'POST' });
        if (tab) tab.location.href = url;
        else window.location.href = url; // вкладку всё-таки заблокировали
        showToast('Вступите в чат по ссылке — аккаунт привяжется автоматически');
    } catch (e) {
        // Чат для приглашений не настроен (503) или Telegram недоступен (502):
        // открываем общий чат без привязки
        if (tab) tab.location.href = fallbackUrl;
        showToast(`Привязка недоступна: ${e.message}`, 'error');
    }
}

export function initTelegram() {
    $('telegram-link').addEventListener('click', openTelegram);
}
