import os
import glob
import xml.etree.ElementTree as ET


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
            return final_files_set
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