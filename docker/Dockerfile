FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY gripprobe /app/gripprobe
COPY specs /app/specs
RUN pip install --no-cache-dir .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
