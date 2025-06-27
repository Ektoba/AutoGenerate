#!/usr/bin/env python3
"""
삭제 로직 테스트 스크립트
"""

import os
import sys
import tempfile
import shutil

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from FileDeleter import FileDeleter
from AppLogger import AppLogger

def test_file_deletion():
    """파일 삭제 기능을 테스트합니다."""
    
    # 로거 설정
    logger = AppLogger(level="DEBUG")
    
    # 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp()
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    
    try:
        # 테스트 파일 생성
        with open(test_file_path, 'w') as f:
            f.write("This is a test file for deletion")
        
        logger.info(f"테스트 파일 생성: {test_file_path}")
        
        # FileDeleter 인스턴스 생성 (DryRun=False로 실제 삭제)
        file_deleter = FileDeleter(dry_run=False, logger=logger)
        
        # 파일 존재 확인
        if os.path.exists(test_file_path):
            logger.info(f"파일 존재 확인: {test_file_path}")
            
            # 삭제 시도
            logger.info("삭제 시도 시작...")
            result = file_deleter.delete(test_file_path)
            
            if result:
                logger.info("✅ 삭제 성공!")
            else:
                logger.error("❌ 삭제 실패!")
            
            # 파일 존재 여부 재확인
            if os.path.exists(test_file_path):
                logger.warning(f"파일이 여전히 존재함: {test_file_path}")
            else:
                logger.info(f"파일이 성공적으로 삭제됨: {test_file_path}")
        else:
            logger.error(f"테스트 파일이 존재하지 않음: {test_file_path}")
            
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)
    finally:
        # 임시 디렉토리 정리
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"임시 디렉토리 정리 완료: {temp_dir}")
        except Exception as e:
            logger.error(f"임시 디렉토리 정리 실패: {e}")

def test_send2trash_availability():
    """send2trash 라이브러리 사용 가능 여부를 확인합니다."""
    logger = AppLogger(level="DEBUG")
    
    try:
        import send2trash
        logger.info("✅ send2trash 라이브러리 사용 가능")
        
        # send2trash 버전 확인
        try:
            version = send2trash.__version__
            logger.info(f"send2trash 버전: {version}")
        except:
            logger.info("send2trash 버전 정보 없음")
            
    except ImportError as e:
        logger.warning(f"❌ send2trash 라이브러리 없음: {e}")
        logger.info("직접 삭제 모드로 동작합니다.")

if __name__ == "__main__":
    print("=== 파일 삭제 테스트 시작 ===")
    
    # send2trash 사용 가능 여부 확인
    test_send2trash_availability()
    
    # 파일 삭제 테스트
    test_file_deletion()
    
    print("=== 파일 삭제 테스트 완료 ===") 