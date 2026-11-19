# Tenara API + worker image (same image, different command).
# Build context: services/api. Models (services/api/models) and storage are NOT baked in:
# they are bind-mounted by docker-compose.prod.yml (SMPL-X is non-commercial, the repo is public).

# ---- build: resolve the locked dependencies into a venv, with CPU-only torch ----
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
# uv.lock pins the default PyPI torch, which on Linux x86_64 drags in ~3 GB of CUDA wheels
# (nvidia-*, triton). This server has no GPU, so drop those and install the CPU build of the
# same torch version from the PyTorch CPU index instead.
RUN uv export --frozen --no-hashes --no-emit-project --extra body3d -o all.txt \
 && grep -viE '^(torch|triton|nvidia-)' all.txt > req.txt \
 && grep -iE '^torch==' all.txt | head -1 | sed -E 's/^(torch==[^ ;]+).*/\1/' > torch.txt \
 && uv venv /opt/venv
# --no-deps: req.txt is the complete locked list; without it smplx pulls CUDA torch back in
RUN VIRTUAL_ENV=/opt/venv uv pip install --no-cache --no-deps -r req.txt
# CPU index only (adding PyPI back makes uv pick the CUDA build again); --no-deps because torch's
# pure-Python dependencies (sympy, networkx, jinja2, ...) are already in req.txt.
RUN VIRTUAL_ENV=/opt/venv uv pip install --no-cache --no-deps -r torch.txt \
      --index-url https://download.pytorch.org/whl/cpu

# ---- runtime ----
FROM python:3.12-slim-bookworm
# opencv (a mediapipe dependency) needs these shared libraries
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 1000 --create-home tenara \
 && mkdir -p /data/storage /data/fastembed && chown -R tenara /data

# config.py finds the repo-root .env at parents[4]; mirror the repo layout so that path exists
# (the file itself is absent here: all settings arrive as real environment variables).
WORKDIR /srv/tenara/services/api
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini worker.py ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY data ./data

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STORAGE_DIR=/data/storage \
    FASTEMBED_CACHE_PATH=/data/fastembed
USER tenara
EXPOSE 8000
# --proxy-headers: the API sits behind Caddy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
