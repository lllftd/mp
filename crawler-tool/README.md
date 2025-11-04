# 小红书爬虫使用指南

## 📋 目录
- [环境准备](#环境准备)
- [启动爬虫](#启动爬虫)
- [AI转述配置](#ai转述配置)
- [上传数据到数据库](#上传数据到数据库)
- [完整工作流程](#完整工作流程)

## 🔧 环境准备

### 1. 安装Python依赖

```bash
cd crawler-tool
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

创建 `.env` 文件（可选，如果不创建会使用默认值）：

```env
# 数据库配置
DB_HOST=47.121.133.201
DB_PORT=3306
DB_USER=root
DB_PASSWORD=adminMysql
DB_NAME=jxwq_end

# AI转述配置（使用Ollama）
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=deepseek-r1:14b
LLM_MAX_TOKENS=500

# 爬虫配置
DEFAULT_TYPE_PID=5
DEFAULT_TYPE_CID=10,42
DOWNLOAD_DIR=./downloads
SAVE_DIR=./saved_data
```

### 3. 安装并启动Ollama（用于AI转述）

如果使用AI转述功能，需要先安装Ollama：

**Windows:**
```bash
# 下载并安装Ollama
# 访问 https://ollama.com/download
# 下载Windows版本并安装

# 启动Ollama服务（会自动启动）
# 下载模型（首次使用）
ollama pull deepseek-r1:14b
```

**Linux/Mac:**
```bash
# 安装Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型
ollama pull deepseek-r1:14b
```

## 🚀 启动爬虫（集成AI转述和自动上传）

### 第一步：设置Ollama本地模型（首次使用）

**1. 安装Ollama**

- **Windows**: 访问 https://ollama.com/download 下载并安装
- **Linux/Mac**: 
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

**2. 下载AI模型**

```bash
cd crawler-tool
python setup_ollama.py
```

脚本会自动：
- 检查Ollama是否安装
- 启动Ollama服务
- 下载配置的AI模型（默认：deepseek-r1:14b）

**注意**: 模型文件较大（约8GB），下载需要较长时间和足够的磁盘空间。

### 第二步：启动爬虫

**方法1: 使用脚本启动（推荐）**

**Linux/Mac:**
```bash
cd crawler-tool
chmod +x run.sh
./run.sh
```

**Windows PowerShell:**
```powershell
cd crawler-tool
python xhs3.py
```

**方法2: 直接运行Python脚本**

```bash
cd crawler-tool
python xhs3.py
```

### 交互式配置

启动后会提示：

1. **是否启用AI转述功能？** (y/n)
   - 选择 `y` 启用AI转述（需要Ollama服务运行）
   - 选择 `n` 只爬取原始内容

2. **是否自动上传到数据库？** (y/n, 仅在启用AI时询问)
   - 选择 `y` 爬取完成后自动上传到数据库
   - 选择 `n` 只保存为CSV文件

3. **关键词**：要搜索的小红书关键词（如：深圳美食、潮汕菜）

4. **页数**：要爬取的页数（建议不超过5页）

### 爬虫输出

**启用AI转述时：**
CSV文件包含以下列：
- 标题（原文）
- 描述（原文）
- 图片链接（逗号分隔）
- 笔记ID
- 转述标题（AI改写后）
- 转述描述（AI改写后）
- 内容类型（AI判断）

**未启用AI转述时：**
CSV文件包含以下列：
- 标题
- 描述
- 图片链接（逗号分隔）
- 笔记ID

文件格式：`关键词_时间戳.csv`

## 🤖 AI转述功能（已集成）

### 功能说明

✅ **AI转述功能已完全集成到爬虫中**

- 自动将爬取的内容改写为原创内容
- 保持原意不变，但使用不同的表达方式
- 自动判断内容类型（美食、旅行、穿搭等）
- 使用本地Ollama模型，数据隐私安全

### 工作原理

1. 爬虫获取小红书笔记的标题和描述
2. 如果启用AI转述，调用本地Ollama模型进行改写
3. 保存原文和转述后的内容到CSV
4. 可选择自动上传转述后的内容到数据库

### 配置AI模型

在 `config.py` 或 `.env` 文件中配置：

```env
# AI转述配置
LLM_API_BASE=http://localhost:11434/v1
LLM_MODEL=deepseek-r1:14b  # 可以改为其他模型，如 qwen2.5:7b
LLM_MAX_TOKENS=500
```

### 推荐模型（按性能排序）

**顶级模型（需要32GB+内存）：**
- **deepseek-r1:32b** - 最高质量，约18GB ⭐⭐⭐⭐⭐
- **qwen2.5:32b** - 最高质量（中文优化），约20GB ⭐⭐⭐⭐⭐
- **llama3.1:70b** - 最强大，约40GB，需要64GB+内存 ⭐⭐⭐⭐⭐

**高质量模型（需要16GB+内存）：**
- **deepseek-r1:14b** (默认) - 高质量，约8GB ⭐⭐⭐⭐
- **qwen2.5:14b** - 高质量（中文优化），约9GB ⭐⭐⭐⭐

**轻量级模型（需要8GB+内存）：**
- **qwen2.5:7b** - 良好质量，速度快，约4.5GB ⭐⭐⭐

### 查看模型指南

运行以下命令查看详细的模型信息和系统推荐：

```bash
python model_guide.py
```

这会显示：
- 所有可用模型列表
- 每个模型的详细规格
- 根据您的系统配置推荐适合的模型
- 如何切换模型

### 切换模型

**方法1: 使用 .env 文件（推荐）**

创建或编辑 `.env` 文件：
```env
LLM_MODEL=qwen2.5:32b  # 使用更高级的模型
```

**方法2: 修改 config.py**

直接修改 `config.py` 中的 `LLM_MODEL` 值：
```python
LLM_MODEL = os.getenv('LLM_MODEL', 'qwen2.5:32b')  # 更改默认模型
```

**方法3: 环境变量**

Windows:
```powershell
$env:LLM_MODEL="qwen2.5:32b"
python xhs3.py
```

Linux/Mac:
```bash
export LLM_MODEL=qwen2.5:32b
python xhs3.py
```

**切换后步骤：**
```bash
# 1. 下载新模型
python setup_ollama.py

# 2. 启动爬虫
python xhs3.py
```

## 📤 上传数据到数据库

### 步骤1: 查看推文类型

在上传前，需要知道推文类型ID：

```bash
python list_tweet_types.py
# 或查看特定父类型
python list_tweet_types.py --parent-id 5
```

### 步骤2: 准备数据文件

确保CSV文件包含以下列（可以使用中文或英文列名）：
- `tweets_title` 或 `title` - 标题（必填）
- `tweets_content` 或 `content` - 内容（必填）
- `tweets_describe` 或 `describe` - 简介（必填）
- `tweets_img` 或 `image` - 图片链接，支持JSON数组或逗号分隔（必填）
- `tweets_type_pid` 或 `type_pid` - 类型父ID（必填）
- `tweets_type_cid` 或 `type_cid` - 类型子ID（必填）

可选字段：
- `tweets_user` 或 `user` - 作者
- `like_num` - 点赞数
- `collect_num` - 收藏数
- `browse_num` - 浏览数

### 步骤3: 批量上传

```bash
# 上传CSV文件
python batch_upload_tweets.py 关键词_20240101120000.csv --format csv

# 上传JSON文件
python batch_upload_tweets.py data.json --format json

# 上传Excel文件
python batch_upload_tweets.py data.xlsx --format excel
```

## 📝 完整工作流程

### 方案1: 完整自动化流程（推荐）✨

**一次性完成：爬虫 → AI转述 → 自动上传**

1. **设置Ollama（首次使用）**
   ```bash
   python setup_ollama.py
   ```

2. **启动爬虫**
   ```bash
   python xhs3.py
   ```
   
3. **交互式配置**
   - 启用AI转述？ → 输入 `y`
   - 自动上传到数据库？ → 输入 `y`
   - 输入关键词和页数

4. **自动完成**
   - ✅ 爬取小红书内容
   - ✅ AI转述改写内容
   - ✅ 自动上传到数据库
   - ✅ 保存CSV备份文件

### 方案2: 爬虫 → 手动上传

1. **启动爬虫（启用AI转述，但不自动上传）**
   ```bash
   python xhs3.py
   # 启用AI转述：y
   # 自动上传：n
   ```

2. **获取CSV文件**
   - 包含原文和AI转述后的内容

3. **手动上传到数据库**
   ```bash
   python batch_upload_tweets.py 关键词_时间戳.csv --format csv
   ```

### 方案3: 仅爬取（不使用AI）

1. **启动爬虫**
   ```bash
   python xhs3.py
   # 启用AI转述：n
   ```

2. **获取原始CSV文件**

3. **手动处理或上传**

## ⚙️ 配置说明

### 爬虫配置 (`spider_config.py`)

- `DELAY_MIN/MAX`: 请求延迟范围（秒）
- `PAGE_DELAY_MIN/MAX`: 页面间延迟范围（秒）
- `MIN_REQUEST_INTERVAL`: 最小请求间隔（秒）
- `RECOMMENDED_MAX_PAGES`: 建议最大页数（默认5页）

### 应用配置 (`config.py`)

- `DB_HOST/PORT/USER/PASSWORD/NAME`: 数据库连接信息
- `LLM_API_BASE`: Ollama API地址
- `LLM_MODEL`: 使用的AI模型
- `DEFAULT_TYPE_PID/CID`: 默认推文类型ID

## 🐛 常见问题

### 1. 爬虫被限制访问

- 减少爬取页数
- 增加延迟时间
- 等待更长时间后重试

### 2. AI转述失败

- 检查Ollama服务是否运行：`ollama list`
- 检查模型是否下载：`ollama list`
- 检查API地址是否正确

### 3. 数据库连接失败

- 检查数据库服务器是否可访问
- 检查 `.env` 文件中的数据库配置
- 使用 `python insert_tweets.py --test` 测试连接

## 📞 支持

如有问题，请检查：
- `python insert_tweets.py --test` - 测试数据库连接
- `python list_tweet_types.py` - 查看推文类型

