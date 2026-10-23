FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY reference_verifier ./reference_verifier
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app
USER app
EXPOSE 8765
CMD ["uvicorn", "reference_verifier.server:app", "--host", "0.0.0.0", "--port", "8765", "--no-proxy-headers"]
