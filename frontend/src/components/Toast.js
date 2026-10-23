import { h } from '../utils/dom.js'

const STYLES = {
  success: 'border-paid/30 bg-paid-soft text-paid',
  error: 'border-overdue/30 bg-overdue-soft text-overdue',
  info: 'border-line bg-surface text-ink',
}

/** toast('Оплата отмечена') / toast('Не удалось…', 'error') */
export function toast(message, type = 'success', timeout = 3500) {
  const root = document.getElementById('toast-root')
  const el = h(
    'div',
    { class: `max-w-sm rounded-md border px-4 py-3 text-sm font-medium shadow-sm ${STYLES[type]}`, role: 'status' },
    message,
  )
  root.append(el)
  setTimeout(() => el.remove(), timeout)
}
