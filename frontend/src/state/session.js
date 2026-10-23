/** Текущая сессия: токен в localStorage, пользователь — в памяти. */
const TOKEN_KEY = 'ik_token'

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export const session = {
  token: readToken(),
  user: null,

  set(token, user) {
    this.token = token
    this.user = user
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* приватный режим — живём без сохранения */
    }
  },

  clear() {
    this.token = null
    this.user = null
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ничего */
    }
  },

  get isAdmin() {
    return this.user?.role === 'admin'
  },
}
