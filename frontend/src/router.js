/**
 * Простой hash-роутер: #/, #/recurring, #/users, #/audit, #/login.
 * Новая страница = функция renderXxx(container) + строка в ROUTES.
 */
import { authApi } from './api/endpoints.js'
import { Layout } from './components/Layout.js'
import { renderAudit } from './pages/audit.js'
import { renderLogin } from './pages/login.js'
import { renderPayments } from './pages/payments.js'
import { renderRecurring } from './pages/recurring.js'
import { renderUsers } from './pages/users.js'
import { session } from './state/session.js'
import { h, mount } from './utils/dom.js'

const ROUTES = {
  '/': { render: renderPayments, title: 'Платежи' },
  '/recurring': { render: renderRecurring, title: 'Регулярные платежи', admin: true },
  '/users': { render: renderUsers, title: 'Пользователи', admin: true },
  '/audit': { render: renderAudit, title: 'Журнал', admin: true },
}

function currentPath() {
  return window.location.hash.replace(/^#/, '') || '/'
}

async function ensureUser() {
  if (!session.token) return false
  if (session.user) return true
  try {
    session.user = await authApi.me()
    return true
  } catch {
    session.clear()
    return false
  }
}

export async function render(root) {
  const path = currentPath()

  if (path === '/login') {
    if (await ensureUser()) return (window.location.hash = '#/')
    document.title = 'Вход — Invoice Keeper'
    return renderLogin(root)
  }

  if (!(await ensureUser())) return (window.location.hash = '#/login')

  const route = ROUTES[path]
  if (!route || (route.admin && !session.isAdmin)) return (window.location.hash = '#/')

  document.title = `${route.title} — Invoice Keeper`
  const content = h('div')
  mount(root, Layout(path, content))
  await route.render(content)
}

export function startRouter(root) {
  window.addEventListener('hashchange', () => render(root))
  render(root)
}
