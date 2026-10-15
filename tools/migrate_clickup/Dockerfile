# Copia incremental ClickUp -> MWSTASKS (sync.py) para correr por cron en el servidor hasta el corte.
# Construir desde esta carpeta: docker build -t mwstasks-clickup-sync:local tools/migrate_clickup
FROM python:3.12-slim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd -u 1000 -m mwsync  # "sync" ya existe en Debian
COPY --chown=1000:1000 . /app/tools/migrate_clickup
WORKDIR /app
USER 1000
ENTRYPOINT ["python", "-m", "tools.migrate_clickup.sync"]
