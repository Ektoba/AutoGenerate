# EventHandler.py
from watchdog.events import FileSystemEventHandler
import threading
import time
import os
import sys
import subprocess
import locale
# DeleteReport를 여기서 import 해줘야 해!
from DeleteReport import DeleteReport


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config_manager, logger, project_file_manager, file_deleter, event_filter):
        self.config_manager = config_manager
        self.logger = logger
        self.project_file_manager = project_file_manager
        self.file_deleter = file_deleter
        # self.delete_report = delete_report # 여기서 초기화하지 않음
        self.event_filter = event_filter

        self.debounce_lock = threading.Lock()
        self.timer = None
        self.is_running_script = False  # 스크립트 실행 여부만 체크
        self.run_lock = threading.Lock()  # 동시 실행 방지

        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()
        self.debounce_time_ms = self.config_manager.get_setting("DebounceTimeMs", 1500)

    def on_any_event(self, event):
        self.logger.debug(f"--- 💡 이벤트 분석 시작: {event.src_path} ({event.event_type}) 💡 ---")

        if self.is_running_script:
            self.logger.debug("➡️ 판단: 스크립트가 이미 실행 중이므로 무시합니다.")
            return

        if event.is_directory:
            self.logger.debug("➡️ 판단: 디렉토리 이벤트이므로 무시합니다.")
            return

        normalized_event_src_path = os.path.abspath(event.src_path).lower()
        watched_extensions = self.config_manager.get_setting("WatchFileExtensions", [])

        is_source_file_event = any(normalized_event_src_path.endswith(ext) for ext in watched_extensions)
        is_main_project_file_event = (normalized_event_src_path == self.normalized_main_vcxproj_path or
                                      normalized_event_src_path == self.normalized_main_vcxproj_filters_path)

        self.logger.debug(f"분석 결과: 소스 파일 이벤트인가? -> {is_source_file_event}")
        self.logger.debug(f"분석 결과: 프로젝트 파일 이벤트인가? -> {is_main_project_file_event}")

        if is_source_file_event and event.event_type == 'modified':
            self.logger.debug("➡️ 판단: 소스 파일 '내용 수정'은 최적화를 위해 무시합니다.")
            return

        if not is_source_file_event and not is_main_project_file_event:
            self.logger.debug("➡️ 판단: 관심 없는 파일 종류이므로 무시합니다.")
            return

        self.logger.debug("✅ 1차 필터 통과! 상세 필터링을 시작합니다...")

        if not self.event_filter.is_valid_event_type(event.event_type):
            self.logger.debug(f"➡️ 판단: 유효하지 않은 이벤트 타입({event.event_type})이므로 무시합니다.")
            return

        if self.event_filter.ignore_by_pattern(event):
            self.logger.debug(f"➡️ 판단: 무시 패턴에 해당하므로 무시합니다.")
            return

        if self.event_filter.is_duplicate(event):
            self.logger.debug(f"➡️ 판단: 중복 이벤트이므로 무시합니다.")
            return

        self.logger.info(f"✅ 최종 통과! 이벤트 감지: {event.src_path} ({event.event_type})")

        delay_ms = self.debounce_time_ms
        delay_reason = f"파일 시스템 변경 감지 ({delay_ms / 1000.0}초 지연)"

        with self.debounce_lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(delay_ms / 1000.0, self.run_update_script)
            self.timer.start()
            self.logger.info(f"프로젝트 갱신 예약됨. ({delay_ms / 1000.0}초 내 추가 변경 감지 시 재예약)")

    def run_update_script(self):
        if not self.run_lock.acquire(blocking=False):
            self.logger.warning("이미 다른 업데이트 작업이 진행 중입니다. 이번 요청은 건너뜁니다.")
            return

        try:
            self.logger.info("VS 프로젝트 갱신/파일 청소 시작!")

            # 매번 새로운 리포트 객체 생성
            delete_report = DeleteReport(logger=self.logger)

            files_to_delete = self.project_file_manager.get_newly_unreferenced_files_and_update_cache()

            if files_to_delete:
                deleted_dirs = set()
                for file_path in files_to_delete:
                    dir_path = os.path.dirname(file_path)
                    if self.file_deleter.delete(file_path):
                        delete_report.add_deleted(file_path)  # 새 리포트에 기록
                        deleted_dirs.add(dir_path)
                    else:
                        delete_report.add_failed(file_path)  # 새 리포트에 기록

                # (빈 폴더 삭제 로직...)

            delete_report.summary(to_file=self.config_manager.get_abs_logfile())

            # --- Generate 스크립트 실행 전후로 플래그 제어 ---
            self.is_running_script = True
            self.logger.info("GenerateProjectFile.ps1 스크립트 실행 중... (이로 인한 파일 변경은 무시됩니다)")

            # (Powershell 스크립트 실행하는 subprocess 로직...)
            # ...

            self.logger.info("GenerateProjectFile.ps1 스크립트 실행 완료!")
            self.is_running_script = False
            # ----------------------------------------------

        except Exception as e:
            self.logger.error(f"예기치 않은 오류 발생: {e}", exc_info=True)
        finally:
            self.run_lock.release()
            self.logger.info("모든 작업 완료. 다시 감시를 시작합니다. ✨")