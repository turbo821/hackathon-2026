# Проект для хакатона

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | JavaScript (без фреймворка), Vite, Tailwind CSS, Axios |
| Backend | Python, Flask, SQLAlchemy, Flask-Migrate |
| БД | SQLite (файл `backend/instance/app.db`) |
| Инфраструктура | Docker, docker-compose |

## Структура проекта

```
project/
├── docker-compose.yml
├── .env.example
├── .env                    # не коммитить
├── .gitignore
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py             # точка входа
│   ├── migrations/         # создаётся командой db init, коммитим в git
│   ├── instance/           # здесь лежит app.db, не коммитить
│   ├── scripts/            # скрипты для данных
│   │   ├── __init__.py
│   │   ├── seed_messages.py
│   │   └── seed_all.py
│   └── app/
│       ├── __init__.py     # create_app()
│       ├── config.py
│       ├── extensions.py   # db, migrate, cors
│       ├── models/         # SQLAlchemy-модели
│       │   ├── __init__.py
│       │   └── message.py
│       └── routes/         # Flask Blueprints
│           ├── __init__.py
│           ├── health.py
│           └── hello.py
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── api/            # axios-клиент и функции запросов
        │   └── client.js
        ├── components/     # функции, возвращающие DOM-элементы
        │   └── Button.js
        ├── pages/          # функции renderXxx(root)
        │   └── home.js
        ├── main.js
        └── index.css
```

Фронт и бек живут независимо, а в корне лежит всё, что связывает их вместе.

## Как работает цепочка hello world

```
SQLite (таблица message)
   → Flask: GET /api/hello (модель Message)
   → Axios: api.get('/hello') в src/pages/home.js
   → текст на странице
```

Строка `hello world` попадает в базу скриптом из папки `backend/scripts`, а не при старте приложения.

## Быстрый старт (Docker)

```bash
cp .env.example .env
docker compose up --build
```

В соседнем терминале примените миграции и добавьте данные:

```bash
docker compose exec backend flask --app main db upgrade
docker compose exec backend python -m scripts.seed_all
```

После этого:

- Фронтенд: http://localhost:5173 (на странице должно быть `hello world`)
- Бекенд: http://localhost:5000/api/hello
- Проверка бека: http://localhost:5000/api/health

Остановка:

```bash
docker compose down
```

Файл базы лежит в `backend/instance/app.db` на вашем компьютере (папка `backend` примонтирована в контейнер), поэтому данные сохраняются между перезапусками. Чтобы начать с чистой базы, остановите контейнеры, удалите этот файл и снова выполните `db upgrade` и `seed_all`.

## Запуск без Docker

Нужны Python 3.12+ и Node.js 22+. Ставить базу данных не нужно: SQLite встроена в Python.

### Backend

Команды выполняются из папки `backend/`.

```bash
cd backend

# создать виртуальное окружение
python -m venv venv

# активировать
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows (cmd / PowerShell)

# установить зависимости
pip install -r requirements.txt

# применить миграции и добавить данные
flask --app main db upgrade
python -m scripts.seed_all

# запустить сервер
flask --app main run --debug
```

Бекенд будет доступен на http://localhost:5000/api/hello.

Выйти из виртуального окружения: `deactivate`. После установки новых библиотек обновляйте зависимости: `pip freeze > requirements.txt`.

### Frontend

В новом терминале:

```bash
cd frontend
npm install
npm run dev
```

Фронтенд будет доступен на http://localhost:5173. Адрес API берётся из переменной `VITE_API_URL`. Если она не задана, используется `http://localhost:5000/api`, так что для локального запуска ничего настраивать не нужно.

Другие команды:

```bash
npm run build      # продакшен-сборка в папку dist/
npm run preview    # локальный просмотр собранной версии
npm install <пакет>
```

## Миграции

Схема БД хранится в папке `backend/migrations/` и коммитится в git. Так у всех в команде одинаковая структура таблиц.

**Первая миграция проекта** (делает один человек, один раз):

```bash
flask --app main db init
flask --app main db migrate -m "create message"
flask --app main db upgrade
```

**Изменили модель:**

```bash
flask --app main db migrate -m "что изменили"
flask --app main db upgrade
```

Новый файл из `migrations/versions/` нужно закоммитить.

**Подтянули чужие изменения** (`git pull`):

```bash
flask --app main db upgrade
```

В Docker перед каждой командой добавляйте `docker compose exec backend`.

> Модели нужно импортировать в `app/__init__.py` (строка `from .models import Message`),
> иначе Flask-Migrate их не увидит.

Если две ветки создали миграции одновременно, Alembic сообщит о нескольких «головах» (heads). Исправление:

```bash
flask --app main db merge heads -m "merge"
```

## Скрипты с данными

Папка `backend/scripts/` содержит скрипты, которые наполняют базу. Каждый скрипт лежит в отдельном файле с функцией `run()`, а `seed_all.py` запускает их по списку. Скрипты идемпотентные: повторный запуск не создаёт дубликаты.

```bash
python -m scripts.seed_all
```

Запускайте именно так, из папки `backend/`. Если выполнить файл напрямую (`python scripts/seed_all.py`), импорты не сработают.

Добавить новый набор данных: создайте файл `scripts/seed_xxx.py` с функцией `run()` и добавьте его в список `SEEDS` в `seed_all.py`.

## Частые проблемы

**`ImportError: cannot import name 'bp' from 'app.routes.hello'`**
Файл `hello.py` пустой или не сохранён, либо Blueprint в нём назван не `bp`. Проверьте файл и сохраните его.

**`NameError: name 'Message' is not defined`**
В `app/__init__.py` нет строки `from .models import Message` (или остался старый блок с `db.create_all()`, которого быть не должно).

**`No changes in schema detected` при `db migrate`**
Таблица уже есть в базе (например, осталась от старого `create_all`). Удалите `backend/instance/app.db` и пустые файлы миграций в `migrations/versions/`, затем повторите `db migrate`. В выводе должна быть строка `Detected added table 'message'`.

**`/api/hello` возвращает ошибку 500**
Таблица пустая: выполните `python -m scripts.seed_all`.

**Страница показывает «Не удалось получить данные с сервера»**
Бек не запущен или адрес в `VITE_API_URL` неверный. Смотрите вкладку Network в DevTools браузера.

**Бек работает с другим файлом БД, чем вы думаете**
Относительный путь `sqlite:///app.db` Flask-SQLAlchemy считает от папки `instance`. Если в терминале задана переменная `DATABASE_URL`, она перебивает значение по умолчанию. Узнать, какой файл используется:

```bash
python -c "from app import create_app; from app.extensions import db; a=create_app(); a.app_context().push(); print(db.engine.url)"
```

**После смены зависимостей фронта в Docker остались старые пакеты**
`node_modules` лежит в анонимном томе. Пересоберите так:

```bash
docker compose up --build --renew-anon-volumes
```

---

## Создание проекта с нуля

Этот раздел нужен, если каркас ещё не создан.

### 1. Каркас

```bash
mkdir project && cd project
git init
mkdir -p backend/app/models backend/app/routes backend/scripts
touch backend/app/models/__init__.py backend/app/routes/__init__.py backend/scripts/__init__.py

# Frontend (Vite, чистый JS)
npm create vite@latest frontend -- --template vanilla
cd frontend
npm install
npm install axios
npm install tailwindcss @tailwindcss/vite
cd ..
```

Из шаблона Vite удалите лишнее: `src/counter.js`, `src/style.css`, `src/javascript.svg`.

### 2. Frontend

`frontend/vite.config.js`:

```js
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
  server: { host: true, port: 5173, watch: { usePolling: true } },
})
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hackathon</title>
  </head>
  <body class="bg-slate-900">
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

`frontend/src/index.css` (одна строка):

```css
@import "tailwindcss";
```

`frontend/src/api/client.js`:

```js
import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
})
```

`frontend/src/components/Button.js`:

```js
export function Button(text, onClick) {
  const btn = document.createElement('button')
  btn.className = 'px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-500'
  btn.textContent = text
  btn.addEventListener('click', onClick)
  return btn
}
```

`frontend/src/pages/home.js`:

```js
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
```

Данные с сервера вставляйте через `textContent`, а не `innerHTML`, чтобы в страницу не попал чужой HTML.

`frontend/src/main.js`:

```js
import './index.css'
import { renderHome } from './pages/home.js'

renderHome(document.querySelector('#app'))
```

Компонент в чистом JS это просто функция, которая возвращает DOM-элемент (как `Button`). Новая страница это функция `renderXxx(root)` в папке `pages/`.

### 3. Backend

`backend/requirements.txt`:

```
flask
flask-sqlalchemy
flask-migrate
flask-cors
python-dotenv
gunicorn
```

`backend/app/extensions.py`:

```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
```

`backend/app/config.py`:

```python
import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
```

`backend/app/models/message.py`:

```python
from ..extensions import db

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
```

`backend/app/models/__init__.py`:

```python
from .message import Message
```

`backend/app/routes/health.py`:

```python
from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)

@bp.get("/health")
def health():
    return jsonify(status="ok")
```

`backend/app/routes/hello.py`:

```python
from flask import Blueprint, jsonify
from ..extensions import db
from ..models import Message

bp = Blueprint("hello", __name__)

@bp.get("/hello")
def hello():
    msg = db.session.get(Message, 1)
    return jsonify(message=msg.text)
```

`backend/app/__init__.py`:

```python
from flask import Flask
from .config import Config
from .extensions import db, migrate, cors
from .models import Message  # нужен, чтобы миграции видели модели

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    cors.init_app(app)

    from .routes.health import router as health_router
    app.register_blueprint(health_router, url_prefix="/api")

    return app
```

Параметр `render_as_batch=True` нужен для SQLite: она не умеет многие `ALTER TABLE`, и без этого режима миграции, меняющие существующие таблицы, будут падать.

`backend/main.py`:

```python
from app import create_app

router = Blueprint("health", __name__)

@router.get("/health")
def health():
    return jsonify(status="ok")
app = create_app()
```

`backend/scripts/seed_messages.py`:

```python
from app.extensions import db
from app.models import Message

def run():
    if db.session.get(Message, 1) is None:
        db.session.add(Message(text="hello world"))
        db.session.commit()
        print("messages: добавлено")
    else:
        print("messages: уже есть, пропускаю")
```

`backend/scripts/seed_all.py`:

```python
from app import create_app
from . import seed_messages

SEEDS = [
    seed_messages,
    # сюда добавлять новые скрипты
]

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        for seed in SEEDS:
            seed.run()
```

### 4. Dockerfile'ы

`backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["flask", "--app", "main", "run", "--host=0.0.0.0", "--port=5000", "--debug"]
```

`frontend/Dockerfile`:

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "dev"]
```

### 5. docker-compose.yml и .env

Сервиса для базы данных нет: SQLite лежит файлом в `backend/instance/`.

`.env.example`:

```
VITE_API_URL=http://localhost:5000/api
# DATABASE_URL=sqlite:///app.db
```

`docker-compose.yml`:

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    ports:
      - "5000:5000"
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    env_file: .env
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
```

Чтобы миграции применялись сами при каждом старте контейнера, добавьте в сервис `backend`:

```yaml
    command: sh -c "flask --app main db upgrade && flask --app main run --host=0.0.0.0 --port=5000 --debug"
```

Это работает только после создания папки `migrations/` (после первого `db init`). Данные скриптами лучше оставить ручными, чтобы они не перезаписывали то, что вы наполнили в процессе разработки.

`.gitignore` (минимум):

```
.env
node_modules/
dist/
__pycache__/
*.pyc
venv/
.venv/
instance/
```

Папку `migrations/` в `.gitignore` добавлять нельзя, она должна быть в репозитории.

---

## Советы для хакатона

- **Git.** Договоритесь о ветках заранее (`main` плюс по ветке на человека или фичу) и закоммитьте каркас до того, как все начнут писать код. Это убережёт от конфликтов.
- **Миграции.** Модели меняйте по очереди, а файлы миграций коммитьте сразу, чтобы не получить несколько heads.
- **Контракт API.** В первый час зафиксируйте список эндпоинтов и формат JSON. Фронт тогда может работать на заглушках, пока бек не готов.
- **Продакшен-деплой.** Для демо dev-режима обычно достаточно. Если нужен прод, соберите фронт через `npm run build` и отдайте через nginx, а бек запустите через gunicorn (`gunicorn main:app`).

---------------ИСПОЛЬЗОВАНИЕ ЛОГГЕРА--------------------
from app.logging_config import get_logger
logger = get_logger(__name__) #теперь можем пользоваться


logger.info("Пользователь зарегистрирован") #для отметки этапа
logger.warning("Email уже занят") #для предвиденной ошибки
logger.exception("Ошибка при сохранении")    #Для полной информации об ошибке(с трейсбеком)
