from bs4 import BeautifulSoup
from src.crawlers.base_crawler import BaseCrawler
import urllib.parse
import json
import re

class MbcCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(source_name="Broadcast")
        self.company = "MBC"
        self.list_api_url = "https://mbcinfo.imbc.com/api/press/list"
        self.info_api_url = "https://mbcinfo.imbc.com/api/press/info"
        self.domain = "https://with.mbc.co.kr"

    def crawl(self, limit=1):
        self.logger.info(f"Starting crawl for {self.company} via API")
        
        params = {
            "callback": "jQuery",
            "opt": "0",
            "keyword": "",
            "page": "1",
            "size": str(limit)
        }
        
        response = self.fetch_url(self.list_api_url, params=params)
        if not response:
            return []

        # JSONP 응답 처리 (jQuery(...); 또는 MBCInfoUtil...(...); 제거)
        json_str = re.sub(r'^[a-zA-Z0-9_.]+\(|\);?\s*$', '', response.text.strip())
        try:
            data = json.loads(json_str)
            items = data.get('list', [])
        except Exception as e:
            self.logger.error(f"Failed to parse MBC JSON: {e}")
            return []
        
        results = []
        for item in items[:limit]:
            try:
                code = item.get('code')
                title = item.get('title')
                raw_date = item.get('reg_dt_full') or item.get('reg_dt')
                detail_url = f"{self.domain}/pr/press/view.html?idx={code}"
                
                # 상세 데이터 API 호출
                detail_data = self.parse_detail(code)
                if not detail_data:
                    continue
                
                unified_data = self.make_unified_data(
                    title=title,
                    date=raw_date,
                    content=detail_data['content'],
                    url=detail_url,
                    company=self.company,
                    image_urls=detail_data.get('images', []),
                    attachments=detail_data.get('attachments', [])
                )
                
                results.append(unified_data)
                self.logger.info(f"Successfully crawled: {title}")
                
            except Exception as e:
                self.logger.error(f"Error processing MBC item: {e}")
                continue
                
        return results

    def parse_detail(self, code):
        params = {
            "callback": "jQuery",
            "intIdx": code
        }
        response = self.fetch_url(self.info_api_url, params=params)
        if not response:
            return None
            
        json_str = re.sub(r'^[a-zA-Z0-9_.]+\(|\);?\s*$', '', response.text.strip())
        try:
            data = json.loads(json_str)
            info = data.get('info', {}).get('info', {})
            content_html = info.get('contents')
        except Exception as e:
            self.logger.error(f"Failed to parse MBC detail JSON: {e}")
            return None
            
        if not content_html:
            return None
            
        soup = BeautifulSoup(content_html, 'html.parser')
        
        # 이미지 추출 (상세 API 본문에 포함됨)
        images = []
        for img in soup.select('img'):
            img_src = img.get('src')
            if img_src:
                images.append(urllib.parse.urljoin("https://mbcinfo.imbc.com", img_src))
        
        return {
            "content": soup,
            "images": images,
            "attachments": []
        }
