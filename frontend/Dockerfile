# --- Сборка: Vite собирает статику в dist/ ---
FROM node:22-alpine AS build
WORKDIR /app

<<<<<<< HEAD
# Реестр npm можно переопределить сборкой: NPM_REGISTRY=https://registry.npmmirror.com
# Нужно там, где официальный реестр недоступен (например, IPv4 до Cloudflare закрыт).
ARG NPM_REGISTRY=https://registry.npmjs.org

COPY package*.json ./
# --no-audit/--no-fund: не ходим в реестр за лишними запросами — на слабой сети
# они висят и роняют всю установку.
RUN npm ci --no-audit --no-fund --registry=$NPM_REGISTRY

COPY . .
CMD ["npm", "run", "dev"]
=======
COPY package*.json ./
RUN npm ci

COPY . .

# Адрес API вшивается в сборку: Vite подставляет import.meta.env.VITE_API_URL
# на этапе build, а не при запуске контейнера. Сменили адрес — пересоберите образ.
ARG VITE_API_URL=http://localhost:5000/api/v1
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# --- Раздача: nginx отдаёт готовые файлы, Node в итоговом образе нет ---
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
>>>>>>> origin/dev
