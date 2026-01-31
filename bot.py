import requests
import os

# 환경 변수 설정
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# [수정 포인트] 검색하고 싶은 키워드들을 리스트로 넣으세요
KEYWORDS = ["국가대표", "대한체육회", "대한빙상경기연맹", "대한스키스노보드협회", "아빠찬스"]

def get_news(keyword):
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=10&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    res = requests.get(url, headers=headers)
    return res.json().get('items', [])

def send_tg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

# 1. 이미 보낸 기사 링크들 불러오기 (최근 100개 정도 유지)
DB_FILE = "sent_links.txt"
sent_links = []
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        sent_links = f.read().splitlines()

new_found_links = []

# 2. 모든 키워드에 대해 루프 돌리기
for kw in KEYWORDS:
    print(f"키워드 '{kw}' 검색 중...")
    items = get_news(kw)
    
    for item in items:
        link = item['link']
        # 이미 보낸 링크라면 건너뛰기
        if link in sent_links or link in new_found_links:
            continue
        
        # 새 기사 발견!
        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
        msg = f"<b>[신규 뉴스: {kw}]</b>\n\n{title}\n\n<a href='{link}'>기사 바로가기</a>"
        send_tg(msg)
        
        # 방금 보낸 링크 저장 리스트에 추가
        new_found_links.append(link)

# 3. 새로운 링크를 DB 파일에 추가하고, 너무 길어지면 최신 100개만 유지
all_links = new_found_links + sent_links
with open(DB_FILE, "w") as f:
    f.write("\n".join(all_links[:100])) 

print(f"총 {len(new_found_links)}개의 새로운 소식을 전송했습니다.")
