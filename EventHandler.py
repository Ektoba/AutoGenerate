from watchdog.events import FileSystemEventHandler
import threading

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config, logger, project_file_manager, file_deleter, delete_report, event_filter):
        super().__init__()
        self.config = config
        self.logger = logger
        self.project_file_manager = project_file_manager
        self.file_deleter = file_deleter
        self.delete_report = delete_report
        self.event_filter = event_filter
        self.debounce_lock = threading.Lock()
        self.timer = None

    def on_any_event(self, event):
        try:
            # 무시 패턴 검사
            if self.event_filter.ignore_by_pattern(
                event,
                self.config.get_setting("IgnoredNamePatterns", []),
                self.config.get_setting("IgnoredDirs", [])
            ):
                self.logger.debug(f"무시된 패턴: {event.src_path}")
                return

            if not self.event_filter.is_interesting(event):
                self.logger.debug(f"관심 파일 아님: {event.src_path}")
                return

            if self.event_filter.is_duplicate(event, event.event_type):
                self.logger.debug(f"중복 이벤트: {event.src_path}")
                return

            self.logger.info(f"이벤트 감지: {event.src_path} ({event.event_type})")

            # 디바운스(예: 0.1초 후 실행)
            with self.debounce_lock:
                if self.timer:
                    self.timer.cancel()
                self.timer = threading.Timer(0.1, self.run_update_script)
                self.timer.start()

        except Exception as e:
            self.logger.error(f"[EventHandler] 이벤트 처리 오류: {e}")

    def run_update_script(self):
        try:
            self.logger.info("VS 프로젝트 갱신/파일 청소 시작!")
            files_to_delete = self.project_file_manager.get_unreferenced_cpp_files()
            for file_path in files_to_delete:
                result = self.file_deleter.delete(file_path)
                if self.file_deleter.dry_run:
                    self.delete_report.add_dryrun(file_path)
                elif result:
                    self.delete_report.add_deleted(file_path)
                else:
                    self.delete_report.add_failed(file_path)
            self.delete_report.summary()
        except Exception as e:
            self
