import glob
import os
import xml.etree.ElementTree as ET
import sys  # sys 모듈 추가


class ProjectFileManager:
    def __init__(self, config_manager):  # config_manager 인스턴스 받음
        self.config_manager = config_manager
        self.project_root_path = self.config_manager.get_project_root_path()
        self.main_vcxproj, _ = self.config_manager.get_main_vcxproj_paths()  # 원본 경로 사용
        self.watch_file_extensions = self.config_manager.get_setting("WatchFileExtensions",
                                                                     [".cpp", ".h", ".hpp", ".c", ".inl"])  # 확장자 목록 가져옴

    def _get_cpp_files_from_vcxproj(self, vcxproj_path):
        """
        .vcxproj 파일에서 <ClCompile> 및 <ClInclude> 태그에 참조된 C++ 파일 목록을 추출합니다.
        절대 경로로 변환하여 반환합니다.
        """
        try:
            tree = ET.parse(vcxproj_path)
            root = tree.getroot()
            ns = {'msb': 'http://schemas.microsoft.com/developer/msbuild/2003'}
            files = []
            for tag in ['ClCompile', 'ClInclude']:
                for elem in root.findall(f".//msb:{tag}", ns):
                    inc = elem.attrib.get('Include')
                    if inc:
                        # vcxproj 파일 경로를 기준으로 상대 경로를 절대 경로로 변환
                        files.append(os.path.abspath(os.path.join(os.path.dirname(vcxproj_path), inc)))
            return set(files)
        except Exception as e:
            print(f"[WARNING] .vcxproj 파일 파싱 실패: {vcxproj_path} - {e}")
            sys.stdout.flush()  # 즉시 출력
            return set()

    def _get_all_cpp_files_in_source(self, source_root):
        """
        지정된 소스 루트 내의 모든 C++ 관련 파일(*.cpp, *.h 등)을 재귀적으로 찾습니다.
        단, Intermediate, Saved, Binaries 등 빌드 관련 폴더는 제외합니다.
        """
        exts = self.watch_file_extensions  # config에서 가져온 확장자 사용
        file_list = []

        excluded_dirs_patterns = [
            'intermediate', 'saved', 'binaries', 'build', 'deriveddata', 'staging', 'unrealbuildtool'
        ]

        for dirpath, dirnames, filenames in os.walk(source_root):
            dirs_to_remove = []
            for dname in dirnames:
                if dname.lower() in excluded_dirs_patterns:
                    dirs_to_remove.append(dname)
            for d in dirs_to_remove:
                dirnames.remove(d)

            for ext in exts:
                for filename in filenames:
                    if glob.fnmatch.fnmatch(filename, f"*{ext}"):  # 와일드카드 매칭
                        file_list.append(os.path.abspath(os.path.join(dirpath, filename)))

        return set(file_list)

    def get_unreferenced_cpp_files(self):
        """
        .vcxproj 파일에는 참조되지 않지만 디스크의 Source/Plugins 폴더에 존재하는 C++ 파일을 삭제합니다.
        """
        print(f"[INFO] 참조되지 않는 C++ 파일 자동 삭제 기능 실행...")
        sys.stdout.flush()

        referenced_files = set()

        # 메인 vcxproj 파일만 파싱하여 참조된 파일 목록 가져오기
        if self.main_vcxproj and os.path.exists(self.main_vcxproj):
            current_vcxproj_files = self._get_cpp_files_from_vcxproj(self.main_vcxproj)
            print(f"[DEBUG] '{os.path.basename(self.main_vcxproj)}' 내의 참조 파일들: {current_vcxproj_files}")
            sys.stdout.flush()
            referenced_files |= current_vcxproj_files
        else:
            print(f"[WARNING] 메인 .vcxproj 파일이 config에 없거나 유효하지 않습니다. 참조 파일 목록 생성 불가.")
            sys.stdout.flush()
            print("[WARNING] Main .vcxproj 파일이 유효하지 않아 참조되지 않는 파일 삭제 기능을 건너뜝니다.")
            sys.stdout.flush()
            return []  # 삭제 기능 수행 불가 시 빈 리스트 반환

        print(f"[DEBUG] 모든 .vcxproj에서 참조되는 최종 파일 목록: {referenced_files}")
        sys.stdout.flush()

        # 실제 Source 또는 Plugins 폴더 내 모든 C++ 파일 찾기
        all_files = set()
        for folder_name in ["Source", "Plugins"]:
            source_folder_path = os.path.join(self.project_root_path, folder_name)
            if os.path.exists(source_folder_path):
                all_files |= self._get_all_cpp_files_in_source(source_folder_path)

        print(f"[DEBUG] 실제 디스크 상의 모든 C++ 파일 목록 (Source/Plugins): {all_files}")
        sys.stdout.flush()

        # 참조 안 된 파일들 찾기
        unreferenced = [f for f in all_files if f not in referenced_files]
        print(f"[DEBUG] 참조되지 않아 삭제 대상으로 식별된 파일들: {unreferenced}")
        sys.stdout.flush()

        return unreferenced  # 삭제 대상 파일 리스트 반환 (삭제는 Deleter가 함)