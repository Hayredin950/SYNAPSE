# ── Stage 1: Dependencies (cached unless package.json changes) ────────────────
FROM node:20-alpine AS deps
WORKDIR /app

# Copy ONLY package files first — Docker caches this layer until they change
COPY package.json package-lock.json ./
RUN npm install

# ── Stage 2: Builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npx next build

# ── Stage 3: Development (used by docker-compose) ─────────────────────────────
FROM node:20-alpine AS development
WORKDIR /app

# Reuse cached node_modules — only reinstall if package.json changed
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

CMD ["npx", "next", "dev", "-p", "3000"]

# ── Stage 4: Production ───────────────────────────────────────────────────────
FROM node:20-alpine AS production
WORKDIR /app

RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid  1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

CMD ["node", "server.js"]
