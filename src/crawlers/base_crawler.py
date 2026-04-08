import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import os
from src.utils.logger import get_logger
from src.utils.file_extractor import FileExtractor

class BaseCrawler:
    def __init__(self, source_name):
        self.source_name = source_name
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def clean_text(self, raw_html):
        """BeautifulSoup으로 태그를 제거하고 순수 텍스트만 추출"""
        if not raw_html:
            return None
        
        soup = BeautifulSoup(str(raw_html), 'html.parser')
        
        # 스크립트, 스타일 태그 제거
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
            
        text = soup.get_text(separator=' ')
        # 연속된 공백 및 줄바꿈 정규화
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text

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

    def make_unified_data(self, title, date, content, url, doc_id=None, company=None, summary=None, department=None, author=None, image_urls=None, attachments=None, hashtags=None, references=None, attachment_text=None):
        """통합 JSON 규격 v1으로 데이터 변환"""
        formatted_date = self.format_date(date)
        
        # doc_id 자동 생성 (없는 경우)
        if not doc_id:
            # 소스_날짜_해시/고유값 (여기선 간단히 url 해시 활용 가능)
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            clean_date = formatted_date.replace('-', '') if formatted_date else "00000000"
            doc_id = f"{self.source_name.lower()}_{clean_date}_{url_hash}"

        return {
            "doc_id": doc_id,
            "source": self.source_name,
            "company": company,
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
        """첨부파일 리스트 중 최적의 파일 하나를 선택하여 텍스트 추출"""
        if not attachments:
            return None
            
        # 우선순위 정의: PDF > DOCX > HWPX > HWP
        priority = {'.pdf': 1, '.docx': 2, '.hwpx': 3, '.hwp': 4}
        
        # 확장자별로 분류 및 정렬
        valid_attachments = []
        for att in attachments:
            url = att.get('download_url')
            name = att.get('file_name', '')
            ext = os.path.splitext(name)[1].lower()
            if not ext and url:
                ext = os.path.splitext(url.split('?')[0])[1].lower()
            
            p = priority.get(ext, 99)
            valid_attachments.append((p, att, ext))
            
        if not valid_attachments:
            return None
            
        # 가장 높은 우선순위 파일 선택
        valid_attachments.sort(key=lambda x: x[0])
        best_p, best_att, best_ext = valid_attachments[0]
        
        if best_p == 99:
            self.logger.warning(f"No supported attachment types found among {len(attachments)} files")
            return None

        # 다운로드 및 추출
        download_url = best_att.get('download_url')
        temp_path = f"tmp_download_{self.source_name}_{hash(download_url)}{best_ext}"
        
        extracted_text = None
        if self.download_file(download_url, temp_path):
            self.logger.info(f"Extracting text from {best_att.get('file_name')} ({best_ext})")
            extracted_text = FileExtractor.extract(temp_path)
            
            # 파일 삭제
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        return extracted_text
