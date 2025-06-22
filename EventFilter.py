import os
import time
from collections import deque
import sys  # sys 모듈 추가


class EventFilter:
    def __init__(self, config_manager):  # config_manager 인스턴스 받음
        self.config_manager = config_manager
        # config_manager에서 설정값 가져오기
        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()
        self.ignored_name_patterns = self.config_manager.get_setting("IgnoredNamePatterns",
                                                                     ['.obj', '.pdb', '.tmp', '.user', '.log', '.ilk',
                                                                      '.ipch', '.sdf', '.vs', '.VC.opendb', '.suo',
                                                                      '.ncb', '.bak', '~', '.swp', '.lock',
                                                                      '.autocover'])
        self.ignored_dirs = [d.lower() for d in self.config_manager.get_setting("IgnoredDirs",
                                                                                ['/intermediate/', '/saved/',
                                                                                 '/binaries/', '/build/',
                                                                                 '/deriveddata/', '/staging/',
                                                                                 '/unrealbuildtool/'])]

        self.recent_events = deque(maxlen=10)

    def is_interesting(self, event):
        """
        이벤트가 메인 .vcxproj 또는 .vcxproj.filters 파일에 대한 것인지 확인합니다.
        """
        normalized_event_src_path = os.path.abspath(event.src_path).lower()
        return normalized_event_src_path == self.normalized_main_vcxproj_path or \
            normalized_event_src_path == self.normalized_main_vcxproj_filters_path

    def is_duplicate(self, event):  # event_type 인자 제거, event 객체에서 추출
        """
        짧은 시간 내에 발생하는 중복 이벤트를 필터링합니다.
        """
        now = time.time()
        key = (event.event_type, event.src_path)  # event_type을 event 객체에서 직접 사용
        for ts, k in list(self.recent_events):
            if now - ts > 0.1:  # 100ms
                self.recent_events.popleft()
            elif k == key:
                return True
        self.recent_events.append((now, key))
        return False

    def ignore_by_pattern(self, event):  # event, ignored_names, ignored_dirs 인자 제거
        """
        이벤트가 무시할 패턴(파일 이름/디렉토리)에 해당하는지 확인합니다.
        """
        # 파일 이름 패턴 검사
        event_file_name_lower = os.path.basename(event.src_path).lower()
        if any(p in event_file_name_lower for p in self.ignored_name_patterns):
            return True

        # 디렉토리 패턴 검사
        normalized_path_for_ignored = os.path.abspath(event.src_path).lower().replace(os.sep, '/')
        if any(d in normalized_path_for_ignored for d in self.ignored_dirs):
            return True

        return False