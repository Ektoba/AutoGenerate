import json
import os
import sys

class ConfigManager:
    """
    config.json 파일을 로드하고 설정값을 제공하는 클래스입니다.
    """
    def __init__(self):
        # exe 파일 위치 기준
        self.base_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_dir, "config.json")
        self.config = self._load_config()
        self.project_root = os.path.abspath(
            os.path.join(self.base_dir, self.config.get("ProjectRootPath", "."))
        )

    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                print(f"[INFO] 설정 파일 로드 성공: {self.config_path}")
                return config_data
        except FileNotFoundError:
            print(f"[ERROR] config.json 파일이 {self.config_path}에 없습니다. 반드시 exe와 같은 폴더에 있어야 합니다.")
            self._crash_log("config.json 파일 없음", self.config_path)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"[ERROR] config.json 형식 오류: {e}")
            self._crash_log(f"config.json 파싱 오류: {e}", self.config_path)
            sys.exit(1)

    def _crash_log(self, msg, path):
        try:
            with open(os.path.join(self.base_dir, "zzz_crashlog.txt"), "a", encoding="utf-8") as f:
                f.write(f"{msg}: {path}\n")
        except Exception:
            pass

    def get_setting(self, key, default=None):
        return self.config.get(key, default)

    def get_abs_path(self, relpath):
        """
        ProjectRootPath 기준으로 relpath를 절대경로로 변환
        """
        return os.path.abspath(os.path.join(self.project_root, relpath))

    def get_abs_watch_paths(self):
        """
        WatchPaths에 들어있는 상대경로들을 ProjectRootPath 기준 절대경로 리스트로 반환
        """
        watch_paths = self.config.get("WatchPaths", [])
        abs_paths = []
        for relpath in watch_paths:
            abspath = self.get_abs_path(relpath)
            if os.path.isdir(abspath):
                abs_paths.append(abspath)
        return abs_paths

    # (선택) 주요 경로도 쉽게 가져오게 헬퍼 메서드 추가
    def get_abs_main_vcxproj(self):
        return self.get_abs_path(self.config.get("MainVcxprojPath", ""))

    def get_abs_main_vcxproj_filters(self):
        return self.get_abs_path(self.config.get("MainVcxprojFiltersPath", ""))

    def get_abs_backup_dir(self):
        return self.get_abs_path(self.config.get("BackupDir", "backup"))

    def get_abs_logfile(self):
        return self.get_abs_path(self.config.get("LogFile", "logs/watcher.log"))
