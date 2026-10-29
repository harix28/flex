FROM nginx:alpine

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 443

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-check-certificate --quiet --tries=1 --spider https://127.0.0.1/health/deployment || exit 1

CMD ["nginx", "-g", "daemon off;"]
