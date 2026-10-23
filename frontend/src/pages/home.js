import { api } from '../api/client.js'
import { Button } from '../components/Button.js'

export async function renderHome(root) {
  root.innerHTML = `
    <div class="min-h-screen flex flex-col items-center justify-center gap-6">
      <h1 id="message" class="text-4xl font-bold text-white">Загрузка...</h1>
      <div id="actions"></div>
    </div>
  `
  const title = root.querySelector('#message')
  const actions = root.querySelector('#actions')

  async function loadMessage() {
    title.textContent = 'Загрузка...'
    try {
      const { data } = await api.get('/hello')
      title.textContent = data.message
    } catch {
      title.textContent = 'Не удалось получить данные с сервера'
    }
  }

  actions.append(Button('Обновить', loadMessage))

  await loadMessage()
}