import os
import re
import json
import hashlib
import urllib.parse
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from src.utils.logger import get_logger
from src.utils.file_extractor import FileExtractor

class BaseCrawler:
    def __init__(self, source_name):
        self.source_name = source_name
        self.logger = get_logger(source_name)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        self.extractor = FileExtractor()

    def format_date(self, raw_date):
        """다양한 날짜 형식을 YYYY-MM-DD로 변환"""
        if not raw_date:
            return None
            
        # 숫자만 추출 (예: 2026.03.18, 03.18, 04.07 17:05)
        nums = re.findall(r'\d+', str(raw_date))
        
        if len(nums) >= 3:
            # 4개 이상의 숫자가 있고 첫 번째가 1~12인 경우 (예: 04.07 17:05)
            # MM.DD HH:mm 형식으로 간주
            if len(nums) >= 4 and int(nums[0]) <= 12 and int(nums[1]) <= 31:
                month, day = nums[0], nums[1]
                year = datetime.now().year
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                
            year, month, day = nums[0], nums[1], nums[2]
            # 연도가 2자리인 경우 (예: 26 -> 2026)
            if len(year) == 2:
                year = "20" + year
            try:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except (ValueError, TypeError):
                return None
        elif len(nums) == 2:
            # 월, 일만 있는 경우 (예: 03.18) -> 현재 연도 사용
            month, day = nums[0], nums[1]
            year = datetime.now().year
            try:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except (ValueError, TypeError):
                return None
        
        return None

    def clean_text(self, text):
        """기본 텍스트 정제"""
        if not text:
            return ""
        
        if hasattr(text, 'get_text'):
            # 본문 추출 전 불필요한 요소 제거 (BS4 전용)
            trash_tags = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'button']
            for tag in trash_tags:
                for match in text.find_all(tag):
                    match.decompose()
            
            # 특정 클래스/아이디 기반의 상용구 영역 제거 (필요 시 확장 가능)
            trash_selectors = ['.nav', '.footer', '.header', '.sidebar', '.ad', '#nav', '#footer']
            for selector in trash_selectors:
                for match in text.select(selector):
                    match.decompose()

            text = text.get_text(separator=' ', strip=True)
            
        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', str(text)).strip()
        # 특수 문자가 연달아 나오는 경우 정리 (선택적)
        text = re.sub(r'\n+', '\n', text)
        return text

    def make_unified_data(self, title, date, content, url, attachments=None, attachment_text=None, 
                          department=None, author=None, summary=None, image_urls=None, 
                          hashtags=None, references=None):
        """JSON v1 규격에 맞게 데이터 구조화"""
        formatted_date = self.format_date(date)
        
        # ID 생성 (원본 URL 해시 + 날짜)
        doc_id = None
        if url:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            clean_date = formatted_date.replace('-', '') if formatted_date else "00000000"
            doc_id = f"{self.source_name.lower()}_{clean_date}_{url_hash}"

        return {
            "doc_id": doc_id,
            "source": self.source_name,
            "department": department,
            "author": author,
            "title": title.strip() if title else None,
            "date": formatted_date,
            "summary": self.clean_text(summary) if summary else None,
            "content_text": self.clean_text(content) if content else None,
            "attachment_text": attachment_text, # 첨부파일에서 추출한 텍스트
            "detail_url": url,
            "image_urls": image_urls if image_urls else [],
            "attachments": attachments if attachments else [],
            "hashtags": hashtags if hashtags else [],
            "references": references if references else [],
            "crawled_at": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }

    def fetch_url(self, url, method="GET", **kwargs):
        """공통 HTTP 요청 함수"""
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    def download_file(self, url, save_path):
        """파일 다운로드 함수"""
        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            self.logger.error(f"Failed to download file from {url}: {e}")
            return False

    def process_attachments(self, attachments):
        """첨부파일 리스트 중 적절한 파일 하나를 선택하여 텍스트 추출 (순차적 시도)"""
        if not attachments:
            return None
            
        # 우선순위 정의: PDF > DOCX > HWPX > HWP
        priority = {'.pdf': 1, '.docx': 2, '.hwpx': 3, '.hwp': 4}
        
        # 확장자별로 분류 및 정렬
        valid_attachments = []
        for att in attachments:
            url = att.get('download_url')
            name = att.get('file_name', '').strip()
            ext = os.path.splitext(name)[1].lower()
            if not ext and url:
                ext = os.path.splitext(url.split('?')[0])[1].lower()
            
            p = priority.get(ext, 99)
            valid_attachments.append((p, att, ext))
            
        if not valid_attachments:
            return None
            
        # 가장 높은 우선순위부터 차례대로 시도
        valid_attachments.sort(key=lambda x: x[0])
        
        for p, att, ext in valid_attachments:
            if p == 99:
                continue
            
            download_url = att.get('download_url')
            file_name = att.get('file_name', 'attachment')
            # temp 폴더를 명시적으로 지정하여 경로 문제 해결
            safe_source = self.source_name.replace(" ", "_").lower()
            temp_path = os.path.join("temp", f"tmp_{safe_source}_{abs(hash(download_url))}{ext}")
            
            self.logger.info(f"Attempting extraction from: {file_name} ({ext})")
            
            if self.download_file(download_url, temp_path):
                try:
                    extracted_text = FileExtractor.extract(temp_path)
                    if extracted_text and len(extracted_text.strip()) > 10:
                        self.logger.info(f"Successfully extracted {len(extracted_text)} characters from {file_name}")
                        return extracted_text
                    else:
                        self.logger.warning(f"Extracted text from {file_name} is too short or empty")
                except Exception as e:
                    self.logger.error(f"Error during extraction from {file_name}: {e}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                self.logger.error(f"Failed to download attachment: {file_name}")
        
        return None
