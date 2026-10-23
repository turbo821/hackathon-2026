/**
 * Мини-хелпер для сборки DOM без innerHTML.
 * Данные с сервера всегда попадают в textContent, поэтому чужой HTML не выполнится.
 *
 *   h('button', { class: 'btn-primary', onclick: save }, 'Сохранить')
 */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag)

  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue
    if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2).toLowerCase(), value)
    } else if (key === 'class') {
      el.className = value
    } else if (key === 'dataset') {
      Object.assign(el.dataset, value)
    } else if (value === true) {
      el.setAttribute(key, '')
    } else {
      el.setAttribute(key, value)
    }
  }

  append(el, children)
  return el
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue
    el.append(child instanceof Node ? child : document.createTextNode(String(child)))
  }
}

/** Очистить контейнер и положить новое содержимое */
export function mount(container, ...children) {
  container.replaceChildren()
  append(container, children)
}

/** Значения формы в объект: { name: value } */
export function formData(form) {
  return Object.fromEntries(new FormData(form).entries())
}
