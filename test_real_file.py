#!/usr/bin/env python3
"""
실제 프로젝트 파일 삭제 테스트 스크립트
"""

import os
import sys
import json

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from FileDeleter import FileDeleter
from AppLogger import AppLogger

def test_real_file_deletion():
    """실제 프로젝트의 캐시된 파일 중 하나를 테스트합니다."""
    
    # 로거 설정
    logger = AppLogger(level="DEBUG")
    
    # 캐시 파일 경로
    cache_file = r"C:\SpartaTeamPrj\Final\1st-Team4-Final-Project\project_cache.json"
    
    try:
        # 캐시 파일 읽기
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_files = json.load(f)
        
        logger.info(f"캐시된 파일 수: {len(cached_files)}")
        
        # 처음 5개 파일 테스트
        test_files = cached_files[:5]
        
        for i, file_path in enumerate(test_files):
            logger.info(f"\n=== 테스트 {i+1}: {file_path} ===")
            
            # 파일 존재 확인
            if os.path.exists(file_path):
                logger.info(f"✅ 파일 존재: {file_path}")
                
                # 파일 정보 출력
                try:
                    stat = os.stat(file_path)
                    logger.info(f"파일 크기: {stat.st_size} bytes")
                    logger.info(f"읽기 권한: {os.access(file_path, os.R_OK)}")
                    logger.info(f"쓰기 권한: {os.access(file_path, os.W_OK)}")
                except Exception as e:
                    logger.error(f"파일 정보 조회 실패: {e}")
                
                # DryRun 모드로 삭제 테스트
                file_deleter = FileDeleter(dry_run=True, logger=logger)
                result = file_deleter.delete(file_path)
                logger.info(f"DryRun 삭제 결과: {result}")
                
            else:
                logger.warning(f"❌ 파일 존재하지 않음: {file_path}")
                
                # 경로 정규화 테스트
                normalized_path = file_path.replace('/', '\\')
                if os.path.exists(normalized_path):
                    logger.info(f"✅ 정규화된 경로로 존재: {normalized_path}")
                else:
                    logger.warning(f"❌ 정규화된 경로도 존재하지 않음: {normalized_path}")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)

def test_file_path_normalization():
    """경로 정규화 문제를 테스트합니다."""
    logger = AppLogger(level="DEBUG")
    
    # 테스트 경로들
    test_paths = [
        r"C:\SpartaTeamPrj\Final\1st-Team4-Final-Project\Source\Ember\AI\Base\BaseAI.cpp",
        r"c:/spartateamprj/final/1st-team4-final-project/source/ember/ai/base/baseai.cpp",
        r"C:/SpartaTeamPrj/Final/1st-Team4-Final-Project/Source/Ember/AI/Base/BaseAI.cpp"
    ]
    
    for path in test_paths:
        logger.info(f"\n=== 경로 테스트: {path} ===")
        
        # 원본 경로 존재 확인
        exists_original = os.path.exists(path)
        logger.info(f"원본 경로 존재: {exists_original}")
        
        # 절대 경로 변환
        try:
            abs_path = os.path.abspath(path)
            logger.info(f"절대 경로: {abs_path}")
            logger.info(f"절대 경로 존재: {os.path.exists(abs_path)}")
        except Exception as e:
            logger.error(f"절대 경로 변환 실패: {e}")
        
        # 정규화된 경로
        normalized = path.replace('/', '\\')
        logger.info(f"정규화된 경로: {normalized}")
        logger.info(f"정규화된 경로 존재: {os.path.exists(normalized)}")

if __name__ == "__main__":
    print("=== 실제 파일 삭제 테스트 시작 ===")
    
    # 경로 정규화 테스트
    test_file_path_normalization()
    
    # 실제 파일 삭제 테스트
    test_real_file_deletion()
    
    print("=== 실제 파일 삭제 테스트 완료 ===") 