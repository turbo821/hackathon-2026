// Invoice Keeper — панель. Все данные берутся из API бэкенда (FastAPI).
// Скрипт подключён как module (type="module"), поэтому функции, которые
// вызываются из onclick в HTML, в конце файла выставляются в window.

const API_URL = (import.meta.env?.VITE_API_URL || 'http://backend:5000/api/v1').replace(/\/+$/, '');

// На бэкенде роль владельца называется superadmin, в интерфейсе — owner
const ROLE_LABELS = { superadmin: 'owner', admin: 'admin', user: 'user' };
const PERIOD_LABELS = { monthly: 'Ежемесячно', quarterly: 'Ежеквартально', yearly: 'Ежегодно' };
const CURRENCY_SIGNS = { RUB: '₽', USD: '$', EUR: '€' };

// Кнопки-фильтры над таблицей → параметры GET /payment-occurrences
const FILTERS = {
    all: {},
    unpaid: { state: 'pending' },   // ждут оплаты, срок не прошёл
    overdue: { state: 'overdue' },  // не оплачены после срока
    paid: { status: 'paid' },       // оплачены (вовремя и с опозданием)
};

let token = localStorage.getItem('token');
let currentUser = null;
let currentFilter = 'all';
let paymentsRequestId = 0;
let usersCache = [];
let editingUserId = null;
let pendingConfirmation = null;

// ---------- Утилиты ----------

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

function formatMoney(amount, currency) {
    const n = Number(amount) || 0;
    const s = n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return `${s} ${CURRENCY_SIGNS[currency] || currency}`;
}

function formatDate(iso) {
    if (!iso) return '—';
    const [y, m, d] = iso.slice(0, 10).split('-');
    return `${d}.${m}.${y}`;
}

function todayIso() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
}

const isAdmin = () => currentUser && ['admin', 'superadmin'].includes(currentUser.role);
const isSuperadmin = () => currentUser?.role === 'superadmin';

function setTableMessage(tbodyId, colspan, text) {
    $(tbodyId).innerHTML = `<tr><td colspan="${colspan}" class="table-message">${escapeHtml(text)}</td></tr>`;
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = 'toast' + (type === 'error' ? ' error' : '');
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ---------- HTTP-клиент ----------

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

async function api(path, { method = 'GET', body, params } = {}) {
    const url = new URL(API_URL + path);
    if (params) {
        for (const [k, v] of Object.entries(params)) {
            if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
        }
    }

    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;

    let res;
    try {
        res = await fetch(url, {
            method,
            headers,
            body: body !== undefined ? JSON.stringify(body) : undefined,
        });
    } catch {
        throw new ApiError('Не удалось связаться с сервером', 0);
    }

    if (res.status === 204) return null;
    const data = await res.json().catch(() => null);

    if (!res.ok) {
        // Бэкенд отдаёт ошибки в едином формате: {code, status, message}
        const message = data?.message || `Ошибка ${res.status}`;
        if (res.status === 401 && token) {
            resetSession();
            showToast(message, 'error');
        }
        throw new ApiError(message, res.status);
    }
    return data;
}

// ---------- Вход / выход ----------

function showLoginError(text) {
    const el = $('login-error');
    el.textContent = text;
    el.classList.remove('hidden');
}

async function handleLogin(event) {
    if (event) event.preventDefault();
    $('login-error').classList.add('hidden');

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
        token = data.access_token;
        localStorage.setItem('token', token);
        currentUser = data.user;
        $('password').value = '';
        showDashboard();
    } catch (e) {
        showLoginError(e.message);
    } finally {
        btn.disabled = false;
    }
}

async function logout(event) {
    if (event) event.preventDefault();
    try {
        await api('/auth/logout', { method: 'POST' });
    } catch {
        // токен мог уже истечь — всё равно выходим
    }
    resetSession();
}

function resetSession() {
    token = null;
    currentUser = null;
    localStorage.removeItem('token');

    $('dashboard-screen').classList.add('hidden');
    $('main-nav').classList.add('hidden');
    $('logout-btn').classList.add('hidden');
    $('user-role').classList.add('hidden');
    $('modal').classList.add('hidden');
    $('modal-user').classList.add('hidden');
    $('login-screen').classList.remove('hidden');
}

// ---------- Дашборд и вкладки ----------

function showDashboard() {
    $('login-screen').classList.add('hidden');
    $('dashboard-screen').classList.remove('hidden');
    $('main-nav').classList.remove('hidden');
    $('logout-btn').classList.remove('hidden');

    const roleSpan = $('user-role');
    roleSpan.textContent = `${currentUser.username} · ${ROLE_LABELS[currentUser.role] || currentUser.role}`;
    roleSpan.classList.remove('hidden');

    // Кнопки админа. Права всё равно проверяет сервер — это только интерфейс.
    $('add-payment-btn').classList.toggle('hidden', !isAdmin());
    $('add-user-btn').classList.toggle('hidden', !isAdmin());
    $('nav-users').classList.toggle('hidden', !isAdmin());

    switchTab('payments');
}

function switchTab(tabName, element) {
    if (tabName === 'users' && !isAdmin()) tabName = 'payments';

    document.querySelectorAll('.nav-link').forEach((link) => {
        link.classList.toggle('active', element ? link === element : link.dataset.tab === tabName);
    });

    for (const name of ['payments', 'regular', 'users']) {
        $(`tab-${name}`).classList.toggle('hidden', name !== tabName);
    }

    if (tabName === 'payments') loadPayments();
    else if (tabName === 'regular') loadRecurring();
    else if (tabName === 'users') loadUsers();
}

// ---------- Платежи (периоды) ----------

function occurrenceStatus(o) {
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

function renderTable(items) {
    const tbody = $('payments-table-body');
    if (!items.length) {
        setTableMessage('payments-table-body', 6, 'Нет платежей по этому фильтру');
        return;
    }

    const maxDate = todayIso();
    tbody.innerHTML = items.map((o) => {
        const [cls, text] = occurrenceStatus(o);
        const ended = o.payment_ended_at ? '<div class="muted">платёж прекращён</div>' : '';
        const action = o.status === 'paid'
            ? `<div class="row-actions">
                   <input type="date" class="input-field input-sm" value="${o.paid_at || ''}" max="${maxDate}"
                          title="Фактическая дата оплаты" onchange="changePaidDate(${o.id}, this.value)">
                   <button class="btn btn-secondary btn-sm" onclick="markUnpaid(${o.id})">Отменить</button>
               </div>`
            : `<button class="btn btn-sm" onclick="markPaid(${o.id})">Оплатить</button>`;

        return `
            <tr>
                <td>${escapeHtml(o.marked_by || '—')}</td>
                <td>${escapeHtml(o.name)}${ended}</td>
                <td>${formatMoney(o.amount, o.currency)}</td>
                <td>${formatDate(o.due_date)}</td>
                <td><span class="status ${cls}">${escapeHtml(text)}</span></td>
                <td>${action}</td>
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

async function loadPayments() {
    const requestId = ++paymentsRequestId;
    setTableMessage('payments-table-body', 6, 'Загрузка…');
    try {
        const [items, summary] = await Promise.all([
            api('/payment-occurrences', { params: FILTERS[currentFilter] }),
            api('/payments/summary'),
        ]);
        if (requestId !== paymentsRequestId) return; // пришёл ответ на устаревший фильтр
        renderTable(items);
        renderSummary(summary);
    } catch (e) {
        if (requestId === paymentsRequestId) setTableMessage('payments-table-body', 6, e.message);
    }
}

function filterPayments(filterType, btnElement) {
    document.querySelectorAll('.filter-btn').forEach((btn) => btn.classList.remove('active'));
    if (btnElement) btnElement.classList.add('active');
    currentFilter = filterType in FILTERS ? filterType : 'all';
    loadPayments();
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

function markPaid(id) {
    updateOccurrence(id, { status: 'paid' }, 'Оплата отмечена');
}

function markUnpaid(id) {
    updateOccurrence(id, { status: 'unpaid' }, 'Отметка об оплате снята');
}

function changePaidDate(id, value) {
    if (!value) {
        loadPayments();
        return;
    }
    updateOccurrence(id, { paid_at: value }, 'Дата оплаты исправлена');
}

// ---------- Красивое подтверждение опасных действий ----------

function showConfirm({ title, message, confirmText = 'Подтвердить' }) {
    const overlay = $('confirm-modal');
    $('confirm-title').textContent = title;
    $('confirm-message').textContent = message;
    $('confirm-accept').textContent = confirmText;
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');

    return new Promise((resolve) => {
        pendingConfirmation = (result) => {
            overlay.classList.add('hidden');
            overlay.setAttribute('aria-hidden', 'true');
            pendingConfirmation = null;
            resolve(result);
        };
        $('confirm-cancel').focus();
    });
}

function resolveConfirmation(result) {
    if (pendingConfirmation) pendingConfirmation(result);
}

function initConfirmModal() {
    const overlay = $('confirm-modal');
    if (!overlay) return;

    $('confirm-accept').addEventListener('click', () => resolveConfirmation(true));
    $('confirm-cancel').addEventListener('click', () => resolveConfirmation(false));
    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) resolveConfirmation(false);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !overlay.classList.contains('hidden')) {
            resolveConfirmation(false);
        }
    });
}

// ---------- Регулярные платежи (шаблоны) ----------

async function loadRecurring() {
    setTableMessage('regular-table-body', 6, 'Загрузка…');
    try {
        const items = await api('/recurring-payments', {
            params: { include_inactive: $('show-inactive').checked },
        });
        if (!items.length) {
            setTableMessage('regular-table-body', 6, 'Регулярных платежей пока нет');
            return;
        }
        $('regular-table-body').innerHTML = items.map((rp) => {
            const status = rp.is_active
                ? '<span class="status status-paid">Активен</span>'
                : `<span class="status status-ended">Прекращён ${formatDate(rp.ended_at)}</span>`;
            const action = isAdmin() && rp.is_active
                ? `<button class="btn btn-secondary btn-sm btn-danger" onclick="stopPayment(${rp.id})">Прекратить</button>`
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
        }).join('');
    } catch (e) {
        setTableMessage('regular-table-body', 6, e.message);
    }
}

async function stopPayment(id) {
    const confirmed = await showConfirm({
        title: 'Прекратить платёж?',
        message: 'Напоминания прекратятся, будущие неоплаченные периоды удалятся, а история оплат сохранится.',
        confirmText: 'Прекратить'
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

function openModal() {
    $('new-date').value = todayIso();
    $('modal').classList.remove('hidden');
}

function closeModal() {
    $('modal').classList.add('hidden');
    $('new-name').value = '';
    $('new-amount').value = '';
    $('new-date').value = '';
    $('new-currency').value = 'RUB';
    $('new-period').value = 'monthly';
}

async function createPayment() {
    const name = $('new-name').value.trim();
    const amount = $('new-amount').value.trim();
    const currency = $('new-currency').value;
    const firstDueDate = $('new-date').value;
    const period = $('new-period').value;

    if (!name || !amount || !firstDueDate) {
        showToast('Пожалуйста, заполните все поля!', 'error');
        return;
    }

    const btn = $('save-payment-btn');
    btn.disabled = true;
    try {
        await api('/recurring-payments', {
            method: 'POST',
            body: { name, amount, currency, first_due_date: firstDueDate, period },
        });
        showToast('Платеж добавлен');
        closeModal();
        loadRecurring();
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

// ---------- Пользователи ----------

function canManage(user) {
    if (user.role === 'superadmin') return false;
    if (user.role === 'admin') return isSuperadmin();
    return isAdmin();
}

async function loadUsers() {
    setTableMessage('users-table-body', 5, 'Загрузка…');
    try {
        usersCache = await api('/users');
        if (!usersCache.length) {
            setTableMessage('users-table-body', 5, 'Пользователей нет');
            return;
        }
        $('users-table-body').innerHTML = usersCache.map((u) => {
            const me = u.id === currentUser.id ? ' <span class="muted">(вы)</span>' : '';
            const actions = canManage(u)
                ? `<div class="row-actions">
                       <button class="btn btn-secondary btn-sm" onclick="editUser(${u.id})">Изменить</button>
                       <button class="btn btn-secondary btn-sm btn-danger" onclick="deleteUser(${u.id})">Удалить</button>
                   </div>`
                : '—';
            return `
                <tr>
                    <td>${escapeHtml(u.username)}${me}</td>
                    <td>${escapeHtml(u.email)}</td>
                    <td><span class="role-badge role-${escapeHtml(u.role)}">${ROLE_LABELS[u.role] || escapeHtml(u.role)}</span></td>
                    <td>${formatDate(u.created_at)}</td>
                    <td>${actions}</td>
                </tr>`;
        }).join('');
    } catch (e) {
        setTableMessage('users-table-body', 5, e.message);
    }
}

function openModal1(user = null) {
    editingUserId = user ? user.id : null;
    $('user-modal-title').textContent = user ? 'Редактирование пользователя' : 'Новый пользователь';
    $('new-user-name').value = user?.username || '';
    $('new-user-email').value = user?.email || '';
    $('new-user-password').value = '';
    $('new-user-password').placeholder = user ? 'Новый пароль (не обязательно)' : 'Пароль (от 6 символов)';
    $('new-user-role').value = user?.role || 'user';
    // Назначать администраторов может только owner
    $('role-field').classList.toggle('hidden', !isSuperadmin());
    $('modal-user').classList.remove('hidden');
}

function closeModal1() {
    $('modal-user').classList.add('hidden');
    editingUserId = null;
    $('new-user-name').value = '';
    $('new-user-email').value = '';
    $('new-user-password').value = '';
    $('new-user-role').value = 'user';
}

function editUser(id) {
    const user = usersCache.find((u) => u.id === id);
    if (user) openModal1(user);
}

async function createUser() {
    const username = $('new-user-name').value.trim();
    const email = $('new-user-email').value.trim().toLowerCase();
    const role = $('new-user-role').value;
    const password = $('new-user-password').value;
    const editing = editingUserId !== null;

    if (!username || !email || (!editing && !password)) {
        showToast('Пожалуйста, заполните все поля!', 'error');
        return;
    }

    let body;
    if (editing) {
        const old = usersCache.find((u) => u.id === editingUserId) || {};
        body = {};
        if (username !== old.username) body.username = username;
        if (email !== old.email) body.email = email;
        if (password) body.password = password;
        if (isSuperadmin() && role !== old.role) body.role = role;
        if (!Object.keys(body).length) {
            closeModal1();
            return;
        }
    } else {
        // Owner может создавать админов, а админ — нет (сервер проверяет это же)
        if (role === 'admin' && !isSuperadmin()) {
            showToast('Только Владелец может создавать администраторов!', 'error');
            return;
        }
        body = { username, email, password };
        if (isSuperadmin()) body.role = role;
    }

    const btn = $('save-user-btn');
    btn.disabled = true;
    try {
        await api(editing ? `/users/${editingUserId}` : '/users', {
            method: editing ? 'PATCH' : 'POST',
            body,
        });
        showToast(editing ? 'Изменения сохранены' : 'Пользователь создан');
        closeModal1();
        loadUsers();
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function deleteUser(id) {
    const user = usersCache.find((u) => u.id === id);
    const confirmed = await showConfirm({
        title: 'Удалить пользователя?',
        message: `Пользователь «${user ? user.username : ''}» будет удалён. История оплат сохранится.`,
        confirmText: 'Удалить',
        icon: '!',
    });
    if (!confirmed) return;

    try {
        await api(`/users/${id}`, { method: 'DELETE' });
        showToast('Пользователь удалён');
    } catch (e) {
        showToast(e.message, 'error');
    }
    loadUsers();
}

// ---------- Старт ----------

async function init() {
    if (!token) return;
    try {
        currentUser = await api('/auth/me');
        showDashboard();
    } catch (e) {
        // 401 уже обработан в api(); здесь — например, сервер недоступен
        if (e.status !== 401) showLoginError(e.message);
    }
}

Object.assign(window, {
    handleLogin, logout, switchTab,
    filterPayments, markPaid, markUnpaid, changePaidDate,
    loadRecurring, openModal, closeModal, createPayment, stopPayment,
    openModal1, closeModal1, createUser, editUser, deleteUser,
});

initConfirmModal();
init();
