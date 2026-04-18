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

    def crawl(self, limit=10):
        self.logger.info(f"Starting crawl for {self.source_name}")
        
        payload = {
            "collection": "trend",
            "query": "",
            "listCount": str(limit),
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
        for item in items[:limit]:
            try:
                control_no = item.get('latestTrendControlNo')
                title = item.get('title')
                publish_date = item.get('publishDt')
                
                if not control_no:
                    continue
                
                detail_url = f"{self.detail_base_url}?latestTrendControlNo={control_no}&listChk=list"
                
                # 상세 페이지 파싱 (NSP는 CSR성향이 있지만 상세는 SSR인 경우가 많음)
                detail_data = self.parse_detail(detail_url)
                
                # NSP 특화: 해시태그 수집 (summary 필드 등에 활용 가능)
                hashtags_str = item.get('hashtag', '')
                hashtag_list = [t.strip() for t in hashtags_str.split(',') if t.strip()] if hashtags_str else []
                
                # 첨부파일 텍스트 추출 (주로 PDF)
                attachment_text = self.process_attachments(detail_data.get('attachments', [])) if detail_data else None
                
                unified_data = self.make_unified_data(
                    title=title,
                    date=publish_date,
                    content=detail_data['content'] if detail_data else None,
                    url=detail_url,
                    summary=hashtags_str if hashtags_str else None,
                    hashtags=hashtag_list,
                    references=[],
                    attachments=detail_data.get('attachments', []) if detail_data else [],
                    attachment_text=attachment_text,
                    image_urls=detail_data.get('image_urls', []) if detail_data else []
                )

                results.append(unified_data)
                self.logger.info(f"Successfully crawled: {title}")
                
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                continue
                
        return results

    def parse_detail(self, url):
        response = self.fetch_url(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상세 본문 추출 (네이버 블로그 스타일의 에디터 사용 시 .se-contents)
        content_elem = soup.select_one('.post_cont_area_editor') or soup.select_one('.se-viewer')
        
        if not content_elem:
            content_elem = soup.select_one('.contents') or soup.find('div', class_='view_cont')

        # 첨부파일 (NSP 상세 페이지 하단에 다운로드 버튼 등 존재)
        attachments = []
        # NSP는 보통 PDF 다운로드 링크가 명시적임, 또는 '참고자료' 섹션에 존재
        file_links = soup.select('a[href*="fileDownload"], a[href*=".pdf"], a[href*="AttachFileDown"], ul.ref_list_area a.data')
        
        # 중복 방지를 위한 셋(Set)
        seen_urls = set()
        
        for link in file_links:
            href = link.get('href', '')
            if href:
                full_url = self.normalize_url(href, url)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                
                name = link.get_text(strip=True) or "Download"
                # 외부 링크인지 내부 다운로드인지 판별하여 이름 보강 (필요 시)
                attachments.append({
                    "file_name": name,
                    "download_url": full_url,
                    "extracted_text": None
                })
        
        # 이미지 추출 (본문 내 이미지)
        image_urls = []
        if content_elem:
            for img in content_elem.select('img'):
                # src 외에도 data-src 등 지연 로딩 속성 체크
                img_src = img.get('src') or img.get('data-src') or img.get('original-src')
                if img_src:
                    full_image_url = self.normalize_url(img_src, url)
                    if full_image_url not in image_urls:
                        image_urls.append(full_image_url)
        
        return {
            "content": content_elem,
            "attachments": attachments,
            "image_urls": image_urls
        }
