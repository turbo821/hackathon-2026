// Окно подтверждения опасных действий (вместо системного confirm()).
//
//   if (await confirmDialog({ title, message, confirmText })) { ... }

import { $ } from '../utils/dom.js';

let pending = null;

function close(result) {
    if (!pending) return;
    const overlay = $('confirm-modal');
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    const resolve = pending;
    pending = null;
    resolve(result);
}

export function initConfirm() {
    const overlay = $('confirm-modal');

    $('confirm-accept').addEventListener('click', () => close(true));
    $('confirm-cancel').addEventListener('click', () => close(false));
    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) close(false);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && pending) close(false);
    });
}

export function confirmDialog({ title, message, confirmText = 'Подтвердить' }) {
    // Предыдущее окно, если вдруг осталось открытым, считаем отменённым
    close(false);

    const overlay = $('confirm-modal');
    $('confirm-title').textContent = title;
    $('confirm-message').textContent = message;
    $('confirm-accept').textContent = confirmText;
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    $('confirm-cancel').focus();

    return new Promise((resolve) => {
        pending = resolve;
    });
}
