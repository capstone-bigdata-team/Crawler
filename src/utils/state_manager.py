import os
import json
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger("StateManager")

class StateManager:
    """
    크롤러의 수집 진행 상태를 소스별로 독립된 파일에 기록하고 복원하는 클래스입니다.
    파일 경로는 data/states/state_{source_name}.json 형식을 사용합니다.
    """
    STATE_DIR = "data/states"

    @classmethod
    def _get_file_path(cls, source_name):
        """소스 이름에 따른 개별 상태 파일 경로를 반환합니다."""
        safe_name = source_name.lower().replace(" ", "_")
        return os.path.join(cls.STATE_DIR, f"state_{safe_name}.json")

    @classmethod
    def get_last_id(cls, source_name):
        """특정 소스의 마지막 수집 ID를 가져옵니다."""
        file_path = cls._get_file_path(source_name)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('last_id')
        except Exception as e:
            logger.error(f"[{source_name}] 상태 읽기 오류: {e}")
            return None

    @classmethod
    def update_last_id(cls, source_name, last_id):
        """특정 소스의 마지막 수집 ID를 개별 파일에 업데이트합니다."""
        file_path = cls._get_file_path(source_name)
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'last_id': last_id, 
                    'updated_at': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"[{source_name}] 개별 상태 저장 완료: {last_id}")
        except Exception as e:
            logger.error(f"[{source_name}] 상태 저장 오류: {e}")
