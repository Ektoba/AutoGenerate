# main.py
import os
import sys
from watchdog.observers import Observer

# 로컬 모듈 임포트 (상대 경로 임포트 사용)
from .config_manager import ConfigManager
from .event_handler import ChangeHandler # ChangeHandler 클래스 임포트
from .project_file_manager import ProjectFileManager # ProjectFileManager 클래스 임포트

# 스크립트가 위치한 디렉토리 (AutoGenerate 폴더)를 기준으로 작업
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. ConfigManager 초기화 (config.json 로드)
config_manager = ConfigManager(SCRIPT_DIR)

# 2. ProjectFileManager 초기화 (config_manager 의존)
project_file_manager = ProjectFileManager(config_manager)

# Watchdog Observer 초기화
observer = Observer()

# Watchdog 감시 대상 경로 설정 (config_manager에서 가져옴)
watch_folders_for_observer = config_manager.get_watch_folders_for_observer()

if not watch_folders_for_observer:
    print("[ERROR] 감시할 유효한 .vcxproj 또는 .vcxproj.filters 폴더를 찾을 수 없습니다. 스크립트를 종료합니다. 😢")
    print("UpdateConfig.ps1을 실행하여 config.json을 초기화하거나 관련 경로를 수동으로 설정해주세요.")
    sys.stdout.flush()
    sys.exit(1)
else:
    for folder in watch_folders_for_observer:
        # ChangeHandler 인스턴스 생성 시 config_manager와 project_file_manager 전달
        observer.schedule(ChangeHandler(config_manager, project_file_manager), folder, recursive=False)
        print(f"[INFO] Watchdog 감시 시작: {folder} (재귀 아님)")
        sys.stdout.flush()

observer.start()

# INFO 메시지에 사용할 설정값들을 config_manager에서 직접 가져옴
default_debounce_time_display = config_manager.get_setting("DebounceTimeMs", 300000)
debounce_time_for_modified_ms = config_manager.get_setting("DebounceTimeForModifiedMs", 100)
debounce_time_for_other_events_ms = config_manager.get_setting("DebounceTimeForOtherEventsMs", 100)

print(f"[INFO] 폴더 변경 감시 중... (기본: {default_debounce_time_display / 1000.0}초 / 수정: {debounce_time_for_modified_ms / 1000.0}초 / 기타: {debounce_time_for_other_events_ms / 1000.0}초 지연 적용) (종료: Ctrl+C)")
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