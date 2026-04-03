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
        # h4.titles를 가진 요소를 먼저 찾고, 그 부모(보통 li 또는 div)를 기사 블록으로 간주
        titles = soup.select('h4.titles')
        items = [t.find_parent('li') or t.find_parent('div') for t in titles if t.find_parent()]
        
        if not items:
            items = soup.select('ul.article-list li') or soup.select('div.list-block')
        
        results = []
        for item in items[:limit]:
            try:
                title_elem = item.select_one('h4.titles a')
                summary_elem = item.select_one('p.lead a')
                author = None
                bylines = item.select('span.byline em')
                if bylines:
                    if len(bylines) >= 2:
                        author = bylines[0].get_text(strip=True)
                        date_elem = bylines[-1]
                    else:
                        date_elem = bylines[0]
                else:
                    date_elem = None
                    
                thumb_elem = item.select_one('a.thumb img')
                
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                summary = summary_elem.get_text(strip=True) if summary_elem else None
                raw_date = date_elem.get_text(strip=True) if date_elem else None
                relative_url = title_elem.get('href')
                detail_url = urllib.parse.urljoin(self.base_url, relative_url)
                
                # 썸네일 이미지 URL (attachments나 별도 필드로 유지 가능)
                thumbnail_url = urllib.parse.urljoin(self.domain, thumb_elem.get('src')) if thumb_elem else None
                image_urls = [thumbnail_url] if thumbnail_url else []

                # 상세 페이지 파싱 (이미 목록에서 많은 정보를 얻었으므로 본문 위주로)
                detail_data = self.parse_detail(detail_url)
                
                unified_data = self.make_unified_data(
                    title=title,
                    date=raw_date,
                    content=detail_data['content'] if detail_data else None,
                    url=detail_url,
                    summary=summary,
                    author=author,
                    image_urls=image_urls,
                    attachments=detail_data.get('attachments', []) if detail_data else []
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
