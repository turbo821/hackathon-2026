# Invoice Keeper — напоминания о регулярных платежах

Веб-панель + Telegram-напоминания о регулярных платежах: администратор заводит
платежи, система напоминает в чат за 3 дня до срока, пользователи отмечают оплату
и видят просрочки.

## Стек

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| База | SQLite (файл `backend/instance/app.db`) |
| Frontend | JavaScript (без фреймворка), Vite, Tailwind CSS, Axios |
| Инфраструктура | Docker, docker-compose |

## Что уже работает (этап «каркас»)

- Авторизация по JWT, две роли: администратор и пользователь.
- Роли проверяются **на сервере**: обычный пользователь не выполнит действие
  администратора даже через API.
- Все обязательные эндпоинты кейса, Swagger (`/api/v1/docs`) и OpenAPI-спецификация.
- Схема БД (4 таблицы) и одна миграция Alembic.
- Единый формат ошибок, тесты на роли, доступ и контракт.

Что запланировано следующим этапом (сейчас это заглушки в `app/services/`):

| Модуль | Что будет реализовано |
|--------|------------------------|
| `services/periods.py` | генерация периодов платежа: своя дата и своя отметка «Оплачено / Не оплачено» |
| `services/reminders.py` | выбор неоплаченных периодов в окне 3 дней и отправка напоминаний без дублей |
| `services/telegram.py` | отправка сообщений в Telegram Bot API |

Заглушки не мешают работать API: список платежей и пользователей живые, списки
периодов пока пустые. Сценарии, которым нужна эта логика, лежат в
`backend/tests/test_domain_logic.py` и помечены `skip` — разблокируются сами,
когда заглушки заменятся реализацией.

### Схема данных

Четыре таблицы: `users`, `recurring_payments` (шаблоны), `payment_occurrences`
(периоды), `revoked_tokens` (завершённые сессии).

Период — **слепок** шаблона: при создании он копирует `name`, `amount`, `currency`
и хранит `payment_ended_at` (когда платёж прекратили). Поэтому любой список
периодов читается по одной таблице, без JOIN, и все фильтры (`state`, `status`,
`currency`, `recurring_payment_id`, даты) работают по ней же. Шаблон нельзя
изменить через API — есть только создать и прекратить, — так что слепок не
расходится с оригиналом.

Просрочка и статус периода **не хранятся**, а считаются при чтении: так
исправление фактической даты оплаты сразу убирает ошибочную просрочку, а срок
не меняется.

### Что убрали и почему

Каркас — это минимум, который нужен для работы приложения. Необязательное убрано:

| Убрали | Почему |
|--------|--------|
| Журнал действий (`audit_logs`) | Бонусная фича из кейса, а не обязательное условие приёмки |
| Отдельный процесс `worker` | Пока напоминания не реализованы, процессу нечего делать; добавляется вместе с ними |
| Файловые логи с ротацией | Хватает stdout (`docker compose logs`) |
| Разбор ошибок pydantic по полям | Осталось первое сообщение об ошибке — фронту этого достаточно |
| `GET /recurring-payments/{id}`, `GET /users/{id}` | Их нет в списке эндпоинтов кейса |

## Структура проекта

```
project/
├── docker-compose.yaml
├── .env.example
├── .env                    # не коммитить
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh       # миграции + сиды при старте контейнера
│   ├── alembic.ini
│   ├── main.py             # точка входа: uvicorn main:app
│   ├── requirements.txt
│   ├── openapi.json        # спецификация из репозитория (перегенерируется скриптом)
│   ├── migrations/         # миграции Alembic (коммитим в git)
│   ├── instance/           # здесь app.db, не коммитить
│   ├── scripts/            # сиды и выгрузка спецификации
│   │   ├── seed_admin.py
│   │   ├── seed_demo.py
│   │   ├── seed_all.py
│   │   └── export_openapi.py
│   ├── tests/
│   └── app/
│       ├── main.py         # create_app(): сборка приложения
│       ├── config.py       # настройки из .env
│       ├── db.py           # engine, сессии, Base
│       ├── auth.py         # JWT, пароли, зависимости ролей
│       ├── errors.py       # единый формат ошибок
│       ├── logging_config.py
│       ├── timeutils.py    # «сегодня» в часовом поясе приложения
│       ├── models/         # SQLAlchemy-модели
│       ├── schemas/        # Pydantic-схемы запросов и ответов
│       ├── routers/        # эндпоинты API
│       ├── services/       # доменная логика (сейчас — заглушки)
│       └── (worker.py)     # процесс напоминаний — добавится вместе с ними
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── api/client.js   # axios-клиент
        ├── components/
        ├── pages/
        ├── main.js
        └── index.css
```

## Быстрый старт (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Поднимаются два сервиса:

- `backend` — API на http://localhost:5000
- `frontend` — панель на http://localhost:5173

При старте backend сам применяет миграции и создаёт администратора из `.env`.
Файла базы отдельно создавать не нужно.

Полезные адреса:

- Swagger: http://localhost:5000/api/v1/docs
- ReDoc: http://localhost:5000/api/v1/redoc
- Проверка живости: http://localhost:5000/api/v1/health
- Панель: http://localhost:5173

Остановка:

```bash
docker compose down
```

Файл базы лежит в `backend/instance/app.db` на вашем компьютере (папка `backend`
примонтирована в контейнер), поэтому данные сохраняются между перезапусками.
Чтобы начать с чистой базы: `docker compose down`, удалите `backend/instance/app.db`
и снова выполните `docker compose up --build`.

## Запуск без Docker

Нужны Python 3.12+ и Node.js 22+. База данных не нужна: SQLite встроена в Python.

### Backend

Команды выполняются из папки `backend/`.

```bash
cd backend

# виртуальное окружение
python -m venv .venv

# активировать
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows (cmd / PowerShell)

# зависимости
pip install -r requirements.txt

# схема БД + администратор из .env + тестовые данные
alembic upgrade head
python -m scripts.seed_all

# сервер
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

API будет доступен на http://localhost:5000/api/v1/docs.
Выйти из окружения: `deactivate`.

### Frontend

В новом терминале:

```bash
cd frontend
npm install
npm run dev
```

Панель: http://localhost:5173. Адрес API берётся из переменной `VITE_API_URL`
(в `.env` уже прописано `http://localhost:5000/api/v1`).

Другие команды:

```bash
npm run build      # продакшен-сборка в папку dist/
npm run preview    # локальный просмотр собранной версии
```

## Роли и доступ

| Действие | Администратор | Пользователь |
|----------|:-------------:|:------------:|
| Смотреть список платежей | ✅ | ✅ |
| Отмечать оплату и править фактическую дату | ✅ | ✅ |
| Добавлять и удалять регулярные платежи | ✅ | ❌ |
| Создавать, менять и удалять пользователей | ✅ | ❌ |

Администратор задаётся в `.env` (`ADMIN_USERNAME`, `ADMIN_PASSWORD`). Его учётную
запись нельзя изменить или удалить через панель.

## API

Префикс всех эндпоинтов — `/api/v1`.

| Метод | Эндпоинт | Назначение |
|--------|-----------|------------|
| POST | `/api/v1/auth/login` | Вход по логину и паролю |
| GET | `/api/v1/auth/me` | Текущий пользователь |
| POST | `/api/v1/auth/logout` | Завершение сессии |
| GET | `/api/v1/recurring-payments` | Список регулярных платежей |
| POST | `/api/v1/recurring-payments` | Создать регулярный платёж (админ) |
| DELETE | `/api/v1/recurring-payments/{id}` | Прекратить платёж, сохранив историю (админ) |
| GET | `/api/v1/payment-occurrences` | Периоды: оплаченные и просроченные |
| GET | `/api/v1/payment-occurrences/{id}` | Конкретный период |
| PATCH | `/api/v1/payment-occurrences/{id}` | Подтвердить/отменить оплату, исправить дату |
| GET | `/api/v1/payments/summary` | Итоги по валютам |
| GET | `/api/v1/users` | Список пользователей (админ) |
| POST | `/api/v1/users` | Создать пользователя (админ) |
| PATCH | `/api/v1/users/{id}` | Изменить пользователя (админ) |
| DELETE | `/api/v1/users/{id}` | Удалить пользователя (админ) |
| GET | `/api/v1/health` | Проверка живости |

Дополнительно: `GET /api/hello` — совместимость с фронтом, у которого базовый
адрес по умолчанию `http://localhost:5000/api`.

Авторизация — заголовок `Authorization: Bearer <token>`. В Swagger есть кнопка
**Authorize**: сначала выполните `POST /api/v1/auth/login`, скопируйте
`access_token` и вставьте её в поле.

### Формат ошибок

Единый для всех ответов, фронт на него рассчитан:

```json
{
  "code": 403,
  "status": "Forbidden",
  "message": "Действие доступно только администратору"
}
```

При ошибке валидации в `message` — причина (например, «Сумма должна быть больше нуля»).

### OpenAPI-спецификация

FastAPI отдаёт спецификацию на `/api/v1/openapi.json`. Копия лежит в репозитории —
`backend/openapi.json`. Обновить:

```bash
cd backend
python -m scripts.export_openapi
```

## Миграции

Схема БД хранится в `backend/migrations/` и коммитится в git — у всех в команде
одинаковая структура таблиц.

```bash
# применить миграции
alembic upgrade head

# изменили модель — создать миграцию
alembic revision --autogenerate -m "что изменили"
alembic upgrade head
```

В Docker добавьте `docker compose exec backend`, например:

```bash
docker compose exec backend alembic upgrade head
```

Первая миграция (`0001_initial`) создаёт таблицы прямо из моделей — так схема и
модели не могут разойтись. Дальше работает обычный цикл с `--autogenerate`.

Новый файл из `migrations/versions/` нужно закоммитить. Если две ветки создали
миграции одновременно, Alembic сообщит о нескольких «головах» (heads) — сводите
их командой `alembic merge heads -m "merge"`.

## Скрипты с данными

Папка `backend/scripts/` — скрипты, которые наполняют базу. Каждый лежит в
отдельном файле с функцией `run(db)`, `seed_all.py` запускает их по списку.
Скрипты идемпотентные: повторный запуск не создаёт дубликаты.

```bash
cd backend
python -m scripts.seed_all
```

- `seed_admin` — администратор из `.env` (логин и пароль обновляются при смене `.env`).
- `seed_demo` — демо-данные: аренда в рублях, сервер в долларах, подписка в евро
  и два пользователя (`user` / `user12345`, `anna` / `anna12345`). Отключается
  переменной `SEED_DEMO_DATA=false`.

Запускайте именно так, из папки `backend/`: при прямом запуске файла
(`python scripts/seed_all.py`) импорты не сработают.

## Telegram-напоминания

1. Создайте бота через @BotFather и получите токен.
2. Узнайте `chat_id` чата (например через `@userinfobot` для личного чата).
3. Пропишите в `.env`:

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-1001234567890
```

4. Реализуйте `app/services/telegram.py` и `app/services/reminders.py` (сейчас
   это заглушки) и добавьте фоновый процесс — по образцу:

```python
# backend/app/worker.py
while True:
    check_and_send(db)          # выборка периодов + отправка
    time.sleep(settings.reminder_check_interval_seconds)
```

и сервис в `docker-compose.yaml`:

```yaml
  worker:
    build: ./backend
    env_file: .env
    entrypoint: ["python", "-m", "app.worker"]
    volumes:
      - ./backend:/app
    depends_on:
      - backend
```

Напоминание приходит минимум за `REMINDER_DAYS_BEFORE` дней (по умолчанию 3) до
срока: название, сумма, валюта и дата оплаты. Дублей нет: период помечается
отправленным, повторная проверка его не отправляет заново. Оплаченный период
напоминания не вызывает.

## Тесты

```bash
cd backend
pytest
```

`tests/test_api.py` — то, что работает уже сейчас (доступ, роли, контракт).
`tests/test_domain_logic.py` — сценарии приёмки, которым нужна доменная логика;
сейчас весь файл помечен `skip`.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `DATABASE_URL` | `sqlite:///./instance/app.db` | Подключение к БД |
| `JWT_SECRET_KEY` | — | Секрет подписи токенов (обязательно задать) |
| `ADMIN_USERNAME` | `admin` | Логин администратора |
| `ADMIN_PASSWORD` | `admin` | Пароль администратора |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | Сколько живёт токен |
| `APP_TIMEZONE` | `Europe/Moscow` | Часовой пояс приложения |
| `TELEGRAM_BOT_TOKEN` | — | Токен Telegram-бота |
| `TELEGRAM_CHAT_ID` | — | Чат для напоминаний |
| `REMINDER_DAYS_BEFORE` | `3` | За сколько дней напоминать |
| `REMINDER_CHECK_INTERVAL_SECONDS` | `60` | Период проверки напоминаний |
| `SEED_DEMO_DATA` | `true` | Создавать демо-данные |
| `CORS_ORIGINS` | `*` | Разрешённые источники |
| `VITE_API_URL` | `http://localhost:5000/api/v1` | Адрес API для фронта |

## Частые проблемы

**`alembic upgrade head` не находит ревизию**

В базе осталась старая версия миграций. Начните с чистой базы: остановите
контейнеры, удалите `backend/instance/app.db` и повторите миграцию.

**`/api/v1/docs` не открывается**

Бекенд не запущен или упал при старте. Смотрите `docker compose logs backend`.
Частая причина — не прошла миграция: сообщение будет в логах при старте.

**Страница показывает «Не удалось получить данные с сервера»**

Бек не запущен или адрес в `VITE_API_URL` неверный. Смотрите вкладку Network
в DevTools браузера.

**401 вместо сообщения об ошибке**

Токен истёк или был завершён через `POST /api/v1/auth/logout`. Войдите заново.

**После смены зависимостей фронта в Docker остались старые пакеты**

`node_modules` лежит в анонимном томе. Пересоберите:

```bash
docker compose up --build --renew-anon-volumes
```

**Ошибка «address already in use»**

Порт 5000 занят. Поменяйте его в `docker-compose.yaml` (и в `VITE_API_URL`).

## Логирование

```python
from app.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Пользователь зарегистрирован")   # обычное событие
logger.warning("Email уже занят")             # предупреждение
logger.exception("Ошибка при сохранении")     # с трейсбеком
```

Пишутся в stdout — их видно в `docker compose logs backend`.
