# Как это развёрнуто и работает

Документ для тех, кто будет это чинить. Описывает схему, хрупкие места и
грабли, на которые уже наступали.

## Схема

```
                        ┌──────────────────────────────────┐
   браузер ────────────►│ frontend (nginx, :80 → :80)    │
                        │  статика, собранная Vite         │
                        └────────────────┬─────────────────┘
                                         │ /api/* (тот же origin)
                                         ▼
                        ┌──────────────────────────────────┐
                        │ backend (FastAPI, :5000)         │
                        │ worker  (напоминания + бот)      │
                        └────────────────┬─────────────────┘
                                         │ исходящие HTTP(S) и SMTP
                                         ▼
                        ┌──────────────────────────────────┐
                        │ xray (SOCKS5 :1080, HTTP :8080)  │
                        └────────────────┬─────────────────┘
                                         ▼
                                      интернет
```

Все четыре сервиса в общей сети `app-network`. Наружу опубликованы только
`:80` (панель) и `:5000` (API/Swagger). Порт xray наружу не публикуется:
контейнеры обращаются к нему по имени сервиса `xray`.

Запуск — только через Docker Compose: без контейнера `xray` исходящие запросы
в Telegram и к почте не проходят.

## Прокси: xray

Кто и как ходит через прокси (переменные из `.env`):

| Переменная      | Кто использует                                    | Как                                         |
| --------------- | ------------------------------------------------- | ------------------------------------------- |
| `PROXY_URL`     | `backend`, `worker` — `ALL_PROXY`/`HTTP(S)_PROXY` | все исходящие HTTP(S)-запросы               |
| `BOT_PROXY_URL` | клиент Telegram (`services/telegram.py`)          | передаётся в httpx явно                     |
| `SMTP_PROXY`    | канал почты (`remind_channels/smtp.py`)           | SOCKS5 CONNECT руками, smtplib прокси не умеет |

`NO_PROXY` в compose оставляет внутренние имена (`backend`, `frontend`,
`worker`, `xray`, `localhost`) напрямую — иначе они уедут в прокси и сломаются.

Конфиг — `xray/config.json`. Проверить его настоящим бинарём:

```bash
docker run --rm -v "$PWD/xray/config.json:/etc/xray/config.json:ro" \
  ghcr.io/xtls/xray-core:latest run -test -config /etc/xray/config.json
```

Тем же способом compose проверяет здоровье контейнера (`healthcheck`): в образе
нет shell и nc, поэтому проверяется сам конфиг.

Что важно знать про конфиг:

* схема xray — не sing-box: входящее соединение описывается полями
  `protocol` и `port`, а не `type` и `listen_port`. Конфиг от sing-box xray
  не поймёт (`listen_port` молча игнорируется, и xray падает с
  «Listen on specific ip without port»);
* `sockopt.domainStrategy: "UseIPv4"` — xray сам резолвит домены и берёт
  только IPv4. Без этого Telegram отдаёт IPv6-адрес, и цепочка рвётся
  (socks5 code=4);
* `dns.servers` — `["localhost"]`, то есть системный резолвер контейнера.
  С публичными резолверами xray перестаёт видеть внутренние имена docker-сети.

`proxy/sing-box.json` — остаток прошлой схемы, в compose его нет.

## Фронт: почему `VITE_API_URL=/api/v1`

Раньше дефолтом стоял `http://backend:5000/api/v1` — **внутреннее имя
docker-сервиса**. Браузер такое имя не резолвит, поэтому на сервере панель
показывала «Не удалось связаться с сервером», а Swagger (он открывается по
внешнему адресу) работал.

Сейчас адрес относительный: запрос уходит на тот же origin, где открыта
панель, а nginx в контейнере `frontend` проксирует `/api/` в `backend:5000`
(`frontend/nginx.conf`). Адрес сервера нигде не зашит, CORS не нужен.

**Важно:** `VITE_API_URL` — аргумент **сборки** образа (`build.args` в compose),
Vite вшивает его в JS при `npm run build`. Поэтому:

* правка `.env` без пересборки ни на что не влияет — нужно
  `docker compose up -d --build frontend` (`--force-recreate` не поможет);
* у сервиса `frontend` нет `env_file`, и переменные окружения контейнера
  на панель не действуют — значение берётся только при сборке.

Ещё о nginx:

* имя `backend` резолвится через `resolver 127.0.0.11` в момент запроса, а не
  при старте. Иначе, если бэкенд поднялся позже, nginx не стартует с
  «host not found in upstream»;
* `index.html` отдаётся с `no-cache`, файлы из `/assets/` (с хешем в имени) —
  с годовым кешем. После пересборки браузер сразу получает новую версию.

Если npm-реестр недоступен при сборке, задайте зеркало:
`NPM_REGISTRY=https://registry.npmmirror.com docker compose up --build`.

## Воркер и SQLite

`worker` запускается с `entrypoint: ["python", "-m", "app.worker"]`. Без этого
он поднимал второй uvicorn, и два процесса одновременно меняли одну
SQLite-базу. Миграции и сиды выполняет только `backend`.

База лежит в томе `backend_data`, а не в bind-mount: SQLite в режиме WAL на
bind-mount Docker Desktop под Windows не работает (не создаются `-wal`/`-shm`).

## Сид и занятый email

`seed_superadmin` поднимает `RuntimeError`, если `SUPERADMIN_EMAIL` уже занят
другим пользователем. Бэкенд при этом не поднимается (entrypoint выходит с
ошибкой → restart loop). Симптом — `docker compose logs backend | grep -i
runtimeerror`.

Решение — освободить email (сменить его другому пользователю) или задать
суперадмину другой.

## Логирование

Настройки: `LOG_LEVEL`, `LOG_FORMAT` (`text` / `json`), `LOG_LEVEL_LIBRARIES`.

Что важно знать:

* `uvicorn.access` отключён — обращения пишет наш middleware, с `request_id`,
  пользователем и таймингом;
* контекст запроса добавляется через **фабрику записей** (`setLogRecordFactory`),
  а не фильтром на обработчике — иначе его не видят другие обработчики,
  в том числе `caplog` в тестах;
* `setup_logging` удаляет **только свои** обработчики. Чужие (например
  перехватчик pytest) не трогает — иначе `caplog` в тестах перестаёт работать;
* поля события не должны называться как стандартные поля `LogRecord`
  (`name`, `message`, …) — Python бросает `KeyError`. Такие поля
  автоматически переименовываются в `field_<имя>`.

## Проверка «всё живо»

```bash
docker compose ps                                   # все четыре сервиса Up

# nginx проксирует API
curl -s http://localhost:5173/api/v1/hello
curl -s http://localhost:5173/api/v1/health

# логин через nginx
curl -s -X POST http://localhost:5173/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<почта>","password":"<пароль>"}'

# Telegram и почта через прокси
docker compose exec backend python -m scripts.check_telegram --send
docker compose exec backend python -m scripts.check_smtp

# напоминания
docker compose logs -f worker
```

`check_smtp` проверяет прямое TLS-подключение на 465 и не учитывает
`SMTP_PROXY`/`SMTP_STARTTLS` — при них проверка подключения может показать
FAIL, хотя worker письма отправляет.

## Что ещё стоит доделать

* `:5000` опубликован на `0.0.0.0` — панель ходит в API через nginx, так что
  наружу достаточно `:5173` (Swagger доступен и как `:5173/api/v1/docs`);
* `JWT_SECRET_KEY` на сервере должен быть случайным (`openssl rand -hex 32`),
  а не значением из `.env.example`;
* `check_smtp` — подключаться через `_connect()` рабочего кода, чтобы
  учитывать прокси и STARTTLS;
* `proxy/sing-box.json` — удалить, больше не используется.
