#!/usr/bin/env python3
"""
경로 정규화 테스트 스크립트
"""

import os
import sys

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ProjectFileManager import ProjectFileManager
from ConfigManager import ConfigManager
from AppLogger import AppLogger

def test_path_normalization():
    """경로 정규화가 제대로 작동하는지 테스트합니다."""
    
    # 로거 설정
    logger = AppLogger(level="DEBUG")
    
    try:
        # ConfigManager 생성
        config_manager = ConfigManager()
        config_manager.set_logger(logger)
        
        # ProjectFileManager 생성
        project_file_manager = ProjectFileManager(config_manager, logger)
        
        logger.info("=== 경로 정규화 테스트 시작 ===")
        
        # 테스트 경로들 (다양한 형태)
        test_paths = [
            r"C:\SpartaTeamPrj\Final\1st-Team4-Final-Project\Source\Ember\AI\Base\BaseAI.cpp",
            r"c:/spartateamprj/final/1st-team4-final-project/source/ember/ai/base/baseai.cpp",
            r"C:/SpartaTeamPrj/Final/1st-Team4-Final-Project/Source/Ember/AI/Base/BaseAI.cpp",
            r"c:\spartateamprj\final\1st-team4-final-project\source\ember\ai\base\baseai.cpp",
            r"..\Source\Ember\AI\Base\BaseAI.cpp",
            r"Source\Ember\AI\Base\BaseAI.cpp"
        ]
        
        logger.info("테스트 경로들:")
        for i, path in enumerate(test_paths):
            logger.info(f"  {i+1}. 원본: {path}")
            
            # 정규화된 경로
            normalized = project_file_manager._normalize_path(path)
            logger.info(f"     정규화: {normalized}")
            
            # 파일 존재 확인
            exists = os.path.exists(path)
            logger.info(f"     존재: {exists}")
            
            logger.info("")
        
        # 실제 프로젝트 파일에서 샘플 테스트
        logger.info("=== 실제 프로젝트 파일 샘플 테스트 ===")
        
        # vcxproj 파일에서 파싱된 파일들
        vcxproj_files = project_file_manager._parse_vcxproj(project_file_manager.main_vcxproj_path)
        if vcxproj_files:
            logger.info(f"vcxproj에서 파싱된 파일 수: {len(vcxproj_files)}")
            logger.info("샘플 (처음 3개):")
            for i, path in enumerate(list(vcxproj_files)[:3]):
                logger.info(f"  {i+1}. {path}")
        
        # filters 파일에서 파싱된 파일들
        filters_files = project_file_manager._parse_vcxproj_filters(project_file_manager.main_vcxproj_filters_path)
        if filters_files:
            logger.info(f"filters에서 파싱된 파일 수: {len(filters_files)}")
            logger.info("샘플 (처음 3개):")
            for i, path in enumerate(list(filters_files)[:3]):
                logger.info(f"  {i+1}. {path}")
        
        logger.info("=== 경로 정규화 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    test_path_normalization() 