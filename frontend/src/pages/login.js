import { errorText } from '../api/client.js'
import { authApi } from '../api/endpoints.js'
import { withLoading } from '../components/Button.js'
import { session } from '../state/session.js'
import { formData, h, mount } from '../utils/dom.js'

export function renderLogin(root) {
  const error = h('p', { class: 'hidden rounded-md bg-overdue-soft px-3 py-2 text-sm text-overdue', role: 'alert' })
  const submit = h('button', { type: 'submit', class: 'btn-primary w-full' }, 'Войти')

  async function onSubmit(e) {
    e.preventDefault()
    error.classList.add('hidden')
    const { username, password } = formData(e.target)
    try {
      await withLoading(submit, async () => {
        const data = await authApi.login(username.trim(), password)
        session.set(data.access_token, data.user)
        window.location.hash = '#/'
      }, 'Входим…')
    } catch (err) {
      error.textContent = errorText(err)
      error.classList.remove('hidden')
    }
  }

  mount(
    root,
    h(
      'div',
      { class: 'flex min-h-screen items-center justify-center px-4' },
      h(
        'div',
        { class: 'w-full max-w-sm' },
        h('h1', { class: 'text-3xl font-extrabold tracking-tight' }, 'Invoice Keeper'),
        h('p', { class: 'mt-2 mb-8 text-muted' }, 'Аренда, серверы и подписки: что оплатить и когда.'),
        h(
          'form',
          { class: 'space-y-4 rounded-xl border border-line bg-surface p-6', onsubmit: onSubmit },
          h(
            'div',
            {},
            h('label', { class: 'label', for: 'username' }, 'Логин'),
            h('input', { id: 'username', name: 'username', class: 'field', autocomplete: 'username', required: true }),
          ),
          h(
            'div',
            {},
            h('label', { class: 'label', for: 'password' }, 'Пароль'),
            h('input', {
              id: 'password',
              name: 'password',
              type: 'password',
              class: 'field',
              autocomplete: 'current-password',
              required: true,
            }),
          ),
          error,
          submit,
        ),
      ),
    ),
  )
  root.querySelector('#username').focus()
}
