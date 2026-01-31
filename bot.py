import requests
import os

# 환경 변수 설정
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# [수정] 따옴표를 포함한 키워드로 검색 정확도를 높입니다.
KEYWORDS = ["\"삼성전자\"", "\"인공지능\"", "\"비트코인\""]

def get_news(keyword):
    # 최신순으로 20개씩 넉넉히 가져옵니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=date"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET
    }
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', [])
    except:
        return []

def send_tg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

# 1. 기존 발송 기록 로드
DB_FILE = "sent_links.txt"
sent_links = set() # 검색 속도를 위해 set 사용
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        sent_links = set(f.read().splitlines())

new_sent_this_time = [] # 이번 실행에서 보낸 링크들

for kw in KEYWORDS:
    pure_kw = kw.replace('"', '')
    items = get_news(kw)
    
    # 기사를 두 그룹으로 나눕니다.
    title_match = [] # 제목에 키워드 있음
    body_match = []  # 제목엔 없지만 본문에 있음(네이버 검색 결과에 포함됨)
    
    for item in items:
        link = item['link']
        if link in sent_links or link in [x['link'] for x in new_sent_this_time]:
            continue
            
        # 제목 태그 제거 및 정리
        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
        
        if pure_kw.lower() in title.lower():
            title_match.append({"title": title, "link": link, "type": "제목일치"})
        else:
            body_match.append({"title": title, "link": link, "type": "본문포함"})

    # 1순위(제목) 먼저 보내고, 2순위(본문) 보냄 (중복은 위에서 이미 걸러짐)
    final_list = title_match + body_match
    
    for news in final_list:
        msg = f"<b>[{news['type']}: {pure_kw}]</b>\n\n{news['title']}\n\n<a href='{news['link']}'>기사 바로가기</a>"
        send_tg(msg)
        new_sent_this_time.append(news)

# 2. 발송 기록 업데이트 (최신 100개 유지)
updated_links = [n['link'] for n in new_sent_this_time] + list(sent_links)
with open(DB_FILE, "w") as f:
    f.write("\n".join(updated_links[:100]))

print(f"작업 완료: 신규 {len(new_sent_this_time)}건 발송")
