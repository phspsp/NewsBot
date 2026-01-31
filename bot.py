import requests  # 네이버 API 및 텔레그램 서버와 통신하기 위한 라이브러리
import os        # 시스템 환경 변수 및 파일 경로를 다루기 위한 라이브러리
from datetime import datetime  # 현재 날짜와 시간을 다루기 위한 라이브러리
import pytz      # 한국 표준시(KST) 설정을 위한 라이브러리

# 1. 환경 변수 설정: GitHub Secrets에 등록한 정보를 가져옵니다.
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# [함수] keywords.txt 파일에서 검색어 목록을 읽어오는 기능
def load_keywords():
    filename = "keywords.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            # 한 줄씩 읽어서 앞뒤 공백을 제거하고 빈 줄이 아닌 것만 리스트로 만듭니다.
            # 검색 정확도를 위해 각 키워드 앞뒤에 따옴표(")를 붙여줍니다.
            return [f'"{line.strip()}"' for line in f.read().splitlines() if line.strip()]
    else:
        print("💡 알림: keywords.txt 파일이 없어 기본 키워드(삼성전자)를 사용합니다.")
        return ["\"삼성전자\""]

# [함수] 네이버 API를 이용해 뉴스를 검색하는 기능
def get_news(keyword):
    # display=20: 기사를 최대 20개 가져옴 / sort=date: 최신순 정렬
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=date"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET
    }
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', [])  # 검색 결과 중 기사 리스트만 반환
    except Exception as e:
        print(f"❌ 네이버 검색 중 오류 발생: {e}")
        return []

# [함수] 텔레그램 메시지를 전송하는 기능
def send_tg(text):
    if not text.strip(): return  # 보낼 내용이 없으면 중단
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # disable_web_page_preview=True: 링크 밑에 미리보기 창이 뜨지 않게 하여 깔끔하게 유지
    payload = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

# --- [메인 로직 시작] ---

# 2. 한국 시간 기준으로 새벽 발송 제한 (00:00 ~ 06:00)
korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)
if 0 <= now_korea.hour < 6:
    print(f"😴 현재 시간 {now_korea.hour}시. 새벽 시간대이므로 알림을 보내지 않습니다.")
    exit()

# 3. 키워드 및 기존 기록(DB) 불러오기
KEYWORDS = load_keywords()
DB_FILE = "sent_links.txt"
sent_links = set()

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        # 이미 보낸 링크들을 집합(set)에 담아 중복 체크를 빠르게 합니다.
        sent_links = set(f.read().splitlines())

all_new_articles = []  # 새로 발견한 기사들을 담을 바구니

# 4. 각 키워드별 뉴스 검색 및 필터링
for kw in KEYWORDS:
    pure_kw = kw.replace('"', '')  # 제목 검사용 (따옴표 제거)
    items = get_news(kw)
    
    for item in items:
        link = item['link']
        
        # [필터 1] 이미 보냈던 기사인지 확인
        if link in sent_links:
            continue
            
        # 제목의 <b> 태그나 특수문자 정화
        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
        
        # [필터 2] 제목에 키워드가 정확히 포함되어 있는지 확인
        if pure_kw.lower() in title.lower():
            all_new_articles.append(f"• <b>[{pure_kw}]</b> {title}\n  <a href='{link}'>기사보기</a>")
            sent_links.add(link)  # 중복 방지를 위해 목록에 즉시 추가

# 5. 메시지 묶음 전송 및 결과 저장
if all_new_articles:
    # chunk_size = 10: 10개씩 끊어서 하나의 메시지로 묶어 보냄
    chunk_size = 10
    for i in range(0, len(all_new_articles), chunk_size):
        chunk = all_new_articles[i:i + chunk_size]
        final_msg = "<b>[신규 뉴스 모음]</b>\n\n" + "\n\n".join(chunk)
        send_tg(final_msg)

    # 발송 기록 업데이트: 최신 순으로 150개만 남기고 파일에 저장
    with open(DB_FILE, "w") as f:
        f.write("\n".join(list(sent_links)[-150:]))
    print(f"✅ 성공: {len(all_new_articles)}개의 신규 기사를 발송했습니다.")
else:
    print("🔔 알림: 새로운 기사가 없습니다.")
