FROM python:3.13-slim

WORKDIR /app

# Install uv to manage dependencies from pyproject.toml/uv.lock.
RUN pip install --no-cache-dir uv

# Copy dependency files first to keep build cache effective.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend source code.
COPY . ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
