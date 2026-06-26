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

# API URL injected at build time via Railway env vars
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

# Copy package files first for better caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Production stage
# nginx-unprivileged runs as the non-root "nginx" user (UID 101) and listens on 8080.
FROM nginxinc/nginx-unprivileged:alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 8080 (non-root nginx cannot bind privileged port 80)
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
