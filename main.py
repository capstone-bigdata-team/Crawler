import argparse
import time
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.blocking import BlockingScheduler

from src.crawlers.kcc_crawler import KccCrawler
from src.crawlers.nsp_crawler import NspCrawler
from src.crawlers.mbc_crawler import MbcCrawler
from src.crawlers.nodong_crawler import NodongCrawler
from src.utils.logger import get_logger

# 로그 설정
logger = get_logger("Main")

# 실행 위치에 상관없이 프로젝트 루트 디렉토리에서 작업하도록 설정
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

def save_to_jsonl(results, filename=None):
    """수집 결과를 JSONL(JSON Lines) 형식으로 통합 저장합니다."""
    if not results:
        return
    
    if filename is None:
        # 날짜별로 파일 생성
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"data/results_{date_str}.jsonl"
        
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'a', encoding='utf-8') as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    logger.info(f"Saved {len(results)} items to {filename}")

def run_crawler_task(crawler_class, limit=50):
    """개별 크롤러를 실행하는 최소 작업 단위"""
    try:
        crawler = crawler_class()
        logger.info(f"--- Starting {crawler.__class__.__name__} (Limit: {limit}) ---")
        # 델타 크롤링이 적용되어 있어, 마지막 지점까지만 안전하게 수집함
        results = crawler.crawl(limit=limit) 
        return results
    except Exception as e:
        logger.error(f"Error in {crawler_class.__name__}: {e}")
        return []

def crawling_job(limit=50):
    """모든 크롤러를 병렬로 실행하는 스케줄러용 잡"""
    logger.info("========== Parallel Crawling Cycle Started ==========")
    start_time = time.time()
    
    crawler_classes = [KccCrawler, NspCrawler, MbcCrawler, NodongCrawler]
    all_new_results = []
    
    # ThreadPool을 사용한 병렬 실행 (EC2 성능 최적화)
    with ThreadPoolExecutor(max_workers=len(crawler_classes)) as executor:
        future_to_crawler = {executor.submit(run_crawler_task, cls, limit): cls for cls in crawler_classes}
        
        for future in as_completed(future_to_crawler):
            crawler_cls = future_to_crawler[future]
            try:
                results = future.result()
                all_new_results.extend(results)
                logger.info(f"Finished {crawler_cls.__name__}: Found {len(results)} new items")
            except Exception as e:
                logger.error(f"{crawler_cls.__name__} generated an exception: {e}")
                
    if all_new_results:
        save_to_jsonl(all_new_results)
    else:
        logger.info("No new items found in this run.")
        
    duration = time.time() - start_time
    logger.info(f"========== Cycle Finished (Duration: {duration:.2f}s) ==========")

def run_manual_mode(limit=25):
    """기존의 순차적 실행 방식 (디버깅/테스트용)"""
    logger.info("Starting Web Crawling Agent (Manual Sequential Mode)...")
    crawler_classes = [KccCrawler, NspCrawler, MbcCrawler, NodongCrawler]
    all_results = []
    
    for cls in crawler_classes:
        results = run_crawler_task(cls, limit=limit)
        all_results.extend(results)
    
    if all_results:
        save_to_jsonl(all_results)
    
    logger.info(f"Manual mode completed. Total results: {len(all_results)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integrated Web Crawling Agent")
    parser.add_argument("--mode", type=str, choices=["manual", "schedule"], default="manual",
                        help="Execution mode: 'manual' for one-time sequential run, 'schedule' for background scheduler")
    parser.add_argument("--interval", type=int, default=10, help="Scheduler interval in minutes (default: 10)")
    parser.add_argument("--limit", type=int, default=25, help="Crawling limit per source (default: 25)")
    
    args = parser.parse_args()
    
    if args.mode == "schedule":
        # 스케줄러 모드 (병렬 실행)
        scheduler = BlockingScheduler()
        # 시작과 동시에 첫 실행이 되도록 next_run_time 설정
        scheduler.add_job(crawling_job, 'interval', minutes=args.interval, 
                          kwargs={'limit': args.limit}, next_run_time=datetime.now())
        
        logger.info(f"Scheduler mode started. Interval: {args.interval} mins. Limit per site: {args.limit}")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler shutting down...")
    else:
        # 매뉴얼 모드 (순차 실행)
        run_manual_mode(limit=args.limit)
