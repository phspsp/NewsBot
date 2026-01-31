import requests
import os

NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 키워드 설정 (따옴표를 넣어 검색 정확도 향상)
KEYWORDS = ["\"국가대표\"", "\"대한체육회\"", "\"국가대표선수촌\"", "\"대한빙상경기연맹\"", "\"국제스케이트장\""]

def get_news(keyword):
    # 'sim'(유사도)으로 가져와서 관련성 높은 기사 30개를 훑습니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=30&sort=sim"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    res = requests.get(url, headers=headers)
    return res.json().get('items', [])

def send_tg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

# 발송 기록 관리 (sent_links.txt 하나로 통일)
DB_FILE = "sent_links.txt"
if not os.path.exists(DB_FILE):
    open(DB_FILE, 'w').close()

with open(DB_FILE, "r") as f:
    sent_links = set(f.read().splitlines())

new_found_links = []

for kw in KEYWORDS:
    pure_kw = kw.replace('"', '')
    items = get_news(kw)
    
    for item in items:
        link = item['link']
        if link in sent_links or link in new_found_links:
            continue
            
        # <b> 태그 제거 및 제목 정화
        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
        
        # [핵심] 제목에 키워드가 정확히 포함된 경우만 전송 (1번 조건)
        if pure_kw.lower() in title.lower():
            msg = f"<b>[제목일치: {pure_kw}]</b>\n{title}\n<a href='{link}'>보기</a>"
            send_tg(msg)
            new_found_links.append(link)
        # 만약 본문 포함 기사도 정 원하신다면 아래 주석을 해제하세요. (2번 조건)
        # else:
        #     msg = f"<b>[본문포함: {pure_kw}]</b>\n{title}\n<a href='{link}'>보기</a>"
        #     send_tg(msg)
        #     new_found_links.append(link)

# 파일 업데이트 (최신 50개 유지)
updated_links = new_found_links + list(sent_links)
with open(DB_FILE, "w") as f:
    f.write("\n".join(updated_links[:50]))
