# SetupManager.py
import os
import json
import winreg
import glob
import sys

class SetupManager:
    """ config.json 파일이 없을 때, 자동으로 설정을 찾아 생성하는 '설정 마법사' """
    def __init__(self, logger):
        self.logger = logger
        self.base_dir = self._get_base_dir()
        self.config_path = os.path.join(self.base_dir, "config.json")

    def _get_base_dir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def run_setup_if_needed(self):
        if not os.path.exists(self.config_path):
            self.logger.info("config.json 파일이 없어 새로 생성합니다. 자동 설정을 시작합니다...")
            self.create_initial_config()

    def create_initial_config(self):
        project_root, uproject_name = self._find_project_root_and_uproject()
        if not project_root:
            self.logger.error("프로젝트 루트(.uproject 파일이 있는 폴더)를 찾을 수 없어 중단합니다.")
            sys.exit(1)

        engine_root = self._find_unreal_engine_root("5.5")
        vcxproj_path, filters_path = self._find_vcxproj_files(project_root, uproject_name)

        config_data = {
            "ProjectRootPath": self._get_relative_path(project_root, self.base_dir),
            "UnrealEngineRootPath": engine_root or "",
            "MainUprojectPath": uproject_name or "",
            "MainVcxprojPath": self._get_relative_path(vcxproj_path, project_root) if vcxproj_path else "",
            "MainVcxprojFiltersPath": self._get_relative_path(filters_path, project_root) if filters_path else "",
            "LogPath": "Logs/Watcher.log",
            "WatchPaths": ["Source", "Plugins"],
            "WatchFileExtensions": [".cpp", ".h", ".hpp", ".c", ".inl"],
            "DebounceTimeMs": 1500,
            "DryRun": False,
            "IgnoredNamePatterns": [".obj", ".pdb", ".tmp", ".user", ".log"],
            "IgnoredDirs": ["/saved/", "/binaries/", "/build/", "/intermediate/"], # .vcxproj 때문에 intermediate는 감시해야 함
            "BackupDir": "backup",
            "PatrolIntervalMinutes": 0 # 기본값은 순찰 기능 끄기
        }

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.logger.info(f"성공적으로 config.json 파일을 생성했습니다: {self.config_path}")
        except IOError as e:
            self.logger.error(f"config.json 파일 저장 실패: {e}")

    def _find_project_root_and_uproject(self):
        current_dir = self.base_dir
        for _ in range(5):
            uproject_files = glob.glob(os.path.join(current_dir, "*.uproject"))
            if uproject_files:
                self.logger.info(f"프로젝트 루트를 찾았습니다: {current_dir}")
                return current_dir, os.path.basename(uproject_files[0])
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir: break
            current_dir = parent_dir
        return None, None

    def _find_unreal_engine_root(self, version):
        try:
            key_path = r"SOFTWARE\EpicGames\Unreal Engine\{}".format(version)
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                engine_path, _ = winreg.QueryValueEx(key, "InstalledDirectory")
                if os.path.exists(engine_path):
                    self.logger.info(f"레지스트리에서 UE {version} 경로를 찾았습니다: {engine_path}")
                    return engine_path
        except FileNotFoundError:
            self.logger.debug("레지스트리에서 UE 경로를 찾지 못했습니다.")
        return None

    def _find_vcxproj_files(self, project_root, uproject_name):
        base_name = os.path.splitext(uproject_name)[0]
        vcxproj_pattern = os.path.join(project_root, "Intermediate", "ProjectFiles", f"{base_name}.vcxproj")
        vcxproj_files = glob.glob(vcxproj_pattern)
        if vcxproj_files:
            vcxproj = vcxproj_files[0]
            filters = vcxproj + ".filters"
            return vcxproj, filters
        return None, None

    def _get_relative_path(self, path, start):
        if not path or not start: return ""
        return os.path.relpath(path, start).replace('/', '\\')