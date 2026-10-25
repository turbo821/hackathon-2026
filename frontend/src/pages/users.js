// Вкладка «Пользователи» (только администратор): список, создание, правка, удаление.

import { api } from '../api.js';
import { ROLE_LABELS } from '../config.js';
import { isAdmin, isSuperadmin, session } from '../state.js';
import { $, escapeHtml, hide, onAction, setTableMessage, show, toggle } from '../utils/dom.js';
import { formatDate } from '../utils/format.js';
import { confirmDialog } from '../ui/confirm.js';
import { showToast } from '../ui/toast.js';

const TBODY = 'users-table-body';
const COLUMNS = 5;

let usersCache = [];
let editingUserId = null;

const findUser = (id) => usersCache.find((u) => u.id === id);

// Суперадмина не трогает никто, администраторами управляет только суперадмин
function canManage(user) {
    if (user.role === 'superadmin') return false;
    if (user.role === 'admin') return isSuperadmin();
    return isAdmin();
}

function renderRow(u) {
    const me = u.id === session.user?.id ? ' <span class="muted">(вы)</span>' : '';
    const actions = canManage(u)
        ? `<div class="row-actions">
               <button class="btn btn-secondary btn-sm" data-action="edit" data-id="${u.id}">Изменить</button>
               <button class="btn btn-secondary btn-sm btn-danger" data-action="delete" data-id="${u.id}">Удалить</button>
           </div>`
        : '—';
    return `
        <tr>
            <td>${escapeHtml(u.username)}${me}</td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="role-badge role-${escapeHtml(u.role)}">${escapeHtml(ROLE_LABELS[u.role] || u.role)}</span></td>
            <td>${formatDate(u.created_at)}</td>
            <td>${actions}</td>
        </tr>`;
}

export async function loadUsers() {
    setTableMessage(TBODY, COLUMNS, 'Загрузка…');
    try {
        usersCache = await api('/users');
        if (!usersCache.length) {
            setTableMessage(TBODY, COLUMNS, 'Пользователей нет');
            return;
        }
        $(TBODY).innerHTML = usersCache.map(renderRow).join('');
    } catch (e) {
        setTableMessage(TBODY, COLUMNS, e.message);
    }
}

async function deleteUser(id) {
    const user = findUser(id);
    const confirmed = await confirmDialog({
        title: 'Удалить пользователя?',
        message: `Пользователь «${user ? user.username : ''}» будет удалён. История оплат сохранится.`,
        confirmText: 'Удалить',
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

// ---------- Модалка создания / редактирования ----------

function openModal(user = null) {
    editingUserId = user ? user.id : null;
    $('user-modal-title').textContent = user ? 'Редактирование пользователя' : 'Новый пользователь';
    $('new-user-name').value = user?.username || '';
    $('new-user-email').value = user?.email || '';
    $('new-user-password').value = '';
    $('new-user-password').placeholder = user ? 'Новый пароль (не обязательно)' : 'Пароль (от 6 символов)';
    $('new-user-role').value = user?.role || 'user';
    // Назначать администраторов может только owner
    toggle('role-field', isSuperadmin());
    show('user-modal');
    $('new-user-name').focus();
}

function closeModal() {
    hide('user-modal');
    editingUserId = null;
    $('new-user-name').value = '';
    $('new-user-email').value = '';
    $('new-user-password').value = '';
    $('new-user-role').value = 'user';
}

// Тело PATCH: только изменённые поля. null — менять нечего.
function buildUpdateBody({ username, email, password, role }) {
    const old = findUser(editingUserId) || {};
    const body = {};
    if (username !== old.username) body.username = username;
    if (email !== old.email) body.email = email;
    if (password) body.password = password;
    if (isSuperadmin() && role !== old.role) body.role = role;
    return Object.keys(body).length ? body : null;
}

async function saveUser() {
    const form = {
        username: $('new-user-name').value.trim(),
        email: $('new-user-email').value.trim().toLowerCase(),
        role: $('new-user-role').value,
        password: $('new-user-password').value,
    };
    const editing = editingUserId !== null;

    if (!form.username || !form.email || (!editing && !form.password)) {
        showToast('Пожалуйста, заполните все поля!', 'error');
        return;
    }

    let body;
    if (editing) {
        body = buildUpdateBody(form);
        if (!body) {
            closeModal();
            return;
        }
    } else {
        body = { username: form.username, email: form.email, password: form.password };
        if (isSuperadmin()) body.role = form.role;
    }

    const btn = $('save-user-btn');
    btn.disabled = true;
    try {
        await api(editing ? `/users/${editingUserId}` : '/users', {
            method: editing ? 'PATCH' : 'POST',
            body,
        });
        showToast(editing ? 'Изменения сохранены' : 'Пользователь создан');
        closeModal();
        loadUsers();
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

export function initUsers() {
    $('add-user-btn').addEventListener('click', () => openModal());
    $('save-user-btn').addEventListener('click', saveUser);
    $('cancel-user-btn').addEventListener('click', closeModal);
    onAction($(TBODY), 'click', {
        edit: (id) => {
            const user = findUser(id);
            if (user) openModal(user);
        },
        delete: deleteUser,
    });
}
