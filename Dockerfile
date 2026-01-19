FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.2.1

COPY pyproject.toml poetry.lock* /app/

# 先只装依赖，不安装当前项目（此时还没 src）
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --only main --no-root

# 再复制源码
COPY src /app/src

# 安装当前项目（把 py_lab 包装进环境）
RUN poetry install --no-interaction --no-ansi --only main

EXPOSE 8000
CMD ["uvicorn", "py_lab.api:app", "--host", "0.0.0.0", "--port", "8000"]
