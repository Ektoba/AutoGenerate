# ConfigManager.py
import json
import os
import sys
import logging


class ConfigManager:
    def __init__(self):
        try:
            self.logger = None
            self.is_pyinstaller_build = getattr(sys, 'frozen', False)

            if self.is_pyinstaller_build:
                self.base_dir = os.path.dirname(sys.executable)
            else:
                self.base_dir = os.path.dirname(os.path.abspath(__file__))

            self.config_path = os.path.join(self.base_dir, "config.json")
            self.config = self._load_config()

            self.project_root = os.path.abspath(
                os.path.join(self.base_dir, self.config.get("ProjectRootPath", "."))
            )

        except FileNotFoundError:
            print(f"[CRITICAL ERROR] 설정 파일(config.json)을 찾을 수 없습니다: {self.config_path}")
            print("[CRITICAL ERROR] 'config.json' 파일이 실행 파일과 같은 폴더에 있는지 확인해주세요.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"[CRITICAL ERROR] config.json 파일 형식 오류: {e}")
            print("[CRITICAL ERROR] config.json 파일의 내용을 다시 확인해주세요.")
            sys.exit(1)
        except Exception as e:
            print(f"[CRITICAL ERROR] ConfigManager 초기화 중 예기치 못한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def set_logger(self, logger):
        """ main.py에서 생성된 로거를 주입받는 메서드 """
        self.logger = logger
        if self.logger:
            self.logger.info("ConfigManager에 메인 로거가 성공적으로 설정되었습니다. ✨")

    def _load_config(self):
        """ config.json 파일을 읽어오는 내부 함수 """
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            print(f"[INFO] 설정 파일 로드 성공: {self.config_path}")
            return config_data

    def _crash_log(self, msg, path):
        try:
            with open(os.path.join(self.base_dir, "zzz_crashlog.txt"), "a", encoding="utf-8") as f:
                f.write(f"{msg}: {path}\n")
        except Exception:
            pass

    def get_setting(self, key, default=None):
        return self.config.get(key, default)

    def get_abs_path(self, relpath):
        """ ProjectRootPath 기준으로 relpath를 절대경로로 변환합니다. """
        calculated_path = os.path.abspath(os.path.join(self.project_root, relpath))
        if self.logger:
            self.logger.debug(f"DEBUG: get_abs_path (ProjectRoot 기준) '{relpath}' -> '{calculated_path}'")
        return calculated_path

    def get_abs_path_from_base_dir(self, relpath):
        """ 실행 파일(base_dir) 기준으로 relpath를 절대경로로 변환합니다. """
        calculated_path = os.path.abspath(os.path.join(self.base_dir, relpath))
        if self.logger:
            self.logger.debug(f"DEBUG: get_abs_path_from_base_dir (BaseDir 기준) '{relpath}' -> '{calculated_path}'")
        return calculated_path

    def get_project_root_path(self):
        return self.project_root

    def get_abs_watch_paths(self):
        """ WatchPaths에 들어있는 상대경로들을 절대경로 리스트로 반환 """
        abs_paths = []
        watch_paths = self.get_setting("WatchPaths", [])

        if self.logger: self.logger.debug("--- 감시 폴더 목록 계산 시작 ---")

        for rel_path in watch_paths:
            full_path = self.get_abs_path(rel_path)
            if os.path.isdir(full_path):
                abs_paths.append(full_path)
            else:
                if self.logger: self.logger.warning(f"[WARN] WatchPaths에 지정된 경로가 유효한 디렉토리가 아닙니다: {full_path}")

        main_vcxproj_path_full = self.get_abs_main_vcxproj()
        main_vcxproj_dir = os.path.dirname(main_vcxproj_path_full)

        if os.path.isdir(main_vcxproj_dir) and main_vcxproj_dir not in abs_paths:
            abs_paths.append(main_vcxproj_dir)

        final_watch_folders = list(set(abs_paths))
        if self.logger:
            self.logger.debug(f"최종 감시 폴더: {final_watch_folders}")
            self.logger.debug("--- 감시 폴더 목록 계산 종료 ---")

        return final_watch_folders

    def get_abs_main_vcxproj(self):
        """ 메인 .vcxproj 파일의 절대 경로를 반환합니다. """
        return self.get_abs_path(self.config.get("MainVcxprojPath", ""))

    def get_abs_main_vcxproj_filters(self):
        """ 메인 .vcxproj.filters 파일의 절대 경로를 반환합니다. """
        return self.get_abs_path(self.config.get("MainVcxprojFiltersPath", ""))

    def get_normalized_main_vcxproj_paths(self):
        """ 메인 .vcxproj 및 .vcxproj.filters 파일의 절대 경로를 정규화하여 반환 """
        main_vcxproj_path = self.get_abs_main_vcxproj()
        main_vcxproj_filters_path = self.get_abs_main_vcxproj_filters()

        normalized_vcxproj = os.path.abspath(main_vcxproj_path).lower()
        normalized_filters = os.path.abspath(main_vcxproj_filters_path).lower()

        return normalized_vcxproj, normalized_filters

    def get_main_vcxproj_paths(self):
        """ 메인 .vcxproj 및 .vcxproj.filters 파일의 원본 절대 경로를 반환 """
        main_vcxproj_path = self.get_abs_main_vcxproj()
        main_vcxproj_filters_path = self.get_abs_main_vcxproj_filters()
        return main_vcxproj_path, main_vcxproj_filters_path

    def get_abs_backup_dir(self):
        return self.get_abs_path_from_base_dir(self.config.get("BackupDir", "backup"))

    def get_abs_logfile(self):
        return self.get_abs_path_from_base_dir(self.config.get("LogPath", "Logs/Watcher.log"))

    def get_abs_uproject_path(self):
        return os.path.join(self.project_root, self.get_setting("MainUprojectPath", ""))