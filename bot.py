import requests
import os
from datetime import datetime, timedelta
import pytz

# 1. 환경 변수 정보
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# [함수] 키워드 로드
def load_keywords():
    filename = "keywords.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.read().splitlines() if line.strip()]
    return []

# [함수] 네이버 뉴스 검색
def get_news(keyword, sort_type):
    query = f'"{keyword}"'
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=30&sort={sort_type}"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', [])
    except:
        return []

# [함수] 텔레그램 전송
def send_tg(text):
    if not text.strip(): return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, json=payload)

# [함수] 제목 정화
def clean_title(title):
    return title.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()

# [함수] 한국 날짜 포맷
def format_date_kor(date_str):
    try:
        weekday_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
        dt_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S +0900')
        kor_w = weekday_map.get(dt_obj.strftime('%a'), dt_obj.strftime('%a'))
        return dt_obj.strftime(f'%Y.%m.%d.({kor_w}) %H:%M')
    except:
        return date_str

# --- [메인 실행] ---

korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)

# 새벽 발송 금지
if 0 <= now_korea.hour < 6:
    exit()

# 이틀(48시간) 기준 시간 계산
two_days_ago = now_korea - timedelta(days=2)

# 1. 기록 파일 로드 및 이틀 지난 기록 자동 삭제
DB_FILE = "sent_links.txt"
valid_records = {} # {링크: 저장날짜문자열}
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "|" in line:
                link, save_date_str = line.strip().split("|")
                try:
                    save_dt = datetime.strptime(save_date_str, '%Y%m%d%H%M')
                    save_dt = korea_tz.localize(save_dt)
                    # 저장된 시간이 이틀 이내인 경우만 유지
                    if save_dt > two_days_ago:
                        valid_records[link] = save_date_str
                except:
                    continue

KEYWORDS = load_keywords()
all_collected_articles = []
no_news_keywords = [] # 새로운 기사가 없는 키워드 보관함

# 2. 키워드별 수집 시작
for kw in KEYWORDS:
    raw_candidates = get_news(kw, "sim") + get_news(kw, "date")
    current_titles = []
    found_new_for_this_kw = False
    
    for item in raw_candidates:
        link = item['link']
        title = clean_title(item['title'])
        pub_date_raw = item.get('pubDate', '')
        
        # 기사 발행일이 이틀 이내인지 확인
        try:
            pub_dt = datetime.strptime(pub_date_raw, '%a, %d %b %Y %H:%M:%S +0900')
            pub_dt = korea_tz.localize(pub_dt)
            if pub_dt < two_days_ago:
                continue
        except:
            continue
            
        # 중복 확인
        if link in valid_records:
            continue
            
        # 제목 중복(도배) 방지
        prefix = title[:15]
        if any(prefix in t for t in current_titles):
            continue
        
        current_titles.append(title)
        found_new_for_this_kw = True
        has_kw = 0 if kw.lower() in title.lower() else 1
        
        all_collected_articles.append({
            "kw": kw, "title": title, "link": link,
            "raw_date": pub_dt, "kor_date": format_date_kor(pub_date_raw),
            "priority": has_kw
        })
        # 새로운 기록 추가 (현재 시간 저장)
        valid_records[link] = now_korea.strftime('%Y%m%d%H%M')

    if not found_new_for_this_kw:
        no_news_keywords.append(kw)

# 3. 결과 전송
# 새로운 기사가 있는 경우 (20개씩 묶음 발송)
if all_collected_articles:
    all_collected_articles.sort(key=lambda x: (x['priority'], x['raw_date']), reverse=True)
    all_collected_articles.sort(key=lambda x: x['priority'])
    
    formatted_msgs = []
    for art in all_collected_articles:
        formatted_msgs.append(f"• <b>[{art['kw']}]</b> {art['title']}\n  🕒 {art['kor_date']}\n  <a href='{art['link']}'>기사보기</a>")

    for i in range(0, len(formatted_msgs), 20):
        chunk = formatted_msgs[i:i + 20]
        send_tg("<b>[실시간 뉴스 리포트]</b>\n\n" + "\n\n".join(chunk))

# 4. 새로운 기사가 없는 키워드 알림
if no_news_keywords:
    status_msg = "<b>[알림: 새로운 기사 없음]</b>\n\n"
    status_msg += "\n".join([f"- {k}" for k in no_news_keywords])
    status_msg += "\n\n위 키워드들에 대한 최근 2일 내 새로운 기사가 없습니다."
    send_tg(status_msg)

# 5. 기록 저장 (유효한 기록만 다시 쓰기)
with open(DB_FILE, "w", encoding="utf-8") as f:
    for link, date_str in valid_records.items():
        f.write(f"{link}|{date_str}\n")
