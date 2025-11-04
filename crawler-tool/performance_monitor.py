"""
爬虫性能监控模块
记录爬虫的执行时间、资源使用等性能指标，并提供实时显示功能
"""
import time
import logging
import psutil
import os
import threading
import json
from typing import Dict, Optional, List
from collections import defaultdict
from datetime import datetime

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


class RealTimePerformanceDisplay:
    """实时性能监控显示"""
    
    def __init__(self, update_interval: float = 2.0):
        """
        初始化实时显示
        
        Args:
            update_interval: 更新间隔（秒），默认2秒
        """
        self.update_interval = update_interval
        self.monitor = get_crawler_performance_monitor()
        self.is_running = False
        self.display_thread = None
        self.start_time = None
    
    def format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 0.001:
            return f"{seconds * 1000000:.0f}us"
        elif seconds < 1:
            return f"{seconds * 1000:.2f}ms"
        else:
            return f"{seconds:.2f}s"
    
    def format_size(self, mb: float) -> str:
        """格式化大小"""
        if mb < 1:
            return f"{mb * 1024:.0f}KB"
        else:
            return f"{mb:.1f}MB"
    
    def clear_screen(self):
        """清屏（使用ANSI转义序列）"""
        print('\033[2J\033[H', end='', flush=True)
    
    def display_stats(self):
        """显示性能统计"""
        summary = self.monitor.get_summary()
        all_stats = self.monitor.get_all_statistics()
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            elapsed_str = f"{elapsed_min}分{elapsed_sec}秒"
        else:
            elapsed_str = "0秒"
        
        self.clear_screen()
        
        print("="*100)
        print(f"实时性能监控 | 运行时间: {elapsed_str} | 更新时间: {time.strftime('%H:%M:%S')}")
        print("="*100)
        
        print(f"\n[总体统计]")
        total_ops = summary.get('total_operations', 0)
        total_time = summary.get('total_time', 0)
        avg_time = summary.get('avg_time_per_operation', 0)
        memory = summary.get('current_memory_mb', 0)
        cpu = summary.get('current_cpu_percent', 0)
        print(f"  总操作数: {total_ops:>6}  |  总耗时: {self.format_duration(total_time):>10}  |  平均耗时: {self.format_duration(avg_time):>10}")
        print(f"  内存使用: {self.format_size(memory):>8}  |  CPU使用率: {cpu:>5.1f}%")
        
        crawl_ops = {k: v for k, v in all_stats.items() if k.startswith('crawl.')}
        if crawl_ops:
            print(f"\n[爬虫操作]")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(crawl_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('crawl.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        ai_ops = {k: v for k, v in all_stats.items() if k.startswith('ai.') and not k.startswith('ai.api_call.attempt_')}
        if ai_ops:
            print(f"\n[AI操作]")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(ai_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('ai.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        ai_success = self.monitor.metrics.get('ai.success', [])
        ai_error = self.monitor.metrics.get('ai.error', [])
        if ai_success or ai_error:
            success_count = len(ai_success)
            error_count = len(ai_error)
            total_ai = success_count + error_count
            if total_ai > 0:
                success_rate = (success_count / total_ai) * 100
                print(f"\n[AI状态]")
                print(f"  成功率: {success_count}/{total_ai} ({success_rate:.1f}%)", end='')
                if error_count > 0:
                    error_types = {}
                    for err in ai_error:
                        err_type = err.get('error_type', 'unknown')
                        error_types[err_type] = error_types.get(err_type, 0) + 1
                    print(f"  |  失败: {error_count}次")
                    if error_types:
                        print(f"  错误类型: {', '.join([f'{k}({v})' for k, v in error_types.items()])}")
                else:
                    print()
        
        parse_ops = {k: v for k, v in all_stats.items() if k.startswith('parse.')}
        if parse_ops:
            print(f"\n[解析操作]")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(parse_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('parse.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        image_ops = {k: v for k, v in all_stats.items() if k.startswith('image.')}
        if image_ops:
            print(f"\n[图片处理]")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(image_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('image.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        db_ops = {k: v for k, v in all_stats.items() if k.startswith('database.')}
        if db_ops:
            print(f"\n[数据库操作]")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(db_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('database.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        print(f"\n[最新操作]（最近10条）")
        recent_ops = []
        for op_name, records in self.monitor.metrics.items():
            if records:
                last_record = records[-1]
                duration = last_record.get('duration') or last_record.get('value')
                if duration is not None:
                    recent_ops.append({
                        'name': op_name,
                        'time': last_record.get('timestamp', ''),
                        'duration': duration
                    })
        
        recent_ops.sort(key=lambda x: x['time'], reverse=True)
        if recent_ops:
            print(f"  {'操作':<35} {'耗时':>12} {'时间':>20}")
            print(f"  {'-'*35} {'-'*12} {'-'*20}")
            for op in recent_ops[:10]:
                name_short = op['name'][:35]
                time_str = op['time'].split('T')[1][:8] if 'T' in op['time'] else op['time'][:8]
                print(f"  {name_short:<35} {self.format_duration(op['duration']):>12} {time_str:>20}")
        
        print("\n" + "="*100)
        print("提示: 性能监控每2秒自动更新 | 按 Ctrl+C 停止爬虫")
        print("="*100)
    
    def _update_loop(self):
        """更新循环（在后台线程中运行）"""
        while self.is_running:
            try:
                self.display_stats()
                time.sleep(self.update_interval)
            except Exception:
                pass
    
    def start(self):
        """启动实时显示"""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = time.time()
        self.display_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.display_thread.start()
    
    def stop(self):
        """停止实时显示"""
        self.is_running = False
        if self.display_thread:
            self.display_thread.join(timeout=1)
        self.display_stats()
    
    def __enter__(self):
        """上下文管理器：进入"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器：退出"""
        self.stop()
        return False


# 全局性能监控实例
_crawler_perf_monitor = None

def get_crawler_performance_monitor() -> CrawlerPerformanceMonitor:
    """获取全局性能监控实例（单例模式）"""
    global _crawler_perf_monitor
    if _crawler_perf_monitor is None:
        _crawler_perf_monitor = CrawlerPerformanceMonitor()
    return _crawler_perf_monitor


# 全局实时显示实例
_real_time_display = None

def get_real_time_display(update_interval: float = 2.0) -> RealTimePerformanceDisplay:
    """获取全局实时显示实例"""
    global _real_time_display
    if _real_time_display is None:
        _real_time_display = RealTimePerformanceDisplay(update_interval)
    return _real_time_display
