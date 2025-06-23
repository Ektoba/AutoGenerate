import logging
import sys
import os

class AppLogger:
    def __init__(self, log_file=None, level="INFO"):
        self.logger = logging.getLogger("ProjectWatcher")
        self.logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # 콘솔 핸들러 중복 추가 방지
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
        # 파일 핸들러
        if log_file:
            log_dir = os.path.dirname(os.path.abspath(log_file))
            try:
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == os.path.abspath(log_file)
                           for h in self.logger.handlers):
                    fh = logging.FileHandler(log_file, encoding='utf-8')
                    fh.setFormatter(formatter)
                    self.logger.addHandler(fh)
            except Exception as e:
                print(f"[AppLogger][경고] 로그 파일 생성 실패: {log_file} / 사유: {e}")

    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)
