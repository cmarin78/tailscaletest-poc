FROM postgres:16-alpine

# init.sql is auto-run by postgres on first startup
COPY init.sql /docker-entrypoint-initdb.d/

ENV POSTGRES_DB=tailscaletest
ENV POSTGRES_USER=tailscaletest
ENV POSTGRES_PASSWORD=tailscaletest