#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控模块 - 内存监控
"""
import os
import time
import threading
import logging
import psutil
from typing import Optional, Dict

from base.config import Config
from base.utils import format_bytes, CrawlerMemoryError

logger = logging.getLogger(__name__)

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, warning_threshold_gb: float = 2.0, critical_threshold_gb: float = 1.0):
        """
        初始化内存监控器
        
        Args:
            warning_threshold_gb: 警告阈值（GB）
            critical_threshold_gb: 严重警告阈值（GB），默认1GB
        """
        self.process = psutil.Process(os.getpid())
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_check_time = 0
        self.check_interval = 30
        
        if '32b' in Config.LLM_MODEL.lower():
            self.warning_threshold = 20.0 * 1024 * 1024 * 1024
            self.critical_threshold = 10.0 * 1024 * 1024 * 1024
        else:
            self.warning_threshold = warning_threshold_gb * 1024 * 1024 * 1024
            self.critical_threshold = critical_threshold_gb * 1024 * 1024 * 1024
    
    def get_memory_info(self) -> Optional[Dict]:
        """获取内存信息"""
        try:
            system_memory = psutil.virtual_memory()
            process_memory = self.process.memory_info()
            
            ollama_memory = 0
            ollama_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        ollama_memory += proc.info['memory_info'].rss
                        ollama_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return {
                'system': {
                    'total': system_memory.total,
                    'available': system_memory.available,
                    'used': system_memory.used,
                    'percent': system_memory.percent
                },
                'process': {
                    'rss': process_memory.rss,
                    'vms': process_memory.vms
                },
                'ollama': {
                    'memory': ollama_memory,
                    'count': ollama_count
                }
            }
        except Exception:
            return None
    
    def check_memory(self, print_info: bool = False, raise_on_critical: bool = True) -> bool:
        """检查内存使用情况"""
        memory_info = self.get_memory_info()
        if not memory_info:
            return True
        
        available = memory_info['system']['available']
        process_rss = memory_info['process']['rss']
        ollama_memory = memory_info['ollama']['memory']
        
        is_warning = available < self.warning_threshold
        is_critical = available < self.critical_threshold
        
        if print_info:
            logger.info(f"[内存监控] 系统可用: {format_bytes(available)} | "
                  f"进程: {format_bytes(process_rss)} | "
                  f"Ollama模型: {format_bytes(ollama_memory)} ({memory_info['ollama']['count']}个进程)")
        
        if is_critical:
            error_msg = f"系统可用内存严重不足: {format_bytes(available)} (低于阈值 {format_bytes(self.critical_threshold)})"
            logger.error(f"[严重警告] {error_msg}")

            
            if raise_on_critical:
                raise CrawlerMemoryError(error_msg)
            return False
        elif is_warning:
            return True
        
        return True
    
    def start_monitoring(self) -> None:
        """开始后台监控"""
        if self.monitoring:
            return
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    time.sleep(self.check_interval)
                    if self.monitoring:
                        # 静默监控，不打印日志
                        self.check_memory(print_info=False, raise_on_critical=False)
                except Exception as e:
                    logger.warning(f"[内存监控] 检查出错: {e}")
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
    
    def print_summary(self) -> None:
        """打印内存监控摘要（已禁用，不输出）"""
        pass

