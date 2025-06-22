# main.py
import time
import sys
import os  # os 모듈 추가 (SCRIPT_DIR 계산용)
from watchdog.observers import Observer

# 로컬 모듈 임포트 (상대 경로 임포트 사용)
from .ConfigManager import ConfigManager
from .ConfigValidator import ConfigValidator
from .ProjectFileManager import ProjectFileManager
from .EventHandler import ChangeHandler
from .AppLogger import AppLogger  # Looger.py -> AppLogger.py 이름 변경 반영
from .BackupManager import BackupManager
from .FileDeleter import FileDeleter
from .DeleteReport import DeleteReport
from .EventFilter import EventFilter


def main():
    # 스크립트 디렉토리 계산 (ConfigManager 초기화에 필요)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Config 로드 및 검증 ---
    config_manager = ConfigManager(script_dir)  # script_dir을 인자로 전달
    validator = ConfigValidator(config_manager.config)  # config_manager.config를 전달
    errors = validator.validate()
    if errors:
        print("[ERROR] 설정 오류:")
        for error in errors:
            print(f" - {error}")
        sys.stdout.flush()
        sys.exit(1)

    # --- Logger/Backup/Deleter/리포트 등 생성 ---
    # AppLogger 초기화 시 level 인자 추가 (DEBUG 레벨로 설정)
    logger = AppLogger(log_file=config_manager.get_setting("LogFile", "logs/watcher.log"),
                       level=os.getenv("LOG_LEVEL", "INFO").upper())
    backup_manager = BackupManager(backup_dir=config_manager.get_setting("BackupDir", "backup"), logger=logger)
    file_deleter = FileDeleter(backup_manager=backup_manager, logger=logger,
                               dry_run=config_manager.get_setting("DryRun", False))
    delete_report = DeleteReport()

    # --- 주요 프로젝트 파일 관리 ---
    project_file_manager = ProjectFileManager(
        config_manager=config_manager  # config_manager 인스턴스 통째로 전달
    )

    # --- 이벤트 필터/핸들러 ---
    # EventFilter도 config_manager 인스턴스 통째로 전달
    event_filter = EventFilter(config_manager=config_manager)

    # --- ChangeHandler 인스턴스 생성 ---
    handler = ChangeHandler(
        config_manager=config_manager,  # config_manager 객체 전달
        logger=logger,
        project_file_manager=project_file_manager,
        file_deleter=file_deleter,
        delete_report=delete_report,
        event_filter=event_filter
    )

    # --- Watchdog Observer 초기화 및 감시 폴더 설정 ---
    observer = Observer()

    # config_manager에서 Watchdog 감시 대상 폴더 목록 가져오기
    watch_folders_for_observer = config_manager.get_watch_folders_for_observer()

    if not watch_folders_for_observer:
        logger.error("감시할 유효한 .vcxproj 또는 .vcxproj.filters 폴더를 찾을 수 없습니다. 스크립트를 종료합니다. 😢")
        logger.error("UpdateConfig.ps1을 실행하여 config.json을 초기화하거나 관련 경로를 수동으로 설정해주세요.")
        sys.exit(1)
    else:
        for folder in watch_folders_for_observer:
            # recursive=False (해당 폴더만 감시)
            observer.schedule(handler, path=folder, recursive=False)
            logger.info(f"Watchdog 감시 시작: {folder} (재귀 아님)")

    observer.start()
    logger.info(
        f"폴더 변경 감시 중... (기본: {config_manager.get_setting('DebounceTimeMs', 300000) / 1000.0}초 / 수정: {config_manager.get_setting('DebounceTimeForModifiedMs', 100) / 1000.0}초 / 기타: {config_manager.get_setting('DebounceTimeForOtherEventsMs', 100) / 1000.0}초 지연 적용) (종료: Ctrl+C)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("폴더 감시 중지 중...")
    except Exception as e:
        logger.error(f"예기치 않은 종료: {e}", exc_info=True)  # exc_info=True로 전체 트레이스백 출력
    finally:
        observer.join()
        logger.info("폴더 감시가 종료되었습니다.")


if __name__ == "__main__":
    main()