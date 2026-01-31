import requests  # 네이버 API와 텔레그램 서버에 데이터를 요청하기 위한 라이브러리
import os        # 시스템 환경 변수(Secrets) 및 파일 경로를 다루기 위한 라이브러리
from datetime import datetime  # 날짜와 시간을 다루기 위한 라이브러리
import pytz      # 한국 표준시(KST) 설정을 위한 라이브러리

# 1. 설정값 불러오기: GitHub Secrets에 등록된 보안 정보를 가져옵니다.
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# [함수] keywords.txt 파일에서 검색어 목록을 한 줄씩 읽어오는 기능
def load_keywords():
    filename = "keywords.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            # 공백 제거 후 빈 줄이 아닌 단어들만 리스트로 만듭니다.
            return [line.strip() for line in f.read().splitlines() if line.strip()]
    return ["삼성전자"] # 파일이 없을 경우를 대비한 기본값

# [함수] 네이버 뉴스 API 호출 (검색어와 정렬 방식을 입력받음)
def get_news(keyword, sort_type):
    # 정확한 검색을 위해 키워드 앞뒤에 따옴표(")를 붙여 검색어를 구성합니다.
    query = f'"{keyword}"'
    # display=30: 한 번에 30개의 기사를 가져옵니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=30&sort={sort_type}"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', []) # 결과 데이터에서 기사 리스트(items)만 반환
    except Exception as e:
        print(f"API 호출 중 오류 발생: {e}")
        return []

# [함수] 텔레그램 메시지 전송
def send_tg(text):
    if not text.strip(): return # 보낼 내용이 없으면 중단
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # disable_web_page_preview: 링크 미리보기 창을 꺼서 메시지를 깔끔하게 만듭니다.
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, json=payload)

# [함수] 뉴스 제목 정화 (태그 및 특수기호 제거)
def clean_title(title):
    # 네이버가 주는 제목의 <b>태그와 특수 문자들을 보기 좋게 바꿉니다.
    return title.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()

# --- [메인 로직 시작] ---

# 1. 한국 시간 기준 새벽 시간대 발송 제한 (00:00 ~ 06:00)
korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)
if 0 <= now_korea.hour < 6:
    print(f"😴 현재 시간 {now_korea.hour}시. 새벽에는 알림을 보내지 않습니다.")
    exit()

# 2. 키워드 및 기존 발송 기록 로드
KEYWORDS = load_keywords()
DB_FILE = "sent_links.txt"
sent_links = set() # 이미 보낸 링크를 저장하는 집합

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        sent_links = set(f.read().splitlines())

all_final_articles = [] # 모든 검증을 통과한 최종 기사들이 담길 리스트

# 3. 키워드별 뉴스 수집 및 중복 제거
for kw in KEYWORDS:
    # (요구사항 1, 2) 유사도순(sim) 30개와 최신순(date) 30개를 각각 가져옵니다.
    sim_items = get_news(kw, "sim")
    date_items = get_news(kw, "date")
    
    # 두 리스트를 하나로 합쳐서 총 60개의 후보를 만듭니다.
    raw_candidates = sim_items + date_items
    
    # 이번 키워드 검색 안에서 제목 중복을 체크하기 위한 리스트
    current_titles = [] 
    
    for item in raw_candidates:
        link = item['link']
        title = clean_title(item['title'])
        pub_date = item.get('pubDate', '') # (요구사항 5) 기사 작성 시간
        
        # [검증 1] 이미 텔레그램으로 보냈던 링크인지 확인
        if link in sent_links:
            continue
            
        # [검증 2] 제목에 키워드가 실제로 포함되어 있는지 확인 (정확도 확보)
        if kw.lower() not in title.lower():
            continue

        # [검증 3] (요구사항 3) 제목 앞 15글자가 겹치는 기사는 동일 기사로 판단하여 제외
        is_title_duplicate = False
        title_prefix = title[:15] # 제목의 앞부분 15자만 추출
        
        for existing_title in current_titles:
            if title_prefix in existing_title:
                is_title_duplicate = True
                break
        
        if not is_title_duplicate:
            # 모든 검증을 통과하면 바구니에 저장
            current_titles.append(title) # 중복 체크 리스트에 제목 추가
            article_data = {
                "keyword": kw,
                "title": title,
                "link": link,
                "date": pub_date
            }
            all_final_articles.append(article_data)
            sent_links.add(link) # 발송 목록에 링크 추가 (중복 방지)

# 4. 결과 메시지 조립 및 발송
if all_final_articles:
    formatted_list = []
    for art in all_final_articles:
        # 텔레그램에 보낼 메시지 모양을 만듭니다. (작성 시간 포함)
        entry = f"• <b>[{art['keyword']}]</b> {art['title']}\n  🕒 <i>{art['date']}</i>\n  <a href='{art['link']}'>기사보기</a>"
        formatted_list.append(entry)

    # (요구사항 6) 10개씩 묶어서 발송하여 메시지 폭탄 방지
    chunk_size = 10
    for i in range(0, len(formatted_list), chunk_size):
        chunk = formatted_list[i:i + chunk_size]
        final_message = "<b>[검증된 뉴스 리포트]</b>\n\n" + "\n\n".join(chunk)
        send_tg(final_message)

    # 5. 발송 기록 파일 업데이트 (파일이 너무 커지지 않게 최신 250개만 유지)
    with open(DB_FILE, "w") as f:
        f.write("\n".join(list(sent_links)[-250:]))
    print(f"✅ {len(all_final_articles)}개의 기사를 선별하여 발송했습니다.")
else:
    print("🔔 검색 결과 중 새로 일치하는 기사가 없습니다.")
