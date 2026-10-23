import { errorText, fieldErrors } from '../api/client.js'
import { occurrencesApi, recurringApi } from '../api/endpoints.js'
import { formData, h } from '../utils/dom.js'
import { CURRENCIES, PERIOD_LABEL, dateLong, dateRu, money, parseDate, todayIso } from '../utils/format.js'
import { Button, withLoading } from './Button.js'
import { openModal } from './Modal.js'
import { toast } from './Toast.js'

function field(label, input, hint) {
  const error = h('p', { class: 'mt-1 hidden text-sm text-overdue', 'data-error-for': input.name })
  return h(
    'div',
    {},
    h('label', { class: 'label', for: input.id }, label),
    input,
    hint ? h('p', { class: 'mt-1 text-xs text-muted' }, hint) : null,
    error,
  )
}

function showErrors(form, errors) {
  form.querySelectorAll('[data-error-for]').forEach((el) => {
    const message = errors[el.dataset.errorFor]
    el.textContent = message || ''
    el.classList.toggle('hidden', !message)
  })
}

/** Модалка «Новый регулярный платёж» (администратор) */
export function openCreatePaymentModal({ onCreated }) {
  const submit = h('button', { type: 'submit', class: 'btn-primary' }, 'Добавить платёж')
  const generalError = h('p', { class: 'hidden text-sm text-overdue', role: 'alert' })

  const form = h(
    'form',
    { class: 'space-y-4', novalidate: true },
    field('Название', h('input', { id: 'rp-name', name: 'name', class: 'field', placeholder: 'Аренда офиса', required: true })),
    h(
      'div',
      { class: 'grid grid-cols-[1fr_7rem] gap-3' },
      field(
        'Сумма',
        h('input', { id: 'rp-amount', name: 'amount', class: 'field', inputmode: 'decimal', placeholder: '50000', required: true }),
      ),
      field(
        'Валюта',
        h('select', { id: 'rp-currency', name: 'currency', class: 'field' }, CURRENCIES.map((c) => h('option', { value: c }, c))),
      ),
    ),
    field(
      'Дата ближайшей оплаты',
      h('input', { id: 'rp-date', name: 'first_due_date', type: 'date', class: 'field', value: todayIso(), required: true }),
      'Если такого числа нет в месяце, оплата переносится на последний день месяца.',
    ),
    field(
      'Периодичность',
      h(
        'select',
        { id: 'rp-period', name: 'period', class: 'field' },
        Object.entries(PERIOD_LABEL).map(([value, label]) => h('option', { value }, label)),
      ),
    ),
    generalError,
    h('div', { class: 'flex justify-end gap-2 pt-2' }, Button('Отмена', () => modal.close(), { variant: 'ghost' }), submit),
  )

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    showErrors(form, {})
    generalError.classList.add('hidden')
    const data = formData(form)
    data.amount = data.amount.replace(/\s/g, '').replace(',', '.')
    try {
      const created = await withLoading(submit, () => recurringApi.create(data))
      modal.close()
      toast(`Платёж «${created.name}» добавлен`)
      const next = created.next_occurrence
      if (next) {
        const left = Math.round((parseDate(next.due_date) - parseDate(todayIso())) / 86400000)
        if (left >= 0 && left <= 3) toast('Срок ближе трёх дней: напоминание уходит в Telegram сразу', 'info')
      }
      onCreated?.(created)
    } catch (err) {
      const errors = fieldErrors(err)
      showErrors(form, errors)
      if (!Object.keys(errors).length) {
        generalError.textContent = errorText(err)
        generalError.classList.remove('hidden')
      }
    }
  })

  const modal = openModal({ title: 'Новый регулярный платёж', body: form })
}

/**
 * Модалка отметки оплаты / исправления даты.
 * mode: 'pay' — отметить оплату, 'edit' — исправить фактическую дату
 */
export function openPayModal(occ, { mode = 'pay', onSaved }) {
  const isEdit = mode === 'edit'
  const submit = h('button', { type: 'submit', class: 'btn-primary' }, isEdit ? 'Сохранить дату' : 'Отметить оплату')
  const error = h('p', { class: 'hidden text-sm text-overdue', role: 'alert' })
  const dateInput = h('input', {
    id: 'paid-at',
    name: 'paid_at',
    type: 'date',
    class: 'field',
    value: occ.paid_at || todayIso(),
    max: todayIso(),
    required: true,
  })
  const hint = h('p', { class: 'mt-1 text-xs text-muted' })
  const updateHint = () => {
    const value = dateInput.value
    if (!value) return (hint.textContent = '')
    hint.textContent = value <= occ.due_date ? 'Вовремя: оплата не позже срока.' : 'Позже срока: период будет отмечен как просроченный.'
  }
  dateInput.addEventListener('input', updateHint)
  updateHint()

  const form = h(
    'form',
    { class: 'space-y-4' },
    h(
      'div',
      { class: 'rounded-lg bg-paper px-4 py-3' },
      h('p', { class: 'font-semibold' }, occ.name),
      h('p', { class: 'text-sm text-muted' }, `${money(occ.amount, occ.currency)}, срок ${dateLong(occ.due_date)}`),
    ),
    h('div', {}, h('label', { class: 'label', for: 'paid-at' }, 'Фактическая дата оплаты'), dateInput, hint),
    error,
    h('div', { class: 'flex justify-end gap-2 pt-2' }, Button('Отмена', () => modal.close(), { variant: 'ghost' }), submit),
  )

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    error.classList.add('hidden')
    try {
      const saved = await withLoading(submit, () =>
        isEdit ? occurrencesApi.changePaidAt(occ.id, dateInput.value) : occurrencesApi.markPaid(occ.id, dateInput.value),
      )
      modal.close()
      toast(isEdit ? `Дата оплаты изменена на ${dateRu(saved.paid_at)}` : `«${saved.name}» оплачено`)
      onSaved?.(saved)
    } catch (err) {
      error.textContent = errorText(err)
      error.classList.remove('hidden')
    }
  })

  const modal = openModal({ title: isEdit ? 'Исправить дату оплаты' : 'Отметить оплату', body: form })
}
