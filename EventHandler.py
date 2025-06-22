# EventHandler.py
from watchdog.events import FileSystemEventHandler
import threading
import time
import os  # os 모듈 추가
import sys  # sys 모듈 추가
import collections  # collections 모듈 추가


# ChangeHandler 클래스 정의
class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config_manager, logger, project_file_manager, file_deleter, delete_report, event_filter):
        self.config_manager = config_manager  # config_manager 인스턴스 받음
        self.logger = logger
        self.project_file_manager = project_file_manager
        self.file_deleter = file_deleter
        self.delete_report = delete_report
        self.event_filter = event_filter  # EventFilter 인스턴스 받음
        self.debounce_lock = threading.Lock()
        self.timer = None

        # config_manager에서 필요한 경로와 지연 시간 설정 가져오기
        self.main_vcxproj_path, self.main_vcxproj_filters_path = self.config_manager.get_main_vcxproj_paths()
        self.normalized_main_vcxproj_path, self.normalized_main_vcxproj_filters_path = self.config_manager.get_normalized_main_vcxproj_paths()

        self.debounce_time_for_modified_ms = self.config_manager.get_setting("DebounceTimeForModifiedMs", 100)
        self.debounce_time_for_other_events_ms = self.config_manager.get_setting("DebounceTimeForOtherEventsMs", 100)
        self.run_script_name = self.config_manager.get_setting("GenerateScript", "GenerateProjectFile.ps1")
        self.script_dir = self.config_manager.script_dir  # config_manager에서 스크립트 디렉토리 가져오기

    def on_any_event(self, event):
        # 모든 Raw 이벤트를 로깅하여 감지 여부 확인 (디버깅용)
        self.logger.debug(f"Raw Event Detected: {event.event_type} - {event.src_path}")

        current_time = time.time()

        # 유효한 .vcxproj/.filters 경로가 없으면 처리 중단 (config_manager에서 이미 체크하지만 혹시 모를 상황 대비)
        if not (self.normalized_main_vcxproj_path and os.path.exists(self.main_vcxproj_path)) and \
                not (self.normalized_main_vcxproj_filters_path and os.path.exists(self.main_vcxproj_filters_path)):
            self.logger.error(f"config.json에 유효한 메인 .vcxproj 또는 .vcxproj.filters 경로가 없습니다. 이벤트 처리를 건너뜝니다.")
            return

        # 정규화된 이벤트 경로
        normalized_event_src_path = os.path.abspath(event.src_path).lower()

        # --- 핵심 필터링 로직: 관심 파일 (메인 .vcxproj 또는 .filters)만 통과 ---
        is_main_project_file_event = False
        if normalized_event_src_path == self.normalized_main_vcxproj_path:
            is_main_project_file_event = True
            self.logger.debug(f"감지된 파일: 메인 .vcxproj")
        elif normalized_event_src_path == self.normalized_main_vcxproj_filters_path:
            is_main_project_file_event = True
            self.logger.debug(f"감지된 파일: 메인 .vcxproj.filters")

        # 1. 관심 파일이 아니라면 바로 무시 (폴더 이벤트, 다른 파일 타입 모두 여기서 걸러짐)
        if not is_main_project_file_event:
            self.logger.debug(f"무시된 이벤트 (관심 .vcxproj/.filters 파일 아님): {event.src_path}")
            return

        # 2. 이벤트 타입 필터링 (modified, created, deleted, moved, renamed만 허용)
        # .vcxproj/.filters 파일에 대한 이벤트는 이 타입들 중 하나여야 함
        if event.event_type not in ['modified', 'created', 'deleted', 'moved', 'renamed']:
            self.logger.debug(f"무시된 이벤트 타입: {event.event_type} - {event.src_path}")
            return

        # 3. 무시할 확장자/이름 패턴 강화 (특히 ~AutoRecover 같은 임시 파일)
        # EventFilter에서 이미 처리하므로, 여기서는 해당 함수 호출만
        if self.event_filter.ignore_by_pattern(event):  # EventFilter 내에서 패턴 로드
            self.logger.debug(f"무시된 패턴: {event.src_path}")
            return

        # 4. 중복 이벤트 필터링 (EventFilter에서 처리)
        if self.event_filter.is_duplicate(event):  # EventFilter 내에서 타입과 경로를 받도록 변경
            self.logger.debug(f"중복 이벤트: {event.src_path}")
            return

        # 모든 필터를 통과한 최종 이벤트만 INFO 레벨로 출력
        self.logger.info(f"이벤트 감지: {event.src_path} ({event.event_type})")

        # .vcxproj 또는 .vcxproj.filters 파일 변경 감지 시 항상 즉시 처리 (0.1초)
        delay_ms = self.debounce_time_for_other_events_ms
        delay_reason = f"주요 프로젝트/필터 파일 변경 ({delay_ms / 1000.0}초 지연)"

        with self.debounce_lock:
            if self.timer:  # 기존 타이머가 있으면 취소
                self.timer.cancel()

            # 새 타이머 시작
            self.logger.info(f"프로젝트 갱신 예약됨: {delay_reason}. 추가 변경 감지 시 재예약.")
            self.timer = threading.Timer(delay_ms / 1000.0, self.run_update_script)
            self.timer.start()

    def run_update_script(self):
        """
        예약된 시간이 되면 실행되는 실제 프로젝트 갱신 및 파일 삭제 로직입니다.
        """
        with self.debounce_lock:  # 락을 걸어서 중복 실행 방지
            # 최종 확인: 예약된 시간 동안 추가 변경이 없었는지 재확인
            # 현재 이벤트 핸들러에서는 Timer 시작 시점의 current_delay_ms를 사용해야 함
            # debounce_lock 때문에 여기서는 last_event_time과 current_delay_ms를 사용하지 않음
            # Timer가 이미 지연 시간을 기다린 후에 호출되기 때문
            self.timer = None  # 타이머 초기화

            self.logger.info(f"VS 프로젝트 갱신/파일 청소 시작!")

            # 1. 참조되지 않는 C++ 파일 자동 삭제 기능 실행
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

            # 2. GenerateProjectFile.ps1 실행 (UnrealBuildTool 호출)
            self.logger.info("GenerateProjectFile.ps1 스크립트 실행 중...")
            try:
                run_file_full_path = os.path.join(self.script_dir, self.run_script_name)

                if not os.path.exists(run_file_full_path):
                    self.logger.error(f"실행할 스크립트를 찾을 수 없습니다: {run_file_full_path}")
                    return

                try_encodings = ['utf-8', locale.getdefaultlocale()[1], 'latin-1']

                # subprocess.Popen을 사용하여 출력을 바이트 스트림으로 받고 수동 디코딩
                proc = None
                if self.run_script_name.lower().endswith(".ps1"):
                    proc = subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", run_file_full_path],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=False,
                                            creationflags=subprocess.CREATE_NO_WINDOW
                                            )
                else:  # .bat 파일 등
                    proc = subprocess.Popen([run_file_full_path], shell=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=False,
                                            creationflags=subprocess.CREATE_NO_WINDOW
                                            )

                stdout_bytes, stderr_bytes = proc.communicate(timeout=600)  # 10분 타임아웃

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
                        continue  # 다음 인코딩 시도

                if not chosen_encoding:  # 모든 인코딩 실패 시 최종 fallback
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
                self.logger.error(f"스크립트 또는 PowerShell/dotnet 실행 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
            except Exception as e:
                self.logger.error(f"예기치 않은 오류 발생: {e}")