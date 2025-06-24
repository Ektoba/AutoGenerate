# EventHandler.py
from watchdog.events import FileSystemEventHandler
import threading
import time
import os
import sys
import collections
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
        self.main_vcxproj_path_raw, self.main_vcxproj_filters_path_raw = self.config_manager.get_main_vcxproj_paths()
        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()
        self.debounce_time_for_modified_ms = self.config_manager.get_setting("DebounceTimeForModifiedMs", 100)
        self.debounce_time_for_other_events_ms = self.config_manager.get_setting("DebounceTimeForOtherEventsMs", 100)
        self.run_script_name = self.config_manager.get_setting("GenerateScript", "GenerateProjectFile.ps1")
        self.script_dir = self.config_manager.base_dir
        self.is_running_script = False # 👈 스크립트 실행 중인지 상태를 저장할 변수 추가!
        self.run_lock = threading.Lock() # 👈 여러 이벤트가 동시에 처리되는 것을 막기 위한 잠금장치


    def on_any_event(self, event):
        # 모든 이벤트를 무조건 기록 (디버깅 목적으로 유지)
        self.logger.debug(
            f"[RAW EVENT HANDLER] Type: {event.event_type}, Src: {event.src_path}, IsDir: {event.is_directory}")

        current_time = time.time()

        # 유효한 .vcxproj/.filters 경로가 없으면 처리 중단 (config_manager에서 이미 체크하지만 혹시 모를 상황 대비)
        if not (self.normalized_main_vcxproj_path and os.path.exists(self.main_vcxproj_path_raw)) and \
                not (self.normalized_main_vcxproj_filters_path and os.path.exists(self.main_vcxproj_filters_path_raw)):
            self.logger.error(f"config.json에 유효한 메인 .vcxproj 또는 .vcxproj.filters 경로가 없습니다. 이벤트 처리를 건너뜝니다.")
            return

        # 정규화된 이벤트 경로 (이후 필터링에서 사용)
        normalized_event_src_path = os.path.abspath(event.src_path).lower()

        # --- 핵심 필터링 로직 활성화! (주석 해제!) ---
        # 1. 관심 파일 (메인 .vcxproj 또는 .filters)만 통과
        is_main_project_file_event = False
        if normalized_event_src_path == self.normalized_main_vcxproj_path:
            is_main_project_file_event = True
            self.logger.debug(f"감지된 파일: 메인 .vcxproj")
        elif normalized_event_src_path == self.normalized_main_vcxproj_filters_path:
            is_main_project_file_event = True
            self.logger.debug(f"감지된 파일: 메인 .vcxproj.filters")

        if not is_main_project_file_event:
            self.logger.debug(f"무시된 이벤트 (관심 .vcxproj/.filters 파일 아님): {event.src_path}")
            return

        # 2. 이벤트 타입 필터링 (EventFilter에서 처리)
        if not self.event_filter.is_valid_event_type(event.event_type):
            self.logger.debug(f"무시된 이벤트 타입: {event.event_type} - {event.src_path}")
            return

        # 3. 무시할 확장자/이름 패턴 강화 (EventFilter에서 처리)
        if self.event_filter.ignore_by_pattern(event):
            self.logger.debug(f"무시된 패턴: {event.src_path}")
            return

        # 4. 중복 이벤트 필터링 (EventFilter에서 처리)
        if self.event_filter.is_duplicate(event):
            self.logger.debug(f"중복 이벤트: {event.src_path}")
            return
        # --- 필터링 로직 활성화 끝 ---

        self.logger.info(f"이벤트 감지: {event.src_path} ({event.event_type})")  # 필터링 활성화 후 INFO 레벨로 출력

        delay_ms = self.debounce_time_for_other_events_ms
        delay_reason = f"주요 프로젝트/필터 파일 변경 ({delay_ms / 1000.0}초 지연)"

        # 스크립트가 실행 중일 때는 모든 이벤트를 무시!
        if self.is_running_script:
            self.logger.debug(f"스크립트 실행 중... 이벤트 무시: {event.src_path}")
            return

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
            time.sleep(1) # 1초 정도 대기해서 Visual Studio가 파일을 완전히 저장할 시간을 주는 거야!

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
            self.delete_report.summary(to_file=self.config_manager.get_abs_logfile())

            self.logger.info("GenerateProjectFile.ps1 스크립트 실행 중...")

            run_file_full_path = os.path.join(self.script_dir, self.config_manager.get_setting("GenerateScript",
                                                                                               "GenerateProjectFile.ps1"))  # generateScript를 config에서 가져오도록 수정

            if not os.path.exists(run_file_full_path):
                self.logger.error(f"실행할 스크립트를 찾을 수 없습니다: {run_file_full_path}")
                return

            try_encodings = ['utf-8', locale.getdefaultlocale()[1], 'latin-1']

            unreal_engine_root = self.config_manager.get_setting("UnrealEngineRootPath", "")
            project_root = self.config_manager.get_project_root_path()
            main_uproject_path = os.path.join(project_root, self.config_manager.get_setting("MainUprojectPath", ""))

            powershell_args = [
                "powershell",
                "-ExecutionPolicy", "Bypass",
                "-File", run_file_full_path,
                "-UnrealEngineRoot", unreal_engine_root,
                "-ProjectRoot", project_root,
                "-UprojectPath", main_uproject_path
            ]
            self.logger.debug(f"Powershell Command: {' '.join(powershell_args)}")

            proc = None
            if self.run_script_name.lower().endswith(".ps1"):
                proc = subprocess.Popen(powershell_args,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=False,
                                        creationflags=subprocess.CREATE_NO_WINDOW
                                        )
            else:
                proc = subprocess.Popen([run_file_full_path], shell=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=False,
                                        creationflags=subprocess.CREATE_NO_WINDOW
                                        )

            stdout_bytes, stderr_bytes = proc.communicate(timeout=600)

            stdout_decoded = ""
            stderr_decoded = ""
            chosen_encoding = "unknown"

            for enc in try_encodings:
                try:
                    stdout_decoded = stdout_bytes.decode(enc, errors='replace')
                    stderr_decoded = stderr_bytes.decode(enc, errors='replace')
                    chosen_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue

            if not chosen_encoding:
                stdout_decoded = stdout_bytes.decode('latin-1', errors='replace')
                stderr_decoded = stderr_bytes.decode('latin-1', errors='replace')
                chosen_encoding = 'latin-1 (fallback)'

            if proc.returncode != 0:
                self.logger.error(f"스크립트 실행 실패 (종료 코드: {proc.returncode}) (인코딩: {chosen_encoding})")
                self.logger.error(f"STDOUT:\n{stdout_decoded}")
                self.logger.error(f"STDERR:\n{stderr_decoded}")
            else:
                self.logger.info(f"스크립트 실행 완료! (인코딩: {chosen_encoding})")
                if stdout_decoded:
                    self.logger.info(f"STDOUT:\n{stdout_decoded}")
                if stderr_decoded:
                    self.logger.info(f"STDERR:\n{stderr_decoded}")

        except subprocess.TimeoutExpired:
            self.logger.error(f"스크립트 실행 시간 초과 (10분). 강제 종료합니다.")
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
            self.logger.error(f"STDOUT (partial):\n{stdout_bytes.decode('latin-1', errors='replace')}")
            self.logger.error(f"STDERR (partial):\n{stderr_bytes.decode('latin-1', errors='replace')}")
        except FileNotFoundError:
            self.logger.error(f"실행할 스크립트 또는 PowerShell/dotnet 실행 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        except Exception as e:
            self.logger.error(f"예기치 않은 오류 발생: {e}", exc_info=True)
        finally:
            self.is_running_script = False  # 👈 스크립트 실행 끝! 플래그 내리기!
            self.run_lock.release()  # 👈 잠금 해제!
            self.logger.info("모든 작업 완료. 다시 감시를 시작합니다. ✨")