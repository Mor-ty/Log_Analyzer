import re
from datetime import datetime
from typing import Optional, List
from app.models.log import LogEntry, LogLevel


class LogParser:
    """Parse various log formats and extract structured data."""
    
    # Common log patterns
    PATTERNS = [
        # Standard timestamp formats
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)',
        r'(?P<timestamp>\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})',
        
        # Log levels
        r'(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL|TRACE)',
        
        # Kubernetes pod format
        r'(?P<pod_name>[a-z0-9-]+-[a-z0-9]{5,10})',
    ]
    
    def __init__(self):
        self.timestamp_pattern = re.compile(self.PATTERNS[0])
        self.level_pattern = re.compile(self.PATTERNS[2])
        self.pod_pattern = re.compile(self.PATTERNS[3])
    
    def parse_line(self, line: str) -> dict:
        """Parse a single log line and extract structured information."""
        result = {
            'timestamp': None,
            'level': None,
            'message': line.strip(),
            'pod_name': None
        }
        
        # Extract timestamp
        timestamp_match = self.timestamp_pattern.search(line)
        if timestamp_match:
            result['timestamp'] = self._parse_timestamp(timestamp_match.group('timestamp'))
        
        # Extract log level
        level_match = self.level_pattern.search(line.upper())
        if level_match:
            level_str = level_match.group('level')
            result['level'] = self._normalize_log_level(level_str)
        
        # Extract pod name if present
        pod_match = self.pod_pattern.search(line)
        if pod_match and 'pod_name' in pod_match.groupdict():
            result['pod_name'] = pod_match.group('pod_name')
        
        return result
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse various timestamp formats."""
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _normalize_log_level(self, level: str) -> Optional[LogLevel]:
        """Normalize various log level formats to standard enum."""
        level_map = {
            'DEBUG': LogLevel.DEBUG,
            'INFO': LogLevel.INFO,
            'WARN': LogLevel.WARNING,
            'WARNING': LogLevel.WARNING,
            'ERROR': LogLevel.ERROR,
            'CRITICAL': LogLevel.CRITICAL,
            'FATAL': LogLevel.CRITICAL,
            'TRACE': LogLevel.DEBUG,
        }
        return level_map.get(level.upper())
    
    def parse_file(self, file_content: str) -> List[dict]:
        """Parse entire log file and return structured entries."""
        entries = []
        for line in file_content.split('\n'):
            if line.strip():
                parsed = self.parse_line(line)
                if parsed['message']:  # Only add if there's content
                    entries.append(parsed)
        return entries
    
    def parse_k8s_log(self, log_content: str, namespace: str, pod_name: str, container: str = None) -> List[dict]:
        """Parse Kubernetes log output with resource metadata."""
        entries = []
        for line in log_content.split('\n'):
            if line.strip():
                parsed = self.parse_line(line)
                parsed['namespace'] = namespace
                parsed['pod_name'] = pod_name
                parsed['container_name'] = container or 'main'
                entries.append(parsed)
        return entries
