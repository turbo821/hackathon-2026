import { errorText } from '../api/client.js'
import { occurrencesApi, summaryApi } from '../api/endpoints.js'
import { Button } from '../components/Button.js'
import { EmptyState, ErrorBox, Loading, PageHeader } from '../components/Layout.js'
import { confirmDialog } from '../components/Modal.js'
import { DateBlock, StateBadge } from '../components/PaymentState.js'
import { openCreatePaymentModal, openPayModal } from '../components/PaymentForms.js'
import { toast } from '../components/Toast.js'
import { session } from '../state/session.js'
import { h, mount } from '../utils/dom.js'
import { CURRENCIES, dateRu, money, plural } from '../utils/format.js'

const FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'unpaid', label: 'К оплате', params: { state: 'unpaid_all' } },
  { id: 'overdue', label: 'Просрочено', params: { state: 'overdue' } },
  { id: 'paid', label: 'Оплачено', params: { status: 'paid' } },
]

// Фильтры переживают перерисовку страницы
const view = { filter: 'all', currency: '' }

export async function renderPayments(container) {
  const totalsBox = h('section', { class: 'mb-8', 'aria-label': 'Итоги по валютам' })
  const filtersBox = h('div', { class: 'mb-4 flex flex-wrap items-center gap-2' })
  const listBox = h('section', { 'aria-live': 'polite' })
  const subtitle = h('p', { class: 'mt-1 text-muted' })

  const header = PageHeader('Платежи', null, session.isAdmin
    ? Button('Добавить платёж', () => openCreatePaymentModal({ onCreated: reload }))
    : null)
  header.firstChild.append(subtitle)

  mount(container, header, totalsBox, filtersBox, listBox)

  async function reload() {
    await Promise.all([loadTotals(), loadList()])
  }

  // ---------- Итоги по валютам ----------
  async function loadTotals() {
    try {
      const summary = await summaryApi.get()
      renderTotals(summary)
    } catch (err) {
      mount(totalsBox, ErrorBox(errorText(err), loadTotals))
    }
  }

  function renderTotals(summary) {
    const overdueCount = summary.currencies.reduce((n, c) => n + c.count_overdue, 0)
    subtitle.textContent = overdueCount
      ? `${overdueCount} ${plural(overdueCount, 'платёж просрочен', 'платежа просрочено', 'платежей просрочено')}`
      : 'Просроченных платежей нет'
    subtitle.className = overdueCount ? 'mt-1 font-medium text-overdue' : 'mt-1 text-muted'

    mount(
      totalsBox,
      h(
        'div',
        { class: 'grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3' },
        summary.currencies.map((c) =>
          h(
            'div',
            { class: 'bg-surface px-5 py-4' },
            h('p', { class: 'text-sm font-medium text-muted' }, `К оплате в ${c.currency}`),
            h('p', { class: 'mt-1 text-2xl font-extrabold tracking-tight' }, money(c.unpaid, c.currency)),
            h(
              'p',
              { class: 'mt-1 text-sm' },
              Number(c.overdue) > 0
                ? h('span', { class: 'font-medium text-overdue' }, `просрочено ${money(c.overdue, c.currency)}`)
                : h('span', { class: 'text-muted' }, 'без просрочек'),
            ),
            h('p', { class: 'text-sm text-muted' }, `оплачено ${money(c.paid, c.currency)}`),
          ),
        ),
      ),
    )
  }

  // ---------- Фильтры ----------
  function renderFilters() {
    const tabs = FILTERS.map((f) =>
      h(
        'button',
        {
          class: `rounded-full px-4 py-1.5 text-sm font-medium ${
            view.filter === f.id ? 'bg-ink text-white' : 'bg-surface text-muted hover:text-ink border border-line'
          }`,
          'aria-pressed': view.filter === f.id ? 'true' : 'false',
          onclick: () => {
            view.filter = f.id
            renderFilters()
            loadList()
          },
        },
        f.label,
      ),
    )
    const currency = h(
      'select',
      {
        class: 'field ml-auto w-auto! py-1.5!',
        'aria-label': 'Валюта',
        onchange: (e) => {
          view.currency = e.target.value
          loadList()
        },
      },
      h('option', { value: '' }, 'Все валюты'),
      CURRENCIES.map((c) => h('option', { value: c, selected: view.currency === c }, c)),
    )
    mount(filtersBox, tabs, currency)
  }

  // ---------- Список периодов ----------
  async function loadList() {
    mount(listBox, Loading())
    const filter = FILTERS.find((f) => f.id === view.filter)
    const params = { ...(filter.params || {}), ...(view.currency && { currency: view.currency }) }
    try {
      const items = await occurrencesApi.list(params)
      renderList(items)
    } catch (err) {
      mount(listBox, ErrorBox(errorText(err), loadList))
    }
  }

  function renderList(items) {
    if (!items.length) {
      const text = view.filter === 'all' ? 'Платежей пока нет.' : 'В этом разделе пусто.'
      const action = session.isAdmin && view.filter === 'all'
        ? Button('Добавить первый платёж', () => openCreatePaymentModal({ onCreated: reload }))
        : null
      return mount(listBox, EmptyState(session.isAdmin ? text : `${text} Платежи добавляет администратор.`, action))
    }

    if (view.filter !== 'all') {
      const sorted = view.filter === 'paid' ? [...items].reverse() : items
      return mount(listBox, List(sorted))
    }

    // «Все»: сначала что нужно оплатить, потом история (свежие сверху)
    const unpaid = items.filter((o) => o.status === 'unpaid')
    const paid = items.filter((o) => o.status === 'paid').reverse()
    mount(
      listBox,
      unpaid.length ? Section('Нужно оплатить', unpaid) : null,
      paid.length ? Section('История оплат', paid) : null,
    )
  }

  function Section(title, items) {
    return h('div', { class: 'mb-8' }, h('h2', { class: 'mb-3 text-lg font-bold' }, title), List(items))
  }

  function List(items) {
    return h('ul', { class: 'divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface' }, items.map(Row))
  }

  function Row(occ) {
    const actions = occ.status === 'unpaid'
      ? [Button('Отметить оплату', () => openPayModal(occ, { onSaved: reload }), { small: true })]
      : [
          Button('Изменить дату', () => openPayModal(occ, { mode: 'edit', onSaved: reload }), { variant: 'ghost', small: true }),
          Button('Отменить оплату', () => cancelPayment(occ), { variant: 'ghost', small: true }),
        ]

    const meta = [`Срок ${dateRu(occ.due_date)}`]
    if (occ.paid_at) meta.push(`оплачено ${dateRu(occ.paid_at)}`)
    if (occ.marked_by) meta.push(`отметил ${occ.marked_by}`)
    if (!occ.recurring_payment_active) meta.push('платёж прекращён')

    return h(
      'li',
      { class: 'flex items-start gap-4 px-4 py-3 lg:items-center' },
      DateBlock(occ.due_date, occ.state),
      h(
        'div',
        { class: 'grid min-w-0 flex-1 items-center gap-x-4 gap-y-2 lg:grid-cols-[minmax(0,1fr)_8.5rem_13rem_17rem]' },
        h(
          'div',
          { class: 'min-w-0' },
          h('p', { class: 'font-semibold break-words' }, occ.name),
          h('p', { class: 'text-sm text-muted' }, meta.join(', ')),
        ),
        h('p', { class: 'font-bold whitespace-nowrap lg:text-right' }, money(occ.amount, occ.currency)),
        h('div', {}, StateBadge(occ)),
        h('div', { class: 'flex flex-wrap gap-2 lg:justify-end' }, actions),
      ),
    )
  }

  async function cancelPayment(occ) {
    const ok = await confirmDialog({
      title: 'Отменить оплату?',
      text: `«${occ.name}» за ${dateRu(occ.due_date)} снова станет неоплаченным, дата оплаты очистится.`,
      confirmText: 'Отменить оплату',
      danger: true,
    })
    if (!ok) return
    try {
      await occurrencesApi.markUnpaid(occ.id)
      toast('Оплата отменена')
      reload()
    } catch (err) {
      toast(errorText(err), 'error')
    }
  }

  renderFilters()
  await reload()
}
