FROM python:3.12.13-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af AS builder
ENV PIP_NO_CACHE_DIR=1 UV_LINK_MODE=copy
WORKDIR /app
RUN python -m pip install "uv==0.12.1"
COPY pyproject.toml uv.lock README.md ./
COPY lore ./lore
RUN uv sync --frozen --no-dev --no-editable --extra aws --extra cockroach

FROM python:3.12.13-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af AS runtime
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --system lore && useradd --system --gid lore --home /app lore
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY migrations ./migrations
USER lore
EXPOSE 8000
ENTRYPOINT ["lore-runtime"]
CMD ["webhook", "--host", "0.0.0.0", "--port", "8000"]
