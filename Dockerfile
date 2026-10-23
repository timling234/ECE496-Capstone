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
# FR-7/8/9/10: credentials injected at runtime; persistent state on /data.
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/feed',timeout=3).close()"
CMD ["python", "run_app.py", "--host", "0.0.0.0", "--db", "/data/asap.sqlite3", "--port", "5000"]
