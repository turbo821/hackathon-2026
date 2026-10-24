# --- Сборка: Vite собирает статику в dist/ ---
FROM node:22-alpine AS build
WORKDIR /app

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
