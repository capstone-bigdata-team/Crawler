from bs4 import BeautifulSoup
from src.crawlers.base_crawler import BaseCrawler
import urllib.parse
import re

class KccCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(source_name="KCC")
        self.base_url = "https://www.kcc.go.kr/user.do?boardId=1113&page=A05030000"
        self.domain = "https://www.kcc.go.kr"

    def crawl(self, limit=10):
        self.logger.info(f"Starting crawl for {self.source_name}")
        response = self.fetch_url(self.base_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        # 방통위 목록 테이블 행 추출
        rows = soup.select('table tbody tr')
        
        results = []
        for row in rows[:limit]:
            try:
                # 공지사항 등 번호가 없는 행 제외 (보통 '공지'라고 써있거나 비어있음)
                num_elem = row.select_one('td:nth-child(1)')
                if num_elem and '공지' in num_elem.get_text():
                    continue

                title_elem = row.select_one('td:nth-child(2) a')
                date_elem = row.select_one('td:nth-child(6)')
                
                if not title_elem or not date_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                raw_date = date_elem.get_text(strip=True)
                
                # 상세 페이지 링크 추출 (onclick 속성에서 seq 추출하는 경우도 있음)
                onclick = title_elem.get('onclick', '')
                detail_url = self.base_url # 기본값
                
                match = re.search(r"viewBoard\('(\d+)',", onclick)
                if match:
                    seq = match.group(1)
                    # KCC 상세 페이지 URL 구조 맞춤 (예시 seq를 활용한 파라미터 조합)
                    detail_url = f"{self.domain}/user.do?boardId=1113&page=A05030000&boardSeq={seq}&boardMode=view"
                else:
                    href = title_elem.get('href', '')
                    detail_url = urllib.parse.urljoin(self.base_url, href)

                # 상세 페이지 파싱
                detail_data = self.parse_detail(detail_url)
                if not detail_data:
                    continue
                
                # 상세 데이터 기반으로 첨부파일 텍스트 추출 (가장 적적한 파일 하나 선택)
                attachment_text = self.process_attachments(detail_data.get('attachments', []))
                
                unified_data = self.make_unified_data(
                    title=title,
                    date=raw_date,
                    content=detail_data['content'],
                    url=detail_url,
                    attachments=detail_data.get('attachments', []),
                    attachment_text=attachment_text,
                    department=detail_data.get('department'),
                    author=detail_data.get('author')
                )
                
                results.append(unified_data)
                self.logger.info(f"Successfully crawled: {title}")
                
            except Exception as e:
                self.logger.error(f"Error parsing row: {e}")
                continue
                
        return results

    def parse_detail(self, url):
        response = self.fetch_url(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # KCC 상세 페이지 본문 영역 (보통 table 내 view_content 등)
        content_elem = soup.select_one('.view_content') or soup.find('td', class_='view_content')
        
        if not content_elem:
            # 본문 영역을 못 찾으면 모든 텍스트라도 가져오기 (전략적 대체)
            content_elem = soup.select_one('#contents') or soup.body
            
        # 첨부파일 추출
        attachments_dict = {}
        # KCC는 보통 'file_list' 또는 특정 클래스 내에 i 태그와 a 태그가 있음
        file_links = soup.select('a[onclick*="fileDownload"], a[href*="fileDownload"], a.file_download')
        
        for link in file_links:
            onclick = link.get('onclick', '')
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # download_url 결정
            download_url = None
            
            # jsessionid 및 쿼리 파라미터 정규화 (dedup용)
            clean_href = re.sub(r';jsessionid=[a-zA-Z0-9.-]+', '', href)
            
            file_match = re.search(r"fileDownload\('(\d+)',\s*'(.+?)'\)", onclick)
            if file_match:
                file_id = file_match.group(1)
                file_name = file_match.group(2)
                download_url = f"{self.domain}/fileDownload.do?fileId={file_id}"
            elif 'download.do' in clean_href or 'download' in clean_href.lower():
                download_url = urllib.parse.urljoin(self.domain, clean_href)
                # URL에서 파일명을 추출하려 시도하거나 텍스트 사용
                file_name = text
            elif clean_href and any(ext in clean_href.lower() for ext in ['.hwp', '.pdf', '.hwpx', '.docx']):
                download_url = urllib.parse.urljoin(self.domain, clean_href)
                file_name = text
            
            if download_url:
                # URL에서 jsessionid를 제거한 버전을 키로 사용
                dedup_key = re.sub(r';jsessionid=[a-zA-Z0-9.-]+', '', download_url)
                
                # 같은 URL이 이미 있으면, 이름에 확장자가 포함된 것을 우선 채택
                has_ext = any(file_name.lower().endswith(e) for e in ['.hwp', '.pdf', '.hwpx', '.docx'])
                
                if dedup_key not in attachments_dict or (not any(attachments_dict[dedup_key]['file_name'].lower().endswith(e) for e in ['.hwp', '.pdf', '.hwpx', '.docx']) and has_ext):
                    attachments_dict[dedup_key] = {
                        "file_name": file_name if file_name else "attachment",
                        "download_url": download_url,
                        "extracted_text": None
                    }
        
        attachments = list(attachments_dict.values())
        
        # 담당부서, 작성자 추출 (보통 th-td 또는 dt-dd 구조)
        department = None
        author = None
        for label in soup.find_all(['th', 'dt', 'span', 'strong']):
            text = label.get_text(strip=True)
            if '담당부서' in text:
                val_elem = label.find_next_sibling(['td', 'dd', 'span'])
                if val_elem: department = val_elem.get_text(strip=True)
            elif '작성자' in text:
                val_elem = label.find_next_sibling(['td', 'dd', 'span'])
                if val_elem: author = val_elem.get_text(strip=True)
        
        return {
            "content": content_elem,
            "attachments": attachments,
            "department": department,
            "author": author
        }
