# BeCoMe Frontend - Multi-stage Docker Build
#
# Stage 1: Build the React application
# Stage 2: Serve with nginx
#
# Usage:
#   docker build -t become-frontend .
#   docker run -p 3000:8080 become-frontend

FROM node:20-alpine AS builder

WORKDIR /app

# Build-time values injected via Railway env vars. Every VITE_* variable the SPA
# reads has to be declared here: Railway passes service variables as build args, and
# Vite only inlines a variable that exists in the builder's environment when
# `npm run build` runs. An undeclared one is simply absent, and the code reading it
# collapses to `undefined` -- which is how the Sentry init below went missing from
# all three deployed bundles while VITE_SENTRY_DSN was set on every service.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
ARG VITE_SENTRY_DSN
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
ARG VITE_APP_ENV
ENV VITE_APP_ENV=${VITE_APP_ENV}

# Copy package files first for better caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Bake the API origin into the SPA's Content-Security-Policy. VITE_API_URL is
# cross-origin on the deploys (https://api.<domain>/api/v1) and a relative path
# locally, in which case the placeholder collapses to nothing and connect-src
# stays at 'self'. Done here rather than at runtime so the served policy is fixed
# in the image and cannot drift with the container environment.
RUN API_ORIGIN="$(printf '%s' "${VITE_API_URL}" | sed -n 's#^\(https\{0,1\}://[^/]*\).*#\1#p')" && \
    if [ -n "${API_ORIGIN}" ]; then REPLACEMENT=" ${API_ORIGIN}"; else REPLACEMENT=""; fi && \
    sed -i "s#__API_ORIGIN__#${REPLACEMENT}#g" nginx.conf && \
    ! grep -q '__API_ORIGIN__' nginx.conf

# Production stage
# nginx-unprivileged runs as the non-root "nginx" user (UID 101) and listens on 8080.
FROM nginxinc/nginx-unprivileged:alpine

# Copy built files from builder stage (owned by the non-root nginx user)
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

# Copy nginx configuration from the builder, where the CSP placeholder was resolved
# (nginx user must be able to read it at startup)
COPY --from=builder --chown=nginx:nginx /app/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 8080 (non-root nginx cannot bind privileged port 80)
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
