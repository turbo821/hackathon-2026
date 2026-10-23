/** Все запросы к API в одном месте — страницы не знают про URL. */
import { api } from './client.js'

export const authApi = {
  login: (username, password) => api.post('/auth/login', { username, password }).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
}

export const occurrencesApi = {
  /** params: state, status, currency, recurring_payment_id, date_from, date_to, order */
  list: (params = {}) => api.get('/payment-occurrences', { params }).then((r) => r.data),
  get: (id) => api.get(`/payment-occurrences/${id}`).then((r) => r.data),
  markPaid: (id, paidAt) =>
    api.patch(`/payment-occurrences/${id}`, { status: 'paid', ...(paidAt && { paid_at: paidAt }) }).then((r) => r.data),
  changePaidAt: (id, paidAt) => api.patch(`/payment-occurrences/${id}`, { paid_at: paidAt }).then((r) => r.data),
  markUnpaid: (id) => api.patch(`/payment-occurrences/${id}`, { status: 'unpaid' }).then((r) => r.data),
}

export const recurringApi = {
  list: (includeInactive = false) =>
    api.get('/recurring-payments', { params: { include_inactive: includeInactive } }).then((r) => r.data),
  create: (payload) => api.post('/recurring-payments', payload).then((r) => r.data),
  remove: (id) => api.delete(`/recurring-payments/${id}`),
}

export const summaryApi = {
  get: (params = {}) => api.get('/payments/summary', { params }).then((r) => r.data),
}

export const usersApi = {
  list: () => api.get('/users').then((r) => r.data),
  create: (payload) => api.post('/users', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/users/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/users/${id}`),
}

export const auditApi = {
  list: (params = {}) => api.get('/audit-logs', { params }).then((r) => r.data),
}
