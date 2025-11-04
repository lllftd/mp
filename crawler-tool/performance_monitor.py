"""
爬虫性能监控模块
记录爬虫的执行时间、资源使用等性能指标

可以作为命令行工具使用:
    python performance_monitor.py [operation] [--export filepath] [--clear]
    
示例:
    python performance_monitor.py
    python performance_monitor.py crawl.深圳美食
    python performance_monitor.py --export performance.json
    python performance_monitor.py ai.paraphrase_and_classify --export ai_perf.json
    python performance_monitor.py --clear
"""
import logging
import psutil
import os
import json
import argparse
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class CrawlerPerformanceMonitor:
    """爬虫性能监控器"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.process = psutil.Process(os.getpid())
        
    def record_metric(self, metric_name: str, value: float, extra: Optional[Dict] = None):
        """记录性能指标"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'value': value
        }
        if isinstance(value, (int, float)):
            record['duration'] = value
        if extra:
            record.update(extra)
        self.metrics[metric_name].append(record)
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用（MB）"""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def get_cpu_usage(self) -> float:
        """获取当前CPU使用率"""
        try:
            return self.process.cpu_percent(interval=0.1)
        except Exception:
            return 0.0
    
    def get_network_sent(self) -> float:
        """获取网络发送量（MB）"""
        try:
            net_io = self.process.io_counters()
            return net_io.write_bytes / 1024 / 1024
        except Exception:
            return 0.0
    
    def get_network_recv(self) -> float:
        """获取网络接收量（MB）"""
        try:
            net_io = self.process.io_counters()
            return net_io.read_bytes / 1024 / 1024
        except Exception:
            return 0.0
    
    def get_statistics(self, operation: str) -> Dict:
        """获取操作统计信息"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        records = self.metrics[operation]
        durations = []
        for r in records:
            if 'duration' in r:
                durations.append(r['duration'])
            elif 'value' in r:
                durations.append(r['value'])
        
        if not durations:
            return {
                'count': len(records),
                'avg_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'total_duration': 0,
                'last_duration': 0,
                'last_memory_mb': records[-1].get('memory_mb', 0) if records else 0,
                'last_cpu_percent': records[-1].get('cpu_percent', 0) if records else 0,
                'last_network_sent_mb': records[-1].get('network_sent_mb', 0) if records else 0,
                'last_network_recv_mb': records[-1].get('network_recv_mb', 0) if records else 0
            }
        
        return {
            'count': len(records),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'total_duration': sum(durations),
            'last_duration': durations[-1] if durations else 0,
            'last_memory_mb': records[-1].get('memory_mb', 0) if records else 0,
            'last_cpu_percent': records[-1].get('cpu_percent', 0) if records else 0,
            'last_network_sent_mb': records[-1].get('network_sent_mb', 0) if records else 0,
            'last_network_recv_mb': records[-1].get('network_recv_mb', 0) if records else 0
        }
    
    def get_all_statistics(self) -> Dict:
        """获取所有操作的统计信息"""
        stats = {}
        for operation in self.metrics:
            stats[operation] = self.get_statistics(operation)
        return stats
    
    def get_summary(self) -> Dict:
        """获取性能摘要"""
        all_stats = self.get_all_statistics()
        summary = {
            'timestamp': datetime.now().isoformat(),
            'operations': all_stats,
            'current_memory_mb': self.get_memory_usage(),
            'current_cpu_percent': self.get_cpu_usage(),
            'total_network_sent_mb': self.get_network_sent(),
            'total_network_recv_mb': self.get_network_recv()
        }
        
        total_duration = sum(
            stats.get('total_duration', 0) 
            for stats in all_stats.values()
        )
        total_count = sum(
            stats.get('count', 0) 
            for stats in all_stats.values()
        )
        
        summary['total_operations'] = total_count
        summary['total_time'] = total_duration
        summary['avg_time_per_operation'] = total_duration / total_count if total_count > 0 else 0
        
        return summary
    
    def clear_metrics(self):
        """清空所有指标"""
        self.metrics.clear()
    
    def export_to_json(self, filepath: str):
        """导出性能数据到JSON文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'summary': self.get_summary(),
                    'detailed_metrics': dict(self.metrics)
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"性能数据已导出到: {filepath}")
        except Exception as e:
            logger.error(f"导出性能数据失败: {e}")


# 全局性能监控实例
_crawler_perf_monitor = None

def get_crawler_performance_monitor() -> CrawlerPerformanceMonitor:
    """获取全局性能监控实例（单例模式）"""
    global _crawler_perf_monitor
    if _crawler_perf_monitor is None:
        _crawler_perf_monitor = CrawlerPerformanceMonitor()
    return _crawler_perf_monitor


# ==================== 命令行工具功能 ====================

def format_duration_cli(seconds: float) -> str:
    """格式化时长（命令行工具用）"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f}us"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.3f}s"


def format_size_cli(mb: float) -> str:
    """格式化大小（命令行工具用）"""
    if mb < 1:
        return f"{mb * 1024:.2f}KB"
    else:
        return f"{mb:.2f}MB"


def print_statistics(stats: dict, operation: str = None):
    """打印统计信息"""
    if not stats:
        print(f"[WARN] 操作 '{operation}' 暂无性能数据")
        return
    
    print(f"\n{'='*60}")
    print(f"性能统计: {operation or '所有操作'}")
    print(f"{'='*60}\n")
    
    if operation:
        # 单个操作的详细统计
        print(f"执行次数: {stats.get('count', 0)}")
        print(f"平均耗时: {format_duration_cli(stats.get('avg_duration', 0))}")
        print(f"最小耗时: {format_duration_cli(stats.get('min_duration', 0))}")
        print(f"最大耗时: {format_duration_cli(stats.get('max_duration', 0))}")
        print(f"总耗时: {format_duration_cli(stats.get('total_duration', 0))}")
        print(f"最后一次耗时: {format_duration_cli(stats.get('last_duration', 0))}")
        print(f"当前内存使用: {format_size_cli(stats.get('last_memory_mb', 0))}")
        print(f"当前CPU使用率: {stats.get('last_cpu_percent', 0):.2f}%")
        if stats.get('last_network_sent_mb', 0) > 0:
            print(f"网络发送量: {format_size_cli(stats.get('last_network_sent_mb', 0))}")
        if stats.get('last_network_recv_mb', 0) > 0:
            print(f"网络接收量: {format_size_cli(stats.get('last_network_recv_mb', 0))}")
    else:
        # 所有操作的概览
        print(f"{'操作':<40} {'次数':<8} {'平均耗时':<15} {'总耗时':<15} {'内存(MB)':<12}")
        print("-" * 95)
        
        for op_name, op_stats in sorted(stats.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            memory = op_stats.get('last_memory_mb', 0)
            print(f"{op_name:<40} {count:<8} {format_duration_cli(avg):<15} {format_duration_cli(total):<15} {memory:<12.2f}")
        
        # 总体统计
        summary = get_crawler_performance_monitor().get_summary()
        print("\n" + "-" * 95)
        print(f"总操作数: {summary.get('total_operations', 0)}")
        print(f"总耗时: {format_duration_cli(summary.get('total_time', 0))}")
        print(f"平均每次操作耗时: {format_duration_cli(summary.get('avg_time_per_operation', 0))}")
        print(f"当前内存使用: {format_size_cli(summary.get('current_memory_mb', 0))}")
        print(f"当前CPU使用率: {summary.get('current_cpu_percent', 0):.2f}%")
        if summary.get('total_network_sent_mb', 0) > 0:
            print(f"总网络发送量: {format_size_cli(summary.get('total_network_sent_mb', 0))}")
        if summary.get('total_network_recv_mb', 0) > 0:
            print(f"总网络接收量: {format_size_cli(summary.get('total_network_recv_mb', 0))}")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='查看爬虫工具性能指标')
    parser.add_argument('operation', nargs='?', help='操作名称（可选）')
    parser.add_argument('--export', help='导出性能数据到JSON文件')
    parser.add_argument('--clear', action='store_true', help='清空性能数据')
    
    args = parser.parse_args()
    
    monitor = get_crawler_performance_monitor()
    
    if args.clear:
        monitor.clear_metrics()
        print("[OK] 性能数据已清空")
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
        print(f"\n[OK] 性能数据已导出到: {args.export}")


if __name__ == "__main__":
    main()
