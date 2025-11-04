"""
爬虫性能监控模块
记录爬虫的执行时间、资源使用等性能指标
"""
import time
import logging
import psutil
import os
from typing import Dict, Optional, List
from collections import defaultdict
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class CrawlerPerformanceMonitor:
    """爬虫性能监控器"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.start_time = None
        self.process = psutil.Process(os.getpid())
        
    def start_timer(self, operation: str):
        """开始计时"""
        self.start_time = time.time()
        return self.start_time
    
    def end_timer(self, operation: str) -> float:
        """结束计时并记录"""
        if self.start_time is None:
            return 0.0
        
        elapsed = time.time() - self.start_time
        self.metrics[operation].append({
            'timestamp': datetime.now().isoformat(),
            'duration': elapsed,
            'memory_mb': self.get_memory_usage(),
            'cpu_percent': self.process.cpu_percent(),
            'network_sent_mb': self.get_network_sent(),
            'network_recv_mb': self.get_network_recv()
        })
        self.start_time = None
        return elapsed
    
    def record_metric(self, metric_name: str, value: float, extra: Optional[Dict] = None):
        """记录性能指标"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'value': value
        }
        # 如果 value 是数字类型，同时添加 duration 字段以保持一致性
        if isinstance(value, (int, float)):
            record['duration'] = value
        if extra:
            record.update(extra)
        self.metrics[metric_name].append(record)
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用（MB）"""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024  # 转换为MB
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
            return net_io.write_bytes / 1024 / 1024  # 转换为MB
        except Exception:
            return 0.0
    
    def get_network_recv(self) -> float:
        """获取网络接收量（MB）"""
        try:
            net_io = self.process.io_counters()
            return net_io.read_bytes / 1024 / 1024  # 转换为MB
        except Exception:
            return 0.0
    
    def get_statistics(self, operation: str) -> Dict:
        """获取操作统计信息"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        records = self.metrics[operation]
        # 支持 duration 和 value 字段（CrawlerPerformanceTimer 使用 value）
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
        
        # 计算总体统计
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


class CrawlerPerformanceTimer:
    """爬虫性能计时上下文管理器"""
    
    def __init__(self, operation: str, monitor: Optional[CrawlerPerformanceMonitor] = None):
        self.operation = operation
        self.monitor = monitor or get_crawler_performance_monitor()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        self.monitor.record_metric(
            self.operation,
            elapsed,
            {
                'memory_mb': self.monitor.get_memory_usage(),
                'cpu_percent': self.monitor.get_cpu_usage(),
                'network_sent_mb': self.monitor.get_network_sent(),
                'network_recv_mb': self.monitor.get_network_recv()
            }
        )
        return False

