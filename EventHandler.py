# event_handler.py
import os
import threading
import time
import subprocess
import locale
import sys
import collections
from watchdog.events import FileSystemEventHandler


class ChangeHandler(FileSystemEventHandler):
    """
    Watchdog 이벤트를 처리하고, 필터링하며, 프로젝트 갱신을 트리거하는 핸들러입니다.
    """

    def __init__(self, config_manager, project_file_manager):
        super().__init__()
        self.config_manager = config_manager
        self.project_file_manager = project_file_manager

        self.timer = None
        self.last_event_time = 0
        self.debounce_lock = threading.Lock()
        self.recent_events = collections.deque(maxlen=10)  # 최근 10개 이벤트 저장 (중복 필터링용)

        # config.json에서 필요한 경로와 지연 시간 설정 가져오기
        self.main_vcxproj_path, self.main_vcxproj_filters_path = self.config_manager.get_main_vcxproj_paths()
        self.debounce_time_for_modified_ms = self.config_manager.get_setting("DebounceTimeForModifiedMs", 100)
        self.debounce_time_for_other_events_ms = self.config_manager.get_setting("DebounceTimeForOtherEventsMs", 100)
        self.run_script_name = self.config_manager.get_setting("GenerateScript", "GenerateProjectFile.ps1")
        self.script_dir = self.config_manager.script_dir  # config_manager에서 스크립트 디렉토리 가져오기

    def on_any_event(self, event):
        # 모든 Raw 이벤트를 로깅하여 감지 여부 확인 (디버깅용)
        print(f"[DEBUG] Raw Event Detected: {event.event_type} - {event.src_path}")
        sys.stdout.flush()

        current_time = time.time()

        # 유효한 .vcxproj/.filters 경로가 없으면 처리 중단 (config_manager에서 이미 체크하지만 혹시 모를 상황 대비)
        if not (self.main_vcxproj_path and os.path.exists(self.config_manager.main_vcxproj_path_raw)) and \
                not (self.main_vcxproj_filters_path and os.path.exists(
                    self.config_manager.main_vcxproj_filters_path_raw)):
            print(f"[ERROR] config.json에 유효한 메인 .vcxproj 또는 .vcxproj.filters 경로가 없습니다. 이벤트 처리를 건너뜝니다.")
            sys.stdout.flush()
            return

        # 정규화된 이벤트 경로
        normalized_event_src_path = os.path.abspath(event.src_path).lower()

        # 1차 필터링: 이벤트 타입 (modified, created, deleted, moved, renamed만 허용)
        if event.event_type not in ['modified', 'created', 'deleted', 'moved', 'renamed']:
            print(f"[DEBUG] 무시된 이벤트 타입: {event.event_type} - {event.src_path}")
            sys.stdout.flush()
            return

        # 2차 필터링: 무시할 확장자/이름 패턴 강화 (특히 ~AutoRecover 같은 임시 파일)
        ignored_name_patterns = ['.obj', '.pdb', '.tmp', '.user', '.log', '.ilk', '.ipch', '.sdf', '.vs', '.VC.opendb',
                                 '.suo', '.ncb', '.bak', '~', '.swp', '.lock', '.autocover',
                                 '.asset']  # .asset도 추가 (WatchPaths에 Source/Plugins 없으니 이제 더 넓게 가능)
        event_file_name_lower = os.path.basename(event.src_path).lower()
        if any(pattern in event_file_name_lower for pattern in ignored_name_patterns):
            print(f"[DEBUG] 무시된 파일 (이름 패턴 일치): {event.src_path}")
            sys.stdout.flush()
            return

        normalized_path_for_ignored = os.path.abspath(event.src_path).lower().replace(os.sep, '/')
        ignored_dirs = ['/intermediate/', '/saved/', '/binaries/', '/build/', '/deriveddata/', '/staging/',
                        '/unrealbuildtool/']
        if any(ignored_dir in normalized_path_for_ignored for ignored_dir in ignored_dirs):
            print(f"[DEBUG] 무시된 디렉토리: {event.src_path}")
            sys.stdout.flush()
            return

        # --- 3차 필터링 (가장 중요): 관심 파일 (메인 .vcxproj 또는 .filters)만 통과 ---
        is_main_project_file_event = False
        if normalized_event_src_path == self.main_vcxproj_path:
            is_main_project_file_event = True
            print(f"[DEBUG] 감지된 파일: 메인 .vcxproj")
        elif normalized_event_src_path == self.main_vcxproj_filters_path:
            is_main_project_file_event = True
            print(f"[DEBUG] 감지된 파일: 메인 .vcxproj.filters")

        # 이제 파일/폴더 여부 os.path.isfile/isdir 검사 없이, 오직 is_main_project_file_event로만 판단
        if not is_main_project_file_event:
            print(f"[DEBUG] 무시된 이벤트 (관심 .vcxproj/.filters 파일 아님): {event.src_path}")
            sys.stdout.flush()
            return

        # 중복 이벤트 필터링 (이전과 동일)
        event_key = (event.event_type, event.src_path)
        for timestamp, key in list(self.recent_events):
            if current_time - timestamp > 0.1:
                self.recent_events.popleft()
            else:
                if key == event_key:
                    print(f"[DEBUG] 중복 이벤트 필터링 (recent_events): {event.src_path} ({event.event_type})")
                    sys.stdout.flush()
                    return
        self.recent_events.append((current_time, event_key))

        # 모든 필터를 통과한 최종 이벤트만 INFO 레벨로 출력
        print(f"[INFO] 변경 감지됨: {event.src_path} (이벤트 타입: {event.event_type})")
        sys.stdout.flush()

        # .vcxproj 또는 .vcxproj.filters 파일 변경 감지 시 항상 즉시 처리 (0.1초)
        delay_ms = self.debounce_time_for_other_events_ms
        delay_reason = f"주요 프로젝트/필터 파일 변경 ({delay_ms / 1000.0}초 지연)"

        with self.debounce_lock:
            if self.timer is not None:
                self.timer.cancel()

            self.last_event_time = current_time
            self.current_delay_ms = delay_ms

            print(f"[INFO] 프로젝트 갱신 예약됨: {delay_reason}. 추가 변경 감지 시 재예약.")
            sys.stdout.flush()
            self.timer = threading.Timer(delay_ms / 1000.0, self.run_update_script)
            self.timer.start()

    def run_update_script(self):
        """
        예약된 시간이 되면 실행되는 실제 프로젝트 갱신 및 파일 삭제 로직입니다.
        """
        with self.debounce_lock:  # 락을 걸어서 중복 실행 방지
            # 최종 확인: 예약된 시간 동안 추가 변경이 없었는지 재확인
            if (time.time() - self.last_event_time) * 1000 < self.current_delay_ms:
                return

            self.timer = None  # 타이머 초기화

            print(f"[INFO] 예약된 지연 시간 ({self.current_delay_ms / 1000.0}초) 만료. VS 프로젝트 갱신 시작!")
            sys.stdout.flush()

            # 1. 참조되지 않는 C++ 파일 자동 삭제 기능 실행
            self.project_file_manager.delete_unreferenced_cpp_files()

            # 2. GenerateProjectFile.ps1 실행 (UnrealBuildTool 호출)
            try:
                run_file_full_path = os.path.join(self.script_dir, self.run_script_name)

                if not os.path.exists(run_file_full_path):
                    print(f"[ERROR] 실행할 스크립트를 찾을 수 없습니다: {run_file_full_path}")
                    sys.stdout.flush()
                    return

                try_encodings = ['utf-8', locale.getdefaultlocale()[1], 'latin-1']
                chosen_encoding = None

                try:
                    for enc in try_encodings:
                        try:
                            if self.run_script_name.lower().endswith(".ps1"):
                                proc = subprocess.Popen(
                                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", run_file_full_path],
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

                            for decode_enc in try_encodings:
                                try:
                                    stdout_decoded = stdout_bytes.decode(decode_enc, errors='replace')
                                    stderr_decoded = stderr_bytes.decode(decode_enc, errors='replace')
                                    chosen_encoding = decode_enc
                                    break
                                except UnicodeDecodeError:
                                    continue

                            if not chosen_encoding:  # 모든 인코딩 실패 시 최종 fallback
                                stdout_decoded = stdout_bytes.decode('latin-1', errors='replace')
                                stderr_decoded = stderr_bytes.decode('latin-1', errors='replace')
                                chosen_encoding = 'latin-1 (fallback)'

                            if proc.returncode != 0:
                                print(f"[ERROR] 스크립트 실행 실패 (종료 코드: {proc.returncode}) (인코딩: {chosen_encoding})")
                                print(f"[STDOUT]\n{stdout_decoded}")
                                print(f"[STDERR]\n{stderr_decoded}")
                            else:
                                print(f"[SUCCESS] 스크립트 실행 완료! (인코딩: {chosen_encoding})")
                                if stdout_decoded:
                                    print(f"[STDOUT]\n{stdout_decoded}")
                                if stderr_decoded:
                                    print(f"[STDERR]\n{stderr_decoded}")
                            sys.stdout.flush()
                            break  # 성공적으로 실행 및 디코딩했으니 루프 종료

                        except UnicodeDecodeError:
                            print(f"[WARNING] {enc} 인코딩으로 실행 결과 읽기 실패, 다음 인코딩 시도...")
                            sys.stdout.flush()
                            continue
                        except subprocess.TimeoutExpired:
                            print(f"[ERROR] 스크ript 실행 시간 초과 (10분). 강제 종료합니다.")  # 오타 수정
                            proc.kill()
                            stdout_bytes, stderr_bytes = proc.communicate()
                            print(f"[STDOUT (partial)]\n{stdout_bytes.decode('latin-1', errors='replace')}")
                            print(f"[STDERR (partial)]\n{stderr_bytes.decode('latin-1', errors='replace')}")
                            sys.stdout.flush()
                            break
                        except FileNotFoundError:
                            print(f"[ERROR] 실행 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
                            sys.stdout.flush()
                            raise
                        except Exception as inner_e:
                            print(f"[ERROR] 스크립트 실행 중 예기치 않은 내부 오류 발생: {inner_e}")
                            sys.stdout.flush()
                            raise

                except Exception as final_e:
                    print(f"[CRITICAL ERROR] run_update_script 실행 중 치명적인 오류 발생: {final_e}")
                    sys.stdout.flush()

            except FileNotFoundError:
                print(f"[ERROR] 스크립트 또는 PowerShell/dotnet 실행 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
                sys.stdout.flush()
            except Exception as e:
                print(f"[ERROR] 예기치 않은 오류 발생: {e}")
                sys.stdout.flush()


# --- 메인 스크립트 실행 부분 ---
if __name__ == "__main__":
    # ConfigManager 초기화
    config_manager = ConfigManager(SCRIPT_DIR)

    # ProjectFileManager 초기화 (config_manager 의존)
    project_file_manager = ProjectFileManager(config_manager)

    observer = Observer()

    # Watchdog 감시 대상 경로 설정 (.vcxproj와 .filters 파일이 있는 폴더 감시)
    watch_folders_for_observer = config_manager.get_watch_folders_for_observer()

    if not watch_folders_for_observer:
        print("[ERROR] 감시할 유효한 .vcxproj 또는 .vcxproj.filters 폴더를 찾을 수 없습니다. 스크립트를 종료합니다. 😢")
        print("UpdateConfig.ps1을 실행하여 config.json을 초기화하거나 관련 경로를 수동으로 설정해주세요.")
        sys.stdout.flush()
        sys.exit(1)
    else:
        for folder in watch_folders_for_observer:
            observer.schedule(ChangeHandler(config_manager, project_file_manager), folder,
                              recursive=False)  # recursive=False
            print(f"[INFO] Watchdog 감시 시작: {folder} (재귀 아님)")
            sys.stdout.flush()

    observer.start()
    print(
        f"[INFO] 폴더 변경 감시 중... (기본: {DEFAULT_DEBOUNCE_TIME_MS_DISPLAY / 1000.0}초 / 수정: {DEBOUNCE_TIME_FOR_MODIFIED_MS / 1000.0}초 / 기타: {DEBOUNCE_TIME_FOR_OTHER_EVENTS_MS / 1000.0}초 지연 적용) (종료: Ctrl+C)")
    sys.stdout.flush()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("[INFO] 폴더 감시 중지 중...")
        sys.stdout.flush()
    except Exception as e:
        print(f"[CRITICAL ERROR] 예기치 않은 종료: {e}")
        sys.stdout.flush()
    finally:
        observer.join()
        print("[INFO] 폴더 감시가 종료되었습니다.")
        sys.stdout.flush()