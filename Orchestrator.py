import os
import locale
import subprocess
import threading
from DeleteReport import DeleteReport


class UpdateOrchestrator:
    """Unreal VS 프로젝트 파일 갱신 + 불필요 파일 삭제 오케스트레이터"""

    # ------------------------------------------------------------------
    # 기능 플래그: False → 기존(UBT → diff) 흐름 유지
    #             True  → filters diff → 즉시 삭제 → 캐시 저장 → UBT
    # ------------------------------------------------------------------
    ENABLE_PRE_UBT_DELETE: bool = True

    def __init__(self, config_manager, logger, project_file_manager, file_deleter):
        self.config_manager = config_manager
        self.logger = logger
        self.project_file_manager = project_file_manager
        self.file_deleter = file_deleter

        # diff 계산용 캐시 (초기 로드)
        self.cache_set = set(self.project_file_manager.cached_file_list)

        self._is_running = False
        self.run_lock = threading.Lock()

    # --------------------------------------------------------------
    # 상태 체크
    # --------------------------------------------------------------
    def is_running(self):
        return self._is_running

    # --------------------------------------------------------------
    # 메인 플로우
    # --------------------------------------------------------------
    def run_full_update(self):
        if not self.run_lock.acquire(blocking=False):
            self.logger.warning("이미 다른 업데이트 작업이 진행 중입니다. 이번 요청은 건너뜁니다.")
            return

        self._is_running = True
        try:
            self.logger.info("VS 프로젝트 갱신/파일 청소 시작!")

            # [A] filters diff → 즉시 삭제 (옵션)
            if self.ENABLE_PRE_UBT_DELETE:
                self.logger.info("=== PRE-UBT 삭제 단계 시작 ===")
                current_set = set(self.project_file_manager.parse_filters(filters_only=True))
                self.logger.info(f"현재 filters에서 파싱된 파일 수: {len(current_set)}")
                self.logger.info(f"캐시에 저장된 파일 수: {len(self.cache_set)}")
                
                # 경로 정규화 디버깅을 위한 샘플 로그 추가
                if current_set:
                    self.logger.info("=== 경로 정규화 디버깅 ===")
                    self.logger.info(f"캐시 파일 샘플 (처음 3개):")
                    for i, path in enumerate(list(self.cache_set)[:3]):
                        self.logger.info(f"  {i+1}. {path}")
                    
                    self.logger.info(f"현재 파일 샘플 (처음 3개):")
                    for i, path in enumerate(list(current_set)[:3]):
                        self.logger.info(f"  {i+1}. {path}")
                
                if not current_set:
                    self.logger.error("Filters 파싱 실패 -> 삭제 작업 중단")
                    self._run_generate_script()
                    return

                removed = self.cache_set - current_set
                self.logger.info(f"삭제 대상 파일 수: {len(removed)}")
                
                # 삭제 대상 샘플 로그 추가
                if removed:
                    self.logger.info(f"삭제 대상 샘플 (처음 5개):")
                    for i, path in enumerate(list(removed)[:5]):
                        self.logger.info(f"  {i+1}. {path}")
                        # 파일 존재 확인
                        if os.path.exists(path):
                            self.logger.info(f"     ✅ 파일 존재")
                        else:
                            self.logger.info(f"     ❌ 파일 존재하지 않음")
                
                MAX_SAFE_DELETE = 50
                if len(removed) > MAX_SAFE_DELETE:
                    self.logger.warning(f"[DIFF] 삭제 대상이 너무 많음: cache={len(self.cache_set)} current={len(current_set)} removed={len(removed)} (최대 {MAX_SAFE_DELETE})")
                    return
                if removed:
                    self.logger.info(f"[DIFF] 삭제 대상 파일 {len(removed)}개 발견")
                    # 삭제 대상 파일 목록 출력
                    for f in list(removed)[:5]:  # 처음 5개만 출력
                        self.logger.info(f"삭제 대상: {f}")
                    if len(removed) > 5:
                        self.logger.info(f"... 외 {len(removed) - 5}개 더")
                    
                    pre_report = DeleteReport(logger=self.logger)
                    for f in removed:
                        self.logger.debug(f"삭제 시도: {f}")
                        if self.file_deleter.delete(f):
                            pre_report.add_deleted(f)
                        else:
                            pre_report.add_failed(f)
                    # 캐시 저장
                    self.cache_set = current_set
                    self.project_file_manager.save_cache(self.cache_set)
                    pre_report.summary(to_file=self.config_manager.get_abs_logfile())
                else:
                    self.logger.info("삭제 대상 파일이 없습니다.")
                self.logger.info("=== PRE-UBT 삭제 단계 완료 ===")

            # [B] UBT 실행 (항상 수행)
            self._run_generate_script()

            # [C] UBT 후 diff → 후처리(기존 로직 유지)
            post_report = DeleteReport(logger=self.logger)
            files_to_delete = self.project_file_manager.get_newly_unreferenced_files_and_update_cache()
            if files_to_delete:
                self.logger.info(f"UBT 후 새롭게 참조가 끊긴 파일 {len(files_to_delete)}개 삭제")
                deleted_dirs = set()
                for file_path in files_to_delete:
                    dir_path = os.path.dirname(file_path)
                    if self.file_deleter.delete(file_path):
                        post_report.add_deleted(file_path)
                        deleted_dirs.add(dir_path)
                    else:
                        post_report.add_failed(file_path)

                # 빈 폴더 정리
                for dir_path in sorted(deleted_dirs, key=len, reverse=True):
                    try:
                        if not os.listdir(dir_path):
                            self.file_deleter.delete_folder(dir_path)
                    except (FileNotFoundError, PermissionError):
                        continue
                post_report.summary(to_file=self.config_manager.get_abs_logfile())
            else:
                self.logger.info("UBT 후: 새롭게 참조 끊긴 파일 없음")

        except Exception as e:
            self.logger.error(f"업데이트 작업 중 예외: {e}", exc_info=True)
        finally:
            self._is_running = False
            self.run_lock.release()
            self.logger.info("모든 작업 완료. 다시 감시를 시작합니다. ✨")

    # --------------------------------------------------------------
    # UBT 직접 호출
    # --------------------------------------------------------------
    def _run_generate_script(self):
        self.logger.info("UnrealBuildTool 프로젝트 파일 생성 시작…")
        engine_root = self.config_manager.get_setting("UnrealEngineRootPath")
        uproject_path = self.config_manager.get_abs_uproject_path()
        ubt_exe_path = os.path.join(engine_root, "Engine", "Binaries", "DotNET", "UnrealBuildTool", "UnrealBuildTool.exe")

        if not (os.path.exists(ubt_exe_path) and os.path.exists(uproject_path)):
            self.logger.error("UBT 또는 .uproject 경로를 찾을 수 없습니다")
            return

        args = [ubt_exe_path, "-projectfiles", f"-project={uproject_path}", "-game", "-rocket", "-progress"]
        self.logger.info("UBT 실행: " + " ".join(args))
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            stdout_b, stderr_b = proc.communicate(timeout=600)
            stdout = self._decode(stdout_b)
            stderr = self._decode(stderr_b)
            if proc.returncode != 0:
                self.logger.error(f"UBT 실패(code {proc.returncode})\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            else:
                self.logger.info("UBT 완료!")
        except Exception as e:
            self.logger.error(f"UBT 실행 오류: {e}", exc_info=True)

    def _decode(self, b):
        if not b:
            return ""
        for enc in ("utf-8", locale.getdefaultlocale()[1], "cp949", "latin-1"):
            try:
                return b.decode(enc, errors="replace").strip()
            except Exception:
                continue
        return b.decode("latin-1", errors="replace").strip()
