import requests  # 네이버 API 및 텔레그램 서버와 통신하기 위해 사용합니다.
import os        # 시스템 환경 변수(Secrets) 및 파일 경로 처리를 위해 사용합니다.
from datetime import datetime, timedelta  # 날짜와 시간 계산을 위해 사용합니다.
import pytz      # 한국 시간대(KST)를 정확하게 맞추기 위해 사용합니다.

# 1. 깃허브 시크릿(Secrets)에 저장된 보안 키들을 불러옵니다.
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# [함수] keywords.txt 파일에서 검색어 목록을 읽어옵니다.
def load_keywords():
    filename = "keywords.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            # 양 끝 공백을 지우고 내용이 있는 줄만 리스트로 반환합니다.
            return [line.strip() for line in f.read().splitlines() if line.strip()]
    return []

# [함수] 네이버 뉴스 API에 접속하여 기사를 가져옵니다.
def get_news(keyword, sort_type):
    query = f'"{keyword}"'  # 정확한 검색을 위해 키워드 양옆에 큰따옴표를 붙입니다.
    # 각각 30개씩 유사도순(sim) 또는 최신순(date)으로 요청합니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=30&sort={sort_type}"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', [])
    except:
        return []

# [함수] 텔레그램으로 메시지를 보냅니다.
def send_tg(text):
    if not text.strip(): return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # HTML 형식을 지원하고 링크 미리보기를 비활성화하여 깔끔하게 보냅니다.
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, json=payload)

# [함수] 뉴스 제목의 HTML 태그를 지웁니다.
def clean_title(title):
    return title.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()

# [함수] 날짜를 한국인이 읽기 편한 포맷으로 바꿉니다.
def format_date_kor(date_str):
    try:
        weekday_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
        dt_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S +0900')
        kor_w = weekday_map.get(dt_obj.strftime('%a'), dt_obj.strftime('%a'))
        return dt_obj.strftime(f'%Y.%m.%d.({kor_w}) %H:%M')
    except:
        return date_str

# --- [메인 실행 로직] ---

# 한국 시간대 설정
korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)

# 새벽 시간(0~5시)에는 알림을 보내지 않고 종료합니다.
if 0 <= now_korea.hour < 6:
    exit()

# 기준 시간 설정: 현재로부터 이틀(48시간) 전
two_days_ago = now_korea - timedelta(days=2)

# 1. 기록 파일(sent_links.txt) 로드 및 이틀 지난 데이터 필터링
DB_FILE = "sent_links.txt"
valid_records = {}  # { '기사링크': '저장날짜' } 형태로 저장합니다.
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "|" in line:
                link, save_date_str = line.strip().split("|")
                try:
                    # 저장된 날짜를 분석하여 이틀 이내의 기록만 유지합니다.
                    save_dt = datetime.strptime(save_date_str, '%Y%m%d%H%M')
                    save_dt = korea_tz.localize(save_dt)
                    if save_dt > two_days_ago:
                        valid_records[link] = save_date_str
                except:
                    continue

KEYWORDS = load_keywords()
all_collected_articles = []  # 새로 발견된 기사들을 모으는 바구니
no_news_keywords = []        # 새로운 소식이 없는 키워드들을 모으는 바구니

# 2. 키워드별 수집 시작
for kw in KEYWORDS:
    # 유사도순과 최신순 결과를 합칩니다.
    raw_candidates = get_news(kw, "sim") + get_news(kw, "date")
    current_titles = []  # 동일 실행 내 중복 기사 방지용
    found_new_for_this_kw = False
    
    # 검색 결과가 아예 없는 경우
    if not raw_candidates:
        no_news_keywords.append(kw)
        continue

    for item in raw_candidates:
        link = item['link']
        title = clean_title(item['title'])
        pub_date_raw = item.get('pubDate', '')
        
        # [검증 1] 기사 발행일이 이틀 이내인지 확인
        try:
            pub_dt = datetime.strptime(pub_date_raw, '%a, %d %b %Y %H:%M:%S +0900')
            pub_dt = korea_tz.localize(pub_dt)
            if pub_dt < two_days_ago:
                continue
        except:
            continue
            
        # [검증 2] 이미 보낸 적이 있는 링크인지 확인
        if link in valid_records:
            continue
            
        # [검증 3] 제목 앞 15자가 겹치면 중복 기사로 간주하여 패스
        prefix = title[:15]
        if any(prefix in t for t in current_titles):
            continue
        
        current_titles.append(title)
        found_new_for_this_kw = True
        
        # 제목에 키워드 포함 시 우선순위 상향 (0이 높음)
        has_kw = 0 if kw.lower() in title.lower() else 1
        
        all_collected_articles.append({
            "kw": kw, "title": title, "link": link,
            "raw_date": pub_dt, "kor_date": format_date_kor(pub_date_raw),
            "priority": has_kw
        })
        # 새로운 기록을 메모리에 저장합니다.
        valid_records[link] = now_korea.strftime('%Y%m%d%H%M')

    # 필터링 후에도 보낼 기사가 없으면 '새 소식 없음' 리스트에 추가
    if not found_new_for_this_kw:
        no_news_keywords.append(kw)

# 3. 새로운 기사 발송 로직
if all_collected_articles:
    # 우선순위(키워드 포함 여부)와 최신순으로 정렬합니다.
    all_collected_articles.sort(key=lambda x: (x['priority'], x['raw_date']), reverse=True)
    all_collected_articles.sort(key=lambda x: x['priority'])
    
    formatted_msgs = []
    for art in all_collected_articles:
        formatted_msgs.append(f"• <b>[{art['kw']}]</b> {art['title']}\n  🕒 {art['kor_date']}\n  <a href='{art['link']}'>기사보기</a>")

    # 기사를 20개씩 묶어서 보냅니다.
    for i in range(0, len(formatted_msgs), 20):
        chunk = formatted_msgs[i:i + 20]
        send_tg("<b>[실시간 뉴스 리포트]</b>\n\n" + "\n\n".join(chunk))

# 4. 소식이 없는 키워드 알림 로직 (목록으로 묶어서 발송)
if no_news_keywords:
    # 키워드가 너무 많을 경우를 대비해 30개씩 끊어서 보냅니다.
    for i in range(0, len(no_news_keywords), 30):
        chunk = no_news_keywords[i:i + 30]
        status_msg = "<b>[알림: 새로운 기사 없음]</b>\n\n"
        status_msg += "\n".join([f"- {k}" for k in chunk])
        status_msg += "\n\n위 키워드들은 최근 2일 내 새로운 기사가 없습니다."
        send_tg(status_msg)

# 5. 최종 유효 기록(이틀 이내)을 파일에 저장합니다.
with open(DB_FILE, "w", encoding="utf-8") as f:
    for link, date_str in valid_records.items():
        f.write(f"{link}|{date_str}\n")

print(f"작업 완료: 신규 {len(all_collected_articles)}건 발송 / 소식 없음 {len(no_news_keywords)}건 보고")
