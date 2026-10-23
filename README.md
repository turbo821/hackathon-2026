# Invoice Keeper — напоминания о регулярных платежах

Система, которая не даёт забыть о платежах: аренда, подписки, серверы. Администратор вносит регулярные платежи, система за 3 дня до срока пишет в Telegram-чат, команда отмечает оплату и следит за просрочками.

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | JavaScript (без фреймворка), Vite, Tailwind CSS, Axios |
| Backend | Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic, Uvicorn |
| БД | SQLite (файл `backend/instance/app.db`) |
| Фон | Процесс `worker`: проверка сроков и отправка в Telegram |
| Инфраструктура | Docker, docker-compose |

## Структура проекта

```
├── docker-compose.yaml
├── .env.example          # шаблон настроек, копируется в .env (.env не коммитим)
├── openapi.json          # спецификация API
├── backend/
│   ├── main.py           # точка входа: uvicorn main:app
│   ├── alembic.ini
│   ├── entrypoint.sh     # миграции + сиды при старте контейнера
│   ├── migrations/       # миграции Alembic, коммитим в git
│   ├── instance/         # здесь лежит app.db, не коммитим
│   ├── scripts/          # наполнение базы: админ из .env, тестовые данные
│   ├── tests/
│   └── app/
│       ├── main.py       # FastAPI-приложение, CORS, Swagger
│       ├── config.py     # настройки из .env
│       ├── db.py         # подключение к БД, сессии
│       ├── auth.py       # пароли, JWT, проверка прав
│       ├── errors.py     # единый формат ошибок
│       ├── worker.py     # фоновые напоминания
│       ├── models/       # таблицы БД
│       ├── schemas/      # pydantic-схемы запросов и ответов
│       ├── routers/      # эндпоинты /api/v1/...
│       └── services/     # периоды, напоминания, Telegram, журнал
└── frontend/
    └── src/
        ├── api/          # axios-клиент и все запросы к API
        ├── components/   # функции, возвращающие DOM-элементы
        ├── pages/        # страницы: renderXxx(container)
        ├── router.js     # hash-роутер
        └── main.js
```

## Запуск через Docker

```bash
cp .env.example .env
# в .env задайте ADMIN_PASSWORD, JWT_SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
docker compose up --build
```

При старте backend сам применяет миграции, создаёт администратора из `.env` и тестовые данные.

| Что | Адрес |
|-----|-------|
| Фронтенд | http://localhost:5173 |
| API | http://localhost:5000/api/v1 |
| Swagger | http://localhost:5000/api/v1/docs |
| Проверка | http://localhost:5000/api/v1/health |

Остановка: `docker compose down`. База лежит в `backend/instance/app.db` и сохраняется между перезапусками.

## Запуск без Docker

Нужны Python 3.12 или 3.13 и Node.js 22+. Базу ставить не нужно: SQLite встроена в Python.

**Backend** (из папки `backend/`):

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env           # Windows: copy ..\.env.example .env
alembic upgrade head
python -m scripts.seed_all
uvicorn main:app --reload --port 5000
```

Напоминания отправляет отдельный процесс. Во втором терминале активируйте venv и запустите `python -m app.worker`.

**Frontend** (из папки `frontend/`):

```bash
npm install
npm run dev                       # http://localhost:5173
```

Адрес API фронт берёт из `VITE_API_URL`, по умолчанию `http://localhost:5000/api/v1`.

## Учётные записи

| Логин | Пароль | Роль |
|-------|--------|------|
| `ADMIN_USERNAME` из `.env` | `ADMIN_PASSWORD` из `.env` | администратор, через панель не изменяется |
| `user` | `user12345` | пользователь (тестовый) |
| `anna` | `anna12345` | пользователь (тестовый) |

Тестовые данные отключаются через `SEED_DEMO_DATA=false`.

## Настройка Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather) и запишите токен в `TELEGRAM_BOT_TOKEN`.
2. Добавьте бота в групповой чат и напишите туда любое сообщение.
3. Откройте `https://api.telegram.org/bot<токен>/getUpdates` и возьмите `chat.id` (у групп начинается с `-100`) для `TELEGRAM_CHAT_ID`.
4. Перезапустите backend и worker.

Работает ли отправка, видно в `/api/v1/health` (поле `telegram_configured`) и в логах worker.

## Как это работает

**Регулярный платёж** — шаблон: название, сумма, валюта (RUB, USD, EUR), дата ближайшей оплаты, периодичность (ежемесячно, а также раз в квартал и раз в год).

**Период** — конкретная оплата со своим сроком и своей отметкой «Оплачено / Не оплачено». Периоды создаются автоматически:

- прошлые оплаты не стираются, просрочка не останавливает следующие периоды;
- если текущий период оплачен заранее, сразу появляется следующий;
- даты считаются от числа первой оплаты: если его нет в месяце, берётся последний день (31.01 → 28.02 → 31.03).

**Состояние периода** вычисляется и не хранится:

| state | Когда |
|-------|-------|
| `pending` | не оплачен, срок сегодня или позже |
| `overdue` | не оплачен, срок прошёл (со следующего дня после срока) |
| `paid` | оплачен в день срока или раньше |
| `paid_late` | оплачен после срока |

Исправили фактическую дату оплаты — просрочка пересчиталась, срок не изменился.

**Напоминания.** Worker регулярно ищет неоплаченные периоды со сроком в ближайшие 3 дня и пишет в чат название, сумму, валюту и дату. Каждый период напоминается один раз. Платёж, добавленный позже чем за 3 дня до срока, получает напоминание сразу. Оплаченные периоды и удалённые платежи напоминаний не вызывают.

**Удаление платежа** мягкое: новые периоды и напоминания не создаются, история оплат остаётся.

Все даты считаются в часовом поясе `APP_TIMEZONE` (по умолчанию `Europe/Moscow`).

## API

Префикс `/api/v1`, полное описание с примерами — в Swagger. Авторизация: `POST /auth/login` возвращает `access_token`, дальше он передаётся в заголовке `Authorization: Bearer <token>`. Права проверяются на сервере, в том числе при прямых запросах к API.

| Метод | Эндпоинт | Кто | Назначение |
|-------|----------|-----|-----------|
| POST | `/auth/login` | все | Вход |
| GET | `/auth/me` | все авторизованные | Текущий пользователь |
| POST | `/auth/logout` | все авторизованные | Выход |
| GET | `/recurring-payments` | все авторизованные | Список регулярных платежей |
| POST | `/recurring-payments` | админ | Создание платежа |
| DELETE | `/recurring-payments/{id}` | админ | Прекращение платежа |
| GET | `/payment-occurrences` | все авторизованные | Периоды с фильтрами |
| GET | `/payment-occurrences/{id}` | все авторизованные | Один период |
| PATCH | `/payment-occurrences/{id}` | все авторизованные | Отметка и отмена оплаты, исправление даты |
| GET | `/payments/summary` | все авторизованные | Итоги по валютам |
| GET, POST | `/users` | админ | Список и создание пользователей |
| PATCH, DELETE | `/users/{id}` | админ | Изменение и удаление пользователя |
| GET | `/audit-logs` | админ | Журнал действий |

## Сценарий демонстрации

1. Войти администратором.
2. Добавить платёж со сроком через 1–2 дня: напоминание сразу приходит в Telegram.
3. Войти как `user` и отметить оплату.
4. Показать просроченный платёж: «Аренда офиса» в тестовых данных.
5. Отметить его оплату сегодняшней датой, затем исправить дату на день срока: просрочка исчезает.
6. Показать следующий период со своим статусом.

## Разработка

**Миграции.** Изменили модель — создайте и примените миграцию, файл из `migrations/versions/` закоммитьте сразу:

```bash
alembic revision --autogenerate -m "что изменили"
alembic upgrade head          # также после каждого git pull
```

Модели меняйте по очереди. Если Alembic сообщил о нескольких heads: `alembic merge heads -m "merge"`. В Docker перед командами добавляйте `docker compose exec backend`.

**Новый эндпоинт.** Роутер в `app/routers/`, схемы в `app/schemas/`. Доступ задаётся параметром `user: CurrentUser` или `admin: AdminUser`, сессия БД — `db: DB`, ошибки — `raise ApiError(404, "Платёж не найден")`.

**Тестовые данные.** Скрипты в `backend/scripts/`, у каждого функция `run(db)`; новый скрипт добавьте в список `SEEDS` в `seed_all.py`. Запуск из `backend/`: `python -m scripts.seed_all` (именно через `-m`, иначе не сработают импорты). Повторный запуск дубликатов не создаёт.

**Новая страница фронта.** Файл в `src/pages/`, строка в `ROUTES` в `src/router.js`, пункт меню в `src/components/Layout.js`. Данные с сервера выводим через `textContent`, не через `innerHTML`.

**Логгер.**

```python
from app.logging_config import get_logger
logger = get_logger(__name__)

logger.info("Платёж создан")           # отметка этапа
logger.warning("Логин уже занят")      # предвиденная ошибка
logger.exception("Ошибка сохранения")  # с трейсбеком
```

Логи идут в консоль и в `backend/logs/`; `LOG_DIR=null` — только консоль.

**Тесты.** Из `backend/`: `python -m pytest`.

## Частые проблемы

**`No module named 'psycopg'`.** В `.env` остался адрес PostgreSQL. Удалите строку `DATABASE_URL` или пересоздайте `.env` из `.env.example`. Если не помогло, переменная задана в системе: проверьте `echo %DATABASE_URL%`.

**`Failed to build ... pyyaml` или другой пакет при `pip install`.** Для вашей версии Python у пакета нет готовой сборки. Создайте venv на Python 3.12 или 3.13: `py -3.12 -m venv venv`.

**`entrypoint.sh: not found` или `\r: command not found` в Docker на Windows.** Файл сохранён с переводами строк Windows. Пересохраните его с LF или выполните `git rm --cached -r . && git reset --hard`.

**Напоминания не приходят.** Проверьте `telegram_configured` в `/api/v1/health`, что worker запущен, бот добавлен в чат и `TELEGRAM_CHAT_ID` верный. По одному периоду напоминание приходит один раз: для повторного демо создайте новый платёж.

**Фронт пишет «Сервер не отвечает».** Backend не запущен или `VITE_API_URL` неверный. Смотрите вкладку Network в DevTools.

**Чистая база.** Остановите backend, удалите `backend/instance/app.db`, затем снова `alembic upgrade head` и `python -m scripts.seed_all` (в Docker достаточно перезапуска).

**В Docker остались старые пакеты фронта.** `docker compose up --build --renew-anon-volumes`.

## Советы для хакатона

- **Git.** Работайте в своих ветках и вливайте в `main` через PR.
- **Контракт API.** Меняете формат ответа — сначала договоритесь с фронтом и обновите `openapi.json`.
- **Перед защитой** пройдите сценарий демонстрации с нуля на чистой машине строго по этому README.
