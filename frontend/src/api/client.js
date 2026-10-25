import axios from 'axios'

export const api = axios.create({
  // Относительный адрес по умолчанию: запрос уходит на тот же origin, где
  // открыта страница. Docker-имя 'backend' (или 'localhost') на сервере
  // означало бы машину пользователя, а не сам сервер.
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
})