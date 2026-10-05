# Dev-образ фронтенда для docker compose (vite dev server с моками или прокси на backend).
FROM node:22-alpine
# Рабочая папка /app/frontend: тогда alias @seed (../data/seed) указывает на /app/data/seed —
# compose монтирует туда ./data/seed.
WORKDIR /app/frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
