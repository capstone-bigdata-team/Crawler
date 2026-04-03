import os
import fitz  # PyMuPDF
import olefile
import zlib
import re
from src.utils.logger import get_logger

logger = get_logger("FileExtractor")

class FileExtractor:
    @staticmethod
    def extract_text_from_pdf(file_path):
        """PDF 파일에서 텍스트 추출"""
        try:
            text = ""
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting PDF: {e}")
            return None

    @staticmethod
    def extract_text_from_hwp(file_path):
        """HWP 파일에서 PrvText 스트림 추출 (가장 간단한 텍스트 추출 방식)"""
        try:
            if not olefile.isOleFile(file_path):
                return None
                
            ole = olefile.OleFileIO(file_path)
            # HWP5 기준 PrvText 스트림에 텍스트 요약이 들어있는 경우가 많음
            if ole.exists('PrvText'):
                data = ole.openstream('PrvText').read()
                # UTF-16LE 인코딩된 경우가 많음
                text = data.decode('utf-16-le', errors='ignore')
                # 제어 문자 및 불필요한 태그 제거
                text = re.sub(r'<.+?>', '', text)
                return text.strip()
            
            # PrvText가 없는 경우 BodyText 섹션들을 순회하며 추출해야 함 (복잡)
            # 여기선 기본적으로 PrvText를 시도하고 실패 시 로그
            ole.close()
            return None
        except Exception as e:
            logger.error(f"Error extracting HWP: {e}")
            return None

    @classmethod
    def extract(cls, file_path):
        """확장자에 따른 동적 추출 호출"""
        if not os.path.exists(file_path):
            return None
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return cls.extract_text_from_pdf(file_path)
        elif ext == '.hwp':
            return cls.extract_text_from_hwp(file_path)
        else:
            logger.warning(f"Unsupported file extension: {ext}")
            return None
