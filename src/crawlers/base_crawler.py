import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from src.utils.logger import get_logger

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
            
        # 숫자만 추출 (예: 2026.03.18, 2026/03/18, 2026-03-18, 26.03.18)
        nums = re.findall(r'\d+', str(raw_date))
        
        if len(nums) >= 3:
            year, month, day = nums[0], nums[1], nums[2]
            
            # 연도가 2자리인 경우 (예: 26 -> 2026)
            if len(year) == 2:
                year = "20" + year
                
            try:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except (ValueError, TypeError):
                return None
        
        return None

    def make_unified_data(self, title, date, content, url, doc_id=None, company=None, summary=None, department=None, author=None, image_urls=None, attachments=None, hashtags=None, references=None):
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
