# Plane MAWESI — web. Imagen OFICIAL de Plane (nginx + config) con el cliente compilado con el overlay ext/.
# Contexto de build: apps/web/build/client del checkout armado con scripts/assemble-web.sh.
ARG UPSTREAM_VERSION=v1.4.2
FROM makeplane/plane-frontend:${UPSTREAM_VERSION}
RUN rm -rf /usr/share/nginx/html/*
COPY . /usr/share/nginx/html/
# Reglas propias de nginx (portadas). Se incluyen dentro del server de Plane; falla si su nginx.conf cambió.
RUN mkdir -p /etc/nginx/mawesi && mv /usr/share/nginx/html/mawesi-nginx/*.conf /etc/nginx/mawesi/ && rmdir /usr/share/nginx/html/mawesi-nginx \
 && [ "$(grep -c 'listen 3000;' /etc/nginx/nginx.conf)" = "1" ] \
 && sed -i 's|listen 3000;|listen 3000;\n    include /etc/nginx/mawesi/*.conf;|' /etc/nginx/nginx.conf \
 && nginx -t
