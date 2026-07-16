FROM node:22-alpine AS dependencies
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM dependencies AS builder
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY apps/web/ ./
RUN npm run build

FROM node:22-alpine AS runtime
ARG VERSION=dev
ARG REVISION=unknown

LABEL org.opencontainers.image.source="https://github.com/JayYu686/commerceflow-agent" \
      org.opencontainers.image.description="CommerceFlow Agent Operations Console" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="MIT"

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs

EXPOSE 3000
CMD ["node", "server.js"]
