FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc

COPY services/processor/requirements.txt .

RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*

COPY services/processor /app/services/processor
COPY common/ /app/common

RUN addgroup --system processorUser && adduser --system --group processorUser
USER processorUser

ENTRYPOINT [ "python3", "-u", "-m", "services.processor.main" ]