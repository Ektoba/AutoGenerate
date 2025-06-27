# EventFilter.py
import os
import time
from collections import deque
import sys


class EventFilter:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()

        self.ignored_name_patterns = [p for p in self.config_manager.get_setting("IgnoredNamePatterns",
                                                                                 ['.obj', '.pdb', '.tmp', '.user',
                                                                                  '.log', '.ilk',
                                                                                  '.ipch', '.sdf', '.vs', '.VC.opendb',
                                                                                  '.suo',
                                                                                  '.ncb', '.bak', '~', '.swp', '.lock',
                                                                                  '.autocover', '.asset']) if
                                      not (p.endswith('.vcxproj') or p.endswith('.vcxproj.filters'))]

        self.ignored_dirs = [d.lower() for d in self.config_manager.get_setting("IgnoredDirs",
                                                                                ['/intermediate/', '/saved/',
                                                                                 '/binaries/', '/build/',
                                                                                 '/deriveddata/', '/staging/',
                                                                                 '/unrealbuildtool/',
                                                                                 '/logs/',
                                                                                 '/backup/'
                                                                                 ])]

        self.recent_events = deque(maxlen=32)
        self.valid_event_types = ['modified', 'created', 'deleted', 'moved', 'renamed']

    def is_valid_event_type(self, event_type):
        return event_type in self.valid_event_types

    def is_interesting(self, event):
        normalized_event_src_path = os.path.abspath(event.src_path).lower()
        return normalized_event_src_path == self.normalized_main_vcxproj_path or \
            normalized_event_src_path == self.normalized_main_vcxproj_filters_path

    def is_duplicate(self, event):
        now = time.time()
        key = (event.event_type, event.src_path, getattr(event, 'dest_path', None))
        for ts, k in list(self.recent_events):
            if now - ts > 0.1:
                self.recent_events.popleft()
            elif k == key:
                return True
        self.recent_events.append((now, key))
        return False

    def ignore_by_pattern(self, event):
        if self.is_interesting(event):
            return False

        event_file_name_lower = os.path.basename(event.src_path).lower()
        if any(p in event_file_name_lower for p in self.ignored_name_patterns):
            return True

        normalized_path_for_ignored = os.path.abspath(event.src_path).lower().replace(os.sep, '/')
        if any(d in normalized_path_for_ignored for d in self.ignored_dirs):
            return True

        return False