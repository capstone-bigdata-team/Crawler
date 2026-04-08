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
        # 언론노조 목록 아이템 추출 (셀렉터 보강)
        titles = soup.select('h4.titles')
        items = [t.find_parent('li') or t.find_parent('div') for t in titles if t.find_parent()]
        
        if not items:
            items = soup.select('ul.article-list li') or soup.select('div.list-block')
        
        results = []
        for item in items[:limit]:
            try:
                title_elem = item.select_one('h4.titles a')
                summary_elem = item.select_one('p.lead a')
                
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                relative_url = title_elem.get('href')
                detail_url = urllib.parse.urljoin(self.base_url, relative_url)
                summary = summary_elem.get_text(strip=True) if summary_elem else None
                
                # 날짜 및 작성자 추출 (신규 셀렉터)
                author = item.select_one('em.info.name').get_text(strip=True) if item.select_one('em.info.name') else None
                date_elem = item.select_one('em.info.dated')
                raw_date = date_elem.get_text(strip=True) if date_elem else None
                    
                thumb_elem = item.select_one('a.thumb img')
                thumbnail_url = urllib.parse.urljoin(self.domain, thumb_elem.get('src')) if thumb_elem else None
                image_urls = [thumbnail_url] if thumbnail_url else []

                # 상세 페이지 파싱
                detail_data = self.parse_detail(detail_url)
                
                # 첨부파일 처리
                attachment_text = self.process_attachments(detail_data.get('attachments', [])) if detail_data else None

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
        
        return {
            "content": content_elem,
            "attachments": attachments
        }
