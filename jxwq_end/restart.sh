#!/usr/bin/env bash
# Spring Boot 服务重启脚本

cd "$(dirname "$0")"

SERVER_PORT=8080

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Spring Boot 服务重启脚本${NC}"
echo -e "${GREEN}  端口: ${SERVER_PORT}${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 1. 停止现有服务
echo -e "${YELLOW}步骤 1: 检查并停止现有服务...${NC}"
PORT_PID=$(lsof -ti:${SERVER_PORT} 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo -e "${YELLOW}发现服务正在运行 (PID: $PORT_PID)，正在停止...${NC}"
    kill -TERM "$PORT_PID" 2>/dev/null || true
    sleep 2
    
    # 如果还在运行，强制关闭
    if kill -0 "$PORT_PID" 2>/dev/null; then
        echo -e "${YELLOW}强制关闭进程...${NC}"
        kill -9 "$PORT_PID" 2>/dev/null || true
        sleep 1
    fi
    
    echo -e "${GREEN}✅ 服务已停止${NC}"
else
    echo -e "${GREEN}✅ 服务未运行${NC}"
fi

echo ""

# 2. 等待端口完全释放
echo -e "${YELLOW}步骤 2: 等待端口释放...${NC}"
for i in {1..5}; do
    if ! lsof -Pi :${SERVER_PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 端口已释放${NC}"
        break
    fi
    sleep 1
done

echo ""

# 3. 启动服务
echo -e "${YELLOW}步骤 3: 启动服务...${NC}"
echo -e "${GREEN}执行 ./run.sh 启动服务${NC}"
echo ""

# 调用 run.sh 启动服务
exec ./run.sh

