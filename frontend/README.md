# Invoice Keeper — frontend

Чистый JavaScript + Vite + Tailwind CSS v4 + Axios. Фреймворка нет: компонент — это функция, которая возвращает DOM-элемент, страница — функция `renderXxx(container)`.

```bash
npm install
npm run dev      # http://localhost:5173, backend должен работать на :5000
npm run build    # сборка в dist/
npm run lint
```

Адрес API — `VITE_API_URL` (по умолчанию `http://localhost:5000/api/v1`).

## Структура

```
src/
├── main.js               # точка входа
├── router.js             # hash-роутер: #/, #/recurring, #/users, #/audit, #/login
├── index.css             # Tailwind + дизайн-токены (@theme) и утилиты btn-*, field, label
├── api/
│   ├── client.js         # axios: токен в заголовке, 401 → экран входа, тексты ошибок
│   └── endpoints.js      # все запросы к API в одном месте
├── state/session.js      # токен (localStorage) и текущий пользователь
├── utils/
│   ├── dom.js            # h(tag, attrs, ...children) — сборка DOM без innerHTML
│   └── format.js         # деньги, даты, склонения
├── components/
│   ├── Layout.js         # шапка, навигация, пустые состояния, загрузка, ошибки
│   ├── Button.js         # кнопки и состояние «Сохраняем…»
│   ├── Modal.js          # модалка и confirmDialog
│   ├── Toast.js          # уведомления
│   ├── PaymentState.js   # отрывной календарь со сроком, бейдж состояния
│   └── PaymentForms.js   # «Новый платёж», «Отметить оплату», «Исправить дату»
└── pages/
    ├── login.js
    ├── payments.js       # главная: итоги по валютам, фильтры, к оплате и история
    ├── recurring.js      # регулярные платежи (админ)
    ├── users.js          # пользователи (админ)
    └── audit.js          # журнал действий (админ)
```

## Правила

- Данные с сервера выводим только через `h()` / `textContent`, не через `innerHTML`.
- Запросы — только через `api/endpoints.js`.
- Цвета и шрифт берём из токенов: `bg-paper`, `text-ink`, `text-muted`, `border-line`, `bg-accent`, `text-overdue`, `bg-paid-soft` и т.д.
- Новая страница: файл в `pages/`, строка в `ROUTES` в `router.js`, при необходимости пункт в `NAV` в `components/Layout.js`.
- Права проверяет backend; в интерфейсе админские разделы просто скрыты у пользователя.
