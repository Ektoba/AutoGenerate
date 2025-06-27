# AppLogger.py
import logging
import sys
import os


class AppLogger:
    def __init__(self, log_file=None, level="INFO"):
        self.logger = logging.getLogger("ProjectWatcher")
        self.logger.setLevel(logging.DEBUG)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        self.formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setFormatter(self.formatter)
        self.console_handler.setLevel(getattr(logging, str(level).upper(), logging.INFO))
        self.logger.addHandler(self.console_handler)

        self.file_handler = None
        if log_file:
            self._add_file_handler(log_file)
        else:
            self.logger.warning("[AppLogger] 초기 로그 파일 경로가 지정되지 않았습니다.")

    def _add_file_handler(self, log_file):
        """ 파일 핸들러를 추가하는 내부 헬퍼 함수 """
        try:
            log_dir = os.path.dirname(os.path.abspath(log_file))
            os.makedirs(log_dir, exist_ok=True)

            if self.file_handler:
                self.logger.removeHandler(self.file_handler)
                self.file_handler = None

            fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            fh.setFormatter(self.formatter)
            fh.setLevel(logging.DEBUG)

            self.file_handler = fh
            self.logger.addHandler(self.file_handler)
            self.info(f"[AppLogger] 로그 파일 핸들러 추가/변경 성공: {log_file}")
        except Exception as e:
            print(f"[AppLogger][CRITICAL ERROR] 로그 파일 핸들러 생성 실패: {e}")
            self.error(f"[AppLogger] 로그 파일 핸들러 생성 실패: {e}", exc_info=True)

    def reconfigure(self, log_file=None, level="INFO"):
        """ 로거의 설정을 동적으로 재구성합니다. """
        self.info(f"로거 설정을 재구성합니다. 로그 파일: {log_file}, 레벨: {level}")

        if self.file_handler:
            self.logger.removeHandler(self.file_handler)
            self.file_handler = None

        if log_file:
            self._add_file_handler(log_file)

        self.console_handler.setLevel(getattr(logging, str(level).upper(), logging.INFO))
        self.info("콘솔 로그 레벨이 업데이트되었습니다.")

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg, exc_info=False):
        self.logger.error(msg, exc_info=exc_info)

    def debug(self, msg):
        self.logger.debug(msg)