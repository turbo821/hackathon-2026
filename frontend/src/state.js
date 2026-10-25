// Состояние сессии: токен и текущий пользователь.
// Права всё равно проверяет сервер — здесь только то, что нужно интерфейсу.

const TOKEN_KEY = 'token';

function readToken() {
    try {
        return localStorage.getItem(TOKEN_KEY);
    } catch {
        return null; // приватный режим или заблокированное хранилище
    }
}

export const session = {
    token: readToken(),
    user: null,
};

export function setToken(token) {
    session.token = token;
    try {
        if (token) localStorage.setItem(TOKEN_KEY, token);
        else localStorage.removeItem(TOKEN_KEY);
    } catch {
        // без хранилища токен живёт только до перезагрузки страницы
    }
}

export function setUser(user) {
    session.user = user;
}

export function clearSession() {
    setToken(null);
    setUser(null);
}

export const isAdmin = () => ['admin', 'superadmin'].includes(session.user?.role);
export const isSuperadmin = () => session.user?.role === 'superadmin';
