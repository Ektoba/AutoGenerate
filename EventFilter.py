import os
import time
from collections import deque

class EventFilter:
    def __init__(self, interesting_paths):
        # 감시대상 전체 절대경로 (소문자)
        self.interesting_paths = set(os.path.abspath(p).lower() for p in interesting_paths)
        self.recent_events = deque(maxlen=32)

    def is_interesting(self, event):
        # 지정 경로에 포함된 파일만 트리거
        return os.path.abspath(event.src_path).lower() in self.interesting_paths

    def is_duplicate(self, event, event_type):
        now = time.time()
        key = (event_type, event.src_path)
        for ts, k in list(self.recent_events):
            if now - ts > 0.5:
                self.recent_events.popleft()
            elif k == key:
                return True
        self.recent_events.append((now, key))
        return False

    def ignore_by_pattern(self, event, ignored_names, ignored_dirs):
        file_name = os.path.basename(event.src_path).lower()
        if any(pattern in file_name for pattern in ignored_names):
            return True
        norm_path = os.path.abspath(event.src_path).lower().replace(os.sep, '/')
        if any(d.lower() in norm_path for d in ignored_dirs):
            return True
        return False
