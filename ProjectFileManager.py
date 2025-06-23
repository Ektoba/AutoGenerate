import os
import glob
import xml.etree.ElementTree as ET

class ProjectFileManager:
    def __init__(self, main_vcxproj, main_vcxproj_filters=None):
        # 둘 다 절대경로로 들어온다고 가정
        self.main_vcxproj = main_vcxproj
        self.main_vcxproj_filters = main_vcxproj_filters

    def get_all_cpp_files(self):
        exts = ['*.cpp', '*.h', '*.hpp', '*.inl', '*.c']
        # main_vcxproj 위치 기준 Source, Plugins 폴더 탐색
        base_dir = os.path.abspath(os.path.join(os.path.dirname(self.main_vcxproj), "../.."))
        source_dirs = [
            os.path.join(base_dir, "Source"),
            os.path.join(base_dir, "Plugins")
        ]
        files = []
        for src_dir in source_dirs:
            if not os.path.isdir(src_dir):
                continue
            for ext in exts:
                files.extend(glob.glob(os.path.join(src_dir, '**', ext), recursive=True))
        return set(map(os.path.abspath, files))

    def get_cpp_files_from_vcxproj(self):
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
            return set(files)
        except Exception as e:
            print(f"[ProjectFileManager][WARNING] .vcxproj 파싱 실패: {e}")
            return set()

    def get_unreferenced_cpp_files(self):
        referenced = self.get_cpp_files_from_vcxproj()
        all_files = self.get_all_cpp_files()
        return [f for f in all_files if f not in referenced]
