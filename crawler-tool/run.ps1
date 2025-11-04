# 集成爬虫脚本 - 一键运行：爬虫 → AI转述 → 水印清洗 → 上传数据库

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 查找虚拟环境：优先使用项目根目录的 env，否则使用当前目录的 venv
$ProjectRoot = Split-Path -Parent $ScriptDir
$VenvPath = ""

if (Test-Path "$ProjectRoot\env") {
    # 使用项目根目录的 env
    $VenvPath = "$ProjectRoot\env"
    Write-Host "使用项目根目录虚拟环境: $VenvPath"
} elseif (Test-Path "$ScriptDir\venv") {
    # 使用当前目录的 venv（向后兼容）
    $VenvPath = "$ScriptDir\venv"
    Write-Host "使用当前目录虚拟环境: $VenvPath"
} else {
    # 如果都不存在，在当前目录创建 venv
    Write-Host "未找到虚拟环境，正在创建..."
    python -m venv "$ScriptDir\venv"
    $VenvPath = "$ScriptDir\venv"
}

# 激活虚拟环境
$ActivateScript = "$VenvPath\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    & $ActivateScript
} else {
    Write-Host "[ERROR] 虚拟环境激活脚本不存在: $ActivateScript"
    exit 1
}

# 安装依赖（如果需要）
$DepsFlag = "$VenvPath\.deps_installed"
if (-not (Test-Path $DepsFlag)) {
    Write-Host "安装依赖..."
    pip install -r "$ScriptDir\requirements.txt"
    New-Item -ItemType File -Path $DepsFlag -Force | Out-Null
}

# 检查参数
if ($args.Count -lt 2) {
    Write-Host "用法: .\run.ps1 <关键词> <页数>"
    Write-Host "示例: .\run.ps1 深圳美食 5"
    exit 1
}

# 运行集成爬虫脚本
python "$ScriptDir\crawler.py" $args

