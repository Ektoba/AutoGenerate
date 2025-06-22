# config_manager.py
import json
import os
import sys


class ConfigManager:
    """
    config.json 파일을 로드하고 설정값을 제공하는 클래스입니다.
    """

    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.config_path = os.path.join(self.script_dir, "config.json")
        self.config = self._load_config()
        self._set_derived_paths()

    def _load_config(self):
        """config.json 파일을 로드합니다."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                print(f"[INFO] 설정 파일 로드 성공: {self.config_path}")
                return config_data
        except FileNotFoundError:
            print(f"[ERROR] 설정 파일 (config.json)을 찾을 수 없습니다: {self.config_path}")
            sys.stdout.flush()
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"[ERROR] config.json 파일 형식이 올바르지 않습니다. 파싱 실패.")
            sys.stdout.flush()
            sys.exit(1)

    def _set_derived_paths(self):
        """
        로드된 config를 바탕으로 파생 경로들을 설정하고 정규화합니다.
        모든 경로는 절대 경로, 소문자, 슬래시(/) 구분자로 통일합니다.
        """
        # PROJECT_ROOT_PATH
        self.project_root_path = os.path.abspath(
            os.path.join(self.script_dir, self.config.get("ProjectRootPath", "..")))

        # MainVcxprojPath 및 MainVcxprojFiltersPath
        self.main_vcxproj_path_raw = self.config.get("MainVcxprojPath", "")
        self.main_vcxproj_filters_path_raw = self.config.get("MainVcxprojFiltersPath", "")

        self.main_vcxproj_path = os.path.abspath(
            self.main_vcxproj_path_raw).lower() if self.main_vcxproj_path_raw else ""
        self.main_vcxproj_filters_path = os.path.abspath(
            self.main_vcxproj_filters_path_raw).lower() if self.main_vcxproj_filters_path_raw else ""

        # 감시할 폴더 목록 (Watchdog Observer에게 전달될 실제 폴더 경로)
        self.watch_folders_for_observer = set()
        if self.main_vcxproj_path and os.path.exists(self.main_vcxproj_path_raw):
            self.watch_folders_for_observer.add(os.path.dirname(self.main_vcxproj_path_raw))
        if self.main_vcxproj_filters_path and os.path.exists(self.main_vcxproj_filters_path_raw):
            self.watch_folders_for_observer.add(os.path.dirname(self.main_vcxproj_filters_path_raw))

        if not self.watch_folders_for_observer:
            print(f"[ERROR] config.json에 유효한 .vcxproj 또는 .vcxproj.filters 경로가 없습니다. 감시할 대상 없음.")
            print(f"UpdateConfig.ps1을 실행하여 config.json을 초기화하거나 관련 경로를 수동으로 설정해주세요.")
            sys.stdout.flush()
            sys.exit(1)

    def get_setting(self, key, default=None):
        """지정된 설정 키의 값을 반환합니다."""
        return self.config.get(key, default)

    def get_project_root_path(self):
        return self.project_root_path

    def get_main_vcxproj_paths(self):
        """정규화된 메인 .vcxproj 및 .filters 경로를 반환합니다."""
        return self.main_vcxproj_path, self.main_vcxproj_filters_path

    def get_watch_folders_for_observer(self):
        """Watchdog Observer가 감시할 실제 폴더 경로 목록을 반환합니다."""
        return list(self.watch_folders_for_observer)