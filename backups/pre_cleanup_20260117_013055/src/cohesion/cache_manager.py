"""
Performance Optimization and Caching System

This module implements intelligent caching with freshness validation,
memory management with eviction policies, and performance monitoring.

Capital-Grade System Laws Enforced:
- Property 23: Cache Freshness Validation (P1)
- Property 24: Memory Threshold Enforcement (P2)
"""

import logging
import threading
import time
import weakref
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import psutil
import pandas as pd
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata for freshness and eviction policies"""
    key: str
    value: Any
    timestamp: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    max_age: timedelta = field(default_factory=lambda: timedelta(hours=1))
    size_bytes: int = 0
    stale_acceptable: bool = False
    priority: int = 1  # Higher = more important
    
    def is_fresh(self) -> bool:
        """Check if cache entry is still fresh"""
        age = datetime.now() - self.timestamp
        return age <= self.max_age
    
    def is_stale_but_acceptable(self) -> bool:
        """Check if entry is stale but marked as acceptable to use"""
        return not self.is_fresh() and self.stale_acceptable
    
    def access(self):
        """Record cache access for LRU tracking"""
        self.access_count += 1
        self.last_accessed = datetime.now()


@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def memory_usage_mb(self) -> float:
        """Memory usage in MB"""
        return self.memory_usage_bytes / (1024 * 1024)


class EvictionPolicy(ABC):
    """Abstract base class for cache eviction policies"""
    
    @abstractmethod
    def select_for_eviction(self, entries: Dict[str, CacheEntry], 
                          target_count: int) -> List[str]:
        """Select entries for eviction"""
        pass


class LRUEvictionPolicy(EvictionPolicy):
    """Least Recently Used eviction policy"""
    
    def select_for_eviction(self, entries: Dict[str, CacheEntry], 
                          target_count: int) -> List[str]:
        """Select least recently used entries for eviction"""
        # Sort by last accessed time (oldest first)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].last_accessed
        )
        return [key for key, _ in sorted_entries[:target_count]]


class PriorityLRUEvictionPolicy(EvictionPolicy):
    """Priority-aware LRU eviction policy"""
    
    def select_for_eviction(self, entries: Dict[str, CacheEntry], 
                          target_count: int) -> List[str]:
        """Select entries for eviction considering priority and recency"""
        # Sort by priority (low first), then by last accessed (old first)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: (x[1].priority, x[1].last_accessed)
        )
        return [key for key, _ in sorted_entries[:target_count]]


class IntelligentCacheManager:
    """
    Intelligent caching system with freshness validation and memory management
    
    Enforces System Laws:
    - Property 23: Cache Freshness Validation (P1)
    - Property 24: Memory Threshold Enforcement (P2)
    """
    
    def __init__(self, 
                 max_memory_mb: float = 1024,
                 memory_threshold: float = 0.8,
                 eviction_policy: EvictionPolicy = None,
                 enable_monitoring: bool = True):
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self.memory_threshold = memory_threshold
        self.eviction_policy = eviction_policy or PriorityLRUEvictionPolicy()
        self.enable_monitoring = enable_monitoring
        
        # Thread-safe cache storage
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Performance statistics
        self._stats = CacheStats()
        
        # Memory monitoring
        self._memory_monitor_active = False
        self._start_memory_monitoring()
        
        logger.info(f"Initialized IntelligentCacheManager with {max_memory_mb}MB limit")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache with freshness validation
        
        Enforces Property 23: Cache Freshness Validation (P1)
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                logger.debug(f"Cache miss for key: {key}")
                return default
            
            # SYSTEM LAW: Property 23 - Cache Freshness Validation
            if not entry.is_fresh() and not entry.is_stale_but_acceptable():
                # Remove stale entry
                del self._cache[key]
                self._update_memory_usage()
                self._stats.misses += 1
                logger.debug(f"Cache entry expired for key: {key}")
                return default
            
            # Record access and return value
            entry.access()
            self._stats.hits += 1
            
            if not entry.is_fresh():
                logger.warning(f"Using stale but acceptable cache entry: {key}")
            
            return entry.value
    
    def put(self, key: str, value: Any, 
            max_age: timedelta = None,
            stale_acceptable: bool = False,
            priority: int = 1) -> bool:
        """
        Put value in cache with metadata
        
        Enforces Property 24: Memory Threshold Enforcement (P2)
        """
        with self._lock:
            # Calculate size
            size_bytes = self._estimate_size(value)
            
            # Check if we need to evict entries
            if self._should_evict(size_bytes):
                self._evict_entries(size_bytes)
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                timestamp=datetime.now(),
                max_age=max_age or timedelta(hours=1),
                size_bytes=size_bytes,
                stale_acceptable=stale_acceptable,
                priority=priority
            )
            
            # Store entry
            self._cache[key] = entry
            self._update_memory_usage()
            
            logger.debug(f"Cached entry: {key} (size: {size_bytes} bytes)")
            return True
    
    def invalidate(self, key: str) -> bool:
        """Remove entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._update_memory_usage()
                logger.debug(f"Invalidated cache entry: {key}")
                return True
            return False
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._update_memory_usage()
            logger.info("Cache cleared")
    
    def get_stats(self) -> CacheStats:
        """Get cache performance statistics"""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                memory_usage_bytes=self._stats.memory_usage_bytes,
                entry_count=len(self._cache)
            )
    
    def _should_evict(self, additional_size: int) -> bool:
        """Check if eviction is needed for new entry"""
        current_usage = self._stats.memory_usage_bytes
        projected_usage = current_usage + additional_size
        threshold_bytes = self.max_memory_bytes * self.memory_threshold
        
        return projected_usage > threshold_bytes
    
    def _evict_entries(self, needed_space: int):
        """
        Evict entries to make space
        
        Enforces Property 24: Memory Threshold Enforcement (P2)
        """
        if not self._cache:
            return
        
        # Calculate how many entries to evict
        current_usage = self._stats.memory_usage_bytes
        target_usage = self.max_memory_bytes * (self.memory_threshold - 0.1)  # 10% buffer
        space_to_free = max(needed_space, current_usage - target_usage)
        
        # Select entries for eviction
        entries_to_evict = []
        freed_space = 0
        
        eviction_candidates = self.eviction_policy.select_for_eviction(
            self._cache, len(self._cache)
        )
        
        for key in eviction_candidates:
            if freed_space >= space_to_free:
                break
            
            entry = self._cache.get(key)
            if entry:
                entries_to_evict.append(key)
                freed_space += entry.size_bytes
        
        # Evict selected entries
        for key in entries_to_evict:
            if key in self._cache:
                del self._cache[key]
                self._stats.evictions += 1
        
        self._update_memory_usage()
        
        logger.info(f"Evicted {len(entries_to_evict)} entries, "
                   f"freed {freed_space} bytes")
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of cached value"""
        if isinstance(value, pd.DataFrame):
            return value.memory_usage(deep=True).sum()
        elif isinstance(value, (list, tuple)):
            return sum(self._estimate_size(item) for item in value)
        elif isinstance(value, dict):
            return sum(self._estimate_size(k) + self._estimate_size(v) 
                      for k, v in value.items())
        elif isinstance(value, str):
            return len(value.encode('utf-8'))
        else:
            # Rough estimate for other types
            return 64  # Base object overhead
    
    def _update_memory_usage(self):
        """Update memory usage statistics"""
        total_size = sum(entry.size_bytes for entry in self._cache.values())
        self._stats.memory_usage_bytes = total_size
        self._stats.entry_count = len(self._cache)
    
    def _start_memory_monitoring(self):
        """Start background memory monitoring"""
        if not self.enable_monitoring or self._memory_monitor_active:
            return
        
        def monitor_memory():
            self._memory_monitor_active = True
            while self._memory_monitor_active:
                try:
                    # Check system memory
                    system_memory = psutil.virtual_memory()
                    if system_memory.percent > 90:  # System memory critical
                        logger.warning(f"System memory usage critical: {system_memory.percent}%")
                        # Aggressive cache eviction
                        with self._lock:
                            if self._cache:
                                evict_count = len(self._cache) // 4  # Evict 25%
                                candidates = self.eviction_policy.select_for_eviction(
                                    self._cache, evict_count
                                )
                                for key in candidates:
                                    if key in self._cache:
                                        del self._cache[key]
                                        self._stats.evictions += 1
                                self._update_memory_usage()
                    
                    # Check cache memory usage
                    usage_ratio = self._stats.memory_usage_bytes / self.max_memory_bytes
                    if usage_ratio > self.memory_threshold:
                        logger.warning(f"Cache memory usage high: {usage_ratio:.2%}")
                        # SYSTEM LAW: Property 24 - Memory Threshold Enforcement
                        self._evict_entries(0)  # Evict to get under threshold
                    
                    time.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Memory monitoring error: {e}")
                    time.sleep(60)  # Back off on error
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
        monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self._memory_monitor_active = False


class BatchFileOperationManager:
    """
    Batch file operations to minimize I/O overhead
    
    Implements Requirement 9.3: Batch file operations
    """
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._read_queue: List[Tuple[str, Callable]] = []
        self._write_queue: List[Tuple[str, Any, Callable]] = []
        self._lock = threading.Lock()
        
        # Auto-flush timer
        self._start_auto_flush()
    
    def queue_read(self, filepath: str, callback: Callable[[Any], None]):
        """Queue file read operation"""
        with self._lock:
            self._read_queue.append((filepath, callback))
            
            if len(self._read_queue) >= self.batch_size:
                self._flush_reads()
    
    def queue_write(self, filepath: str, data: Any, callback: Callable = None):
        """Queue file write operation"""
        with self._lock:
            self._write_queue.append((filepath, data, callback))
            
            if len(self._write_queue) >= self.batch_size:
                self._flush_writes()
    
    def flush_all(self):
        """Flush all pending operations"""
        with self._lock:
            self._flush_reads()
            self._flush_writes()
    
    def _flush_reads(self):
        """Execute batched read operations"""
        if not self._read_queue:
            return
        
        logger.debug(f"Flushing {len(self._read_queue)} read operations")
        
        for filepath, callback in self._read_queue:
            try:
                # Group reads by file type for optimization
                if filepath.endswith('.parquet'):
                    data = pd.read_parquet(filepath)
                elif filepath.endswith('.csv'):
                    data = pd.read_csv(filepath)
                else:
                    with open(filepath, 'r') as f:
                        data = f.read()
                
                callback(data)
                
            except Exception as e:
                logger.error(f"Batch read error for {filepath}: {e}")
                callback(None)
        
        self._read_queue.clear()
    
    def _flush_writes(self):
        """Execute batched write operations"""
        if not self._write_queue:
            return
        
        logger.debug(f"Flushing {len(self._write_queue)} write operations")
        
        for filepath, data, callback in self._write_queue:
            try:
                if isinstance(data, pd.DataFrame):
                    if filepath.endswith('.parquet'):
                        data.to_parquet(filepath)
                    else:
                        data.to_csv(filepath, index=False)
                else:
                    with open(filepath, 'w') as f:
                        f.write(str(data))
                
                if callback:
                    callback(True)
                    
            except Exception as e:
                logger.error(f"Batch write error for {filepath}: {e}")
                if callback:
                    callback(False)
        
        self._write_queue.clear()
    
    def _start_auto_flush(self):
        """Start auto-flush timer"""
        def auto_flush():
            while True:
                time.sleep(self.flush_interval)
                try:
                    self.flush_all()
                except Exception as e:
                    logger.error(f"Auto-flush error: {e}")
        
        flush_thread = threading.Thread(target=auto_flush, daemon=True)
        flush_thread.start()


class DataFrameOptimizer:
    """
    DataFrame operation optimizer for large datasets
    
    Implements Requirement 9.5: Optimize DataFrame operations
    """
    
    @staticmethod
    def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame data types to reduce memory usage"""
        optimized = df.copy()
        
        for col in optimized.columns:
            col_type = optimized[col].dtype
            
            if col_type == 'object':
                # Try to convert to category if low cardinality
                unique_ratio = optimized[col].nunique() / len(optimized)
                if unique_ratio < 0.5:  # Less than 50% unique values
                    optimized[col] = optimized[col].astype('category')
            
            elif col_type == 'int64':
                # Downcast integers
                col_min = optimized[col].min()
                col_max = optimized[col].max()
                
                if col_min >= 0:  # Unsigned
                    if col_max < 255:
                        optimized[col] = optimized[col].astype('uint8')
                    elif col_max < 65535:
                        optimized[col] = optimized[col].astype('uint16')
                    elif col_max < 4294967295:
                        optimized[col] = optimized[col].astype('uint32')
                else:  # Signed
                    if col_min > -128 and col_max < 127:
                        optimized[col] = optimized[col].astype('int8')
                    elif col_min > -32768 and col_max < 32767:
                        optimized[col] = optimized[col].astype('int16')
                    elif col_min > -2147483648 and col_max < 2147483647:
                        optimized[col] = optimized[col].astype('int32')
            
            elif col_type == 'float64':
                # Downcast floats
                optimized[col] = pd.to_numeric(optimized[col], downcast='float')
        
        return optimized
    
    @staticmethod
    def chunk_process(df: pd.DataFrame, 
                     func: Callable[[pd.DataFrame], pd.DataFrame],
                     chunk_size: int = 10000) -> pd.DataFrame:
        """Process large DataFrame in chunks"""
        if len(df) <= chunk_size:
            return func(df)
        
        results = []
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i + chunk_size]
            result = func(chunk)
            results.append(result)
        
        return pd.concat(results, ignore_index=True)


class LazyDataLoader:
    """
    Lazy loading for non-critical data
    
    Implements Requirement 9.7: Lazy loading for non-critical data
    """
    
    def __init__(self, cache_manager: IntelligentCacheManager):
        self.cache_manager = cache_manager
        self._loaders: Dict[str, Callable] = {}
        self._loaded: Set[str] = set()
    
    def register_loader(self, key: str, loader: Callable[[], Any], 
                       priority: int = 1):
        """Register lazy loader for data"""
        self._loaders[key] = loader
        logger.debug(f"Registered lazy loader: {key}")
    
    def get_data(self, key: str) -> Any:
        """Get data with lazy loading"""
        # Check cache first
        cached_data = self.cache_manager.get(key)
        if cached_data is not None:
            return cached_data
        
        # Load if not cached
        if key not in self._loaders:
            raise KeyError(f"No loader registered for key: {key}")
        
        logger.debug(f"Lazy loading data: {key}")
        data = self._loaders[key]()
        
        # Cache the loaded data
        self.cache_manager.put(
            key, data, 
            max_age=timedelta(hours=2),  # Cache for 2 hours
            priority=1  # Non-critical data has low priority
        )
        
        self._loaded.add(key)
        return data
    
    def preload_critical(self, keys: List[str]):
        """Preload critical data"""
        for key in keys:
            if key not in self._loaded:
                try:
                    self.get_data(key)
                    logger.debug(f"Preloaded critical data: {key}")
                except Exception as e:
                    logger.error(f"Failed to preload {key}: {e}")


def cached(max_age: timedelta = None, 
          stale_acceptable: bool = False,
          priority: int = 1):
    """
    Decorator for caching function results
    
    Usage:
        @cached(max_age=timedelta(minutes=30))
        def expensive_calculation(param):
            return complex_computation(param)
    """
    def decorator(func):
        cache_manager = IntelligentCacheManager()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # Try to get from cache
            result = cache_manager.get(key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.put(
                key, result,
                max_age=max_age or timedelta(hours=1),
                stale_acceptable=stale_acceptable,
                priority=priority
            )
            
            return result
        
        return wrapper
    return decorator


# Global cache manager instance
_global_cache_manager = None

def get_global_cache_manager() -> IntelligentCacheManager:
    """Get global cache manager instance"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = IntelligentCacheManager()
    return _global_cache_manager