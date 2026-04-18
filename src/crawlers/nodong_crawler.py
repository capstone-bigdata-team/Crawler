from bs4 import BeautifulSoup
from src.crawlers.base_crawler import BaseCrawler
import urllib.parse

class NodongCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(source_name="Media Union")
        # 성명/논평 게시판 URL
        self.base_url = "https://media.nodong.org/news/articleList.html?sc_sub_section_code=S2N14&view_type=sm"
        self.domain = "https://media.nodong.org"

    def crawl(self, limit=10):
        self.logger.info(f"Starting crawl for {self.source_name}")
        response = self.fetch_url(self.base_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        # 리스트 영역 정확한 선택자로 교정 (#section-list ul li)
        items = soup.select('#section-list ul li')
        
        results = []
        for item in items:
            if len(results) >= limit:
                break
                
            try:
                category_elem = item.select_one('.info.category')
                category = category_elem.get_text(strip=True) if category_elem else ""
                
                # S2N14 리스트 내에서도 '보도자료' 카테고리가 명시된 것만 수집 (성명, 미디어위키 등 제외)
                # 만약 '성명'도 포함하고 싶다면 아래 조건을 조정해야 함
                if "보도자료" not in category:
                    continue
                
                title_elem = item.select_one('.titles a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                relative_url = title_elem.get('href')
                detail_url = self.normalize_url(relative_url, self.base_url)
                
                summary_elem = item.select_one('.lead a')
                summary = summary_elem.get_text(strip=True) if summary_elem else None
                
                # 날짜 및 작성자 추출
                author = item.select_one('.info.name').get_text(strip=True) if item.select_one('.info.name') else None
                date_elem = item.select_one('.info.dated')
                raw_date = date_elem.get_text(strip=True) if date_elem else None
                    
                thumb_elem = item.select_one('.thumb img')
                thumbnail_url = self.normalize_url(thumb_elem.get('src'), self.domain) if thumb_elem else None
                image_urls = [thumbnail_url] if thumbnail_url else []

                # 상세 페이지 파싱
                detail_data = self.parse_detail(detail_url)
                
                # 첨부파일 처리
                attachment_text = self.process_attachments(detail_data.get('attachments', [])) if detail_data else None

                # 기사 본문 이미지 추가
                if detail_data and detail_data.get('image_urls'):
                    image_urls.extend([url for url in detail_data['image_urls'] if url not in image_urls])

                unified_data = self.make_unified_data(
                    title=title,
                    date=raw_date,
                    content=detail_data['content'] if detail_data else None,
                    url=detail_url,
                    summary=summary,
                    author=author,
                    image_urls=image_urls,
                    attachments=detail_data.get('attachments', []) if detail_data else [],
                    attachment_text=attachment_text
                )

                results.append(unified_data)
                self.logger.info(f"Successfully crawled: {title}")
                
            except Exception as e:
                self.logger.error(f"Error parsing item: {e}")
                continue
                
        return results

    def parse_detail(self, url):
        response = self.fetch_url(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        content_elem = soup.select_one('#article-view-content-div')
        
        if not content_elem:
            content_elem = soup.select_one('.article-body') or soup.find('div', id='article-view-content-div')

        # 언론노조는 보통 성명서 본문에 텍스트가 위주이며 첨부파일은 드묾
        attachments = []
        
        # 이미지 추출 (본문 내 이미지)
        image_urls = []
        if content_elem:
            for img in content_elem.select('img'):
                img_src = img.get('src')
                if img_src:
                    full_image_url = self.normalize_url(img_src, url)
                    if full_image_url not in image_urls:
                        image_urls.append(full_image_url)
        
        return {
            "content": content_elem,
            "attachments": attachments,
            "image_urls": image_urls
        }
