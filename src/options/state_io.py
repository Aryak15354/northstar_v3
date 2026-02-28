"""
State I/O Layer for Northstar V2 - Persistence and Crash Resilience

Provides atomic writes, WAL journaling, and process locking for options engine state.
"""

import json
import os
import platform
import time
import hashlib
import fcntl
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import pandas as pd
import logging
from src.options.runtime_guard import write_runtime_signature, verify_runtime_signature

logger = logging.getLogger(__name__)


def _fsync_parent_dir(path: Path) -> None:
    """Best-effort directory fsync so atomic replaces survive power loss."""
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
    except Exception:
        return
    try:
        os.fsync(dir_fd)
    except Exception:
        pass
    finally:
        os.close(dir_fd)


class ProcessLock:
    """Process lock file manager"""
    
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_file = None
        self.acquired = False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
    
    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire process lock with timeout"""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Use append/update mode so failed lock attempts do not truncate
                # an existing lock file owned by another process.
                self.lock_file = open(self.lock_path, 'a+', encoding='utf-8')
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Write process info
                lock_info = {
                    'pid': os.getpid(),
                    'acquired_at': datetime.now().isoformat(),
                    'hostname': platform.node(),
                }
                self.lock_file.seek(0)
                self.lock_file.truncate(0)
                self.lock_file.write(json.dumps(lock_info, indent=2))
                self.lock_file.flush()
                os.fsync(self.lock_file.fileno())
                
                self.acquired = True
                logger.info(f"Process lock acquired: {self.lock_path}")
                return True
                
            except (IOError, OSError):
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                time.sleep(1.0)
        
        logger.error(f"Failed to acquire process lock: {self.lock_path}")
        return False
    
    def release(self):
        """Release process lock"""
        if self.acquired and self.lock_file:
            owner_pid: Optional[int] = None
            try:
                try:
                    owner_pid = os.getpid()
                except Exception:
                    owner_pid = None
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                logger.info(f"Process lock released: {self.lock_path}")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")
            finally:
                self.lock_file = None
                self.acquired = False
                # Best-effort cleanup to avoid stale lock metadata confusing diagnostics.
                # We only remove the file if it still appears to belong to this process.
                try:
                    if self.lock_path.exists() and owner_pid is not None:
                        payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
                        if int(payload.get("pid", -1)) == int(owner_pid):
                            self.lock_path.unlink(missing_ok=True)
                except Exception:
                    # Ignore cleanup failures; flock release already guarantees unlock.
                    pass


class WriteAheadLog:
    """Write-Ahead Log for atomic operations"""
    
    def __init__(self, wal_path: Path):
        self.wal_path = wal_path
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _compute_checksum(self, file_path: Path) -> Optional[str]:
        """Compute file checksum"""
        if not file_path.exists():
            return None
        
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def log_operation(self, op_id: str, stage: str, target_path: Path, 
                     checksum_before: Optional[str] = None, 
                     checksum_after: Optional[str] = None,
                     error: Optional[str] = None) -> None:
        """Log WAL entry"""
        entry = {
            'op_id': op_id,
            'stage': stage,  # prepared|committed|failed
            'target_path': str(target_path),
            'timestamp': datetime.now().isoformat(),
            'checksum_before': checksum_before,
            'checksum_after': checksum_after,
            'error': error
        }
        
        with open(self.wal_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
            f.flush()
            os.fsync(f.fileno())
    
    def read_log(self) -> List[Dict[str, Any]]:
        """Read all WAL entries"""
        if not self.wal_path.exists():
            return []
        
        entries = []
        with open(self.wal_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid WAL entry: {line} - {e}")
        return entries
    
    def get_interrupted_operations(self) -> List[Dict[str, Any]]:
        """Find operations that were prepared but not committed"""
        entries = self.read_log()
        
        # Group by op_id
        ops = {}
        for entry in entries:
            op_id = entry['op_id']
            if op_id not in ops:
                ops[op_id] = []
            ops[op_id].append(entry)
        
        # Find interrupted operations
        interrupted = []
        for op_id, op_entries in ops.items():
            stages = [e['stage'] for e in op_entries]
            if 'prepared' in stages and 'committed' not in stages and 'failed' not in stages:
                interrupted.append({
                    'op_id': op_id,
                    'entries': op_entries,
                    'target_path': op_entries[0]['target_path']
                })
        
        return interrupted
    
    def clear_log(self):
        """Clear WAL (use with caution)"""
        if self.wal_path.exists():
            self.wal_path.unlink()
        logger.info("WAL cleared")


class AtomicStateWriter:
    """Atomic state writer with WAL support"""
    
    def __init__(self, wal: WriteAheadLog):
        self.wal = wal
    
    def write_json(self, target_path: Path, data: Dict[str, Any]) -> bool:
        """Atomically write JSON data"""
        op_id = f"json_{int(time.time() * 1000000)}"
        temp_path = target_path.with_suffix(target_path.suffix + '.tmp')
        
        try:
            # Prepare phase
            checksum_before = self.wal._compute_checksum(target_path)
            self.wal.log_operation(op_id, 'prepared', target_path, checksum_before)
            
            # Write to temp file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic move
            temp_path.replace(target_path)
            _fsync_parent_dir(target_path)
            
            # Commit phase
            checksum_after = self.wal._compute_checksum(target_path)
            self.wal.log_operation(op_id, 'committed', target_path, 
                                 checksum_before, checksum_after)
            
            logger.debug(f"Atomic JSON write completed: {target_path}")
            return True
            
        except Exception as e:
            # Failed phase
            self.wal.log_operation(op_id, 'failed', target_path, error=str(e))
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Atomic JSON write failed: {target_path} - {e}")
            return False
    
    def write_parquet(self, target_path: Path, df: pd.DataFrame) -> bool:
        """Atomically write Parquet data"""
        op_id = f"parquet_{int(time.time() * 1000000)}"
        temp_path = target_path.with_suffix(target_path.suffix + '.tmp')
        
        try:
            # Prepare phase
            checksum_before = self.wal._compute_checksum(target_path)
            self.wal.log_operation(op_id, 'prepared', target_path, checksum_before)
            
            # Write to temp file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(temp_path, index=False)
            try:
                with open(temp_path, "rb") as tmp_fh:
                    os.fsync(tmp_fh.fileno())
            except Exception:
                pass
            
            # Atomic move
            temp_path.replace(target_path)
            _fsync_parent_dir(target_path)
            
            # Commit phase
            checksum_after = self.wal._compute_checksum(target_path)
            self.wal.log_operation(op_id, 'committed', target_path, 
                                 checksum_before, checksum_after)
            
            logger.debug(f"Atomic Parquet write completed: {target_path}")
            return True
            
        except Exception as e:
            # Failed phase
            self.wal.log_operation(op_id, 'failed', target_path, error=str(e))
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Atomic Parquet write failed: {target_path} - {e}")
            return False


class StateIOManager:
    """Main state I/O manager"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.lock_path = base_path / "options_engine.lock"
        self.wal_path = base_path / "write_journal.log"
        self.runtime_write_lock_path = base_path / "options_runtime_state.write.lock"
        
        self.wal = WriteAheadLog(self.wal_path)
        self.writer = AtomicStateWriter(self.wal)
        self.process_lock = ProcessLock(self.lock_path)
    
    def acquire_lock(self, timeout: float = 30.0) -> bool:
        """Acquire process lock"""
        return self.process_lock.acquire(timeout)
    
    def release_lock(self):
        """Release process lock"""
        self.process_lock.release()
    
    def check_interrupted_operations(self) -> List[Dict[str, Any]]:
        """Check for interrupted operations from previous runs"""
        return self.wal.get_interrupted_operations()

    def resolve_interrupted_operations(
        self,
        interrupted_ops: List[Dict[str, Any]],
        reason: str = "recovered_on_startup",
    ) -> None:
        """Mark interrupted operations as resolved by writing failed terminal entries."""
        for op in interrupted_ops or []:
            try:
                op_id = str(op.get("op_id") or "")
                target = Path(str(op.get("target_path") or ""))
                if not op_id:
                    continue
                self.wal.log_operation(
                    op_id=op_id,
                    stage="failed",
                    target_path=target,
                    error=reason,
                )
            except Exception as e:
                logger.warning(f"Failed to mark interrupted op as resolved: {e}")

    def _acquire_advisory_lock(self, lock_path: Path, timeout: float = 10.0):
        """Acquire a short-lived advisory file lock."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+", encoding="utf-8")
        start = time.time()
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return handle
            except (IOError, OSError):
                if time.time() - start >= timeout:
                    handle.close()
                    return None
                time.sleep(0.05)

    @staticmethod
    def _release_advisory_lock(handle) -> None:
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass
    
    def write_runtime_state(self, data: Dict[str, Any]) -> bool:
        """Write runtime state atomically with cross-process serialization."""
        runtime_path = self.base_path / "options_runtime_state.json"
        lock_handle = self._acquire_advisory_lock(self.runtime_write_lock_path, timeout=10.0)
        if lock_handle is None:
            logger.error("Runtime write lock timeout: %s", self.runtime_write_lock_path)
            return False
        try:
            ok = self.writer.write_json(runtime_path, data)
            if not ok:
                return False
            return bool(write_runtime_signature(runtime_path))
        finally:
            self._release_advisory_lock(lock_handle)
    
    def write_dashboard_state(self, data: Dict[str, Any]) -> bool:
        """Write dashboard state atomically"""
        return self.writer.write_json(self.base_path / "options_dashboard_state.json", data)

    def verify_runtime_state_signature(self) -> Dict[str, Any]:
        """Verify runtime checksum sidecar status."""
        return verify_runtime_signature(self.base_path / "options_runtime_state.json")
    
    def write_ledger(self, df: pd.DataFrame) -> bool:
        """Write trade ledger atomically"""
        return self.writer.write_parquet(self.base_path.parent / "trade_ledger.parquet", df)
    
    def create_eod_snapshot(self, date_str: str, data: Dict[str, Any]) -> bool:
        """Create end-of-day snapshot"""
        eod_dir = self.base_path / "eod_snapshots"
        eod_dir.mkdir(exist_ok=True)
        return self.writer.write_json(eod_dir / f"{date_str}.json", data)
