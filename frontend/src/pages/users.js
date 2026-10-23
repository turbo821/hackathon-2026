import { errorText, fieldErrors } from '../api/client.js'
import { usersApi } from '../api/endpoints.js'
import { Button, withLoading } from '../components/Button.js'
import { ErrorBox, Loading, PageHeader } from '../components/Layout.js'
import { confirmDialog, openModal } from '../components/Modal.js'
import { toast } from '../components/Toast.js'
import { session } from '../state/session.js'
import { formData, h, mount } from '../utils/dom.js'
import { dateTime } from '../utils/format.js'

/** Пользователи — только администратор */
export async function renderUsers(container) {
  const listBox = h('section')
  mount(
    container,
    PageHeader(
      'Пользователи',
      'Пользователи видят все платежи, отмечают оплату и исправляют дату.',
      Button('Добавить пользователя', () => openUserModal()),
    ),
    listBox,
  )

  async function load() {
    mount(listBox, Loading())
    try {
      render(await usersApi.list())
    } catch (err) {
      mount(listBox, ErrorBox(errorText(err), load))
    }
  }

  function render(users) {
    mount(
      listBox,
      h(
        'ul',
        { class: 'divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface' },
        users.map((u) =>
          h(
            'li',
            { class: 'flex flex-wrap items-center gap-3 px-4 py-3' },
            h(
              'div',
              { class: 'min-w-0 flex-1' },
              h(
                'p',
                { class: 'font-semibold' },
                u.username,
                u.id === session.user.id ? h('span', { class: 'ml-2 text-sm font-normal text-muted' }, '(вы)') : null,
              ),
              h(
                'p',
                { class: 'text-sm text-muted' },
                u.role === 'admin' ? 'Администратор, задаётся в .env' : `Пользователь с ${dateTime(u.created_at)}`,
              ),
            ),
            u.role === 'admin'
              ? null
              : h(
                  'div',
                  { class: 'flex gap-2' },
                  Button('Изменить', () => openUserModal(u), { variant: 'ghost', small: true }),
                  Button('Удалить', () => remove(u), { variant: 'danger', small: true }),
                ),
          ),
        ),
      ),
    )
  }

  function openUserModal(user = null) {
    const isEdit = Boolean(user)
    const submit = h('button', { type: 'submit', class: 'btn-primary' }, isEdit ? 'Сохранить' : 'Создать пользователя')
    const error = h('p', { class: 'hidden text-sm text-overdue', role: 'alert' })

    const form = h(
      'form',
      { class: 'space-y-4' },
      h(
        'div',
        {},
        h('label', { class: 'label', for: 'u-name' }, 'Логин'),
        h('input', { id: 'u-name', name: 'username', class: 'field', value: user?.username || '', required: true, autocomplete: 'off' }),
        h('p', { class: 'mt-1 text-xs text-muted' }, 'Латиница, цифры, точка, дефис, подчёркивание.'),
      ),
      h(
        'div',
        {},
        h('label', { class: 'label', for: 'u-pass' }, isEdit ? 'Новый пароль' : 'Пароль'),
        h('input', {
          id: 'u-pass',
          name: 'password',
          type: 'password',
          class: 'field',
          required: !isEdit,
          minlength: 6,
          autocomplete: 'new-password',
          placeholder: isEdit ? 'Оставьте пустым, чтобы не менять' : 'Не короче 6 символов',
        }),
      ),
      error,
      h('div', { class: 'flex justify-end gap-2 pt-2' }, Button('Отмена', () => modal.close(), { variant: 'ghost' }), submit),
    )

    form.addEventListener('submit', async (e) => {
      e.preventDefault()
      error.classList.add('hidden')
      const data = formData(form)
      data.username = data.username.trim()
      if (isEdit) {
        if (!data.password) delete data.password
        if (data.username === user.username) delete data.username
      }
      try {
        await withLoading(submit, () => (isEdit ? usersApi.update(user.id, data) : usersApi.create(data)))
        modal.close()
        toast(isEdit ? 'Пользователь обновлён' : `Пользователь ${data.username} создан`)
        load()
      } catch (err) {
        const fields = fieldErrors(err)
        error.textContent = Object.values(fields)[0] || errorText(err)
        error.classList.remove('hidden')
      }
    })

    const modal = openModal({ title: isEdit ? `Изменить ${user.username}` : 'Новый пользователь', body: form })
  }

  async function remove(user) {
    const ok = await confirmDialog({
      title: `Удалить ${user.username}?`,
      text: 'Пользователь больше не сможет войти. Отметки об оплате, которые он сделал, сохранятся.',
      confirmText: 'Удалить пользователя',
      danger: true,
    })
    if (!ok) return
    try {
      await usersApi.remove(user.id)
      toast(`Пользователь ${user.username} удалён`)
      load()
    } catch (err) {
      toast(errorText(err), 'error')
    }
  }

  await load()
}
