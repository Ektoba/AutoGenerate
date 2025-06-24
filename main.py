# main.py
import os
import sys
import time
from watchdog.observers import Observer

# 로컬 모듈 임포트
import ConfigManager
import ConfigValidator
import ProjectFileManager
import EventHandler
import AppLogger
import BackupManager
import FileDeleter
import DeleteReport
import EventFilter


def main():
    # script_dir 계산 (ConfigManager에서 더 이상 직접 사용하지 않지만, 다른 곳에서 필요할 수 있으므로 유지)
    script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))

    # --- 설정 로드 및 검증 ---
    config_manager = ConfigManager.ConfigManager()

    # AppLogger 초기화 전에 ConfigManager의 임시 로거를 사용하여 로그 레벨을 가져옴
    # AppLogger 초기화 시 config_manager의 최종 로거를 사용하도록 함
    logger = AppLogger.AppLogger(log_file=config_manager.get_abs_logfile(),
                                 level=config_manager.get_setting("LogLevel", "INFO").upper())

    logger.info("모든 시스템에 메인 로거를 주입하며 초기화를 시작합니다...")

    config_manager.set_logger(logger)

    logger.info(f"로그 파일 경로: {config_manager.get_abs_logfile()}")

    validator = ConfigValidator.ConfigValidator(config_manager.config)
    errors = validator.validate()

    if errors:
        logger.error("설정 오류:")
        for error in errors:
            logger.error(f" - {error}")
        sys.exit(1)

    backup_manager = BackupManager.BackupManager(
        backup_dir=config_manager.get_abs_backup_dir(),
        logger=logger
    )
    file_deleter = FileDeleter.FileDeleter(
        backup_manager=backup_manager,
        logger=logger,
        dry_run=config_manager.get_setting("DryRun", False)
    )
    delete_report = DeleteReport.DeleteReport(logger=logger)  # logger 인자 추가!

    project_file_manager = ProjectFileManager.ProjectFileManager(
        config_manager=config_manager,
        logger=logger  # logger 인자 추가!
    )

    event_filter = EventFilter.EventFilter(config_manager=config_manager)

    handler = EventHandler.ChangeHandler(
        config_manager=config_manager,
        logger=logger,
        project_file_manager=project_file_manager,
        file_deleter=file_deleter,
        delete_report=delete_report,
        event_filter=event_filter
    )

    # --- 감시 폴더 설정 ---
    observer = Observer()
    watch_folders_for_observer = config_manager.get_abs_watch_paths()

    if not watch_folders_for_observer:
        logger.error("감시할 유효한 .vcxproj 또는 .vcxproj.filters 폴더를 찾을 수 없습니다. 스크립트를 종료합니다. 😢")
        logger.error("UpdateConfig.ps1을 실행하여 config.json을 초기화하거나 관련 경로를 수동으로 설정해주세요.")
        sys.exit(1)
    else:
        for folder in watch_folders_for_observer:
            observer.schedule(handler, path=folder, recursive=True)
            logger.info(f"Watchdog 감시 시작: {folder} (재귀 포함)")

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
        logger.error(f"예기치 않은 종료: {e}", exc_info=True)
    finally:
        observer.join()
        logger.info("폴더 감시가 종료되었습니다.")


if __name__ == "__main__":
    main()