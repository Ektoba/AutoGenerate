import os
import sys
import time
from watchdog.observers import Observer

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
    # --- 설정 로드 및 검증 ---
    config_manager = ConfigManager.ConfigManager()
    validator = ConfigValidator.ConfigValidator(config_manager.config)
    logger = AppLogger.AppLogger(log_file=config_manager.get_abs_logfile())
    backup_manager = BackupManager.BackupManager(
        backup_dir=config_manager.get_abs_backup_dir(),
        logger=logger
    )
    file_deleter = FileDeleter.FileDeleter(
        backup_manager=backup_manager,
        logger=logger,
        dry_run=config_manager.get_setting("DryRun", False)
    )
    delete_report = DeleteReport.DeleteReport()
    project_file_manager = ProjectFileManager.ProjectFileManager(
        main_vcxproj=config_manager.get_abs_main_vcxproj(),
        main_vcxproj_filters=config_manager.get_abs_main_vcxproj_filters()
    )
    # EventFilter는 감시 대상 파일 리스트를 넣어도 되고, WatchPaths 기준만으로도 동작 가능
    event_filter = EventFilter.EventFilter(config_manager.get_setting("WatchPaths", []))

    handler = EventHandler.ChangeHandler(
        config=config_manager,
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
        logger.error("감시할 유효한 폴더를 찾을 수 없습니다. 스크립트를 종료합니다. 😢")
        logger.error("UpdateConfig.ps1을 실행하여 config.json을 초기화하거나 관련 경로를 수동으로 설정해주세요.")
        sys.exit(1)
    else:
        for folder in watch_folders_for_observer:
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
        logger.error(f"예기치 않은 종료: {e}", exc_info=True)
    finally:
        observer.join()
        logger.info("폴더 감시가 종료되었습니다.")

if __name__ == "__main__":
    main()
