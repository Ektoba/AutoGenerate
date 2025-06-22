import os

class FileDeleter:
    def __init__(self, backup_manager=None, logger=None, dry_run=False):
        self.backup_manager = backup_manager
        self.logger = logger
        self.dry_run = dry_run

    def delete(self, file_path):
        if not os.path.isfile(file_path):
            if self.logger:
                self.logger.warning(f"삭제할 파일이 없음: {file_path}")
            return False
        if self.dry_run:
            if self.logger:
                self.logger.info(f"[DryRun] 삭제 예정: {file_path}")
            return True
        # 백업
        if self.backup_manager:
            self.backup_manager.backup(file_path)
        try:
            os.remove(file_path)
            if self.logger:
                self.logger.info(f"삭제 완료: {file_path}")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"파일 삭제 오류: {file_path} - {e}")
            return False
