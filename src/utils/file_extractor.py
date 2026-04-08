import os
import fitz  # PyMuPDF
import olefile
import zlib
import re
import zipfile
import xml.etree.ElementTree as ET
from docx import Document
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
    def extract_text_from_docx(file_path):
        """DOCX 파일에서 텍스트 추출"""
        try:
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return "\n".join(full_text).strip()
        except Exception as e:
            logger.error(f"Error extracting DOCX: {e}")
            return None

    @staticmethod
    def extract_text_from_hwpx(file_path):
        """HWPX 파일(ZIP)에서 텍스트 추출"""
        try:
            text = []
            with zipfile.ZipFile(file_path, 'r') as z:
                # Contents/section0.xml, section1.xml ... 에 본문이 들어있음
                sections = [f for f in z.namelist() if f.startswith('Contents/section') and f.endswith('.xml')]
                for section in sorted(sections):
                    with z.open(section) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        # hp:t 태그 스트링 추출 (네임스페이스 무시하고 간단히 찾기)
                        for elem in root.iter():
                            if elem.tag.endswith('}t') and elem.text:
                                text.append(elem.text)
            return "\n".join(text).strip()
        except Exception as e:
            logger.error(f"Error extracting HWPX: {e}")
            return None

    @staticmethod
    def extract_text_from_hwp(file_path):
        """HWP 파일에서 PrvText 스트림 추출"""
        try:
            if not olefile.isOleFile(file_path):
                return None
                
            ole = olefile.OleFileIO(file_path)
            if ole.exists('PrvText'):
                data = ole.openstream('PrvText').read()
                text = data.decode('utf-16-le', errors='ignore')
                text = re.sub(r'<.+?>', '', text)
                ole.close()
                return text.strip()
            
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
        elif ext == '.docx':
            return cls.extract_text_from_docx(file_path)
        elif ext == '.hwpx':
            return cls.extract_text_from_hwpx(file_path)
        elif ext == '.hwp':
            return cls.extract_text_from_hwp(file_path)
        else:
            logger.warning(f"Unsupported file extension: {ext}")
            return None
