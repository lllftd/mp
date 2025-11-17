#!/usr/bin/env bash
# Spring Boot 服务器启动脚本
# 功能：固定端口启动服务器，退出脚本时自动关闭服务器

cd "$(dirname "$0")"

# 服务器端口（从application.yml读取，确保固定）
SERVER_PORT=8080

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Spring Boot 服务器启动脚本${NC}"
echo -e "${GREEN}  端口: ${SERVER_PORT}${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查Maven是否安装
if ! command -v mvn &> /dev/null; then
    echo -e "${RED}错误: 未找到 Maven，请先安装 Maven${NC}"
    exit 1
fi

# 检查Java是否安装
if ! command -v java &> /dev/null; then
    echo -e "${RED}错误: 未找到 Java，请先安装 Java${NC}"
    exit 1
fi

# 检查端口是否被占用
if lsof -Pi :${SERVER_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}警告: 端口 ${SERVER_PORT} 已被占用${NC}"
    echo -e "${YELLOW}正在尝试关闭占用该端口的进程...${NC}"
    lsof -ti:${SERVER_PORT} | xargs kill -9 2>/dev/null || true
    sleep 2
    if lsof -Pi :${SERVER_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${RED}错误: 无法关闭占用端口 ${SERVER_PORT} 的进程${NC}"
        echo -e "${YELLOW}请手动关闭占用该端口的进程后重试${NC}"
        exit 1
    else
        echo -e "${GREEN}端口已释放${NC}"
    fi
fi

# 清理函数：在脚本退出时调用
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务器...${NC}"
    
    # 查找并关闭Java进程（Spring Boot应用）
    if [ ! -z "$SERVER_PID" ]; then
        echo -e "${YELLOW}关闭进程 PID: $SERVER_PID${NC}"
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        sleep 2
        
        # 如果还在运行，强制关闭
        if kill -0 "$SERVER_PID" 2>/dev/null; then
            echo -e "${YELLOW}强制关闭进程...${NC}"
            kill -9 "$SERVER_PID" 2>/dev/null || true
        fi
    fi
    
    # 也尝试通过端口关闭
    PORT_PID=$(lsof -ti:${SERVER_PORT} 2>/dev/null)
    if [ ! -z "$PORT_PID" ]; then
        echo -e "${YELLOW}关闭占用端口 ${SERVER_PORT} 的进程: $PORT_PID${NC}"
        kill -TERM "$PORT_PID" 2>/dev/null || true
        sleep 1
        kill -9 "$PORT_PID" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}服务器已关闭${NC}"
    exit 0
}

# 注册清理函数，捕获退出信号
trap cleanup SIGINT SIGTERM EXIT

# 编译项目（如果需要）
echo -e "${GREEN}正在编译项目...${NC}"
mvn clean package -DskipTests -q
if [ $? -ne 0 ]; then
    echo -e "${RED}编译失败${NC}"
    exit 1
fi

# 启动服务器
echo -e "${GREEN}正在启动服务器（端口: ${SERVER_PORT}）...${NC}"
echo -e "${YELLOW}按 Ctrl+C 退出服务器${NC}"
echo ""

# 后台启动服务器并保存PID
cd jxwq-server
mvn spring-boot:run > ../server.log 2>&1 &
SERVER_PID=$!

# 等待服务器启动
echo -e "${YELLOW}等待服务器启动...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:${SERVER_PORT} > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  服务器启动成功！${NC}"
        echo -e "${GREEN}  访问地址: http://localhost:${SERVER_PORT}${NC}"
        echo -e "${GREEN}  API文档: http://localhost:${SERVER_PORT}/doc.html${NC}"
        echo -e "${GREEN}  进程 PID: $SERVER_PID${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        break
    fi
    sleep 1
    echo -n "."
done

# 检查服务器是否启动成功
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo ""
    echo -e "${RED}服务器启动失败，请查看日志: server.log${NC}"
    tail -20 ../server.log
    exit 1
fi

# 等待服务器进程结束（前台运行，以便捕获Ctrl+C）
wait $SERVER_PID

