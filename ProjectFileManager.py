"""
ProjectFileManager.py  (patched – 2025‑06‑27)
------------------------------------------------
변경 사항
1. parse_filters(filters_only=False)  추가
   • filters_only=True  → .vcxproj.filters 만 파싱
   • False (기본)      → 기존 .vcxproj + .filters 합집합과 동일
2. save_cache(set_or_list)  공개 메서드 추가
   • Orchestrator 에서 project_file_manager.save_cache(...) 호출 가능
3. 내부 구현은 기존 로직 최대한 유지(가독성 용 리팩터 최소화)
"""

import os
import json
import xml.etree.ElementTree as ET
import glob
from typing import List, Set


class ProjectFileManager:
    def __init__(self, config_manager, logger):
        self.config_manager = config_manager
        self.logger = logger
        self.project_root_path = self.config_manager.get_project_root_path()
        self.main_vcxproj_path = self.config_manager.get_abs_main_vcxproj()
        self.main_vcxproj_filters_path = self.config_manager.get_abs_main_vcxproj_filters()
        self.cache_file_path = os.path.join(self.project_root_path, "project_cache.json")
        self.watch_file_extensions = self.config_manager.get_setting(
            "WatchFileExtensions", [".cpp", ".h", ".hpp", ".c", ".inl"])

        # 초기 캐시 로드
        self.cached_file_list: List[str] = self._load_cache()

    # ---------------------------------------------------------------------
    # Public helpers -------------------------------------------------------
    # ---------------------------------------------------------------------
    def parse_filters(self, *, filters_only: bool = False) -> List[str]:
        """현재 프로젝트에서 참조 중인 파일 목록을 반환.
        • filters_only=True  → .vcxproj.filters 파일만 파싱
        • filters_only=False → .vcxproj  + .filters  모두 파싱(기존 동작)
        """
        if filters_only:
            files: Set[str] = self._parse_vcxproj_filters(self.main_vcxproj_filters_path)
            # 파싱 실패 세이프가드
            if files is None or len(files) == 0:
                self.logger.error("filters 파싱 실패·빈 결과 → 빈 리스트 반환")
                return []
        else:
            files = set(self._get_files_from_project_files())

        return list(files)

    def save_cache(self, iterable):
        """외부(Orchestrator)에서 캐시 세트를 저장할 때 사용."""
        # 리스트인지 세트인지 구분하지 않고 처리
        if isinstance(iterable, set):
            iterable = list(iterable)
        self._save_cache(iterable)
        # 내부 상태 동기화
        self.cached_file_list = list(iterable)

    # ---------------------------------------------------------------------
    # Private helpers ------------------------------------------------------
    # ---------------------------------------------------------------------
    def _load_cache(self):
        if os.path.exists(self.cache_file_path):
            try:
                with open(self.cache_file_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if isinstance(cached_data, list):
                        self.logger.debug(f"캐시 파일 로드 성공: {self.cache_file_path}")
                        return [self._normalize_path(p) for p in cached_data]
                    else:
                        self.logger.warning("캐시 파일 형식이 올바르지 않습니다. 캐시를 다시 생성합니다.")
            except json.JSONDecodeError as e:
                self.logger.error(f"캐시 파일 디코딩 오류: {e}. 캐시를 다시 생성합니다.")
            except Exception as e:
                self.logger.error(f"캐시 파일 로드 중 예기치 않은 오류: {e}. 캐시를 다시 생성합니다.")

        self.logger.info("캐시 파일이 없거나 유효하지 않아 현재 .vcxproj에서 파일 목록을 생성합니다.")
        initial_files = self._get_files_from_project_files()
        self._save_cache(initial_files)
        return initial_files

    def _save_cache(self, file_list):
        try:
            with open(self.cache_file_path, "w", encoding="utf-8") as f:
                json.dump(file_list, f, indent=4)
            self.logger.debug(f"캐시 파일 저장 성공: {self.cache_file_path}")
        except Exception as e:
            self.logger.error(f"캐시 파일 저장 중 오류 발생: {e}")

    @staticmethod
    def _normalize_path(path):
        """절대 경로 + 소문자 + 슬래시 정규화 - 모든 경로 정규화 문제 해결"""
        try:
            # 절대 경로로 변환
            abs_path = os.path.abspath(path)
            
            # Windows 환경에서 드라이브 문자를 소문자로 통일
            if os.name == 'nt' and len(abs_path) > 1 and abs_path[1] == ':':
                abs_path = abs_path[0].lower() + abs_path[1:]
            
            # 슬래시 정규화 (Windows에서는 백슬래시를 슬래시로)
            normalized = abs_path.replace(os.sep, "/")
            
            # 전체 경로를 소문자로 변환 (대소문자 불일치 해결)
            normalized = normalized.lower()
            
            return normalized
        except Exception:
            # 오류 발생 시 원본 경로를 소문자로 변환하여 반환
            try:
                return path.lower().replace(os.sep, "/")
            except:
                return path

    # ------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------
    def _get_files_from_project_files(self):
        files: Set[str] = set()
        files.update(self._parse_vcxproj(self.main_vcxproj_path))
        files.update(self._parse_vcxproj_filters(self.main_vcxproj_filters_path))
        self.logger.debug(f"현재 프로젝트 파일(.vcxproj + .filters)에서 파싱된 총 파일 수: {len(files)}")
        return list(files)

    def _parse_vcxproj(self, vcxproj_path):
        files: Set[str] = set()
        if not os.path.exists(vcxproj_path):
            self.logger.warning(f".vcxproj 파일을 찾을 수 없습니다: {vcxproj_path}")
            return files
        try:
            tree = ET.parse(vcxproj_path)
            root = tree.getroot()
            for item_group in root.findall(".//{*}ItemGroup"):
                for element in item_group:
                    if element.tag.endswith(("ClCompile", "ClInclude")):
                        include = element.get("Include")
                        if include:
                            files.add(self._normalize_path(os.path.join(os.path.dirname(vcxproj_path), include)))
        except Exception as e:
            self.logger.error(f"'{vcxproj_path}' 파싱 실패: {e}")
            return set()
        self.logger.debug(f"'{vcxproj_path}'에서 파싱된 파일 수: {len(files)}")
        return files

    def _parse_vcxproj_filters(self, filters_path):
        files: Set[str] = set()
        if not os.path.exists(filters_path):
            self.logger.warning(f".vcxproj.filters 파일을 찾을 수 없습니다: {filters_path}")
            return files
        try:
            tree = ET.parse(filters_path)
            root = tree.getroot()
            for item_group in root.findall(".//{*}ItemGroup"):
                for element in item_group:
                    if element.tag.endswith(("ClCompile", "ClInclude")):
                        include = element.get("Include")
                        if include:
                            files.add(self._normalize_path(os.path.join(os.path.dirname(filters_path), include)))
        except Exception as e:
            self.logger.error(f"'{filters_path}' 파싱 실패: {e}")
            return set()
        self.logger.debug(f"'{filters_path}'에서 파싱된 파일 수: {len(files)}")
        return files

    # ---------------------------------------------------------------------
    # 기존 compare/update API ------------------------------------------------
    # ---------------------------------------------------------------------
    def get_newly_unreferenced_files_and_update_cache(self):
        """이전 캐시와 현재(.vcxproj + .filters) 비교 → 새롭게 끊긴 파일 반환"""
        self.logger.info("실시간 변경 감지: 캐시와 현재 프로젝트 상태를 비교합니다.")
        current = set(self._get_files_from_project_files())
        newly_unreferenced = list(set(self.cached_file_list) - current)

        if newly_unreferenced:
            self.logger.info(f"새롭게 참조가 끊긴 파일 {len(newly_unreferenced)}개 발견")
        else:
            self.logger.info("새롭게 참조가 끊긴 파일이 없습니다.")

        # 캐시 갱신
        self.cached_file_list = list(current)
        self._save_cache(self.cached_file_list)
        return newly_unreferenced

    # ---------------------------------------------------------------------
    # 오프라인 변경 감지 ------------------------------------------------------
    # ---------------------------------------------------------------------
    def check_for_offline_changes(self):
        self.logger.info("오프라인 변경 사항 확인 중…")
        current = set(self._get_files_from_project_files())
        deleted = list(set(self.cached_file_list) - current)
        if deleted:
            self.logger.info(f"오프라인 상태에서 삭제된 파일 {len(deleted)}개 발견")
            self.cached_file_list = list(current)
            self._save_cache(self.cached_file_list)
        return deleted
