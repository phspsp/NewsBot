import requests  # 네이버/텔레그램 서버와 데이터를 주고받기 위한 도구입니다.
import os        # 시스템 환경 변수나 파일 경로를 다루기 위해 사용합니다.
from datetime import datetime, timedelta  # 현재 시간 계산 및 일주일 전 날짜를 구하기 위해 사용합니다.
import pytz      # 한국 표준시(KST)를 정확하게 설정하기 위해 사용합니다.

# 1. 환경 변수(GitHub Secrets)에서 보안 키 정보를 안전하게 가져옵니다.
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')      # 네이버 API ID
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')  # 네이버 API 비밀키
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')       # 텔레그램 봇 토큰
CHAT_ID = os.environ.get('CHAT_ID')               # 알림 받을 채팅방 ID

# [함수] keywords.txt 파일에서 검색어 목록을 한 줄씩 읽어옵니다.
def load_keywords():
    filename = "keywords.txt"
    if os.path.exists(filename):  # 파일이 실제로 있을 때만 실행합니다.
        with open(filename, "r", encoding="utf-8") as f:
            # 양 끝 공백을 지우고, 빈 줄이 아닌 것들만 리스트로 만듭니다.
            return [line.strip() for line in f.read().splitlines() if line.strip()]
    return ["삼성전자"]  # 파일이 없으면 기본 키워드로 검색합니다.

# [함수] 네이버 뉴스 API를 호출하여 기사를 가져옵니다.
def get_news(keyword, sort_type):
    query = f'"{keyword}"'  # 정확한 검색을 위해 키워드에 큰따옴표를 붙입니다.
    # 각 키워드당 30개씩 요청합니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=30&sort={sort_type}"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers)
        return res.json().get('items', []) # 결과물 중 기사 리스트(items)만 뽑아옵니다.
    except:
        return []

# [함수] 텔레그램으로 최종 결과 메시지를 보냅니다.
def send_tg(text):
    if not text.strip(): return # 보낼 내용이 없으면 아무것도 안 합니다.
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # HTML 형식을 허용하고, 링크 미리보기 화면은 꺼서 깔끔하게 만듭니다.
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, json=payload)

# [함수] 기사 제목에 포함된 HTML 태그와 특수기호를 깨끗하게 정리합니다.
def clean_title(title):
    return title.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()

# [함수] 영어 날짜를 한국어 스타일(2026.01.31.(토) 22:10)로 변환합니다.
def format_date_kor(date_str):
    try:
        weekday_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
        dt_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S +0900') # 영어 날짜 분석
        kor_w = weekday_map.get(dt_obj.strftime('%a'), dt_obj.strftime('%a')) # 요일 번역
        return dt_obj.strftime(f'%Y.%m.%d.({kor_w}) %H:%M') # 한국식 재구성
    except:
        return date_str # 변환 실패 시 원본을 그대로 둡니다.

# --- [메인 실행 부분] ---

# 1. 한국 시간대 설정 및 새벽 발송 금지 체크
korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)

if 0 <= now_korea.hour < 6: # 새벽 0시 ~ 아침 6시 사이라면
    print(f"현재 {now_korea.hour}시입니다. 새벽에는 알림을 보내지 않습니다.")
    exit() # 프로그램 종료

# 2. 일주일 이내의 기사만 수집하기 위한 기준 시간 계산
one_week_ago = now_korea - timedelta(days=7)

# 3. 키워드 및 중복 방지 DB(450개 저장용) 불러오기
KEYWORDS = load_keywords()
DB_FILE = "sent_links.txt"
sent_links = set()
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        sent_links = set(f.read().splitlines())

all_collected_articles = [] # 모든 후보 기사를 담을 바구니

# 4. 각 키워드별로 뉴스 수집 및 필터링 시작
for kw in KEYWORDS:
    # 유사도순 30개와 최신순 30개를 모두 합칩니다.
    raw_candidates = get_news(kw, "sim") + get_news(kw, "date")
    current_titles = [] # 도배 방지용 임시 리스트
    
    for item in raw_candidates:
        link = item['link']
        title = clean_title(item['title'])
        pub_date_raw = item.get('pubDate', '')
        
        # [검증 A] 일주일 이내 기사인지 확인
        try:
            pub_dt = datetime.strptime(pub_date_raw, '%a, %d %b %Y %H:%M:%S +0900')
            pub_dt = korea_tz.localize(pub_dt)
            if pub_dt < one_week_ago: # 일주일이 넘었다면
                continue # 건너뜁니다.
        except:
            pub_dt = now_korea
            
        # [검증 B] 이미 보냈던 링크인지 확인
        if link in sent_links:
            continue
            
        # [검증 C] 제목 앞 15글자로 중복(도배) 여부 확인
        is_title_duplicate = False
        prefix = title[:15]
        for existing in current_titles:
            if prefix in existing:
                is_title_duplicate = True
                break
        
        if not is_title_duplicate:
            current_titles.append(title)
            
            # [우선순위 설정] 제목에 키워드가 있으면 0순위, 없으면 1순위로 기록합니다.
            has_kw = 0 if kw.lower() in title.lower() else 1
            
            all_collected_articles.append({
                "kw": kw,
                "title": title,
                "link": link,
                "raw_date": pub_dt, # 정렬용 실제 날짜 객체
                "kor_date": format_date_kor(pub_date_raw), # 화면 표시용 한국어 날짜
                "priority": has_kw # 정렬 우선순위 값
            })
            sent_links.add(link)

# 5. [정렬] 제목에 키워드가 포함된 것이 위로 오게 하고, 그다음 최신순으로 정렬합니다.
all_collected_articles.sort(key=lambda x: (x['priority'], x['raw_date']), reverse=True)
# priority는 0이 1보다 앞에 와야 하므로 한 번 더 잡아줍니다.
all_collected_articles.sort(key=lambda x: x['priority'])

# 6. 결과 전송 및 기록 저장
if all_collected_articles:
    formatted_msgs = []
    for art in all_collected_articles:
        formatted_msgs.append(f"• <b>[{art['kw']}]</b> {art['title']}\n  🕒 {art['kor_date']}\n  <a href='{art['link']}'>기사보기</a>")

    # (수정사항) 기사 20개씩 묶어서 하나의 메시지로 발송합니다.
    chunk_size = 20 
    for i in range(0, len(formatted_msgs), chunk_size):
        chunk = formatted_list[i:i + chunk_size] if (formatted_list := formatted_msgs) else []
        send_tg("<b>[선별 뉴스 리포트]</b>\n\n" + "\n\n".join(chunk))

    # (수정사항) 발송 기록을 최신 450개까지 파일에 저장합니다.
    with open(DB_FILE, "w") as f:
        f.write("\n".join(list(sent_links)[-450:]))
    print(f"성공: {len(all_collected_articles)}건의 기사를 발송하고 450개 기록을 저장했습니다.")
else:
    print("새로운 기사가 없어 종료합니다.")
