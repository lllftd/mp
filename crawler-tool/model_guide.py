#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI模型选择指南
根据硬件配置选择最适合的AI模型
"""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config


MODEL_GUIDE = {
    "deepseek-r1:32b": {
        "name": "DeepSeek R1 32B",
        "size": "约18GB",
        "ram_required": "32GB+",
        "vram_required": "24GB+ (如果有GPU)",
        "quality": "⭐⭐⭐⭐⭐ 最高质量",
        "speed": "中等",
        "description": "最强大的推理模型，适合高质量内容改写",
        "recommended_for": "高端工作站，专业内容创作"
    },
    "qwen2.5:32b": {
        "name": "Qwen 2.5 32B",
        "size": "约20GB",
        "ram_required": "32GB+",
        "vram_required": "24GB+ (如果有GPU)",
        "quality": "⭐⭐⭐⭐⭐ 最高质量（中文优化）",
        "speed": "中等",
        "description": "中文理解能力极强，适合中文内容改写",
        "recommended_for": "高端工作站，中文内容处理"
    },
    "deepseek-r1:14b": {
        "name": "DeepSeek R1 14B",
        "size": "约8GB",
        "ram_required": "16GB+",
        "vram_required": "12GB+ (如果有GPU)",
        "quality": "⭐⭐⭐⭐ 高质量",
        "speed": "较快",
        "description": "平衡质量和速度的优秀选择",
        "recommended_for": "主流配置，日常使用"
    },
    "qwen2.5:14b": {
        "name": "Qwen 2.5 14B",
        "size": "约9GB",
        "ram_required": "16GB+",
        "vram_required": "12GB+ (如果有GPU)",
        "quality": "⭐⭐⭐⭐ 高质量（中文优化）",
        "speed": "较快",
        "description": "中文优化，平衡选择",
        "recommended_for": "主流配置，中文内容处理"
    },
    "llama3.1:70b": {
        "name": "Llama 3.1 70B",
        "size": "约40GB",
        "ram_required": "64GB+",
        "vram_required": "48GB+ (如果有GPU)",
        "quality": "⭐⭐⭐⭐⭐ 顶级质量",
        "speed": "较慢",
        "description": "最强大的通用模型，需要顶级硬件",
        "recommended_for": "服务器级硬件，专业工作站"
    },
    "qwen2.5:7b": {
        "name": "Qwen 2.5 7B",
        "size": "约4.5GB",
        "ram_required": "8GB+",
        "vram_required": "6GB+ (如果有GPU)",
        "quality": "⭐⭐⭐ 良好",
        "speed": "很快",
        "description": "轻量级选择，速度快但质量稍低",
        "recommended_for": "入门配置，快速处理"
    },
}


def check_system_resources():
    """检查系统资源"""
    import psutil
    
    ram_gb = psutil.virtual_memory().total / (1024**3)
    ram_available_gb = psutil.virtual_memory().available / (1024**3)
    
    print(f"\n系统资源检查：")
    print(f"  总内存: {ram_gb:.1f} GB")
    print(f"  可用内存: {ram_available_gb:.1f} GB")
    
    # 检查GPU（如果可用）
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            vram_mb = int(result.stdout.strip().split('\n')[0])
            vram_gb = vram_mb / 1024
            print(f"  GPU显存: {vram_gb:.1f} GB")
            return ram_gb, vram_gb
    except:
        pass
    
    return ram_gb, None


def recommend_models(ram_gb, vram_gb=None):
    """根据系统配置推荐模型"""
    recommendations = []
    
    for model_id, info in MODEL_GUIDE.items():
        ram_req = float(info['ram_required'].replace('GB+', '').replace('+', ''))
        suitable = ram_gb >= ram_req
        
        if vram_gb:
            vram_req = float(info['vram_required'].split()[0].replace('GB+', '').replace('+', ''))
            suitable = suitable and vram_gb >= vram_req
        
        if suitable:
            recommendations.append((model_id, info))
    
    return recommendations


def display_model_info(model_id):
    """显示模型详细信息"""
    if model_id not in MODEL_GUIDE:
        print(f"❌ 未找到模型: {model_id}")
        return
    
    info = MODEL_GUIDE[model_id]
    print(f"\n{'='*60}")
    print(f"模型信息: {info['name']}")
    print(f"{'='*60}")
    print(f"模型ID: {model_id}")
    print(f"文件大小: {info['size']}")
    print(f"内存要求: {info['ram_required']}")
    print(f"显存要求: {info['vram_required']}")
    print(f"质量评级: {info['quality']}")
    print(f"处理速度: {info['speed']}")
    print(f"描述: {info['description']}")
    print(f"推荐场景: {info['recommended_for']}")
    print(f"{'='*60}\n")


def main():
    """主函数"""
    print("=" * 60)
    print("AI模型选择指南")
    print("=" * 60)
    
    # 检查当前配置
    current_model = Config.LLM_MODEL
    print(f"\n当前配置的模型: {current_model}")
    
    # 检查系统资源
    ram_gb, vram_gb = check_system_resources()
    
    # 显示所有可用模型
    print("\n" + "=" * 60)
    print("可用模型列表")
    print("=" * 60)
    print(f"{'模型ID':<25} {'大小':<12} {'内存要求':<12} {'质量':<15}")
    print("-" * 60)
    
    for model_id, info in MODEL_GUIDE.items():
        marker = " ⭐ 当前" if model_id == current_model else ""
        print(f"{model_id:<25} {info['size']:<12} {info['ram_required']:<12} {info['quality']:<15}{marker}")
    
    # 显示当前模型详细信息
    print("\n" + "=" * 60)
    print("当前模型详细信息")
    print("=" * 60)
    display_model_info(current_model)
    
    # 推荐模型
    print("\n" + "=" * 60)
    print("根据您的系统配置推荐")
    print("=" * 60)
    recommendations = recommend_models(ram_gb, vram_gb)
    
    if recommendations:
        print("\n✅ 以下模型适合您的系统：")
        for model_id, info in recommendations:
            marker = " ⭐ 当前使用" if model_id == current_model else ""
            print(f"\n{model_id}")
            print(f"  - {info['name']}")
            print(f"  - {info['description']}")
            print(f"  - {info['quality']}")
            if marker:
                print(f"  {marker}")
    else:
        print("\n⚠️  警告：您的系统可能无法运行这些模型")
        print("推荐至少8GB内存使用 qwen2.5:7b")
    
    # 切换模型提示
    print("\n" + "=" * 60)
    print("如何切换模型")
    print("=" * 60)
    print("\n方法1: 修改 .env 文件")
    print("  添加或修改: LLM_MODEL=模型ID")
    print(f"  例如: LLM_MODEL=qwen2.5:32b")
    
    print("\n方法2: 修改 config.py")
    print(f"  修改 LLM_MODEL = '模型ID'")
    
    print("\n方法3: 设置环境变量")
    print("  Windows: set LLM_MODEL=qwen2.5:32b")
    print("  Linux/Mac: export LLM_MODEL=qwen2.5:32b")
    
    print("\n切换后需要:")
    print("  1. 运行 python setup_ollama.py 下载新模型")
    print("  2. 确保Ollama服务运行")
    print("  3. 重新启动爬虫")


if __name__ == '__main__':
    try:
        main()
    except ImportError:
        print("缺少依赖: pip install psutil")
        print("\n仍然可以查看模型信息，但无法检测系统资源")
        print("\n可用模型:")
        for model_id, info in MODEL_GUIDE.items():
            print(f"  {model_id:<25} {info['size']:<12} {info['quality']:<15}")

