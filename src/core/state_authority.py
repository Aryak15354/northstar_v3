"""
State Authority — Single write interface for all UnifiedState mutations.

This module makes all state writes auditable, atomic, and conflict-checked.
All shared state mutations must flow through StateAuthority.update().
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WritePriority(IntEnum):
    """Write priority levels for conflict resolution."""

    EMERGENCY = 0
    LIVE_RISK = 1
    LIVE_TRADING = 2
    BRIDGE_SYNC = 3
    RESEARCH = 4


@dataclass
class StateUpdate:
    """A single state update request."""

    writer_id: str
    section: str
    field_path: str
    new_value: Any
    priority: WritePriority
    source: str
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WriterRegistration:
    """Registered writer configuration."""

    writer_id: str
    allowed_sections: List[str]
    priority: WritePriority


class StateAuthority:
    """The sole interface for mutating UnifiedState."""

    SECTION_ALIASES = {
        'market_state': 'market',
        'macro_state': 'macro',
        'regime_state': 'regime',
        'pulse_state': 'pulse',
        'belief_state': 'beliefs',
        'beliefs_state': 'beliefs',
        'confidence_state': 'confidence',
        'strategy_state': 'strategies',
        'strategies_state': 'strategies',
        'capital_state': 'capital',
        'portfolio_state': 'portfolio',
        'risk_state': 'risk',
        'health_state': 'health',
        'memory_state': 'memory',
    }

    CRITICAL_SECTIONS = {'portfolio', 'risk', 'pnl_state', 'governor_state'}

    def __init__(self, unified_state, config: Optional[dict] = None):
        self.unified_state = unified_state
        self.state = unified_state
        self.config = config or {}
        self.dev_mode = bool(self.config.get('dev_mode', False))

        self._locks: Dict[str, threading.RLock] = {}
        self._lock_holders: Dict[str, Optional[str]] = {}
        self._writers: Dict[str, WriterRegistration] = {}
        self._dirty_sections: set[str] = set()

        default_log_path = Path('data/state/state_change_log.jsonl')
        self._log_path = Path(self.config.get('state_change_log_path', default_log_path))
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        checkpoint_path = self.config.get('checkpoint_path')
        self._checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        if self._checkpoint_path is not None:
            self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize_locks()
        logger.info("StateAuthority initialized")

    def _initialize_locks(self) -> None:
        """Initialize write locks for all canonical state sections."""
        sections = [
            'market',
            'macro',
            'regime',
            'pulse',
            'beliefs',
            'confidence',
            'strategies',
            'capital',
            'portfolio',
            'risk',
            'health',
            'memory',
            'sentiment',
            'alternative_data',
            'alpha_os',
            'intelligence_state',
            'pnl_state',
            'governor_state',
            'shadow_state',
            'valuation_state',
        ]

        for section in sections:
            self._locks[section] = threading.RLock()
            self._lock_holders[section] = None

    def _canonical_section(self, section: str) -> str:
        return self.SECTION_ALIASES.get(section, section)

    def register_writer(
        self,
        writer_id: str,
        allowed_sections: List[str],
        priority: WritePriority,
    ) -> None:
        normalized_sections = sorted(
            {self._canonical_section(section) for section in allowed_sections}
        )
        self._writers[writer_id] = WriterRegistration(
            writer_id=writer_id,
            allowed_sections=normalized_sections,
            priority=priority,
        )
        logger.info(
            "Registered writer: %s (sections=%s, priority=%s)",
            writer_id,
            normalized_sections,
            priority.name,
        )

    @property
    def registered_writers(self) -> Dict[str, WriterRegistration]:
        """Compatibility view for legacy integration checks."""
        return self._writers

    def update(self, state_update: StateUpdate) -> bool:
        """Thread-safe state update. All shared-state mutations flow through here."""
        if not self._validate_update(state_update):
            return False

        lock_key = self._canonical_section(state_update.section)
        if not self._acquire_lock(lock_key, state_update.writer_id):
            logger.warning(
                "Update rejected - lock held by higher priority writer: %s",
                state_update.section,
            )
            return False

        try:
            success = self._apply_update(state_update)
            if success:
                self._dirty_sections.add(lock_key)
                self._log_update(state_update)
                if lock_key in self.CRITICAL_SECTIONS:
                    self.checkpoint()
            return success
        finally:
            self._release_lock(lock_key)

    def batch_update(self, updates: List[StateUpdate]) -> int:
        """Apply multiple updates atomically and return the number applied."""
        if not updates:
            return 0

        for update in updates:
            if not self._validate_update(update):
                return 0

        lock_keys = sorted({self._canonical_section(update.section) for update in updates})
        acquired = []

        for lock_key in lock_keys:
            writer_id = next(
                update.writer_id
                for update in updates
                if self._canonical_section(update.section) == lock_key
            )
            if not self._acquire_lock(lock_key, writer_id):
                for held in reversed(acquired):
                    self._release_lock(held)
                return 0
            acquired.append(lock_key)

        original_values: List[Tuple[StateUpdate, Any]] = []
        applied_updates: List[StateUpdate] = []

        try:
            for update in updates:
                original_values.append((update, copy.deepcopy(self._get_current_value(update))))
                if not self._apply_update(update):
                    for applied_update, original_value in reversed(original_values):
                        self._restore_value(applied_update, original_value)
                    return 0
                applied_updates.append(update)

            for update in applied_updates:
                self._dirty_sections.add(self._canonical_section(update.section))
                self._log_update(update)

            if any(self._canonical_section(update.section) in self.CRITICAL_SECTIONS for update in updates):
                self.checkpoint()

            return len(applied_updates)
        finally:
            for lock_key in reversed(acquired):
                self._release_lock(lock_key)

    def _validate_update(self, state_update: StateUpdate) -> bool:
        """Validate writer permissions and field-path integrity."""
        canonical_section = self._canonical_section(state_update.section)

        if state_update.priority == WritePriority.EMERGENCY and not str(state_update.reason or "").strip():
            logger.error("Emergency update rejected - reason required")
            return False

        if state_update.writer_id not in self._writers:
            logger.warning("Unregistered writer attempted update: %s", state_update.writer_id)
            if self.dev_mode:
                warnings.warn(
                    f"Direct write by {state_update.writer_id} bypasses StateAuthority. "
                    "Register writer with register_writer().",
                    DeprecationWarning,
                    stacklevel=3,
                )
            else:
                return False
        else:
            writer = self._writers[state_update.writer_id]
            if canonical_section not in writer.allowed_sections:
                logger.error(
                    "Writer %s not authorized for section %s",
                    state_update.writer_id,
                    state_update.section,
                )
                return False

        if not hasattr(self.unified_state, canonical_section):
            logger.error("Invalid state section: %s", state_update.section)
            return False

        try:
            container, key = self._resolve_container_and_key(
                getattr(self.unified_state, canonical_section),
                state_update.field_path,
                create_missing_dicts=False,
            )
        except AttributeError:
            logger.error("Invalid field path: %s", state_update.field_path)
            return False

        if isinstance(container, dict):
            return True

        if not hasattr(container, key):
            logger.error("Invalid field: %s", state_update.field_path)
            return False

        return True

    def _resolve_container_and_key(
        self,
        section_obj: Any,
        field_path: str,
        create_missing_dicts: bool = False,
    ) -> Tuple[Any, str]:
        parts = field_path.split('.')
        current_obj = section_obj

        for part in parts[:-1]:
            if isinstance(current_obj, dict):
                if part not in current_obj:
                    if not create_missing_dicts:
                        raise AttributeError(field_path)
                    current_obj[part] = {}
                current_obj = current_obj[part]
                continue

            if not hasattr(current_obj, part):
                raise AttributeError(field_path)

            current_obj = getattr(current_obj, part)

        return current_obj, parts[-1]

    def _coerce_value(self, current_value: Any, new_value: Any) -> Any:
        if isinstance(current_value, Enum) and isinstance(new_value, str):
            try:
                return current_value.__class__(new_value)
            except Exception:
                return new_value
        return new_value

    def _apply_update(self, state_update: StateUpdate) -> bool:
        canonical_section = self._canonical_section(state_update.section)
        section_obj = getattr(self.unified_state, canonical_section)

        try:
            container, key = self._resolve_container_and_key(
                section_obj,
                state_update.field_path,
                create_missing_dicts=True,
            )

            if isinstance(container, dict):
                container[key] = state_update.new_value
            else:
                current_value = getattr(container, key)
                setattr(container, key, self._coerce_value(current_value, state_update.new_value))

            if hasattr(section_obj, 'last_updated'):
                section_obj.last_updated = datetime.now()

            return True
        except Exception as exc:
            logger.error("Failed to apply update: %s", exc)
            return False

    def _get_current_value(self, state_update: StateUpdate) -> Any:
        canonical_section = self._canonical_section(state_update.section)
        section_obj = getattr(self.unified_state, canonical_section)
        container, key = self._resolve_container_and_key(
            section_obj,
            state_update.field_path,
            create_missing_dicts=True,
        )
        if isinstance(container, dict):
            return container.get(key)
        return getattr(container, key)

    def _restore_value(self, state_update: StateUpdate, original_value: Any) -> None:
        canonical_section = self._canonical_section(state_update.section)
        section_obj = getattr(self.unified_state, canonical_section)
        container, key = self._resolve_container_and_key(
            section_obj,
            state_update.field_path,
            create_missing_dicts=True,
        )
        if isinstance(container, dict):
            if original_value is None and key in container:
                del container[key]
            else:
                container[key] = original_value
            return

        setattr(container, key, original_value)

    def _acquire_lock(self, canonical_section: str, writer_id: str) -> bool:
        lock = self._locks.get(canonical_section)
        if lock is None:
            logger.error("No lock for section: %s", canonical_section)
            return False

        acquired = lock.acquire(timeout=5.0)
        if acquired:
            self._lock_holders[canonical_section] = writer_id
        return acquired

    def _release_lock(self, canonical_section: str) -> None:
        lock = self._locks.get(canonical_section)
        if lock is None:
            return

        self._lock_holders[canonical_section] = None
        lock.release()

    def _log_update(self, state_update: StateUpdate) -> None:
        log_entry = {
            'timestamp': state_update.timestamp.isoformat(),
            'writer_id': state_update.writer_id,
            'section': state_update.section,
            'canonical_section': self._canonical_section(state_update.section),
            'field_path': state_update.field_path,
            'new_value': state_update.new_value,
            'priority': state_update.priority.name,
            'source': state_update.source,
            'reason': state_update.reason,
        }

        try:
            with open(self._log_path, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(log_entry, default=str) + '\n')
        except Exception as exc:
            logger.error("Failed to log state update: %s", exc)

    def checkpoint(self, force: bool = False) -> None:
        """
        Write unified_state.json atomically.

        Args:
            force: Reserved for future checkpoint throttling support.
        """
        del force

        dirty_sections = set(self._dirty_sections)

        if self._checkpoint_path is None:
            self.unified_state.save_state(preserve_existing=True)
            self._dirty_sections.clear()
            return

        if not dirty_sections and self._checkpoint_path.exists():
            return

        payload = self.unified_state.get_state_dict()
        if self._checkpoint_path.exists() and dirty_sections:
            try:
                with open(self._checkpoint_path, 'r', encoding='utf-8') as handle:
                    existing_payload = json.load(handle)
            except Exception:
                existing_payload = {}

            if isinstance(existing_payload, dict):
                merged_payload = dict(existing_payload)
                passthrough_sections = {
                    'timestamp',
                    'version',
                    'locked',
                    'lock_reason',
                    'lock_authority',
                    'time',
                    'recent_events',
                }
                for key, value in payload.items():
                    if key in passthrough_sections or key in dirty_sections or key not in existing_payload:
                        merged_payload[key] = value
                payload = merged_payload

        temp_path = self._checkpoint_path.with_suffix(f"{self._checkpoint_path.suffix}.tmp")
        with open(temp_path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, default=str)
        temp_path.replace(self._checkpoint_path)
        try:
            self.unified_state.update_state_history(payload)
        except Exception as exc:
            logger.error("Failed to update unified state history after checkpoint: %s", exc)
        self._dirty_sections.clear()

    def get_state_history(
        self,
        section: str,
        since: datetime,
        field_path: Optional[str] = None,
    ) -> List[dict]:
        """Read the append-only state change log and reconstruct section history."""
        if not self._log_path.exists():
            return []

        requested_section = section
        canonical_section = self._canonical_section(section)
        matching_entries: List[dict] = []
        filtered_entries: List[dict] = []

        try:
            with open(self._log_path, 'r', encoding='utf-8') as handle:
                for line in handle:
                    if not line.strip():
                        continue

                    entry = json.loads(line)
                    entry_section = entry.get('section')
                    entry_canonical = entry.get('canonical_section', self._canonical_section(entry_section))

                    if entry_section not in {requested_section, canonical_section} and entry_canonical != canonical_section:
                        continue

                    if field_path and entry.get('field_path') != field_path:
                        continue

                    matching_entries.append(entry)

                    entry_time = datetime.fromisoformat(entry['timestamp'])
                    if entry_time >= since:
                        filtered_entries.append(entry)

        except Exception as exc:
            logger.error("Failed to read state history: %s", exc)
            return []

        return filtered_entries if filtered_entries else matching_entries

    def get_current_writer(self, section: str) -> Optional[str]:
        """Get the writer currently holding the section lock."""
        return self._lock_holders.get(self._canonical_section(section))
