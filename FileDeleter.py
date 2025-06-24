import os
import send2trash
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
            #os.remove(file_path)
            send2trash.send2trash(file_path)  # 👈 2. 휴지통으로 보내기!
            msg = f"삭제 완료(드럼통으로 이동): {file_path}"
            if self.logger:
                self.logger.info(msg)

            # 2. 파일이 있던 폴더를 확인한다
            dir_path = os.path.dirname(file_path)

            # 3. 폴더가 비어있는지 확인한다 (파일, 폴더 모두 없는지)
            if not os.listdir(dir_path):
                if self.logger:
                    self.logger.info(f"빈 폴더 발견! 함께 정리합니다 (휴지통으로 이동): {dir_path}")
                # 4. 비어있으면 폴더도 휴지통으로 보낸다!
                send2trash.send2trash(dir_path)
            # ✨✨✨ 여기까지! ✨✨✨

            return True
        except Exception as e:
            msg = f"파일 삭제 오류: {file_path} - {e}"
            if self.logger:
                self.logger.error(msg)
            else:
                print(f"[FileDeleter] {msg}")
            return False

    def delete_folder(self, dir_path):
        """ 폴더를 휴지통으로 보냅니다. """
        try:
            # send2trash는 파일과 폴더 모두 처리 가능!
            send2trash.send2trash(dir_path)
            if self.logger:
                self.logger.info(f"폴더 삭제 완료 (휴지통으로 이동): {dir_path}")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"폴더 삭제 오류: {dir_path} - {e}")
            return False