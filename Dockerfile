# FR-10: Current Python runtime, provider pipeline and verification harness
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 asap && useradd --uid 10001 --gid asap --no-create-home asap \
    && mkdir -p /data && chown asap:asap /data
COPY --chown=asap:asap src/ ./src/
COPY --chown=asap:asap tests/ ./tests/
COPY --chown=asap:asap config/ ./config/
COPY --chown=asap:asap run_tests.py run_demo.py run_polling.py run_app.py ./
USER asap
VOLUME ["/data"]
# All example sources are disabled. No credentials or live requests by default.
CMD ["python", "run_polling.py", "--db", "/data/asap.sqlite3"]
