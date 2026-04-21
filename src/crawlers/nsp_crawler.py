import json
from bs4 import BeautifulSoup
from src.crawlers.base_crawler import BaseCrawler
import urllib.parse

class NspCrawler(BaseCrawler):
    def __init__(self):
        # 국립국회도서관은 'National Assembly' 소스로 설정
        super().__init__(source_name="National Assembly")
        self.api_url = "https://nsp.nanet.go.kr/search/searchInnerList.do"
        self.detail_base_url = "https://nsp.nanet.go.kr/trend/latest/detail.do"

    def crawl(self, limit=25):
        self.logger.info(f"Starting crawl for {self.source_name} (Goal: {limit})")
        
        # 마지막 수집한 ID 불러오기
        last_id = self.get_last_id()
        if last_id:
            self.logger.info(f"기존 마지막 수집 ID: {last_id}")
        
        payload = {
            "collection": "trend",
            "query": "",
            "listCount": str(limit + 5), # 필터링 대비 약간 넉넉히
            "startCount": 0
        }
        
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://nsp.nanet.go.kr/trend/latest/list.do"
        }

        response = self.fetch_url(self.api_url, method="POST", json=payload, headers=headers)
        if not response:
            return []

        try:
            data = response.json()
            items = data.get('searchResultMap', {}).get('searchResultList', [])
        except Exception as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            return []
        
        results = []
        seen_ids = set() # 중복 방지용 고유 번호 (idxno 역할)
        newest_id_candidate = None
        
        for i, item in enumerate(items):
            if len(results) >= limit:
                break
                
            try:
                # 고유 번호 추출
                control_no = item.get('latestTrendControlNo')
                
                # [델타 크롤링] 마지막으로 수집했던 ID를 만나면 즉시 중단
                if last_id and str(control_no) == str(last_id):
                    self.logger.info(f"마지막 수집 지점({last_id})에 도달했습니다. 크롤링을 종료합니다.")
                    break
                
                # 이번 실행에서 가장 최신 ID 저장 (목록의 첫 번째 아이템)
                if i == 0:
                    newest_id_candidate = control_no

                if not control_no or control_no in seen_ids:
                    continue
                
                title = item.get('title')
                publish_date = item.get('publishDt')
                detail_url = f"{self.detail_base_url}?latestTrendControlNo={control_no}&listChk=list"
                
                # 상세 페이지로 이동하여 크롤링
                detail_data = self.parse_detail(detail_url)
                if not detail_data:
                    continue
                
                # 해시태그 수집
                hashtags_str = item.get('hashtag', '')
                hashtag_list = [t.strip() for t in hashtags_str.split(',') if t.strip()] if hashtags_str else []
                
                # 첨부파일 텍스트 추출
                attachment_text = self.process_attachments(detail_data.get('attachments', []))
                
                unified_data = self.make_unified_data(
                    title=title,
                    date=publish_date,
                    content=detail_data['content'],
                    url=detail_url,
                    summary=hashtags_str if hashtags_str else None,
                    hashtags=hashtag_list,
                    attachments=detail_data.get('attachments', []),
                    attachment_text=attachment_text,
                    image_urls=detail_data.get('image_urls', [])
                )

                results.append(unified_data)
                seen_ids.add(control_no)
                self.logger.info(f"[{len(results)}/{limit}] Successfully crawled: {title}")
                
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                continue
                
        # 수집된 데이터가 있다면 마지막 수집 ID 업데이트
        if newest_id_candidate:
            self.update_last_id(newest_id_candidate)
            
        return results

    def parse_detail(self, url):
        response = self.fetch_url(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상세 본문 추출
        content_elem = soup.select_one('.post_cont_area_editor') or soup.select_one('.se-viewer')
        if not content_elem:
            content_elem = soup.select_one('.contents') or soup.select_one('.view_cont')
            
        content_text = ""
        image_urls = []
        
        if content_elem:
            # 텍스트 추출
            content_text = content_elem.get_text(separator='\n', strip=True)
            # 이미지 추출
            for img in content_elem.select('img'):
                img_src = img.get('src') or img.get('data-src')
                if img_src:
                    image_urls.append(self.normalize_url(img_src, url))

        # 첨부파일 추출
        attachments = []
        file_links = soup.select('a[href*="fileDownload"], a[href*=".pdf"], ul.ref_list_area a.data')
        
        seen_file_urls = set()
        for link in file_links:
            href = link.get('href', '')
            if href:
                full_url = self.normalize_url(href, url)
                if full_url in seen_file_urls:
                    continue
                seen_file_urls.add(full_url)
                
                attachments.append({
                    "file_name": link.get_text(strip=True) or "Download",
                    "download_url": full_url
                })
        
        return {
            "content": content_text,
            "attachments": attachments,
            "image_urls": image_urls
        }
