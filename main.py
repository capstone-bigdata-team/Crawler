import json
from datetime import datetime
from src.crawlers.kcc_crawler import KccCrawler
from src.crawlers.nsp_crawler import NspCrawler
from src.crawlers.mbc_crawler import MbcCrawler
from src.crawlers.nodong_crawler import NodongCrawler
from src.utils.logger import get_logger

logger = get_logger("Main")

def run_all_crawlers():
    crawlers = [
        KccCrawler(),
        NspCrawler(),
        MbcCrawler(),
        NodongCrawler()
    ]
    
    all_results = []
    
    for crawler in crawlers:
        try:
            logger.info(f"--- Starting {crawler.__class__.__name__} ---")
            results = crawler.crawl(limit=3) # 3개씩 수집
            all_results.extend(results)
            logger.info(f"Collected {len(results)} items from {crawler.source_name}")
        except Exception as e:
            logger.error(f"Critical error in {crawler.__class__.__name__}: {e}")
            
    return all_results

def save_results(results, filename="sampledata/crawled_data.json"):
    import os
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(results)} results to {filename}")

if __name__ == "__main__":
    logger.info("Starting Web Crawling Agent...")
    results = run_all_crawlers()
    
    # 결과 요약 출력
    logger.info(f"Total results collected: {len(results)}")
    
    # 파일 저장
    save_results(results)
    
    # 첫 번째 결과 샘플 출력 (확인용)
    if results:
        print("\n--- SAMPLE RESULT (First Item) ---")
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
