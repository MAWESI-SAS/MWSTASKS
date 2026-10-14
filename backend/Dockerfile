# Plane MAWESI — backend. Se monta sobre la imagen OFICIAL de Plane, sin tocar su código.
ARG UPSTREAM_VERSION=v1.4.2
FROM makeplane/plane-backend:${UPSTREAM_VERSION}
COPY plane_mawesi /code/plane_mawesi
ENV DJANGO_SETTINGS_MODULE=plane_mawesi.settings
