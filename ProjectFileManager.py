# project_file_manager.py
import os
import glob
import xml.etree.ElementTree as ET
import sys


class ProjectFileManager:
    """
    UE 프로젝트 파일(.vcxproj, .vcxproj.filters)을 파싱하고
    참조되지 않는 C++ 파일을 관리(삭제)하는 책임을 가집니다.
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.project_root_path = self.config_manager.get_project_root_path()
        self.main_vcxproj_path, _ = self.config_manager.get_main_vcxproj_paths()
        # get_all_cpp_files_in_source에서 사용할 확장자 목록
        self.watch_file_extensions = self.config_manager.get_setting("WatchFileExtensions",
                                                                     [".cpp", ".h", ".hpp", ".c", ".inl"])

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
            sys.stdout.flush()
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
            # dirnames를 직접 수정하여 os.walk가 특정 하위 디렉토리를 방문하지 않도록 함
            dirs_to_remove = []
            for dname in dirnames:
                if dname.lower() in excluded_dirs_patterns:
                    dirs_to_remove.append(dname)
            for d in dirs_to_remove:
                dirnames.remove(d)  # 이 리스트를 수정하면 os.walk가 이 디렉토리들을 건너뜀

            # 현재 디렉토리의 파일들을 추가
            for ext in exts:
                for filename in filenames:
                    if glob.fnmatch.fnmatch(filename, f"*{ext}"):  # 전체 파일명에 확장자가 일치하는지 확인
                        file_list.append(os.path.abspath(os.path.join(dirpath, filename)))

        return set(file_list)

    def delete_unreferenced_cpp_files(self):
        """
        .vcxproj 파일에는 참조되지 않지만 디스크의 Source/Plugins 폴더에 존재하는 C++ 파일을 삭제합니다.
        """
        print(f"[INFO] 참조되지 않는 C++ 파일 자동 삭제 기능 실행...")
        sys.stdout.flush()

        referenced_files = set()

        # 메인 vcxproj 파일만 파싱하여 참조된 파일 목록 가져오기
        if self.main_vcxproj_path and os.path.exists(self.main_vcxproj_path):
            current_vcxproj_files = self._get_cpp_files_from_vcxproj(self.main_vcxproj_path)
            print(f"[DEBUG] '{os.path.basename(self.main_vcxproj_path)}' 내의 참조 파일들: {current_vcxproj_files}")
            sys.stdout.flush()
            referenced_files |= current_vcxproj_files
        else:
            print(f"[WARNING] 메인 .vcxproj 파일이 config에 없거나 유효하지 않습니다. 참조 파일 목록 생성 불가.")
            sys.stdout.flush()
            # 메인 vcxproj를 못 찾으면 모든 vcxproj를 탐색하는 Fallback 로직 제거
            # 이제 MainVcxprojPath에 의존. 없으면 삭제 기능이 제대로 작동 안 함.
            print("[WARNING] Main .vcxproj 파일이 유효하지 않아 참조되지 않는 파일 삭제 기능을 건너뜝니다.")
            sys.stdout.flush()
            return  # 삭제 기능 수행 불가

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

        if unreferenced:
            print(f"[INFO] 프로젝트에서 제거되어 디스크에서 자동 삭제할 파일 목록:")
            sys.stdout.flush()
            for f in unreferenced:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        print(f" - [삭제됨] {f}")
                    else:
                        print(f" - [이미 없음] {f} (디스크에 이미 존재하지 않습니다.)")
                    sys.stdout.flush()
                except Exception as e:
                    print(f" - [삭제 실패] {f} (오류: {e})")
                    sys.stdout.flush()
        else:
            print("[INFO] 자동 삭제할 참조되지 않는 C++ 파일이 없습니다.")
            sys.stdout.flush()

        print(f"[INFO] 참조되지 않는 C++ 파일 자동 삭제 기능 완료.")
        sys.stdout.flush()