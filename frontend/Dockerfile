# --- Сборка: Vite собирает статику в dist/ ---
FROM node:22-alpine AS build
WORKDIR /app

# Реестр npm можно переопределить сборкой: NPM_REGISTRY=https://registry.npmmirror.com
# Нужно там, где официальный реестр недоступен (например, IPv4 до Cloudflare закрыт).
ARG NPM_REGISTRY=https://registry.npmjs.org

COPY package*.json ./
# --no-audit/--no-fund: не ходим в реестр за лишними запросами — на слабой сети
# они висят и роняют всю установку.
RUN npm ci --no-audit --no-fund --registry=$NPM_REGISTRY

COPY . .
CMD ["npm", "run", "dev"]
