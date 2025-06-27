# main.py
import sys
import os
import time
from watchdog.observers import Observer
import threading

# 모든 모듈 임포트
import AppLogger
import ConfigManager
import SetupManager
import ProjectFileManager
import FileDeleter
import EventFilter
import EventHandler
import Orchestrator
import BackupManager

class PatrolThread(threading.Thread):
    logger: object

    def __init__(self, orchestrator, patrol_interval_minutes, logger):
        super().__init__()
        self.orchestrator = orchestrator
        self.patrol_interval_seconds = patrol_interval_minutes * 60
        self.logger = logger
        self._stop_event = threading.Event()

    def run(self):
        if self.patrol_interval_seconds <= 0:
            self.logger.info("정기 순찰 기능이 비활성화되었습니다. (PatrolIntervalMinutes가 0 이하)")
            return

        self.logger.info(
            f"정기 순찰 스레드 시작. 매 {self.patrol_interval_seconds}초 ({self.patrol_interval_seconds / 60}분)마다 프로젝트 상태를 확인합니다.")
        while not self._stop_event.is_set():
            stopped = self._stop_event.wait(self.patrol_interval_seconds)
            if stopped:
                break

            self.orchestrator.patrol_for_changes()

        self.logger.info("정기 순찰 스레드 종료.")

    def stop(self):
        self._stop_event.set()


def main():
    # 1. 로거 및 설정 마법사 실행 (config.json 생성 보장)
    base_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))

    # 임시 로그 경로를 .txt 확장자로 변경
    temp_log_path = os.path.join(base_dir, 'Logs/Watcher_init.txt')
    logger = AppLogger.AppLogger(log_file=temp_log_path, level="INFO")

    setup_manager = SetupManager.SetupManager(logger=logger)
    setup_manager.run_setup_if_needed()

    # 2. 핵심 관리자들 생성
    config_manager = ConfigManager.ConfigManager()
    config_manager.set_logger(logger)

    # 이제 진짜 설정값을 읽어서 로거를 재설정
    # 로그 파일 경로도 .txt 확장자로 변경
    logger.reconfigure(log_file=config_manager.get_abs_logfile().replace('.log', '.txt'),
                       level=config_manager.get_setting("LogLevel", "INFO").upper())

    # 3. 의존성 객체들 생성
    backup_manager = BackupManager.BackupManager(config_manager.get_abs_backup_dir(), logger)

    file_deleter = FileDeleter.FileDeleter(
        config_manager.get_setting("DryRun", False),
        backup_manager,
        logger
    )

    project_file_manager = ProjectFileManager.ProjectFileManager(config_manager, logger)
    event_filter = EventFilter.EventFilter(config_manager)

    # 4. 실제 작업을 할 Orchestrator 생성
    orchestrator = Orchestrator.UpdateOrchestrator(config_manager, logger, project_file_manager, file_deleter)

    # 5. 이벤트를 감지할 EventHandler 생성 (Orchestrator 전달)
    handler = EventHandler.ChangeHandler(config_manager, logger, event_filter, orchestrator)

    # 6. Watchdog 감시 시작
    observer = Observer()
    watch_paths = config_manager.get_abs_watch_paths()
    if not watch_paths:
        logger.error("감시할 경로가 설정되지 않았습니다. config.json의 WatchPaths를 확인해주세요.")
        return

    for path in watch_paths:
        if os.path.exists(path):
            observer.schedule(handler, path, recursive=True)
            logger.info(f"Watchdog 감시 시작: {path} (재귀 포함)")
        else:
            logger.warning(f"감시할 경로를 찾을 수 없습니다: {path}")

    if not observer.emitters:
        logger.error("감시할 폴더가 하나도 없습니다. 프로그램을 종료합니다.")
        return

    observer.start()
    logger.info(f"폴더 변경 감시 중... (딜레이: {config_manager.get_setting('DebounceTimeMs', 1500) / 1000.0}초) (종료: Ctrl+C)")

    # 정기 순찰 스레드 시작
    patrol_interval = config_manager.get_setting("PatrolIntervalMinutes", 0.0)  # 0.0으로 명시하여 float형 기본값 보장
    patrol_thread = PatrolThread(orchestrator, patrol_interval, logger)
    patrol_thread.start()

    # 메인 루프
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("사용자 요청으로 종료합니다...")
    finally:
        observer.stop()
        observer.join()
        patrol_thread.stop()
        patrol_thread.join()
        logger.info("폴더 감시가 완전히 종료되었습니다.")


if __name__ == "__main__":
    main()