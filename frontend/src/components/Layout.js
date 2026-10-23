import { authApi } from '../api/endpoints.js'
import { session } from '../state/session.js'
import { h } from '../utils/dom.js'

const NAV = [
  { href: '#/', label: 'Платежи' },
  { href: '#/recurring', label: 'Регулярные', admin: true },
  { href: '#/users', label: 'Пользователи', admin: true },
  { href: '#/audit', label: 'Журнал', admin: true },
]

async function logout() {
  try {
    await authApi.logout()
  } catch {
    /* даже если сервер недоступен — выходим локально */
  }
  session.clear()
  window.location.hash = '#/login'
}

/** Каркас страницы: шапка с навигацией + контент */
export function Layout(currentPath, content) {
  const user = session.user
  const links = NAV.filter((item) => !item.admin || session.isAdmin).map((item) => {
    const active = item.href === `#${currentPath}`
    return h(
      'a',
      {
        href: item.href,
        class: `rounded-md px-3 py-2 text-sm font-medium ${
          active ? 'bg-ink text-white' : 'text-muted hover:bg-line/60 hover:text-ink'
        }`,
        'aria-current': active ? 'page' : null,
      },
      item.label,
    )
  })

  return h(
    'div',
    { class: 'min-h-screen' },
    h(
      'header',
      { class: 'border-b border-line bg-surface' },
      h(
        'div',
        { class: 'mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3' },
        h('a', { href: '#/', class: 'text-lg font-extrabold tracking-tight' }, 'Invoice Keeper'),
        h('nav', { class: 'flex flex-wrap gap-1', 'aria-label': 'Разделы' }, links),
        h(
          'div',
          { class: 'ml-auto flex items-center gap-3 text-sm' },
          h(
            'span',
            { class: 'text-muted' },
            user.username,
            session.isAdmin ? h('span', { class: 'ml-1.5 rounded bg-accent/10 px-1.5 py-0.5 text-xs font-semibold text-accent' }, 'админ') : null,
          ),
          h('button', { class: 'font-medium text-muted hover:text-ink', onclick: logout }, 'Выйти'),
        ),
      ),
    ),
    h('main', { class: 'mx-auto max-w-6xl px-4 py-8' }, content),
  )
}

/** Заголовок страницы с действием справа */
export function PageHeader(title, subtitle, action) {
  return h(
    'div',
    { class: 'mb-6 flex flex-wrap items-end justify-between gap-4' },
    h(
      'div',
      {},
      h('h1', { class: 'text-2xl font-extrabold tracking-tight sm:text-3xl' }, title),
      subtitle ? h('p', { class: 'mt-1 text-muted' }, subtitle) : null,
    ),
    action || null,
  )
}

export function EmptyState(text, action) {
  return h(
    'div',
    { class: 'rounded-xl border border-dashed border-line bg-surface px-6 py-12 text-center' },
    h('p', { class: 'mb-4 text-muted' }, text),
    action || null,
  )
}

export function Loading() {
  return h('p', { class: 'py-12 text-center text-muted' }, 'Загружаем…')
}

export function ErrorBox(text, onRetry) {
  return h(
    'div',
    { class: 'rounded-xl border border-overdue/30 bg-overdue-soft px-6 py-6 text-overdue' },
    h('p', { class: 'font-medium' }, text),
    onRetry ? h('button', { class: 'mt-3 underline', onclick: onRetry }, 'Повторить') : null,
  )
}
