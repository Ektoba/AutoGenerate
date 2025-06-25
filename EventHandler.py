# EventHandler.py
from watchdog.events import FileSystemEventHandler
import threading
import time
import os
import sys
import subprocess
import locale


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config_manager, logger, project_file_manager, file_deleter, delete_report, event_filter):
        self.config_manager = config_manager
        self.logger = logger
        self.project_file_manager = project_file_manager
        self.file_deleter = file_deleter
        self.delete_report = delete_report
        self.event_filter = event_filter

        self.debounce_lock = threading.Lock()
        self.timer = None
        self.is_running_script = False
        self.run_lock = threading.Lock()

        self.main_vcxproj_path_raw, self.main_vcxproj_filters_path_raw = self.config_manager.get_main_vcxproj_paths()
        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()
        self.debounce_time_for_other_events_ms = self.config_manager.get_setting("DebounceTimeMs", 1500)
        self.run_script_name = self.config_manager.get_setting("GenerateScript", "GenerateProjectFile.ps1")
        self.script_dir = self.config_manager.base_dir

    def on_any_event(self, event):
        self.logger.debug(
            f"[RAW EVENT HANDLER] Type: {event.event_type}, Src: {event.src_path}, IsDir: {event.is_directory}")

        if self.is_running_script:
            self.logger.debug(f"스크립트 실행 중... 이벤트 무시: {event.src_path}")
            return

        if event.is_directory:
            self.logger.debug(f"디렉토리 이벤트는 무시: {event.src_path}")
            return

        # --- ✨ 여기가 최종적으로 정리된 이벤트 필터링 로직! ✨ ---
        normalized_event_src_path = os.path.abspath(event.src_path).lower()
        watched_extensions = self.config_manager.get_setting("WatchFileExtensions", [])

        is_source_file_event = any(normalized_event_src_path.endswith(ext) for ext in watched_extensions)
        is_main_project_file_event = (normalized_event_src_path == self.normalized_main_vcxproj_path or
                                      normalized_event_src_path == self.normalized_main_vcxproj_filters_path)

        # 최적화: 소스 파일의 '내용'만 바뀐 경우는 무시!
        if is_source_file_event and event.event_type == 'modified':
            self.logger.debug(f"소스 파일 내용 변경은 무시 (최적화): {event.src_path}")
            return

        # 관심 대상이 아니면 모두 무시
        if not is_source_file_event and not is_main_project_file_event:
            self.logger.debug(f"관심 없는 이벤트. 무시됨: {event.src_path}")
            return

        # --- 이하 나머지 필터링 및 타이머 실행 ---
        if not self.event_filter.is_valid_event_type(event.event_type):
            self.logger.debug(f"무시된 이벤트 타입: {event.event_type} - {event.src_path}")
            return

        if self.event_filter.ignore_by_pattern(event):
            self.logger.debug(f"무시된 패턴: {event.src_path}")
            return

        if self.event_filter.is_duplicate(event):
            self.logger.debug(f"중복 이벤트: {event.src_path}")
            return

        self.logger.info(f"이벤트 감지: {event.src_path} ({event.event_type})")

        delay_ms = self.debounce_time_for_other_events_ms
        delay_reason = f"파일 시스템 변경 감지 ({delay_ms / 1000.0}초 지연)"

        with self.debounce_lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(delay_ms / 1000.0, self.run_update_script)
            self.timer.start()
            self.logger.info(f"프로젝트 갱신 예약됨: {delay_reason}. 추가 변경 감지 시 재예약.")

    def run_update_script(self):
        if not self.run_lock.acquire(blocking=False):
            self.logger.warning("이미 다른 업데이트 작업이 진행 중입니다. 이번 요청은 건너뜁니다.")
            return

        try:
            self.is_running_script = True

            self.logger.info("파일 시스템이 안정화되기를 잠시 대기합니다... (1초)")
            time.sleep(1)

            self.logger.info("VS 프로젝트 갱신/파일 청소 시작!")
            files_to_delete = self.project_file_manager.get_newly_unreferenced_files_and_update_cache()

            deleted_dirs = set()
            if files_to_delete:
                for file_path in files_to_delete:
                    dir_path = os.path.dirname(file_path)
                    if self.file_deleter.delete(file_path):
                        deleted_dirs.add(dir_path)
            else:
                self.logger.info("삭제할 파일이 없습니다.")

            sorted_dirs = sorted(list(deleted_dirs), key=len, reverse=True)
            for dir_path in sorted_dirs:
                try:
                    if not os.listdir(dir_path):
                        self.logger.info(f"빈 폴더 발견! 함께 정리합니다 (휴지통으로 이동): {dir_path}")
                        self.file_deleter.delete_folder(dir_path)
                except FileNotFoundError:
                    self.logger.debug(f"이미 정리된 폴더입니다. 건너뜁니다: {dir_path}")
                except Exception as e:
                    self.logger.error(f"빈 폴더 정리 중 오류: {dir_path} - {e}")

            self.delete_report.summary(to_file=self.config_manager.get_abs_logfile())
            self.logger.info("GenerateProjectFile.ps1 스크립트 실행 중...")

            # (이하 스크립트 실행 및 결과 출력 로직은 모두 동일)
            # ...

        except Exception as e:
            self.logger.error(f"예기치 않은 오류 발생: {e}", exc_info=True)
        finally:
            self.is_running_script = False
            self.run_lock.release()
            self.logger.info("모든 작업 완료. 다시 감시를 시작합니다. ✨")