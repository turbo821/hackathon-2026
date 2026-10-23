import axios from 'axios'

import { session } from '../state/session.js'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api/v1',
  timeout: 15000,
})

// Токен в каждый запрос
api.interceptors.request.use((config) => {
  const token = session.token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 → сессия закончилась: выходим на экран входа
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLogin = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLogin && session.token) {
      session.clear()
      window.location.hash = '#/login'
    }
    return Promise.reject(error)
  },
)

/**
 * Человекочитаемый текст ошибки из ответа API.
 * Формат бэкенда: { message, errors: { json: { field: ["..."] } } }
 */
export function errorText(error) {
  if (!error.response) return 'Сервер не отвечает. Проверьте, что backend запущен.'
  const data = error.response.data || {}
  const fieldErrors = data.errors?.json || data.errors?.query
  if (fieldErrors) {
    const first = Object.values(fieldErrors).flat()[0]
    if (typeof first === 'string') return first
    if (first && typeof first === 'object') return Object.values(first).flat()[0]
  }
  return data.message || `Ошибка ${error.response.status}`
}

/** Ошибки валидации по полям: { amount: "Сумма должна быть больше нуля" } */
export function fieldErrors(error) {
  const errors = error.response?.data?.errors?.json || {}
  return Object.fromEntries(
    Object.entries(errors).map(([field, messages]) => [field, [].concat(messages).flat()[0]]),
  )
}
