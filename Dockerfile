FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Git (needed for pylti install)
RUN apt-get update && apt-get install -y --no-install-recommends git

# Pre-compile at build-time
ENV UV_COMPILE_BYTECODE=1
# Silence warnings due to mounted cache
ENV UV_LINK_MODE=copy
# Install dependencies, including waitress as a production server
COPY pyproject.toml pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --prefix=/install -r pyproject.toml \
    && uv pip install --prefix=/install waitress~=3.0

# Bring in the rest of the code
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --prefix=/install .


FROM python:3.14-slim
COPY --from=builder /install /usr/local
COPY --chmod=0755 container_entrypoint.sh /usr/local/bin

# Ideally will run image read-only anyway, and will never re-run app in the same container.
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

ENTRYPOINT ["sh", "/usr/local/bin/container_entrypoint.sh"]
# Default to serve; see container_entrypoint.sh
CMD ["serve"]
