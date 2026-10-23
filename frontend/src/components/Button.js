import { h } from '../utils/dom.js'

const VARIANTS = {
  primary: 'btn-primary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
}

/**
 * Button('Сохранить', onClick, { variant: 'primary' | 'ghost' | 'danger', small: true, type: 'submit' })
 */
export function Button(text, onClick, { variant = 'primary', small = false, type = 'button', ...attrs } = {}) {
  const size = small ? ' px-3! py-1.5! text-xs!' : ''
  return h('button', { type, class: VARIANTS[variant] + size, onclick: onClick, ...attrs }, text)
}

/**
 * Пока выполняется async-действие, кнопка заблокирована и показывает текст загрузки.
 */
export async function withLoading(button, action, loadingText = 'Сохраняем…') {
  const original = button.textContent
  button.disabled = true
  button.textContent = loadingText
  try {
    return await action()
  } finally {
    button.disabled = false
    button.textContent = original
  }
}
