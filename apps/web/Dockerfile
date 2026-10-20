FROM node:22.23.2-alpine AS web-build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM nginx:1.28-alpine
COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=web-build /app/dist/ /usr/share/nginx/html/
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
