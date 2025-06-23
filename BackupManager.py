import os
import shutil
from datetime import datetime

class BackupManager:
    def __init__(self, backup_dir, logger=None):
        # backup_dir는 항상 절대경로가 들어온다고 가정
        self.backup_dir = backup_dir
        self.logger = logger

    def backup(self, file_path):
        # file_path도 절대경로로 들어온다고 가정
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            rel_path = os.path.basename(file_path)
            backup_path = os.path.join(self.backup_dir, f"{rel_path}.{ts}.bak")
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(file_path, backup_path)
            if self.logger:
                self.logger.info(f"백업 완료: {backup_path}")
            else:
                print(f"[BackupManager] 백업 완료: {backup_path}")
            return backup_path
        except Exception as e:
            msg = f"백업 실패: {file_path}, 사유: {e}"
            if self.logger:
                self.logger.error(msg)
            else:
                print(f"[BackupManager] {msg}")
            return None
