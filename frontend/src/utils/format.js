const CURRENCY_SIGN = { RUB: '₽', USD: '$', EUR: '€' }

/** "85000.00", "RUB" → "85 000,00 ₽" */
export function money(amount, currency) {
  const value = Number(amount)
  const text = new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
  return `${text} ${CURRENCY_SIGN[currency] || currency}`
}

/** "2026-10-25" → Date в локальной полуночи (без сдвига часовых поясов) */
export function parseDate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** "2026-10-25" → "25.10.2026" */
export function dateRu(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

/** "2026-10-25" → "25 октября" */
export function dateLong(iso) {
  return parseDate(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

/** "2026-10-25" → "окт" */
export function monthShort(iso) {
  return parseDate(iso).toLocaleDateString('ru-RU', { month: 'short' }).replace('.', '')
}

/** ISO-время с сервера → "23.10.2026, 21:04" в часовом поясе браузера */
export function dateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Сегодня в формате YYYY-MM-DD по локальному времени */
export function todayIso() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** plural(3, 'день', 'дня', 'дней') → "дня" */
export function plural(n, one, few, many) {
  const n10 = n % 10
  const n100 = n % 100
  if (n10 === 1 && n100 !== 11) return one
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return few
  return many
}

export const days = (n) => `${n} ${plural(n, 'день', 'дня', 'дней')}`

export const PERIOD_LABEL = {
  monthly: 'Ежемесячно',
  quarterly: 'Раз в квартал',
  yearly: 'Раз в год',
}

export const CURRENCIES = ['RUB', 'USD', 'EUR']
