# AI 模拟面试官系统 — 后端镜像
# FastAPI + LangGraph + LangChain + ChromaDB + BGE
FROM python:3.11-slim

WORKDIR /app

# 构建依赖 (部分编译型包需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖 (利用 Docker 层缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码 (代码变动不重装依赖)
COPY . .

EXPOSE 8000

# 启动服务; 首次需先建库 (见 docker-compose 说明 / README)
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
