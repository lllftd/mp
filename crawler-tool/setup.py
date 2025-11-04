#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动配置Ollama和DeepSeek模型
一键完成：检查安装 → 启动服务 → 下载模型
"""
import os
import sys
import subprocess
import requests
import time
import platform

# 配置
OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "deepseek-r1:32b"
OLLAMA_DOWNLOAD_URLS = {
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Linux": "https://ollama.com/download/ollama-linux-amd64",
    "Darwin": "https://ollama.com/download/Ollama-darwin"
}


def print_step(step, message):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"步骤 {step}: {message}")
    print(f"{'='*60}")


def check_ollama_installed():
    """检查Ollama是否已安装"""
    try:
        result = subprocess.run(
            ['ollama', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"[OK] Ollama已安装: {version}")
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_ollama():
    """安装Ollama"""
    system = platform.system()
    print(f"\n检测到系统: {system}")
    
    if system == "Windows":
        print("\n请手动安装Ollama:")
        print("1. 访问: https://ollama.com/download")
        print("2. 下载 Windows 版本并安装")
        print("3. 安装完成后重新运行此脚本")
        return False
    elif system == "Linux":
        print("\n正在安装Ollama (Linux)...")
        try:
            subprocess.run(
                ['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh'],
                shell=True,
                check=True
            )
            print("[OK] Ollama安装完成")
            return True
        except Exception as e:
            print(f"❌ 安装失败: {e}")
            print("请手动运行: curl -fsSL https://ollama.com/install.sh | sh")
            return False
    elif system == "Darwin":
        print("\n请手动安装Ollama (Mac):")
        print("1. 访问: https://ollama.com/download")
        print("2. 下载 macOS 版本并安装")
        print("3. 或运行: brew install ollama")
        return False
    else:
        print(f"[ERROR] 不支持的系统: {system}")
        return False


def check_ollama_running():
    """检查Ollama服务是否运行"""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def start_ollama_service():
    """启动Ollama服务"""
    print("正在启动Ollama服务...")
    
    system = platform.system()
    if system == "Windows":
        try:
            # Windows上Ollama通常作为服务运行
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            print("已启动Ollama服务进程")
            time.sleep(3)
            return check_ollama_running()
        except Exception as e:
            print(f"启动失败: {e}")
            print("请手动启动Ollama服务")
            return False
    else:
        try:
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            time.sleep(3)
            return check_ollama_running()
        except Exception as e:
            print(f"启动失败: {e}")
            return False


def check_model_exists():
    """检查模型是否已下载"""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            return MODEL_NAME in model_names
        return False
    except Exception as e:
        print(f"检查模型失败: {e}")
        return False


def download_model():
    """下载DeepSeek模型"""
    print(f"\n准备下载模型: {MODEL_NAME}")
    print("注意：模型文件约18GB，下载需要较长时间")
    print("请确保：")
    print("- 网络连接稳定")
    print("- 有足够的磁盘空间（至少20GB）")
    print("- 系统内存至少32GB")
    
    confirm = input("\n确认下载？(y/n): ").strip().lower()
    if confirm != 'y':
        print("取消下载")
        return False
    
    print("\n开始下载，请耐心等待...")
    print("下载进度将实时显示...")
    
    try:
        process = subprocess.Popen(
            ['ollama', 'pull', MODEL_NAME],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 实时显示进度
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
        if process.returncode == 0:
            print(f"\n[OK] 模型 {MODEL_NAME} 下载成功！")
            return True
        else:
            print(f"\n[ERROR] 模型下载失败")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 下载出错: {e}")
        return False


def verify_setup():
    """验证配置"""
    print("\n" + "="*60)
    print("验证配置")
    print("="*60)
    
    # 检查Ollama
    if not check_ollama_installed():
        print("[ERROR] Ollama未安装")
        return False
    print("[OK] Ollama已安装")
    
    # 检查服务
    if not check_ollama_running():
        print("[ERROR] Ollama服务未运行")
        return False
    print("[OK] Ollama服务运行中")
    
    # 检查模型
    if not check_model_exists():
        print(f"[ERROR] 模型 {MODEL_NAME} 未下载")
        return False
    print(f"[OK] 模型 {MODEL_NAME} 已下载")
    
    print("\n" + "="*60)
    print("[OK] 配置完成！所有检查通过")
    print("="*60)
    return True


def main():
    """主函数"""
    print("="*60)
    print("Ollama & DeepSeek 自动配置工具")
    print("="*60)
    
    # 步骤1: 检查并安装Ollama
    print_step(1, "检查Ollama安装")
    if not check_ollama_installed():
        print("[ERROR] Ollama未安装")
        if not install_ollama():
            print("\n请先安装Ollama后再运行此脚本")
            return
    else:
        print("[OK] Ollama已安装")
    
    # 步骤2: 检查并启动Ollama服务
    print_step(2, "检查Ollama服务")
    if not check_ollama_running():
        print("[WARN] Ollama服务未运行，尝试启动...")
        if not start_ollama_service():
            print("[ERROR] 无法启动Ollama服务")
            print("请手动启动：")
            print("  Windows: Ollama会自动启动，或运行 'ollama serve'")
            print("  Linux/Mac: 运行 'ollama serve'")
            return
    else:
        print("[OK] Ollama服务运行中")
    
    # 步骤3: 检查并下载模型
    print_step(3, "检查DeepSeek模型")
    if not check_model_exists():
        print(f"[WARN] 模型 {MODEL_NAME} 未下载")
        if not download_model():
            print("\n模型下载失败，请检查网络连接后重试")
            return
    else:
        print(f"[OK] 模型 {MODEL_NAME} 已下载")
    
    # 步骤4: 验证配置
    print_step(4, "验证配置")
    if verify_setup():
        print("\n配置成功！")
        print("\n现在可以使用爬虫了：")
        print("  python crawler.py <关键词> <页数>")
        print("  示例: python crawler.py 深圳美食 5")
    else:
        print("\n[ERROR] 配置验证失败，请检查上述步骤")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")

