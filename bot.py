import requests
import os
from datetime import datetime
import pytz

# 환경 변수 설정
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 키워드 설정
KEYWORDS = ["\"대한체육회\"", "\"국가대표\"", "\"국제스케이트장\"", "\"대한스키스노보드협회\""]

def get_news(keyword):
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', [])
    except:
        return []

def send_tg(text):
    if not text.strip(): return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})

# --- 시간 제한 로직 (한국 시간 기준 00:00 ~ 06:00 발송 안 함) ---
korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)
if 0 <= now_korea.hour < 6:
    print(f"현재 시간 {now_korea.hour}시. 새벽 시간대이므로 알림을 보낼 수 없습니다.")
    exit()

# 1. 기존 발송 기록 로드
DB_FILE = "sent_links.txt"
sent_links = set()
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        sent_links = set(f.read().splitlines())

all_new_articles = [] # 이번에 보낼 기사들 모음

# 2. 키워드별 검색
for kw in KEYWORDS:
    pure_kw = kw.replace('"', '')
    items = get_news(kw)
    
    for item in items:
        link = item['link']
        if link in sent_links:
            continue
            
        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
        
        # 제목에 키워드가 포함된 경우만 추가 (1순위 필터)
        if pure_kw.lower() in title.lower():
            all_new_articles.append(f"• <b>[{pure_kw}]</b> {title}\n  <a href='{link}'>기사보기</a>")
            sent_links.add(link) # 중복 방지를 위해 즉시 추가

# 3. 메시지 묶어서 보내기
if all_new_articles:
    # 너무 길면 텔레그램 메시지 제한에 걸리므로 5개씩 끊어서 한 메시지로 합침
    chunk_size = 5
    for i in range(0, len(all_new_articles), chunk_size):
        chunk = all_new_articles[i:i + chunk_size]
        final_msg = "<b>[신규 뉴스 모음]</b>\n\n" + "\n\n".join(chunk)
        send_tg(final_msg)

    # 4. 발송 기록 저장 (최신 100개)
    with open(DB_FILE, "w") as f:
        f.write("\n".join(list(sent_links)[-100:]))
    print(f"{len(all_new_articles)}개의 기사를 묶음 발송했습니다.")
else:
    print("새로운 기사가 없습니다.")
