const API_URL = 'http://localhost:5000/api/v1'; 
let myRole = 'admin'; 
let globalPayments = []; 

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

async function handleLogin() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    if (email === 'admin' && password === 'admin') {
        myRole = 'admin';
        localStorage.setItem('token', 'fake-token-admin');
        showDashboard();
    } else if (email === 'user' && password === 'user') {
        myRole = 'user';
        localStorage.setItem('token', 'fake-token-user');
        showDashboard();
    } else if (email === 'owner' && password === 'owner') {
        myRole = 'owner';
        localStorage.setItem('token', 'fake-token-owner');
        showDashboard();
    } else {
        document.getElementById('login-error').classList.remove('hidden');
    }
}

function logout(e) {
    if (e) e.preventDefault();
    localStorage.removeItem('token');
    location.reload();
}

function showDashboard() {
    document.getElementById('login-screen').classList.add('hidden'); 
    document.getElementById('dashboard-screen').classList.remove('hidden'); 
    document.getElementById('main-nav').classList.remove('hidden');
    document.getElementById('logout-btn').classList.remove('hidden');

    const roleSpan = document.getElementById('user-role');
    roleSpan.innerText = myRole;
    roleSpan.classList.remove('hidden');

    const addPaymentBtn = document.getElementById('add-payment-btn');
    const addUserBtn = document.getElementById('add-user-btn');

    if (myRole === 'admin' || myRole === 'owner') {
        if (addPaymentBtn) addPaymentBtn.classList.remove('hidden');
        if (addUserBtn) addUserBtn.classList.remove('hidden');
    } else {
        if (addPaymentBtn) addPaymentBtn.classList.add('hidden');
        if (addUserBtn) addUserBtn.classList.add('hidden');
    }

    switchTab('payments', document.querySelector('.nav-link.active'));
    loadPayments(); 
}

async function loadPayments() {
    globalPayments = [
        { id: 1, name: 'Аренда офиса', amount: 50000, currency: 'RUB', date: '2023-11-01', status: 'unpaid', paid_by: null },
        { id: 2, name: 'Аренда офиса', amount: 50000, currency: 'RUB', date: '2023-11-01', status: 'unpaid', paid_by: null },
        { id: 3, name: 'Сервер', amount: 20, currency: 'USD', date: '2023-10-25', status: 'paid', actual_date: '2023-10-24', paid_by: 'Вася' },
        { id: 4, name: 'Подписка', amount: 15, currency: 'EUR', date: '2023-10-20', status: 'overdue', paid_by: null }
    ];

    const allBtn = document.querySelector('.filter-btn');
    if (allBtn) filterPayments('all', allBtn);
}

function renderTable(paymentsToRender) {
    const tbody = document.getElementById('payments-table-body');
    tbody.innerHTML = ''; 

    let sums = { RUB: 0, USD: 0, EUR: 0 };

    if (paymentsToRender.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #898989;">Нет платежей по этому фильтру</td></tr>';
    }

    paymentsToRender.forEach(p => {
        const amount = Number(p.amount) || 0;
        sums[p.currency] += amount;

        let statusText = 'Не оплачено';
        let statusClass = 'status-unpaid';
        
        if (p.status === 'paid') {
            statusText = `Оплачено`;
            if(p.actual_date) statusText += ` (${p.actual_date})`;
            statusClass = 'status-paid';
        } else if (p.status === 'overdue') {
            statusText = 'Просрочка';
            statusClass = 'status-overdue';
        }

        let actionBtn = '';
        if (p.status !== 'paid') {
            actionBtn = `<button class="btn" style="padding: 8px 15px; font-size: 13px;" onclick="markPaid(${p.id})">Оплатить</button>`;
        } else {
            actionBtn = `<button class="btn btn-secondary" style="padding: 8px 15px; font-size: 13px;" onclick="markUnpaid(${p.id})">Отменить</button>`;
        }

        const row = `
            <tr>
                <td>${p.paid_by ? p.paid_by : '—'}</td> 
                <td>${p.name}</td>
                <td>${amount} ${p.currency}</td>
                <td>${p.date}</td>
                <td><span class="status ${statusClass}">${statusText}</span></td>
                <td>${actionBtn}</td>
            </tr>
        `;
        tbody.innerHTML += row;
    });

    document.getElementById('sum-rub').innerText = sums.RUB.toLocaleString() + ' ₽';
    document.getElementById('sum-usd').innerText = '$' + sums.USD.toLocaleString();
    document.getElementById('sum-eur').innerText = '€' + sums.EUR.toLocaleString();
}

function filterPayments(filterType, btnElement) {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    if (btnElement) btnElement.classList.add('active');

    if (filterType === 'all') {
        renderTable(globalPayments);
    } else {
        const filtered = globalPayments.filter(p => p.status === filterType);
        renderTable(filtered);
    }
}

function markPaid(id) {
    const today = new Date().toISOString().split('T')[0]; 
    alert(`Отправляем PATCH запрос: отметить платеж ${id} как оплаченный (дата: ${today})`);
}

function markUnpaid(id) {
    alert(`Отправляем PATCH запрос: отменить оплату для платежа ${id}`);
}

// --- РЕГУЛЯРНЫЕ ПЛАТЕЖИ ---
function openModalRegular() {
    document.getElementById('modal-regular').classList.remove('hidden');
}

function closeModalRegular() {
    document.getElementById('modal-regular').classList.add('hidden');
    document.getElementById('reg-name').value = '';
    document.getElementById('reg-amount').value = '';
    document.getElementById('reg-date').value = '';
    document.getElementById('reg-period').value = 'monthly';
}

function createRegularPayment() {
    const name = document.getElementById('reg-name').value;
    const amount = document.getElementById('reg-amount').value;
    const currency = document.getElementById('reg-currency').value;
    const date = document.getElementById('reg-date').value;
    const period = document.getElementById('reg-period').value;

    if (!name || !amount || !date) {
        showToast('Пожалуйста, заполните все поля!', 'error');
        return;
    }

    const newRegPayment = {
        name: name,
        amount: Number(amount),
        currency: currency,
        date: date,
        period: period
    };

    // Здесь потом будет fetch POST запрос к /recurring-payments
    console.log('Создан регулярный платеж:', newRegPayment);

    showToast('Шаблон регулярного платежа создан!');
    closeModalRegular();
}

// --- ПОЛЬЗОВАТЕЛИ ---
function openModal1() {
    document.getElementById('modal-user').classList.remove('hidden');
}

function closeModal1() {
    document.getElementById('modal-user').classList.add('hidden');
    document.getElementById('new-user-name').value = '';
    document.getElementById('new-user-email').value = '';
    document.getElementById('new-user-password').value = '';
    document.getElementById('new-user-role').value = 'user';
}

function createUser() {
    const name = document.getElementById('new-user-name').value.trim();
    const email = document.getElementById('new-user-email').value.trim();
    const role = document.getElementById('new-user-role').value;
    const password = document.getElementById('new-user-password').value;

    if (!name || !email || !password) {
        showToast('Пожалуйста, заполните все поля!', 'error');
        return;
    }

    if (role === 'admin' && myRole !== 'owner') {
        showToast('Только Владелец может создавать администраторов!', 'error');
        return;
    }

    const newUser = {
        name: name,
        email: email,
        role: role,
        password: password
    };

    showToast('Пользователь создан');
    closeModal1();
}

function switchTab(tabName, element) {
    const links = document.querySelectorAll('.nav-link');
    links.forEach(link => link.classList.remove('active'));
    if (element) element.classList.add('active');

    document.getElementById('tab-payments').classList.add('hidden');
    document.getElementById('tab-regular').classList.add('hidden');
    document.getElementById('tab-users').classList.add('hidden');

    if (tabName === 'payments') {
        document.getElementById('tab-payments').classList.remove('hidden');
    } else if (tabName === 'regular') {
        document.getElementById('tab-regular').classList.remove('hidden');
    } else if (tabName === 'users') {
        document.getElementById('tab-users').classList.remove('hidden');
    }
}

window.onload = () => {
    if (localStorage.getItem('token')) {
        if(localStorage.getItem('token') === 'fake-token-admin') myRole = 'admin';
        if(localStorage.getItem('token') === 'fake-token-owner') myRole = 'owner';
        if(localStorage.getItem('token') === 'fake-token-user') myRole = 'user';
        showDashboard();
    }
}