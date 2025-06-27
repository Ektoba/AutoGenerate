# EventHandler.py
from watchdog.events import FileSystemEventHandler
import threading
import os


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config_manager, logger, event_filter, orchestrator):
        super().__init__()
        self.config_manager = config_manager
        self.logger = logger
        self.event_filter = event_filter
        self.orchestrator = orchestrator

        self.debounce_lock = threading.Lock()
        self.timer = None

        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()
        self.debounce_time_ms = self.config_manager.get_setting("DebounceTimeMs", 1500)

        self.watch_exts = set(config_manager.get_setting(
            "WatchFileExtensions", [".cpp", ".h", ".hpp", ".c", ".inl"]
        ))

    def _is_interesting_extension(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self.watch_exts
    def on_any_event(self, event):
        if self._is_filters_change(event):
            self.orchestrator.run_full_update()

        if self.orchestrator.is_running():
            self.logger.debug(f"업데이트 작업 중... 이벤트 무시: {event.src_path}")
            return

        if event.is_directory:
            self.logger.debug(f"디렉토리 이벤트는 무시: {event.src_path}")
            return

        # Vcxproj 파일 변경은 최우선으로 처리!
        if self.event_filter.is_interesting(event):
            self.logger.info(f"⚡ Vcxproj 파일 변경 감지! 즉시 프로젝트 갱신: {event.src_path} ({event.event_type})")
            with self.debounce_lock:
                if self.timer:
                    self.timer.cancel()
                self.orchestrator.run_full_update()
            return

        normalized_event_src_path = os.path.abspath(event.src_path).lower()
        watched_extensions = self.config_manager.get_setting("WatchFileExtensions", [])

        is_source_file_event = any(normalized_event_src_path.endswith(ext) for ext in watched_extensions)

        if is_source_file_event and event.event_type == 'modified':
            self.logger.debug(f"소스 파일 내용 변경은 무시 (최적화): {event.src_path}")
            return

        if not is_source_file_event:
            self.logger.debug(f"관심 없는 확장자 파일. 무시됨: {event.src_path}")
            return

        if not self.event_filter.is_valid_event_type(event.event_type):
            self.logger.debug(f"무시된 이벤트 타입: {event.event_type} - {event.src_path}")
            return

        if self.event_filter.ignore_by_pattern(event):
            self.logger.debug(f"무시된 패턴: {event.src_path}")
            return

        if self.event_filter.is_duplicate(event):
            self.logger.debug(f"중복 이벤트: {event.src_path}")
            return

        self.logger.info(f"✅ 최종 통과! 이벤트 감지: {event.src_path} ({event.event_type})")

        with self.debounce_lock:
            if self.timer:
                self.timer.cancel()

            self.timer = threading.Timer(self.debounce_time_ms / 1000.0, self.orchestrator.run_full_update)
            self.timer.start()
            self.logger.info(f"프로젝트 갱신 예약됨. ({self.debounce_time_ms / 1000.0}초 내 추가 변경 감지 시 재예약)")

    def on_deleted(self, event):
        # 소스/헤더 파일이 실제로 지워졌을 때
        if self._is_interesting_extension(event.src_path):
            self.logger.info(f"[DEBUG] 실제 삭제 감지, UBT 이전에 직접 처리: {event.src_path}")
            self.orchestrator.handle_file_deleted_pre_ubt(event.src_path)

    def _is_filters_change(self, event):
        if event.is_directory:
            return False
        normalized = os.path.abspath(event.src_path).lower()
        return normalized in (
            self.normalized_main_vcxproj_path,
            self.normalized_main_vcxproj_filters_path,
        )