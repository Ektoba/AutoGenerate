import os
import glob
import xml.etree.ElementTree as ET
import json

# import sys # sys 모듈은 이제 필요 없으므로 제거 (AppLogger 사용)


class ProjectFileManager:
    def __init__(self, config_manager, logger):  # logger 인자 추가
        self.config_manager = config_manager
        self.logger = logger  # logger 저장
        self.project_root_path = self.config_manager.get_project_root_path()
        self.main_vcxproj = self.config_manager.get_abs_main_vcxproj()
        self.main_vcxproj_filters = self.config_manager.get_abs_main_vcxproj_filters()
        self.watch_file_extensions = self.config_manager.get_setting("WatchFileExtensions",
                                                                     [".cpp", ".h", ".hpp", ".c", ".inl"])

        self.logger.debug(f"DEBUG: ProjectFileManager init - project_root_path: '{self.project_root_path}'")
        self.logger.debug(f"DEBUG: ProjectFileManager init - main_vcxproj: '{self.main_vcxproj}'")
        self.logger.debug(f"DEBUG: ProjectFileManager init - main_vcxproj_filters: '{self.main_vcxproj_filters}'")
        self.logger.debug(f"DEBUG: ProjectFileManager init - watch_file_extensions: {self.watch_file_extensions}")
        # --- ✨ 캐시 기능 추가 (순서가 중요해!) ✨ ---
        # ✅ 1단계: 캐시 파일 경로를 *먼저* 정의해준다!
        self.cache_path = os.path.join(self.config_manager.base_dir, "project_cache.json")
        # ✅ 2단계: 그 다음에 캐시를 로드한다!
        self.cached_file_list = self._load_cache()
        # ✅ 3단계: 캐시가 없으면 만듬
        if not self.cached_file_list:
             # 첫 실행이라 캐시가 없다면, 현재 프로젝트 상태로 새로 생성
            self.cached_file_list = self.get_cpp_files_from_vcxproj()
            self._save_cache(self.cached_file_list)
            self.logger.info(f"프로젝트 파일 캐시를 생성했습니다: {self.cache_path}")
        else:
            self.logger.info(f"기존 프로젝트 파일 캐시를 로드했습니다: {self.cache_path}")
    def get_all_cpp_files(self):
        exts = self.watch_file_extensions
        source_dirs = [
            os.path.join(self.project_root_path, "Source"),
            os.path.join(self.project_root_path, "Plugins")
        ]
        files = []
        self.logger.debug(f"DEBUG: get_all_cpp_files - Scanning directories: {source_dirs}")

        for src_dir in source_dirs:
            if not os.path.isdir(src_dir):
                self.logger.debug(f"DEBUG: get_all_cpp_files - Directory does not exist: {src_dir}")
                continue
            for ext in exts:
                pattern = os.path.join(src_dir, '**', f"*{ext}")
                found_files_in_ext = glob.glob(pattern, recursive=True)
                self.logger.debug(
                    f"DEBUG: get_all_cpp_files - Found {len(found_files_in_ext)} files for pattern: {pattern}")
                files.extend(found_files_in_ext)

        final_files_set = set(map(os.path.abspath, files))
        self.logger.debug(f"DEBUG: get_all_cpp_files - Total {len(final_files_set)} C++ files found on disk.")
        # if len(final_files_set) < 10: self.logger.debug(f"DEBUG: All C++ files: {final_files_set}") # 너무 많으면 출력 안함
        return final_files_set

    def get_cpp_files_from_vcxproj(self):
        if not os.path.isfile(self.main_vcxproj):
            self.logger.error(f"[ProjectFileManager][ERROR] .vcxproj 파일이 존재하지 않습니다: {self.main_vcxproj}")
            return set()
        try:
            tree = ET.parse(self.main_vcxproj)
            root = tree.getroot()
            ns = {'msb': 'http://schemas.microsoft.com/developer/msbuild/2003'}
            files = []
            for tag in ['ClCompile', 'ClInclude']:
                for elem in root.findall(f".//msb:{tag}", ns):
                    inc = elem.attrib.get('Include')
                    if inc:
                        files.append(os.path.abspath(os.path.join(os.path.dirname(self.main_vcxproj), inc)))
            final_files_set = set(files)
            self.logger.debug(
                f"DEBUG: get_cpp_files_from_vcxproj - Total {len(final_files_set)} files referenced in .vcxproj.")
            # if len(final_files_set) < 10: self.logger.debug(f"DEBUG: Referenced files: {final_files_set}") # 너무 많으면 출력 안함
            return list(final_files_set)
        except Exception as e:
            self.logger.error(f"[ProjectFileManager][CRITICAL ERROR] .vcxproj 파싱 실패: {self.main_vcxproj} / 사유: {e}",
                              exc_info=True)  # exc_info=True 추가
            return set()

    def get_unreferenced_cpp_files(self):
        referenced = self.get_cpp_files_from_vcxproj()
        all_files = self.get_all_cpp_files()
        unreferenced_files = [f for f in all_files if f not in referenced]
        self.logger.debug(
            f"DEBUG: get_unreferenced_cpp_files - Total {len(all_files)} total files, {len(referenced)} referenced files.")
        self.logger.debug(f"DEBUG: get_unreferenced_cpp_files - Found {len(unreferenced_files)} unreferenced files.")
        # if len(unreferenced_files) < 10: self.logger.debug(f"DEBUG: Unreferenced files: {unreferenced_files}") # 너무 많으면 출력 안함
        return unreferenced_files

    def _load_cache(self):
        """디스크에서 project_cache.json 파일을 읽어와 파일 목록을 반환합니다."""
        if not os.path.exists(self.cache_path):
            return []
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"캐시 파일 로드 실패: {e}")
            return []

    def _save_cache(self, file_list):
        """메모리에 있는 파일 목록을 project_cache.json 파일로 저장합니다."""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(file_list, f, indent=4)
        except IOError as e:
            self.logger.error(f"캐시 파일 저장 실패: {e}")

    def get_newly_unreferenced_files_and_update_cache(self):
        """
        새롭게 참조가 끊긴 파일 목록만 반환하고, 내부 캐시를 업데이트합니다.
        """
        self.logger.info("실시간 변경 감지: 캐시와 현재 프로젝트 상태를 비교합니다.")

        # 현재 .vcxproj 파일에 있는 파일 목록 가져오기
        current_files = self.get_cpp_files_from_vcxproj()

        # 메모리에 있던 이전 파일 목록(cached_file_list)과 비교
        # 이전 목록에는 있었는데, 현재 목록에는 없는 파일을 찾는다!
        newly_unreferenced = list(set(self.cached_file_list) - set(current_files))

        if newly_unreferenced:
            self.logger.info(f"새롭게 참조가 끊긴 파일 {len(newly_unreferenced)}개를 발견했습니다.")
        else:
            self.logger.info("새롭게 참조가 끊긴 파일이 없습니다.")

        # ✨ 가장 중요! 다음 비교를 위해 메모리 캐시와 디스크 캐시를 현재 상태로 업데이트!
        self.cached_file_list = list(current_files)
        self._save_cache(self.cached_file_list)

        return newly_unreferenced