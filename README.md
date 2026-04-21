# 🕸️ Intelligent Parallel Crawling Agent

본 프로젝트는 EC2 환경에서 24시간 가동되며, 4개의 주요 뉴스 및 보도자료 사이트(KCC, NSP, MBC, Nodong)에서 최신 데이터를 지능적으로 수집하는 병렬 크롤링 에이전트 시스템입니다.

---

## 1. 크롤러 구현 전략 (Crawler Implementation)

시스템은 **유지보수성과 확장성**을 최우선으로 고려하여 객체 지향 프로그래밍(OOP) 구조로 설계되었습니다.

*   **추상화된 BaseCrawler**: 모든 크롤러의 공통 기능을 `BaseCrawler` 클래스에 정의했습니다. 이를 통해 새로운 수집 대상을 추가할 때 코드 중복 없이 핵심 파싱 로직에만 집중할 수 있습니다.
*   **사이트별 맞춤형 파싱**: 
    - **API 기반**: MBC 등 API를 제공하는 소스는 빠른 속도와 정확도를 보장하는 JSON 파싱 방식을 사용합니다.
    - **HTML 기반**: KCC, Nodong, nsp 등 정적/동적 웹 페이지는 `BeautifulSoup4`를 활용해 정밀한 선택자(Selector) 기반으로 데이터를 추출합니다.
*   **문서 텍스트 추출 (File Extraction)**: 단순 텍스트 수집에 그치지 않고, 첨부된 PDF, HWP, DOCX 파일을 실시간으로 읽어 본문을 추출하는 기능을 탑재하였습니다.

---

## 2. 스케줄러 작동 원리 및 설계 시 고려사항 (Scheduler & Considerations)

스케줄러(`main.py --mode schedule`)는 단순히 시간마다 실행되는 것을 넘어, **안정성과 효율성**을 위해 다음 요소들을 깊이 있게 고려했습니다.

### 🚀 병렬 실행 (Parallelism)
- **고려사항**: 단일 스레드로 4개 사이트를 순차 수집할 경우 전체 소요 시간이 길어지고 네트워크 리소스가 비효율적으로 사용됩니다.
- **해결책**: `ThreadPoolExecutor`를 사용하여 모든 크롤러를 동시에 가동합니다. EC2(배포시)의 멀티 코어 자원을 최대한 활용하여 전체 수집 시간을 수배 이상 단축했습니다.

### 🎯 델타 크롤링 (Delta Crawling)
- **고려사항**: 실행할 때마다 모든 데이터를 다시 긁는 것은 타겟 사이트에 부하를 주고, 데이터 중복 처리 이슈를 발생시킵니다.
- **해결책**: 각 사이트의 마지막 수집 문서 ID를 `data/states/` 폴더에 소스별로 독립 저장합니다. 실행 시 이를 대조하여 **새로 올라온 데이터가 발견되는 즉시 수집을 시작하고, 마지막 지점에 도달하면 즉시 종료**하는 지능형 로직을 구현했습니다.

### 🛡️ 차단 방지 (Anti-Blocking)
- **고려사항**: 짧은 시간에 많은 요청을 보내면 IP가 차단되거나 봇으로 감지될 위험이 있습니다.
- **해결책**: 
    - **User-Agent 로테이션**: 요청마다 다양한 브라우저 정보로 위장합니다.
    - **랜덤 지연(Random Delay)**: 요청 사이에 1~3초의 가변적 휴식 시간을 주어 사람이 접속하는 것과 같은 패턴을 유지합니다.

---

## 3. 프로젝트 파일 구조 설명 (File Description)

```bash
.
├── main.py                 # [Entry Point] 수동/자동 모드를 제어하는 통합 진입점
├── requirements.txt        # 프로젝트 실행을 위한 필수 라이브러리 목록
├── scripts/
│   └── run_background.sh   # EC2 백그라운드 구동 스크립트 (nohup 활용)
├── src/
│   ├── crawlers/
│   │   ├── base_crawler.py # 크롤러 공통 로직 및 인터페이스 정의
│   │   ├── kcc_crawler.py  # 방송통신위원회 보도자료 수집 로직
│   │   └── ...             # 기타 소스별 크롤러 (Nsp, Mbc, Nodong)
│   └── utils/
│       ├── state_manager.py# 소스별 독립적 상태(ID) 저장 및 관리 유틸리티 # 어디까지 크롤링 했는지 기록
│       ├── file_extractor.py# 첨부파일(PDF, HWP 등) 본문 추출기
│       └── logger.py       # 시스템 전반의 로그 기록 및 관리
├── data/
│   ├── states/             # 크롤러별 마지막 수집 ID 저장 (JSON)
│   └── results_*.jsonl     # 수집 완료된 날짜별 통합 결과물 (JSONL 포맷)
└── logs/                   # 시스템 실행 로그 기록 폴더
```

---

## 📈 데이터 저장 포맷 (JSONL)
본 시스템은 대용량 데이터 처리에 유리한 **JSONL(JSON Lines)** 포맷을 사용합니다. 각 행이 하나의 수집 객체로 구성되어 있어, 나중에 전처리 모델이나 데이터베이스(DB)에 데이터 스트림을 그대로 밀어 넣기 최적화되어 있습니다.

---

## 🚀 시작하기
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 백그라운드 실행 시
./scripts/run_background.sh

# 3. 수동 테스트 시
python3 main.py --mode manual
```
