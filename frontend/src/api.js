// HTTP-клиент для API бэкенда (FastAPI).
// Ошибки бэкенд отдаёт в едином формате: {code, status, message}.

import { API_URL } from './config.js';
import { session } from './state.js';

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

// Что делать, когда сервер ответил 401 на запрос с токеном (истёк, отозван).
// Задаётся из main.js, чтобы api.js не зависел от модулей интерфейса.
let unauthorizedHandler = null;

export function onUnauthorized(handler) {
    unauthorizedHandler = handler;
}

export async function api(path, { method = 'GET', body, params } = {}) {
    // Второй аргумент нужен для относительного API_URL:
    // без него new URL('/api/v1/...') бросает Invalid URL.
    const url = new URL(API_URL + path, window.location.origin);
    if (params) {
        for (const [key, value] of Object.entries(params)) {
            if (value !== null && value !== undefined && value !== '') {
                url.searchParams.set(key, value);
            }
        }
    }

    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (session.token) headers.Authorization = `Bearer ${session.token}`;

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
        const message = data?.message || `Ошибка ${res.status}`;
        if (res.status === 401 && session.token && unauthorizedHandler) {
            unauthorizedHandler(message);
        }
        throw new ApiError(message, res.status);
    }
    return data;
}
