"""
Clock Guard Module for Northstar V2

Verifies timezone and clock drift for trading system integrity.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import requests
import pytz

logger = logging.getLogger(__name__)


class ClockGuard:
    """Clock and timezone verification for trading systems"""
    
    def __init__(
        self,
        target_timezone: str = "Asia/Kolkata",
        drift_threshold_seconds: float = 5.0,
        reference_sources: Optional[list[str]] = None,
    ):
        """
        Initialize clock guard
        
        Args:
            target_timezone: Expected timezone (default: Asia/Kolkata)
            drift_threshold_seconds: Maximum allowed drift (default: 5.0s)
        """
        self.target_timezone = target_timezone
        self.drift_threshold = drift_threshold_seconds
        default_sources = [
            "http://worldtimeapi.org/api/timezone/Asia/Kolkata",
            "https://timeapi.io/api/Time/current/zone?timeZone=Asia/Kolkata",
        ]
        if reference_sources:
            self.reference_sources = [str(x).strip() for x in reference_sources if str(x).strip()]
        else:
            self.reference_sources = default_sources

    def _localize_reference_datetime(
        self, dt: datetime, source_timezone: Optional[str] = None
    ) -> datetime:
        """Ensure a reference datetime is timezone-aware."""
        if dt.tzinfo is not None:
            return dt

        tz_candidates = [source_timezone, self.target_timezone]
        for tz_name in tz_candidates:
            if not tz_name:
                continue
            try:
                tz = pytz.timezone(str(tz_name))
                return tz.localize(dt)
            except Exception:
                continue

        # Last resort fallback when source timezone is unavailable.
        return dt.replace(tzinfo=timezone.utc)
    
    def verify_timezone(self) -> Dict[str, Any]:
        """Verify system timezone configuration"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'check': 'timezone_verification',
            'status': 'unknown',
            'target_timezone': self.target_timezone,
            'system_timezone': None,
            'local_time': None,
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get system timezone
            local_tz = datetime.now().astimezone().tzinfo
            system_tz_name = str(local_tz)
            
            # Get local time in target timezone
            target_tz = pytz.timezone(self.target_timezone)
            local_time_target = datetime.now(target_tz)
            
            report.update({
                'system_timezone': system_tz_name,
                'local_time': local_time_target.isoformat(),
                'target_tz_offset': str(local_time_target.utcoffset())
            })
            
            # Check if timezone matches or is equivalent
            if self.target_timezone.lower() in system_tz_name.lower():
                report['status'] = 'correct'
                logger.info(f"Timezone verification passed: {system_tz_name}")
            else:
                # Check if offset matches (might be different name but same timezone)
                system_time = datetime.now()
                target_time = datetime.now(target_tz).replace(tzinfo=None)
                offset_diff = abs((system_time - target_time).total_seconds())
                
                if offset_diff < 60:  # Within 1 minute (accounting for execution time)
                    report['status'] = 'equivalent'
                    logger.info(f"Timezone equivalent: {system_tz_name} matches {self.target_timezone}")
                else:
                    report['status'] = 'incorrect'
                    report['issues'].append(f"System timezone {system_tz_name} != {self.target_timezone}")
                    report['recommendations'].append(f"Set system timezone to {self.target_timezone}")
                    logger.warning(f"Timezone mismatch: {system_tz_name} vs {self.target_timezone}")
        
        except Exception as e:
            report['status'] = 'error'
            report['issues'].append(f"Timezone verification failed: {e}")
            logger.error(f"Timezone verification error: {e}")
        
        return report
    
    @staticmethod
    def _sntp_offset(server: str = "time.apple.com", timeout: float = 3.0) -> Optional[float]:
        """True clock offset via a raw SNTP query (RFC 4330, UDP 123).

        Unlike the HTTP time APIs (which sit behind CDNs and can serve stale
        cached timestamps — measured ~15s of phantom 'drift' on 2026-07-06),
        SNTP measures offset with round-trip compensation:
            offset = ((t1 - t0) + (t2 - t3)) / 2
        Returns seconds of local-clock error, or None if unreachable."""
        import socket
        import struct
        import time as _time
        NTP_DELTA = 2208988800  # 1900→1970 epoch difference
        packet = b"\x1b" + 47 * b"\0"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(timeout)
                t0 = _time.time()
                sock.sendto(packet, (server, 123))
                data, _ = sock.recvfrom(512)
                t3 = _time.time()
            if len(data) < 48:
                return None
            unpacked = struct.unpack("!12I", data[:48])
            def _ts(hi_idx: int) -> float:
                return unpacked[hi_idx] - NTP_DELTA + unpacked[hi_idx + 1] / 2**32
            t1 = _ts(8)   # server receive
            t2 = _ts(10)  # server transmit
            return ((t1 - t0) + (t2 - t3)) / 2.0
        except Exception:
            return None

    def get_reference_time(self) -> Optional[datetime]:
        """Get reference time from external source"""
        for source in self.reference_sources:
            try:
                logger.debug(f"Fetching reference time from: {source}")
                response = requests.get(source, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # Parse different API formats
                if 'datetime' in data:  # worldtimeapi.org format
                    time_str = data['datetime']
                    ref_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    ref_time = self._localize_reference_datetime(
                        ref_time,
                        source_timezone=str(data.get("timezone", "") or self.target_timezone),
                    )
                elif 'dateTime' in data:  # timeapi.io format
                    time_str = data['dateTime']
                    ref_time = datetime.fromisoformat(time_str)
                    ref_time = self._localize_reference_datetime(
                        ref_time,
                        source_timezone=str(data.get("timeZone", "") or self.target_timezone),
                    )
                elif all(k in data for k in ['year', 'month', 'day', 'hour', 'minute']):
                    sec = int(data.get('seconds', 0) or 0)
                    ms = int(data.get('milliSeconds', 0) or 0)
                    ref_time = datetime(
                        int(data['year']),
                        int(data['month']),
                        int(data['day']),
                        int(data['hour']),
                        int(data['minute']),
                        sec,
                        ms * 1000,
                    )
                    ref_time = self._localize_reference_datetime(
                        ref_time,
                        source_timezone=str(data.get("timeZone", "") or self.target_timezone),
                    )
                else:
                    continue
                
                logger.debug(f"Reference time obtained: {ref_time}")
                return ref_time
                
            except Exception as e:
                logger.debug(f"Failed to get time from {source}: {e}")
                continue
        
        logger.warning("Could not obtain reference time from any source")
        return None
    
    def verify_clock_drift(self) -> Dict[str, Any]:
        """Verify clock drift against reference time"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'check': 'clock_drift_verification',
            'status': 'unknown',
            'local_time': None,
            'reference_time': None,
            'drift_seconds': None,
            'drift_threshold': self.drift_threshold,
            'within_threshold': False,
            'reference_available': False,
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get local time in target timezone
            target_tz = pytz.timezone(self.target_timezone)
            local_time = datetime.now(target_tz)
            report['local_time'] = local_time.isoformat()

            # PRIMARY: raw SNTP with round-trip compensation — immune to the
            # CDN-cached HTTP timestamps and request latency that previously
            # produced ~15s of phantom drift and blocked daemon startup.
            sntp_offset = self._sntp_offset()
            if sntp_offset is not None:
                drift_seconds = float(sntp_offset)
                ref_time_local = (local_time - timedelta(seconds=drift_seconds))
                report['reference_source'] = 'sntp:time.apple.com'
            else:
                # FALLBACK: HTTP time APIs. Compare against a local stamp taken
                # AFTER the fetch and tolerate their second-level precision.
                ref_time = self.get_reference_time()
                if ref_time is None:
                    report['status'] = 'unknown'
                    report['reference_available'] = False
                    report['issues'].append("No reference time source available")
                    report['recommendations'].append("Check internet connectivity for time sync")
                    logger.warning("Clock drift check: No reference time available")
                    return report
                if ref_time.tzinfo is None:
                    # For API payloads with naive datetime, assume target/source
                    # timezone, not UTC, to avoid false ±5:30h drift on IST hosts.
                    ref_time = self._localize_reference_datetime(ref_time, source_timezone=self.target_timezone)
                ref_time_local = ref_time.astimezone(target_tz)
                local_after_fetch = datetime.now(target_tz)
                drift_seconds = (local_after_fetch - ref_time_local).total_seconds()
                report['reference_source'] = 'http'
            
            report.update({
                'reference_time': ref_time_local.isoformat(),
                'drift_seconds': drift_seconds,
                'reference_available': True,
                'within_threshold': abs(drift_seconds) <= self.drift_threshold
            })
            
            if report['within_threshold']:
                report['status'] = 'acceptable'
                logger.info(f"Clock drift check passed: {drift_seconds:.2f}s "
                           f"(threshold: ±{self.drift_threshold}s)")
            else:
                report['status'] = 'excessive'
                report['issues'].append(f"Clock drift {drift_seconds:.2f}s exceeds threshold ±{self.drift_threshold}s")
                report['recommendations'].extend([
                    "Synchronize system clock with NTP",
                    "Check system time configuration",
                    "Consider using chrony or ntpd for time sync"
                ])
                logger.error(f"Clock drift EXCESSIVE: {drift_seconds:.2f}s "
                            f"(threshold: ±{self.drift_threshold}s)")
        
        except Exception as e:
            report['status'] = 'error'
            report['issues'].append(f"Clock drift verification failed: {e}")
            logger.error(f"Clock drift verification error: {e}")
        
        return report
    
    def comprehensive_time_check(self) -> Dict[str, Any]:
        """Perform comprehensive time and timezone verification"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'unknown',
            'checks': {},
            'alerts': [],
            'recommendations': [],
            'trading_safe': False
        }
        
        # Timezone check
        tz_check = self.verify_timezone()
        summary['checks']['timezone'] = tz_check
        
        # Clock drift check
        drift_check = self.verify_clock_drift()
        summary['checks']['clock_drift'] = drift_check
        
        # Determine overall status
        tz_ok = tz_check['status'] in ['correct', 'equivalent']
        drift_ok = drift_check['status'] in ['acceptable', 'unknown']  # Allow unknown for fallback
        
        if tz_ok and drift_ok:
            summary['overall_status'] = 'healthy'
            summary['trading_safe'] = True
            logger.info("Time verification: All checks passed - TRADING SAFE")
        elif tz_ok and drift_check['status'] == 'unknown':
            summary['overall_status'] = 'warning'
            summary['trading_safe'] = True  # Allow trading with warning
            summary['alerts'].append("Clock drift unknown - reference unavailable")
            logger.warning("Time verification: Clock drift unknown but timezone OK - TRADING ALLOWED")
        else:
            summary['overall_status'] = 'critical'
            summary['trading_safe'] = False
            
            if not tz_ok:
                summary['alerts'].append("Timezone configuration incorrect")
            if drift_check['status'] == 'excessive':
                summary['alerts'].append("Clock drift excessive")
            
            logger.error("Time verification: CRITICAL ISSUES - TRADING NOT SAFE")
        
        # Collect recommendations
        for check in summary['checks'].values():
            summary['recommendations'].extend(check.get('recommendations', []))
        
        return summary
    
    def get_market_time_info(self) -> Dict[str, Any]:
        """Get current market time information"""
        try:
            target_tz = pytz.timezone(self.target_timezone)
            now = datetime.now(target_tz)
            
            # Market hours (9:30 AM - 3:30 PM IST)
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            
            # Pre-market and post-market
            pre_market_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
            post_market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
            
            is_weekday = now.weekday() < 5  # Monday=0, Friday=4
            is_market_hours = (market_open <= now <= market_close) and is_weekday
            is_pre_market = (pre_market_start <= now < market_open) and is_weekday
            is_post_market = (market_close < now <= post_market_end) and is_weekday
            
            return {
                'current_time': now.isoformat(),
                'market_open': market_open.isoformat(),
                'market_close': market_close.isoformat(),
                'is_weekday': is_weekday,
                'is_market_hours': is_market_hours,
                'is_pre_market': is_pre_market,
                'is_post_market': is_post_market,
                'market_status': (
                    'open' if is_market_hours else
                    'pre_market' if is_pre_market else
                    'post_market' if is_post_market else
                    'closed'
                )
            }
        
        except Exception as e:
            logger.error(f"Market time info error: {e}")
            return {'error': str(e)}
