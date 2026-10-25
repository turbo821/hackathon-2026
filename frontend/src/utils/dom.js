// Мелкие помощники для работы с DOM.

export const $ = (id) => document.getElementById(id);

export function show(id) {
    $(id).classList.remove('hidden');
}

export function hide(id) {
    $(id).classList.add('hidden');
}

export function toggle(id, visible) {
    $(id).classList.toggle('hidden', !visible);
}

export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

// Одна строка-сообщение на всю ширину таблицы: «Загрузка…», «Нет данных», ошибка
export function setTableMessage(tbodyId, colspan, text) {
    $(tbodyId).innerHTML =
        `<tr><td colspan="${colspan}" class="table-message">${escapeHtml(text)}</td></tr>`;
}

// Делегирование: один обработчик на контейнер вместо onclick на каждой кнопке.
// Кнопка помечается data-action="..." и data-id="...".
export function onAction(container, eventType, handlers) {
    container.addEventListener(eventType, (event) => {
        const target = event.target.closest('[data-action]');
        if (!target || !container.contains(target)) return;
        const handler = handlers[target.dataset.action];
        if (handler) handler(Number(target.dataset.id), target, event);
    });
}
