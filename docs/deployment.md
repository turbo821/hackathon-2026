# Как это развёрнуто и работает

Документ для тех, кто будет это чинить. Описывает схему, хрупкие места и
грабли, на которые уже наступали.

## Схема

```
                        ┌────────────────────────────┐
   браузер ────────────►│ frontend (Vite dev, :5173) │
                        └─────────────┬──────────────┘
                                      │ /api/v1/* (тот же origin)
                                      ▼
                        ┌────────────────────────────┐
                        │  Vite proxy → backend      │
                        │  backend (FastAPI, :5000)  │
                        └─────────────┬──────────────┘
                                      │ исходящие HTTP(S)/SMTP
                                      ▼
                        ┌────────────────────────────┐
                        │ xray (SOCKS5 :1080)        │
                        └─────────────┬──────────────┘
                                      ▼
                                   интернет
```

Плюс отдельный сервис `worker` — фоновые напоминания и Telegram-бот.

Все четыре сервиса в общей сети `app-network`. Наружу опубликованы только
`:5173` (панель) и `:5000` (API/Swagger).

## Почему xray, а не sing-box

`proxy/sing-box.json` — остаток прошлой схемы, в compose его больше нет.
Xray-конфиг лежит в `xray/config.json` и валидируется настоящим бинарём:

```bash
docker run --rm -v "$PWD/xray/config.json:/etc/xray/config.json:ro" \
  ghcr.io/xtls/xray-core:latest run -test -config /etc/xray/config.json
```

Две вещи, которые стоит знать про схему Xray v26 (отличаются от документов
для старых версий):

* входящее соединение описывается полями `protocol` и `port`
  (не `type` и не `listen_port` — старый `listen_port` **молча игнорируется**,
  и xray падает с «Listen on specific ip without port»);
* `sockopt.domainStrategy: "UseIPv4"` — аналог sing-box'овского
  `domain_strategy: prefer_ipv4`. Без него Telegram отдаёт IPv6-адрес, и
  цепочка рвётся (socks5 code=4).

`dns.servers` в конфиге — `["localhost"]`, а не публичные резолверы: с
публичными xray перестаёт видеть внутренние имена docker-сети.

## Фронт и бэк: почему `VITE_API_URL=/api/v1`

Раньше дефолтом стоял `http://backend:5000/api/v1` — **внутреннее имя
docker-сервиса**. Браузер такое имя не резолвит, поэтому на сервере панель
показывала «Не удалось связаться с сервером», а Swagger (он открывается по
внешнему адресу, тот же origin) работал.

Сейчас адрес относительный: запрос уходит на тот же origin, где открыта
страница, а dev-сервер Vite перенаправляет `/api` в бэкенд (`server.proxy` в
`frontend/vite.config.js`). Адрес сервера нигде не зашит, CORS не нужен.

**Важно:** `VITE_API_URL` приходит из `.env` через `env_file` в `process.env`,
и Vite подставляет его **при трансформации модуля**. Поэтому:

* правка `.env` без пересоздания контейнера ни на что не влияет —
  `docker compose up -d --force-recreate frontend`;
* `environment:` в compose **перекрывает** `env_file`. Если в `frontend`
  окажется `environment: VITE_API_URL=...`, значение из `.env` будет
  проигнорировано — это уже случалось.

## Воркер и SQLite

`worker` запускается с `entrypoint: ["python", "-m", "app.worker"]`. Без этого
он поднимал второй uvicorn, и два процесса одновременно меняли одну
SQLite-базу. Миграции и сиды выполняет только `backend`.

База лежит в томе `backend_data`, а не в bind-mount: SQLite в режиме WAL на
bind-mount Docker Desktop над Windows не работает (не создаются `-wal`/`-shm`).

## Сид и занятый email

`seed_superadmin` поднимает `RuntimeError`, если `SUPERADMIN_EMAIL` уже занят
другим пользователем. Бэкенд при этом не поднимается (entrypoint выходит с
ошибкой → restart loop). Симптом — `docker compose logs backend | grep -i
runtimeerror`.

Если email занят — освободить его (переименовать email другого пользователя)
или задать суперадмину другой.

## Логирование

Настройки: `LOG_LEVEL`, `LOG_FORMAT` (`text` / `json`), `LOG_LEVEL_LIBRARIES`.
Подробности — в README, раздел «Логирование».

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
# фронт отдаёт относительный адрес
curl -s http://localhost:5173/src/api/client.js | grep -o '"VITE_API_URL": "[^"]*"'

# прокси-путь жив
curl -s http://localhost:5173/api/v1/hello

# логин через прокси
curl -s -X POST http://localhost:5173/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<почта>","password":"<пароль>"}'

# почта и телеграм
docker compose exec backend python -m scripts.check_smtp
docker compose exec backend python -m scripts.check_telegram
```

## Что ещё стоит доделать

* прод-режим фронта: `npm run build` + nginx, который проксирует `/api`
  (сейчас работает `npm run dev`, а `server.proxy` есть только у dev-сервера);
* `:5000` опубликован на `0.0.0.0` — с прокси достаточно держать открытым
  только `:5173`;
* `JWT_SECRET_KEY` на сервере — заглушка `replace-with-your-own-random-string`
  из `.env.example`; нужно заменить на `openssl rand -hex 32`;
* `frontend/src/pages/home.js` — мёртвый код, нигде не импортируется;
* `proxy/sing-box.json` — больше не используется.
