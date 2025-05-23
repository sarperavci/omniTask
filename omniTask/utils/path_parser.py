import re
from typing import Tuple, Optional

class PathParser:
    RELATIVE_PATH_PATTERN = re.compile(r'^prev(\d*)(?:\.(.*))?$')
    ARRAY_ACCESS_PATTERN = re.compile(r'^([^[]*)(?:\[(\d+)\])?$')

    @staticmethod
    def parse_relative_path(path: str) -> Tuple[Optional[int], Optional[str]]:
        match = PathParser.RELATIVE_PATH_PATTERN.match(path)
        if not match:
            return None, None
        
        steps_back = int(match.group(1)) if match.group(1) else 1
        remaining_path = match.group(2) or ""
        return steps_back, remaining_path

    @staticmethod
    def parse_array_access(part: str) -> Tuple[Optional[str], Optional[int]]:
        match = PathParser.ARRAY_ACCESS_PATTERN.match(part)
        if not match:
            return None, None
        
        key = match.group(1) or None
        index = int(match.group(2)) if match.group(2) else None
        return key, index 