import os

class FileDeleter:
    def __init__(self, backup_manager=None, logger=None, dry_run=False):
        self.backup_manager = backup_manager
        self.logger = logger
        self.dry_run = dry_run

    def delete(self, file_path):
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            msg = f"삭제할 파일이 없음: {file_path}"
            if self.logger:
                self.logger.warning(msg)
            else:
                print(f"[FileDeleter] {msg}")
            return False
        if self.dry_run:
            msg = f"[DryRun] 삭제 예정: {file_path}"
            if self.logger:
                self.logger.info(msg)
            else:
                print(f"[FileDeleter] {msg}")
            return True
        # 백업 시도
        if self.backup_manager:
            backup_result = self.backup_manager.backup(file_path)
            if not backup_result:
                msg = f"백업에 실패해서 삭제를 건너뜁니다: {file_path}"
                if self.logger:
                    self.logger.warning(msg)
                else:
                    print(f"[FileDeleter] {msg}")
                return False
        try:
            os.remove(file_path)
            msg = f"삭제 완료: {file_path}"
            if self.logger:
                self.logger.info(msg)
            else:
                print(f"[FileDeleter] {msg}")
            return True
        except Exception as e:
            msg = f"파일 삭제 오류: {file_path} - {e}"
            if self.logger:
                self.logger.error(msg)
            else:
                print(f"[FileDeleter] {msg}")
            return False
