#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫性能查询脚本
查看爬虫工具的性能指标

用法:
    python3 get_performance.py [operation] [--export filepath]
    
参数:
    operation: 可选，指定操作名称（如 crawl.深圳美食, ai.paraphrase_and_classify）
               如果不指定，显示所有操作的统计信息
    --export: 可选，导出性能数据到JSON文件
    
示例:
    python3 get_performance.py
    python3 get_performance.py crawl.深圳美食
    python3 get_performance.py --export performance.json
    python3 get_performance.py ai.paraphrase_and_classify --export ai_perf.json
"""
import sys
import json
import os
import argparse

# 添加项目根目录到Python路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from performance_monitor import get_crawler_performance_monitor


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.3f}s"


def format_size(mb: float) -> str:
    """格式化大小"""
    if mb < 1:
        return f"{mb * 1024:.2f}KB"
    else:
        return f"{mb:.2f}MB"


def print_statistics(stats: dict, operation: str = None):
    """打印统计信息"""
    if not stats:
        print(f"⚠️  操作 '{operation}' 暂无性能数据")
        return
    
    print(f"\n{'='*60}")
    print(f"📊 性能统计: {operation or '所有操作'}")
    print(f"{'='*60}\n")
    
    if operation:
        # 单个操作的详细统计
        print(f"执行次数: {stats.get('count', 0)}")
        print(f"平均耗时: {format_duration(stats.get('avg_duration', 0))}")
        print(f"最小耗时: {format_duration(stats.get('min_duration', 0))}")
        print(f"最大耗时: {format_duration(stats.get('max_duration', 0))}")
        print(f"总耗时: {format_duration(stats.get('total_duration', 0))}")
        print(f"最后一次耗时: {format_duration(stats.get('last_duration', 0))}")
        print(f"当前内存使用: {format_size(stats.get('last_memory_mb', 0))}")
        print(f"当前CPU使用率: {stats.get('last_cpu_percent', 0):.2f}%")
        if stats.get('last_network_sent_mb', 0) > 0:
            print(f"网络发送量: {format_size(stats.get('last_network_sent_mb', 0))}")
        if stats.get('last_network_recv_mb', 0) > 0:
            print(f"网络接收量: {format_size(stats.get('last_network_recv_mb', 0))}")
    else:
        # 所有操作的概览
        print(f"{'操作':<40} {'次数':<8} {'平均耗时':<15} {'总耗时':<15} {'内存(MB)':<12}")
        print("-" * 95)
        
        for op_name, op_stats in sorted(stats.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            memory = op_stats.get('last_memory_mb', 0)
            print(f"{op_name:<40} {count:<8} {format_duration(avg):<15} {format_duration(total):<15} {memory:<12.2f}")
        
        # 总体统计
        summary = get_crawler_performance_monitor().get_summary()
        print("\n" + "-" * 95)
        print(f"总操作数: {summary.get('total_operations', 0)}")
        print(f"总耗时: {format_duration(summary.get('total_time', 0))}")
        print(f"平均每次操作耗时: {format_duration(summary.get('avg_time_per_operation', 0))}")
        print(f"当前内存使用: {format_size(summary.get('current_memory_mb', 0))}")
        print(f"当前CPU使用率: {summary.get('current_cpu_percent', 0):.2f}%")
        if summary.get('total_network_sent_mb', 0) > 0:
            print(f"总网络发送量: {format_size(summary.get('total_network_sent_mb', 0))}")
        if summary.get('total_network_recv_mb', 0) > 0:
            print(f"总网络接收量: {format_size(summary.get('total_network_recv_mb', 0))}")


def main():
    parser = argparse.ArgumentParser(description='查看爬虫工具性能指标')
    parser.add_argument('operation', nargs='?', help='操作名称（可选）')
    parser.add_argument('--export', help='导出性能数据到JSON文件')
    parser.add_argument('--clear', action='store_true', help='清空性能数据')
    
    args = parser.parse_args()
    
    monitor = get_crawler_performance_monitor()
    
    if args.clear:
        monitor.clear_metrics()
        print("✅ 性能数据已清空")
        return
    
    if args.operation:
        # 显示指定操作的统计
        stats = monitor.get_statistics(args.operation)
        print_statistics(stats, args.operation)
    else:
        # 显示所有操作的统计
        all_stats = monitor.get_all_statistics()
        print_statistics(all_stats)
    
    if args.export:
        monitor.export_to_json(args.export)
        print(f"\n✅ 性能数据已导出到: {args.export}")


if __name__ == "__main__":
    main()

