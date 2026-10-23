import { h } from '../utils/dom.js'
import { dateRu, days, monthShort } from '../utils/format.js'

/** Цвета состояний периода (state из API) */
export const STATE_COLORS = {
  pending: { strip: 'var(--color-pending)', badge: 'bg-pending-soft text-pending' },
  overdue: { strip: 'var(--color-overdue)', badge: 'bg-overdue-soft text-overdue' },
  paid: { strip: 'var(--color-paid)', badge: 'bg-paid-soft text-paid' },
  paid_late: { strip: 'var(--color-paid)', badge: 'bg-paid-soft text-paid' },
}

/** Отрывной календарь со сроком оплаты; полоска сверху — цвет состояния */
export function DateBlock(isoDate, state) {
  const day = Number(isoDate.slice(8, 10))
  return h(
    'div',
    { class: 'date-block', title: `Срок оплаты ${dateRu(isoDate)}` },
    h('div', { class: 'date-block__strip', style: `background:${STATE_COLORS[state]?.strip}` }),
    h('div', { class: 'date-block__day' }, day),
    h('div', { class: 'date-block__month' }, monthShort(isoDate)),
  )
}

/** Текст состояния: «Через 2 дня», «Просрочено на 5 дней», «Оплачено 22.10.2026» */
export function stateText(occ) {
  switch (occ.state) {
    case 'overdue':
      return `Просрочено на ${days(occ.overdue_days)}`
    case 'pending':
      if (occ.days_until_due === 0) return 'Срок сегодня'
      if (occ.days_until_due === 1) return 'Срок завтра'
      return `Через ${days(occ.days_until_due)}`
    case 'paid':
      return 'Оплачено вовремя'
    case 'paid_late':
      return `Оплачено позже на ${days(occ.overdue_days)}`
    default:
      return occ.state
  }
}

export function StateBadge(occ) {
  return h(
    'span',
    { class: `inline-block rounded-full px-2.5 py-1 text-xs font-semibold whitespace-nowrap ${STATE_COLORS[occ.state]?.badge}` },
    stateText(occ),
  )
}
