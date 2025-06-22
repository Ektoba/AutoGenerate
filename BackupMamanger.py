import os
import shutil
from datetime import datetime

class BackupManager:
    def __init__(self, backup_dir, logger=None):
        self.backup_dir = backup_dir
        self.logger = logger
    def backup(self, file_path):
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            rel_path = os.path.relpath(file_path)
            backup_path = os.path.join(self.backup_dir, f"{rel_path}.{ts}.bak")
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(file_path, backup_path)
            if self.logger:
                self.logger.info(f"백업 완료: {backup_path}")
            return backup_path
        except Exception as e:
            if self.logger:
                self.logger.error(f"백업 실패: {file_path}, 사유: {e}")
            return None
