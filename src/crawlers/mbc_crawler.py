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
        self.logger.info(f"Starting crawl for {self.company} via API (Target: {limit})")
        
        # 마지막 수집한 ID 불러오기
        last_id = self.get_last_id()
        if last_id:
            self.logger.info(f"기존 마지막 수집 ID: {last_id}")
        
        params = {
            "callback": "jQuery",
            "opt": "0",
            "keyword": "",
            "page": "1",
            "size": str(limit + 5) # 필터링을 고려하여 조금 더 넉넉히 요청
        }
        
        response = self.fetch_url(self.list_api_url, params=params)
        if not response:
            return []

        # JSONP 응답 처리
        json_str = re.sub(r'^[a-zA-Z0-9_.]+\(|\);?\s*$', '', response.text.strip())
        try:
            data = json.loads(json_str)
            items = data.get('list', [])
        except Exception as e:
            self.logger.error(f"Failed to parse MBC JSON: {e}")
            return []
        
        results = []
        seen_codes = set() # 중복 방지용 고유 코드 집합
        newest_id_candidate = None
        
        for i, item in enumerate(items):
            if len(results) >= limit:
                break
                
            try:
                code = item.get('code')
                
                # [델타 크롤링] 마지막으로 수집했던 ID를 만나면 즉시 중단
                if last_id and str(code) == str(last_id):
                    self.logger.info(f"마지막 수집 지점({last_id})에 도달했습니다. 크롤링을 종료합니다.")
                    break
                
                # 이번 실행에서 가장 최신 ID 저장 (목록의 첫 번째 아이템)
                if i == 0:
                    newest_id_candidate = code

                if not code or code in seen_codes:
                    continue
                    
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
                    image_urls=detail_data.get('images', []),
                    attachments=detail_data.get('attachments', [])
                )
                
                results.append(unified_data)
                seen_codes.add(code)
                self.logger.info(f"[{len(results)}/{limit}] Successfully crawled: {title}")
                
            except Exception as e:
                self.logger.error(f"Error processing MBC item: {e}")
                continue
                
        # 수집된 데이터가 있다면 마지막 수집 ID 업데이트
        if newest_id_candidate:
            self.update_last_id(newest_id_candidate)
            
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
        
        images = []
        # 1. API의 'file' 리스트에서 이미지 추출 (가장 확실함)
        file_list = data.get('file', [])
        for f in file_list:
            if f.get('iskind') == 'P': # Photo/Image 자료형
                file_path = f.get('file_fullpath')
                if file_path:
                    # MBC 이미지 서버 베이스 경로와 결합
                    full_url = self.normalize_url(file_path, "https://mbcinfo.imbc.com/data/")
                    if full_url not in images:
                        images.append(full_url)
        
        # 2. 혹시 본문 HTML 내에도 <img> 태그가 있다면 추출 (보조)
        for img in soup.select('img'):
            img_src = img.get('src')
            if img_src:
                full_url = self.normalize_url(img_src, "https://mbcinfo.imbc.com")
                if full_url not in images:
                    images.append(full_url)
        
        return {
            "content": soup,
            "images": images,
            "attachments": []
        }
