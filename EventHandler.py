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

        # EventHandler.py 안에 있는 run_update_script 함수

    def run_update_script(self):
        # 다른 작업이 이미 실행 중이면 이번 요청은 건너뜀 (동시 실행 방지)
        if not self.run_lock.acquire(blocking=False):
            self.logger.warning("이미 다른 업데이트 작업이 진행 중입니다. 이번 요청은 건너뜁니다.")
            return

        try:
            self.logger.info("VS 프로젝트 갱신/파일 청소 시작!")

            # 👈 1. 매번 새로운 리포트 객체를 생성해서 보고서가 중첩되지 않게 함
            delete_report = DeleteReport(logger=self.logger)

            # 캐시와 비교해서 '새롭게' 참조가 끊긴 파일만 가져옴
            files_to_delete = self.project_file_manager.get_newly_unreferenced_files_and_update_cache()

            deleted_dirs = set()
            if files_to_delete:
                self.logger.info(f"프로젝트에서 제거된 파일 {len(files_to_delete)}개를 정리합니다...")
                for file_path in files_to_delete:
                    dir_path = os.path.dirname(file_path)
                    if self.file_deleter.delete(file_path):
                        delete_report.add_deleted(file_path)
                        deleted_dirs.add(dir_path)
                    else:
                        delete_report.add_failed(file_path)
            else:
                self.logger.info("정리할 파일이 없습니다.")

            # 가장 깊은 폴더부터 비어있는지 확인하고 정리
            sorted_dirs = sorted(list(deleted_dirs), key=len, reverse=True)
            for dir_path in sorted_dirs:
                try:
                    if not os.listdir(dir_path):
                        self.logger.info(f"빈 폴더 발견! 함께 정리합니다 (휴지통으로 이동): {dir_path}")
                        self.file_deleter.delete_folder(dir_path)
                except FileNotFoundError:
                    self.logger.debug(f"이미 상위 폴더가 정리되어 건너뜁니다: {dir_path}")
                except Exception as e:
                    self.logger.error(f"빈 폴더 정리 중 오류: {dir_path} - {e}")

            # 이번 작업에 대한 리포트만 요약해서 출력
            delete_report.summary(to_file=self.config_manager.get_abs_logfile())

            # 👈 2. Generate 스크립트 실행 로직 변경!
            #    .bat 파일을 직접 실행하는 방식으로 변경하여 안정성 향상
            self.is_running_script = True  # .bat 파일 실행 동안 이벤트 무시 시작

            project_root = self.config_manager.get_project_root_path()
            bat_file_path = os.path.join(project_root, "GenerateProjectFiles.bat")

            if not os.path.exists(bat_file_path):
                self.logger.error(f"GenerateProjectFiles.bat 파일을 찾을 수 없습니다: {bat_file_path}")
                # finally에서 플래그와 락을 해제하므로 여기서 바로 return 해도 안전
                return

            self.logger.info(f"'{os.path.basename(bat_file_path)}' 실행 중... (이로 인한 파일 변경은 무시됩니다)")

            # .bat 파일 실행
            proc = subprocess.Popen(
                [bat_file_path],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=True
            )

            stdout_bytes, stderr_bytes = proc.communicate(timeout=600)

            # (이하 인코딩 및 결과 출력 로직은 동일)
            # ...

            self.logger.info(f"'{os.path.basename(bat_file_path)}' 실행 완료!")

        except Exception as e:
            self.logger.error(f"예기치 않은 오류 발생: {e}", exc_info=True)
        finally:
            # 👈 3. 작업이 끝나면 플래그와 락을 반드시 해제!
            self.is_running_script = False
            self.run_lock.release()
            self.logger.info("모든 작업 완료. 다시 감시를 시작합니다. ✨")