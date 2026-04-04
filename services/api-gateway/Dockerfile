# Edge Crew v3.0 API Gateway Dockerfile
# Based on Kong Gateway with custom plugins

FROM kong:3.5

USER root

# Install Python and required dependencies for custom plugins
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for custom plugins
RUN pip3 install --no-cache-dir \
    kong-pdk==0.33 \
    PyJWT==2.8.0 \
    redis==5.0.1 \
    requests==2.31.0 \
    cryptography==41.0.7

# Create plugin directories
RUN mkdir -p /usr/local/kong/plugins/edge-auth \
    /usr/local/kong/plugins/edge-rate-limiting \
    /usr/local/kong/plugins/edge-transform \
    /usr/local/kong/logs

# Copy custom plugins
COPY plugins/auth.py /usr/local/kong/plugins/edge-auth/handler.py
COPY plugins/rate_limiting.py /usr/local/kong/plugins/edge-rate-limiting/handler.py
COPY plugins/transform.py /usr/local/kong/plugins/edge-transform/handler.py

# Create plugin schemas
RUN echo '{\"name\": \"edge-auth\", \"fields\": [{\"jwt_secret\": {\"type\": \"string\"}}]}' > /usr/local/kong/plugins/edge-auth/schema.json
RUN echo '{\"name\": \"edge-rate-limiting\", \"fields\": [{\"minute\": {\"type\": \"number\", \"default\": 60}}]}' > /usr/local/kong/plugins/edge-rate-limiting/schema.json
RUN echo '{\"name\": \"edge-transform\", \"fields\": [{\"request_headers_add\": {\"type\": \"map\"}}]}' > /usr/local/kong/plugins/edge-transform/schema.json

# Set proper permissions
RUN chown -R kong:kong /usr/local/kong/plugins /usr/local/kong/logs

# Copy Kong configuration
COPY kong.yml /kong/declarative/kong.yml

# Environment variables for Kong
ENV KONG_DATABASE=off
ENV KONG_DECLARATIVE_CONFIG=/kong/declarative/kong.yml
ENV KONG_PROXY_ACCESS_LOG=/dev/stdout
ENV KONG_ADMIN_ACCESS_LOG=/dev/stdout
ENV KONG_PROXY_ERROR_LOG=/dev/stderr
ENV KONG_ADMIN_ERROR_LOG=/dev/stderr
ENV KONG_PLUGINS=bundled,edge-auth,edge-rate-limiting,edge-transform
ENV KONG_PLUGINSERVER_NAMES=python
ENV KONG_PLUGINSERVER_PYTHON_SOCKET=/usr/local/kong/python-pluginserver.sock
ENV KONG_PLUGINSERVER_PYTHON_START_CMD=/usr/local/bin/kong-python-pluginserver
ENV KONG_PLUGINSERVER_PYTHON_QUERY_CMD=/usr/local/bin/kong-python-pluginserver --dump-all-plugins
ENV KONG_LUA_PACKAGE_PATH=/usr/local/kong/plugins/?.lua;;

# Switch back to kong user
USER kong

# Expose ports
EXPOSE 8000 8443 8001 8444

# Health check
HEALTHCHECK --interval=10s --timeout=10s --retries=10 \
    CMD kong health

# Start Kong
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["kong", "docker-start"]
