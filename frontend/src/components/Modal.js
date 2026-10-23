import { h } from '../utils/dom.js'
import { Button } from './Button.js'

/**
 * Модальное окно. Возвращает { close }.
 * openModal({ title, body: Node, onClose })
 */
export function openModal({ title, body, onClose }) {
  const root = document.getElementById('modal-root')
  const previouslyFocused = document.activeElement

  function close() {
    document.removeEventListener('keydown', onKey)
    overlay.remove()
    previouslyFocused?.focus?.()
    onClose?.()
  }

  function onKey(e) {
    if (e.key === 'Escape') close()
  }

  const titleId = `modal-title-${Date.now()}`
  const overlay = h(
    'div',
    {
      class: 'fixed inset-0 z-40 flex items-end justify-center bg-ink/40 p-4 sm:items-center',
      onmousedown: (e) => e.target === overlay && close(),
    },
    h(
      'div',
      {
        class: 'modal-panel w-full max-w-md rounded-xl bg-surface p-6 shadow-xl',
        role: 'dialog',
        'aria-modal': 'true',
        'aria-labelledby': titleId,
      },
      h(
        'div',
        { class: 'mb-4 flex items-start justify-between gap-4' },
        h('h2', { id: titleId, class: 'text-lg font-bold' }, title),
        h(
          'button',
          { class: 'text-2xl leading-none text-muted hover:text-ink', 'aria-label': 'Закрыть', onclick: close },
          '×',
        ),
      ),
      body,
    ),
  )

  root.append(overlay)
  document.addEventListener('keydown', onKey)
  overlay.querySelector('input, select, button[type=submit]')?.focus()
  return { close }
}

/** Подтверждение действия. Возвращает Promise<boolean>. */
export function confirmDialog({ title, text, confirmText = 'Подтвердить', danger = false }) {
  return new Promise((resolve) => {
    let answered = false
    const finish = (value) => {
      answered = true
      resolve(value)
      modal.close()
    }
    const modal = openModal({
      title,
      onClose: () => !answered && resolve(false),
      body: h(
        'div',
        {},
        h('p', { class: 'mb-6 text-muted' }, text),
        h(
          'div',
          { class: 'flex justify-end gap-2' },
          Button('Отмена', () => finish(false), { variant: 'ghost' }),
          Button(confirmText, () => finish(true), { variant: danger ? 'danger' : 'primary', type: 'submit' }),
        ),
      ),
    })
  })
}
