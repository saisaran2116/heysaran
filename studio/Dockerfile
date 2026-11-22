FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build && npm prune --omit=dev
FROM node:24-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0
COPY --chown=node:node --from=build /app/node_modules node_modules
COPY --chown=node:node --from=build /app/dist dist
COPY --chown=node:node --from=build /app/server server
COPY --chown=node:node package.json .
USER node
EXPOSE 3000
CMD ["node","server/index.js"]
