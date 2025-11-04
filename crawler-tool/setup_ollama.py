#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama本地模型设置脚本
用于下载和管理Ollama模型
"""
import os
import sys
import subprocess
import requests
import time
from config import Config


def check_ollama_installed() -> bool:
    """检查Ollama是否已安装"""
    try:
        result = subprocess.run(
            ['ollama', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_ollama_running() -> bool:
    """检查Ollama服务是否运行"""
    try:
        response = requests.get(
            Config.LLM_API_BASE.replace('/v1', '/api/tags'),
            timeout=5
        )
        return response.status_code == 200
    except:
        return False


def start_ollama_service():
    """启动Ollama服务（Windows）"""
    if sys.platform == 'win32':
        try:
            # 尝试启动Ollama服务
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            print("正在启动Ollama服务...")
            time.sleep(3)
            return check_ollama_running()
        except Exception as e:
            print(f"启动Ollama服务失败: {e}")
            return False
    return False


def list_models() -> list:
    """列出已安装的模型"""
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            models = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            return models
        return []
    except Exception as e:
        print(f"获取模型列表失败: {e}")
        return []


def download_model(model_name: str = None):
    """下载指定的模型"""
    if model_name is None:
        model_name = Config.LLM_MODEL
    
    print(f"准备下载模型: {model_name}")
    print("注意：模型下载可能需要较长时间，请耐心等待...")
    
    try:
        # 使用ollama pull命令下载模型
        process = subprocess.Popen(
            ['ollama', 'pull', model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 实时显示下载进度
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
        if process.returncode == 0:
            print(f"\n✅ 模型 {model_name} 下载成功！")
            return True
        else:
            print(f"\n❌ 模型 {model_name} 下载失败")
            return False
            
    except Exception as e:
        print(f"下载模型时出错: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Ollama本地模型设置工具")
    print("=" * 60)
    print()
    
    # 检查Ollama是否安装
    if not check_ollama_installed():
        print("❌ Ollama未安装")
        print()
        print("请先安装Ollama：")
        print("  Windows: 访问 https://ollama.com/download 下载安装")
        print("  Linux/Mac: curl -fsSL https://ollama.com/install.sh | sh")
        print()
        return
    
    print("✅ Ollama已安装")
    
    # 检查Ollama服务是否运行
    if not check_ollama_running():
        print("⚠️  Ollama服务未运行，尝试启动...")
        if not start_ollama_service():
            print("❌ 无法启动Ollama服务")
            print("请手动启动Ollama服务后再运行此脚本")
            return
        print("✅ Ollama服务已启动")
    else:
        print("✅ Ollama服务正在运行")
    
    print()
    
    # 列出已安装的模型
    print("已安装的模型：")
    models = list_models()
    if models:
        for model in models:
            print(f"  - {model}")
    else:
        print("  （无）")
    
    print()
    
    # 检查目标模型是否已安装
    target_model = Config.LLM_MODEL
    if target_model in models:
        print(f"✅ 目标模型 {target_model} 已安装")
        print()
        choice = input("是否重新下载？(y/n): ").strip().lower()
        if choice != 'y':
            print("退出")
            return
    
    # 下载模型
    print()
    print(f"开始下载模型: {target_model}")
    print("注意：模型文件较大，下载可能需要较长时间")
    print()
    
    choice = input("确认下载？(y/n): ").strip().lower()
    if choice != 'y':
        print("取消下载")
        return
    
    success = download_model(target_model)
    
    if success:
        print()
        print("=" * 60)
        print("✅ 设置完成！")
        print("=" * 60)
        print()
        print("现在可以使用AI转述功能了")
        print(f"模型: {target_model}")
        print(f"API地址: {Config.LLM_API_BASE}")
    else:
        print()
        print("=" * 60)
        print("❌ 设置失败")
        print("=" * 60)
        print()
        print("请检查：")
        print("1. 网络连接是否正常")
        print("2. Ollama服务是否运行")
        print("3. 模型名称是否正确")


if __name__ == '__main__':
    main()

