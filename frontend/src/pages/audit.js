import { errorText } from '../api/client.js'
import { auditApi } from '../api/endpoints.js'
import { EmptyState, ErrorBox, Loading, PageHeader } from '../components/Layout.js'
import { h, mount } from '../utils/dom.js'
import { dateRu, dateTime } from '../utils/format.js'

const ACTIONS = {
  'auth.login': 'Вход',
  'auth.login_failed': 'Неудачный вход',
  'auth.logout': 'Выход',
  'recurring_payment.create': 'Добавил платёж',
  'recurring_payment.delete': 'Прекратил платёж',
  'occurrence.mark_paid': 'Отметил оплату',
  'occurrence.mark_unpaid': 'Отменил оплату',
  'occurrence.change_paid_at': 'Изменил дату оплаты',
  'user.create': 'Создал пользователя',
  'user.update': 'Изменил пользователя',
  'user.delete': 'Удалил пользователя',
}

/** Человекочитаемая расшифровка деталей записи */
function describe(entry) {
  const d = entry.details || {}
  switch (entry.action) {
    case 'recurring_payment.create':
      return `${d.name}: ${d.amount} ${d.currency}, с ${dateRu(d.first_due_date)}`
    case 'recurring_payment.delete':
      return d.name
    case 'occurrence.mark_paid':
    case 'occurrence.mark_unpaid':
    case 'occurrence.change_paid_at':
      return `${d.payment} за ${dateRu(d.due_date)}${d.after?.paid_at ? `, дата оплаты ${dateRu(d.after.paid_at)}` : ''}`
    case 'user.create':
    case 'user.delete':
    case 'user.update':
      return d.username
    default:
      return ''
  }
}

export async function renderAudit(container) {
  const listBox = h('section')
  mount(container, PageHeader('Журнал', 'Входы в систему и действия с платежами и пользователями.'), listBox)

  async function load() {
    mount(listBox, Loading())
    try {
      const entries = await auditApi.list({ limit: 200 })
      if (!entries.length) return mount(listBox, EmptyState('Записей пока нет.'))
      mount(
        listBox,
        h(
          'ul',
          { class: 'divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface text-sm' },
          entries.map((e) =>
            h(
              'li',
              { class: 'grid gap-1 px-4 py-3 sm:grid-cols-[10rem_8rem_1fr]' },
              h('span', { class: 'text-muted' }, dateTime(e.created_at)),
              h('span', { class: 'font-semibold' }, e.username || '—'),
              h(
                'span',
                {},
                h('span', { class: e.action === 'auth.login_failed' ? 'font-medium text-overdue' : 'font-medium' }, ACTIONS[e.action] || e.action),
                describe(e) ? h('span', { class: 'text-muted' }, `: ${describe(e)}`) : null,
              ),
            ),
          ),
        ),
      )
    } catch (err) {
      mount(listBox, ErrorBox(errorText(err), load))
    }
  }

  await load()
}
