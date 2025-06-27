#!/usr/bin/env python3
"""
Orchestrator 삭제 로직 디버깅 스크립트
"""

import os
import sys
import json

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ConfigManager import ConfigManager
from ProjectFileManager import ProjectFileManager
from FileDeleter import FileDeleter
from AppLogger import AppLogger

def debug_orchestrator_logic():
    """Orchestrator의 삭제 로직을 직접 테스트합니다."""
    
    # 로거 설정
    logger = AppLogger(level="DEBUG")
    
    try:
        # ConfigManager 생성
        config_manager = ConfigManager()
        config_manager.set_logger(logger)
        
        # ProjectFileManager 생성
        project_file_manager = ProjectFileManager(config_manager, logger)
        
        # FileDeleter 생성 (DryRun=False로 실제 삭제)
        file_deleter = FileDeleter(dry_run=False, logger=logger)
        
        logger.info("=== Orchestrator 로직 디버깅 시작 ===")
        
        # 1. 현재 filters 파싱
        logger.info("1. 현재 filters 파싱 중...")
        current_set = set(project_file_manager.parse_filters(filters_only=True))
        logger.info(f"현재 filters에서 파싱된 파일 수: {len(current_set)}")
        
        if not current_set:
            logger.error("Filters 파싱 실패!")
            return
        
        # 2. 캐시 로드
        logger.info("2. 캐시 로드 중...")
        cache_set = set(project_file_manager.cached_file_list)
        logger.info(f"캐시에 저장된 파일 수: {len(cache_set)}")
        
        # 3. 삭제 대상 계산
        logger.info("3. 삭제 대상 계산 중...")
        removed = cache_set - current_set
        logger.info(f"삭제 대상 파일 수: {len(removed)}")
        
        # 4. 삭제 대상 파일 목록 출력 (처음 10개)
        if removed:
            logger.info("4. 삭제 대상 파일 목록 (처음 10개):")
            for i, file_path in enumerate(list(removed)[:10]):
                logger.info(f"   {i+1}. {file_path}")
                # 파일 존재 확인
                if os.path.exists(file_path):
                    logger.info(f"      ✅ 존재함")
                else:
                    logger.info(f"      ❌ 존재하지 않음")
            
            if len(removed) > 10:
                logger.info(f"   ... 외 {len(removed) - 10}개 더")
            
            # 5. 실제 삭제 테스트 (처음 3개만)
            logger.info("5. 실제 삭제 테스트 (처음 3개만)...")
            test_files = list(removed)[:3]
            
            for i, file_path in enumerate(test_files):
                logger.info(f"\n=== 삭제 테스트 {i+1}: {file_path} ===")
                
                if os.path.exists(file_path):
                    logger.info(f"파일 존재 확인됨")
                    
                    # 삭제 시도
                    result = file_deleter.delete(file_path)
                    
                    if result:
                        logger.info(f"✅ 삭제 성공!")
                        
                        # 파일 존재 여부 재확인
                        if os.path.exists(file_path):
                            logger.warning(f"⚠️ 파일이 여전히 존재함")
                        else:
                            logger.info(f"✅ 파일이 성공적으로 삭제됨")
                    else:
                        logger.error(f"❌ 삭제 실패!")
                else:
                    logger.warning(f"파일이 존재하지 않음")
        else:
            logger.info("삭제 대상 파일이 없습니다.")
        
        logger.info("=== Orchestrator 로직 디버깅 완료 ===")
        
    except Exception as e:
        logger.error(f"디버깅 중 오류 발생: {e}", exc_info=True)

def test_cache_vs_current():
    """캐시와 현재 상태의 차이를 자세히 분석합니다."""
    logger = AppLogger(level="DEBUG")
    
    try:
        # ConfigManager 생성
        config_manager = ConfigManager()
        config_manager.set_logger(logger)
        
        # ProjectFileManager 생성
        project_file_manager = ProjectFileManager(config_manager, logger)
        
        logger.info("=== 캐시 vs 현재 상태 분석 ===")
        
        # 현재 상태 파싱
        current_files = project_file_manager.parse_filters(filters_only=True)
        current_set = set(current_files)
        
        # 캐시 상태
        cache_files = project_file_manager.cached_file_list
        cache_set = set(cache_files)
        
        logger.info(f"현재 파일 수: {len(current_set)}")
        logger.info(f"캐시 파일 수: {len(cache_set)}")
        
        # 차이 분석
        removed = cache_set - current_set
        added = current_set - cache_set
        
        logger.info(f"삭제 대상: {len(removed)}")
        logger.info(f"추가된 파일: {len(added)}")
        
        # 삭제 대상 중 실제 존재하는 파일만 필터링
        existing_removed = [f for f in removed if os.path.exists(f)]
        logger.info(f"실제 존재하는 삭제 대상: {len(existing_removed)}")
        
        if existing_removed:
            logger.info("실제 존재하는 삭제 대상 파일들:")
            for f in existing_removed[:5]:
                logger.info(f"  - {f}")
            if len(existing_removed) > 5:
                logger.info(f"  ... 외 {len(existing_removed) - 5}개 더")
        
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    print("=== Orchestrator 디버깅 시작 ===")
    
    # 캐시 vs 현재 상태 분석
    test_cache_vs_current()
    
    # Orchestrator 로직 디버깅
    debug_orchestrator_logic()
    
    print("=== Orchestrator 디버깅 완료 ===") 