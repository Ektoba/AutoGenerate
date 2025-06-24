import logging
import sys
import os


class AppLogger:
    def __init__(self, log_file=None, level="INFO"):
        self.logger = logging.getLogger("ProjectWatcher")
        # 메인 로거 레벨은 가장 낮은 레벨 (DEBUG)로 설정하여 모든 메시지를 수집
        self.logger.setLevel(logging.DEBUG)  # 메인 로거는 모든 레벨을 수집

        formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # 기존 핸들러 제거 (재실행 시 핸들러 중복 방지)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 콘솔 핸들러: config.json의 LogLevel (INFO)에 따라 필터링
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        ch.setLevel(getattr(logging, str(level).upper(), logging.INFO))  # 콘솔 출력 레벨
        self.logger.addHandler(ch)

        # 파일 핸들러: DEBUG 레벨 이상 모든 메시지 출력
        if log_file:
            log_dir = os.path.dirname(os.path.abspath(log_file))
            try:
                os.makedirs(log_dir, exist_ok=True)

                if os.path.exists(log_file):
                    try:
                        os.remove(log_file)
                        self.logger.info(f"[AppLogger][INFO] 기존 로그 파일 초기화: {log_file}")  # print 대신 logger.info
                        # sys.stdout.flush() # AppLogger 내부 메서드가 flush 처리
                    except Exception as e:
                        self.logger.warning(
                            f"[AppLogger][WARNING] 기존 로그 파일 초기화 실패: {log_file} / 사유: {e}")  # print 대신 logger.warning
                        # sys.stdout.flush() # AppLogger 내부 메서드가 flush 처리

                fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
                fh.setFormatter(formatter)
                fh.setLevel(logging.DEBUG)  # 파일에는 모든 DEBUG 메시지 기록
                self.logger.addHandler(fh)

                self.logger.info(f"[AppLogger][INFO] 로그 파일 핸들러 추가 성공: {log_file}")  # print 대신 logger.info
                # sys.stdout.flush() # AppLogger 내부 메서드가 flush 처리
            except Exception as e:
                self.logger.error(f"[AppLogger][CRITICAL ERROR] 로그 파일 생성 실패: {log_file} / 사유: {e}",
                                  exc_info=True)
                # sys.stdout.flush() # AppLogger 내부 메서드가 flush 처리

    # 로깅 메서드들은 이제 내부적으로 flush를 포함하도록 수정 (핸들러가 버퍼링 처리)
    def info(self, msg):
        self.logger.info(msg)
        sys.stdout.flush()  # 콘솔 핸들러 강제 flush (중요)

    def warning(self, msg):
        self.logger.warning(msg)
        sys.stdout.flush()

    def error(self, msg, exc_info=False):
        self.logger.error(msg, exc_info=exc_info)
        sys.stdout.flush()

    def debug(self, msg):
        self.logger.debug(msg)
        sys.stdout.flush()