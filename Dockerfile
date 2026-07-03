FROM condaforge/miniforge3:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG APP_UID=1000
ARG APP_GID=1000

WORKDIR /app

RUN if ! getent group "${APP_GID}" >/dev/null; then groupadd --gid "${APP_GID}" rpi-meteo; fi \
    && if ! getent passwd "${APP_UID}" >/dev/null; then useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash rpi-meteo; fi \
    && mkdir -p /app/data \
    && chown -R "${APP_UID}:${APP_GID}" /app

COPY environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml \
    && conda clean --all --yes \
    && rm -f /tmp/environment.yml

ENV PATH=/opt/conda/envs/rpi-meteo/bin:$PATH

COPY --chown=${APP_UID}:${APP_GID} app ./app
COPY --chown=${APP_UID}:${APP_GID} tools ./tools

USER ${APP_UID}:${APP_GID}

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host ${RPI3_METEO_HOST:-0.0.0.0} --port ${RPI3_METEO_PORT:-8000}"]
