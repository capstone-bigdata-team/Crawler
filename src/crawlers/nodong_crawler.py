import re
import urllib.parse
from bs4 import BeautifulSoup
from src.crawlers.base_crawler import BaseCrawler

class NodongCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(source_name="Media Union")
        self.domain = "https://media.nodong.org"
        # 사용자 제공 기반 목록 기초 URL
        self.list_base_url = "https://media.nodong.org/news/articleList.html"

    def crawl(self, limit=25):
        self.logger.info(f"Starting crawl for {self.source_name} (Goal: {limit})")
        
        # 마지막 수집한 ID 불러오기
        last_id = self.get_last_id()
        if last_id:
            self.logger.info(f"기존 마지막 수집 ID: {last_id}")
            
        results = []
        seen_urls = set()
        page = 1
        newest_id_candidate = None
        stop_entire_crawl = False
        
        # 목록에서 순차적으로 기사 수집
        while len(results) < limit and not stop_entire_crawl:
            # total 파라미터가 문제를 일으킬 수 있으므로 page와 필수 필터만 우선 사용
            # 사용자 예시: /news/articleList.html?page=3&total=1426&box_idxno=&sc_sub_section_code=S2N14&view_type=sm
            params = {
                "page": str(page),
                "sc_sub_section_code": "S2N14",
                "view_type": "sm"
            }
            list_url = f"{self.list_base_url}?{urllib.parse.urlencode(params)}"
            self.logger.info(f"Scanning page {page}: {list_url}")
            
            response = self.fetch_url(list_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 목록 아이템 선택 (사용자 제공 구조 반영)
            # ul.type2 내의 각 항목을 찾습니다.
            items = soup.select('ul.type2 li') or soup.select('#section-list ul li')
            
            if not items:
                self.logger.warning(f"No items found on page {page}. Stopping.")
                break
                
            found_on_page = 0
            for i, item in enumerate(items):
                if len(results) >= limit:
                    break
                    
                try:
                    # 제목과 링크 추출 (h4.titles a)
                    title_elem = item.select_one('h4.titles a') or item.select_one('a[href*="articleView.html"]')
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    relative_url = title_elem.get('href')
                    detail_url = self.normalize_url(relative_url, self.domain)
                    
                    # [델타 크롤링] idxno 추출 및 중복 체크
                    idxno_match = re.search(r"idxno=(\d+)", relative_url or "")
                    idxno = idxno_match.group(1) if idxno_match else detail_url
                    
                    if last_id and str(idxno) == str(last_id):
                        self.logger.info(f"마지막 수집 지점({last_id})에 도달했습니다. 페이징을 중단합니다.")
                        stop_entire_crawl = True
                        break
                    
                    # 이번 실행에서 가장 최신 ID 저장 (1페이지의 첫 번째 아이템)
                    if page == 1 and newest_id_candidate is None:
                        newest_id_candidate = idxno
                    
                    # 중복 체크
                    if detail_url in seen_urls:
                        continue
                    
                    # 보도자료 섹션이므로 별도 텍스트 필터 없이 수집 (사용자 요청 반영)
                    self.logger.info(f"Adding item: {title}")
                    
                    # 상세 페이지 데이터 수집
                    detail_data = self.parse_detail(detail_url)
                    if not detail_data:
                        continue
                        
                    # 작성자, 날짜 등 추가 정보
                    author = item.select_one('.info.name').get_text(strip=True) if item.select_one('.info.name') else "언론노조"
                    date_elem = item.select_one('.info.dated')
                    raw_date = date_elem.get_text(strip=True) if date_elem else None
                    
                    # 썸네일
                    thumb_elem = item.select_one('.thumb img')
                    thumbnail_url = self.normalize_url(thumb_elem.get('src'), self.domain) if thumb_elem else None
                    image_urls = [thumbnail_url] if thumbnail_url else []
                    image_urls.extend(detail_data.get('image_urls', []))
                    
                    unified_data = self.make_unified_data(
                        title=title,
                        date=raw_date,
                        content=detail_data['content'],
                        url=detail_url,
                        author=author,
                        attachments=detail_data.get('attachments', []),
                        image_urls=list(set(filter(None, image_urls)))
                    )
                    
                    results.append(unified_data)
                    seen_urls.add(detail_url)
                    found_on_page += 1
                    
                except Exception as e:
                    self.logger.error(f"Error parsing item on page {page}: {e}")
                    continue
            
            self.logger.info(f"Page {page} processed. Added {found_on_page} new items. Total: {len(results)}")
            
            # 이번 페이지에서 한 개도 새로 추가하지 못했다면 (중복만 있다면) 중단 방지 위해 페이지는 일단 넘김
            # 단, items 자체가 없으면 위에서 break 됨
            if found_on_page == 0:
                # 실제로 더 이상 새로운 데이터가 없는 경우 (이미 다 긁은 경우) 루프 보호
                if page > 1 and page > (limit // 2) + 5: # 적정 수준 이상 헛돌면 중단
                     self.logger.warning("Too many pages without new items. Stopping.")
                     break

            page += 1
            if page > 30: # 최대 30페이지 정도만 탐색
                break
                
        # 수집된 데이터가 있다면 마지막 수집 ID 업데이트
        if newest_id_candidate:
            self.update_last_id(newest_id_candidate)
            
        return results

    def parse_detail(self, url):
        response = self.fetch_url(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 본문 영역 (#article-view-content-div)
        content_elem = soup.select_one('#article-view-content-div') or soup.select_one('.article-body')
            
        content_text = ""
        image_urls = []
        
        if content_elem:
            # 본문 내 이미지
            for img in content_elem.select('img'):
                src = img.get('src')
                if src:
                    image_urls.append(self.normalize_url(src, url))
            
            # 본문 텍스트
            content_text = content_elem.get_text(separator='\n', strip=True)

        # 첨부파일 (.download-view)
        attachments = []
        download_area = soup.select_one('.download-view') or soup.select_one('.file-list')
        if download_area:
            for link in download_area.select('a'):
                file_url = link.get('href')
                file_name = link.get_text(strip=True)
                if file_url and 'javascript' not in file_url:
                    attachments.append({
                        "file_name": file_name,
                        "download_url": self.normalize_url(file_url, self.domain)
                    })
                    
        return {
            "content": content_text,
            "image_urls": image_urls,
            "attachments": attachments
        }
