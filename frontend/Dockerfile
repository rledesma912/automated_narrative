# ── Stage 1: build TypeScript ────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build:css && npm run build
# Las vistas EJS no se compilan — copiarlas donde el código compilado las espera
RUN cp -r src/views dist/views

# ── Stage 2: imagen de producción ────────────────────────────────────────────
FROM node:22-alpine
WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist
COPY public/ ./public/
COPY config/ ./config/

RUN mkdir -p ./public/output_stories

EXPOSE 3000

CMD ["node", "dist/server.js"]
