import { errorText } from '../api/client.js'
import { recurringApi } from '../api/endpoints.js'
import { Button } from '../components/Button.js'
import { EmptyState, ErrorBox, Loading, PageHeader } from '../components/Layout.js'
import { confirmDialog } from '../components/Modal.js'
import { StateBadge } from '../components/PaymentState.js'
import { openCreatePaymentModal } from '../components/PaymentForms.js'
import { toast } from '../components/Toast.js'
import { h, mount } from '../utils/dom.js'
import { PERIOD_LABEL, dateRu, dateTime, money } from '../utils/format.js'

const view = { showInactive: false }

/** Регулярные платежи (шаблоны) — только администратор */
export async function renderRecurring(container) {
  const listBox = h('section')
  const toggle = h(
    'label',
    { class: 'mb-4 inline-flex cursor-pointer items-center gap-2 text-sm text-muted' },
    h('input', {
      type: 'checkbox',
      checked: view.showInactive,
      class: 'size-4 accent-accent',
      onchange: (e) => {
        view.showInactive = e.target.checked
        load()
      },
    }),
    'Показывать прекращённые',
  )

  mount(
    container,
    PageHeader(
      'Регулярные платежи',
      'Аренда, серверы, подписки. Периоды и напоминания создаются автоматически.',
      Button('Добавить платёж', () => openCreatePaymentModal({ onCreated: load })),
    ),
    toggle,
    listBox,
  )

  async function load() {
    mount(listBox, Loading())
    try {
      render(await recurringApi.list(view.showInactive))
    } catch (err) {
      mount(listBox, ErrorBox(errorText(err), load))
    }
  }

  function render(items) {
    if (!items.length) {
      return mount(
        listBox,
        EmptyState('Регулярных платежей нет.', Button('Добавить платёж', () => openCreatePaymentModal({ onCreated: load }))),
      )
    }

    mount(
      listBox,
      h(
        'div',
        { class: 'overflow-x-auto rounded-xl border border-line bg-surface' },
        h(
          'table',
          { class: 'w-full min-w-[44rem] text-left text-sm' },
          h(
            'thead',
            { class: 'border-b border-line text-muted' },
            h(
              'tr',
              {},
              ['Название', 'Сумма', 'Периодичность', 'Ближайшая оплата', ''].map((t) =>
                h('th', { class: 'px-4 py-3 font-medium' }, t),
              ),
            ),
          ),
          h('tbody', { class: 'divide-y divide-line' }, items.map(Row)),
        ),
      ),
    )
  }

  function Row(rp) {
    const next = rp.next_occurrence
    let nextCell
    if (!rp.is_active) nextCell = h('span', { class: 'text-muted' }, `Прекращён ${dateTime(rp.ended_at)}`)
    else if (next) {
      nextCell = h(
        'div',
        { class: 'flex flex-wrap items-center gap-2' },
        h('span', { class: 'font-medium' }, dateRu(next.due_date)),
        StateBadge({ ...next, overdue_days: overdueDays(next.due_date), days_until_due: -overdueDays(next.due_date) }),
      )
    } else nextCell = h('span', { class: 'text-muted' }, '—')

    return h(
      'tr',
      { class: rp.is_active ? '' : 'opacity-60' },
      h('td', { class: 'px-4 py-3 font-semibold' }, rp.name),
      h('td', { class: 'px-4 py-3 font-bold whitespace-nowrap' }, money(rp.amount, rp.currency)),
      h('td', { class: 'px-4 py-3' }, PERIOD_LABEL[rp.period] || rp.period, h('span', { class: 'text-muted' }, `, ${rp.anchor_day}-го`)),
      h('td', { class: 'px-4 py-3' }, nextCell),
      h(
        'td',
        { class: 'px-4 py-3 text-right' },
        rp.is_active ? Button('Прекратить', () => stop(rp), { variant: 'danger', small: true }) : null,
      ),
    )
  }

  async function stop(rp) {
    const ok = await confirmDialog({
      title: `Прекратить «${rp.name}»?`,
      text: 'Новые периоды и напоминания больше не появятся. Оплаченные и уже наступившие периоды останутся в истории.',
      confirmText: 'Прекратить платёж',
      danger: true,
    })
    if (!ok) return
    try {
      await recurringApi.remove(rp.id)
      toast(`Платёж «${rp.name}» прекращён`)
      load()
    } catch (err) {
      toast(errorText(err), 'error')
    }
  }

  await load()
}

/** Дней от срока до сегодня (>0 — срок прошёл) */
function overdueDays(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  const due = new Date(y, m - 1, d)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((today - due) / 86400000)
}
