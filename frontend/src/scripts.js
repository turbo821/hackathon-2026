const API_URL = 'http://localhost:5000/api/v1'; 
let myRole = 'admin'; 

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
    } else if (email === '' | password === ''){
        document.getElementById('login-error').classList.remove('hidden');
    }
    /* 
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ login: login, password: password })
        });
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('token', data.token);
            myRole = data.role; // Бэк должен прислать роль (admin или user)
            showDashboard();
        } else {
            document.getElementById('login-error').classList.remove('hidden');
        }
    } catch (e) { 
        console.error('Ошибка сети:', e); 
        alert('Сервер не отвечает');
    }
    */
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
    roleSpan.innerText = myRole === 'admin' ? 'admin' : 'user';
    roleSpan.classList.remove('hidden');


    if (myRole === 'admin') {
        document.getElementById('add-payment-btn').classList.remove('hidden');
    } else {
        document.getElementById('add-payment-btn').classList.add('hidden');
    }

    loadPayments(); 
}

async function loadPayments() {

    let payments = [
    { id: 1, name: 'Аренда офиса', amount: 50000, currency: 'RUB', date: '2023-11-01', status: 'unpaid', paid_by: null },
    { id: 2, name: 'Аренда офиса', amount: 50000, currency: 'RUB', date: '2023-11-01', status: 'unpaid', paid_by: null },
    { id: 3, name: 'Сервер', amount: 20, currency: 'USD', date: '2023-10-25', status: 'paid', actual_date: '2023-10-24', paid_by: 'Вася' },
    { id: 4, name: 'Подписка', amount: 15, currency: 'EUR', date: '2023-10-20', status: 'overdue', paid_by: null }
];

    /* 
    try {
        const response = await fetch(`${API_URL}/recurring-payments`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if(response.ok) {
            payments = await response.json();
        }
    } catch(e) {
        console.error("Не удалось загрузить платежи", e);
    }
    */

    const tbody = document.getElementById('payments-table-body');
    tbody.innerHTML = ''; // Очищаем таблицу перед заполнением

    // Объект для подсчета сумм по валютам
    let sums = { RUB: 0, USD: 0, EUR: 0 };

    payments.forEach(p => {
        // Проверка: если сумма пришла строкой, превращаем в число. Если пусто - 0.
        const amount = Number(p.amount) || 0;
        sums[p.currency] += amount;

        // Определяем, как будет выглядеть статус
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

        // Кнопка действия в зависимости от статуса
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

    // Обновляем карточки с итогами
    document.getElementById('sum-rub').innerText = sums.RUB.toLocaleString() + ' ₽';
    document.getElementById('sum-usd').innerText = '$' + sums.USD.toLocaleString();
    document.getElementById('sum-eur').innerText = '€' + sums.EUR.toLocaleString();
}

function markPaid(id) {
    const today = new Date().toISOString().split('T')[0]; 
    
    alert(`[Фронт] Отправляем PATCH запрос: отметить платеж ${id} как оплаченный (дата: ${today})`);
    
    /* 
    // РЕАЛЬНЫЙ КОД:
    fetch(`${API_URL}/payment-occurrences/${id}`, {
        method: 'PATCH',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}` 
        },
        body: JSON.stringify({ status: 'paid', actual_date: today })
    }).then(res => {
        if(res.ok) loadPayments(); // Обновляем таблицу
    });
    */
}

function markUnpaid(id) {
    alert(`[Фронт] Отправляем PATCH запрос: отменить оплату для платежа ${id}`);
    
    /* 
    // РЕАЛЬНЫЙ КОД:
    fetch(`${API_URL}/payment-occurrences/${id}`, {
        method: 'PATCH',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}` 
        },
        body: JSON.stringify({ status: 'unpaid', actual_date: null })
    }).then(res => {
        if(res.ok) loadPayments(); 
    });
    */
}

function openModal() {
    document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
    document.getElementById('new-name').value = '';
    document.getElementById('new-amount').value = '';
    document.getElementById('new-date').value = '';
}

function createPayment() {
    const name = document.getElementById('new-name').value;
    const amount = document.getElementById('new-amount').value;
    const currency = document.getElementById('new-currency').value;
    const date = document.getElementById('new-date').value;

    // Проверка, чтобы не отправлять пустые поля (защита от ошибки!)
    if (!name || !amount || !date) {
        alert('Пожалуйста, заполните все поля!');
        return;
    }

    // Собираем данные в объект
    const newPayment = {
        name: name,
        amount: Number(amount),
        currency: currency,
        date: date
    };

    alert(`[Фронт] Отправляем POST запрос на создание платежа:\n${JSON.stringify(newPayment, null, 2)}`);
    closeModal();

    /* 
    // РЕАЛЬНЫЙ КОД:
    fetch(`${API_URL}/recurring-payments`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}` 
        },
        body: JSON.stringify(newPayment)
    }).then(res => {
        if(res.ok) loadPayments(); // Если создалось — обновляем таблицу
        else alert('Ошибка при создании');
    });
    */
}

window.onload = () => {
    // Если токен уже есть (пользователь недавно заходил), сразу показываем дашборд
    if (localStorage.getItem('token')) {
        // Для тестов на хакатоне: если токен admin, даем права админа
        if(localStorage.getItem('token') === 'fake-token-admin') myRole = 'admin';
        showDashboard();
    }
}
