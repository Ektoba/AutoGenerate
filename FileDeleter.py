import os
try:
    import send2trash
    SEND2TRASH_AVAILABLE = True
except ImportError:
    SEND2TRASH_AVAILABLE = False


class FileDeleter:
    """
    실제 또는 시뮬레이션(드라이런) 모드로 파일/폴더를 삭제한다.
    - dry_run: True  → 실제로 지우지 않고 로그만 남긴다.
               False → send2trash(휴지통) 또는 os.remove 로 삭제
    - backup_manager: 삭제 전에 백업을 수행할 수 있는 객체(선택)
    - logger: python logging.Logger 호환 객체(선택)
    """

    def __init__(self, dry_run: bool = True, backup_manager=None, logger=None):
        self.dry_run = dry_run
        self.backup_manager = backup_manager
        self.logger = logger

    # ---------------------------------------------------
    # Public API
    # ---------------------------------------------------
    def delete(self, file_path: str) -> bool:
        """
        단일 파일 또는 빈 폴더를 삭제한다.
        폴더인 경우 내부가 비어 있지 않으면 삭제하지 않는다.
        Returns:
            bool: True  → (실제 or 드라이런) 삭제 루틴이 정상 수행됨
                  False → 삭제 실패
        """
        if not os.path.exists(file_path):
            self._log_info(f"존재하지 않는 경로: {file_path}")
            return False

        # DryRun 모드: 실제 삭제는 하지 않고 성공으로 간주
        if self.dry_run:
            msg = f"[DryRun] 삭제 예정: {file_path}"
            self._log_info(msg)
            return True

        # --- 백업(선택) --------------------------------------------------
        if self.backup_manager:
            backed = self._backup_if_needed(file_path)
            if not backed:
                # 백업 실패 시 삭제를 중단
                return False
        # ---------------------------------------------------------------

        try:
            if os.path.isfile(file_path):
                # 파일: 휴지통으로 이동 시도, 실패 시 직접 삭제
                if SEND2TRASH_AVAILABLE:
                    try:
                        send2trash.send2trash(file_path)
                        self._log_info(f"파일 삭제(휴지통): {file_path}")
                        return True
                    except Exception as e:
                        self._log_warn(f"휴지통 이동 실패, 직접 삭제 시도: {file_path} - {e}")
                
                # 직접 삭제 시도
                try:
                    os.remove(file_path)
                    self._log_info(f"파일 삭제(직접): {file_path}")
                except Exception as e2:
                    self._log_error(f"직접 삭제도 실패: {file_path} - {e2}")
                    return False
            elif os.path.isdir(file_path):
                # 폴더: 내부가 비어 있을 때만 삭제
                if not os.listdir(file_path):
                    if SEND2TRASH_AVAILABLE:
                        try:
                            send2trash.send2trash(file_path)
                            self._log_info(f"빈 폴더 삭제(휴지통): {file_path}")
                            return True
                        except Exception as e:
                            self._log_warn(f"휴지통 이동 실패, 직접 삭제 시도: {file_path} - {e}")
                    
                    # 직접 삭제 시도
                    try:
                        os.rmdir(file_path)
                        self._log_info(f"빈 폴더 삭제(직접): {file_path}")
                    except Exception as e2:
                        self._log_error(f"직접 삭제도 실패: {file_path} - {e2}")
                        return False
                else:
                    self._log_warn(f"폴더가 비어 있지 않아 삭제 생략: {file_path}")
                    return False
            else:
                self._log_warn(f"파일도 폴더도 아닌 경로, 삭제 불가: {file_path}")
                return False
        except Exception as e:
            self._log_error(f"삭제 실패: {file_path} - {e}")
            return False

        return True

    # ---------------------------------------------------
    # Internal Helpers
    # ---------------------------------------------------
    def _backup_if_needed(self, file_path: str) -> bool:
        """백업 매니저가 있으면 삭제 전 백업 수행."""
        try:
            self.backup_manager.backup(file_path)
            self._log_info(f"백업 완료: {file_path}")
            return True
        except Exception as e:
            self._log_error(f"백업에 실패해서 삭제를 건너뜁니다: {file_path} - {e}")
            return False

    def _log_info(self, msg: str):
        if self.logger:
            self.logger.info(msg)
        else:
            print(f"[FileDeleter] {msg}")

    def _log_warn(self, msg: str):
        if self.logger:
            self.logger.warning(msg)
        else:
            print(f"[FileDeleter][WARN] {msg}")

    def _log_error(self, msg: str):
        if self.logger:
            self.logger.error(msg)
        else:
            print(f"[FileDeleter][ERROR] {msg}")

    # ---------------------------------------------------
    # New helper ─ delete_folder
    # ---------------------------------------------------
    def delete_folder(self, dir_path: str) -> bool:
        """
        폴더 삭제용 얇은 래퍼.
        내부가 비어 있을 때만 self.delete()가 성공(True)을 돌려줘.
        """
        return self.delete(dir_path)
