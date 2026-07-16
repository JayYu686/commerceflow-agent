FROM python:3.11-slim AS runtime

ARG VERSION=dev
ARG REVISION=unknown

LABEL org.opencontainers.image.source="https://github.com/JayYu686/commerceflow-agent" \
      org.opencontainers.image.description="CommerceFlow Agent controlled after-sales API" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace/services/api

COPY services/api/requirements-lock.txt ./requirements-lock.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements-lock.txt

COPY services/api/ ./
COPY data/policies/ /workspace/data/policies/
COPY eval/reports/ /workspace/eval/reports/
COPY LICENSE /workspace/LICENSE

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

ENTRYPOINT ["./docker-entrypoint.sh"]
