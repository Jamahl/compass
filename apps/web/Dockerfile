# Dev-mode Vite in a container. Fast iteration, proxies /api/* -> api:8000.
FROM node:20-alpine

WORKDIR /app

# Install only the web workspace's deps. Root package.json is copied for the
# workspaces resolver, but we don't install there to keep the image small.
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json

# Install deps only for the "web" workspace.
RUN npm install --workspace web --include-workspace-root --no-audit --no-fund

# Bring in the actual source last so code edits invalidate less cache.
COPY apps/web/ ./apps/web/

WORKDIR /app/apps/web

EXPOSE 5173

# --host=0.0.0.0 exposes Vite to the host; docker-compose maps it to :5173.
CMD ["npx", "vite", "dev", "--host", "0.0.0.0", "--port", "5173"]
