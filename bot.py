import requests  # 네이버 API 서버나 텔레그램 서버와 데이터를 주고받기 위해 사용합니다.
import os        # 깃허브 시크릿(Secrets)에 저장한 보안 키들을 불러오거나 파일을 다루기 위해 사용합니다.
from datetime import datetime, timedelta  # 현재 시간을 구하고 일주일 전 날짜를 계산하기 위해 사용합니다.
import pytz      # 전 세계 시간대 설정 라이브러리로, '한국 시간'을 정확히 맞추기 위해 사용합니다.

# 1. 환경 변수 설정: 깃허브 레포지토리 Settings > Secrets에 저장한 값을 가상 환경에서 가져옵니다.
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')      # 네이버 API 클라이언트 ID입니다.
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')  # 네이버 API 클라이언트 비밀키입니다.
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')       # 텔레그램 봇 토큰입니다.
CHAT_ID = os.environ.get('CHAT_ID')               # 알림을 받을 텔레그램 채팅방 ID입니다.

# [함수] keywords.txt 파일에서 검색어 목록을 한 줄씩 읽어오는 기능입니다.
def load_keywords():
    filename = "keywords.txt"  # 키워드가 저장된 파일 이름입니다.
    if os.path.exists(filename):  # 만약 파일이 실제로 존재한다면
        with open(filename, "r", encoding="utf-8") as f:  # 파일을 읽기 모드로 엽니다.
            # 각 줄을 읽어와서 앞뒤 공백을 제거(.strip)하고, 내용이 있는 줄만 리스트로 만듭니다.
            return [line.strip() for line in f.read().splitlines() if line.strip()]
    return ["삼성전자"]  # 파일이 없으면 기본값으로 '삼성전자'를 검색합니다.

# [함수] 네이버 뉴스 API에 접속해 기사 목록을 가져오는 기능입니다.
def get_news(keyword, sort_type):
    # 정확한 검색을 위해 검색어 양옆에 쌍따옴표(")를 붙여 쿼리를 만듭니다.
    query = f'"{keyword}"'
    # display=30: 30개 기사 요청 / sort_type: 최신순(date) 또는 유사도순(sim)을 결정합니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=30&sort={sort_type}"
    # 네이버 API 사용을 위한 인증 정보를 헤더에 담습니다.
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    try:
        res = requests.get(url, headers=headers)  # API 서버에 요청을 보냅니다.
        return res.json().get('items', [])  # 받아온 결과에서 뉴스 목록(items)만 뽑아냅니다.
    except:
        return []  # 에러가 발생하면 빈 리스트를 반환합니다.

# [함수] 텔레그램 봇을 통해 메시지를 전송하는 기능입니다.
def send_tg(text):
    if not text.strip(): return  # 보낼 내용이 없으면 함수를 종료합니다.
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"  # 텔레그램 전송 주소입니다.
    # HTML 태그 사용 허용 및 링크 미리보기 끄기 설정을 포함합니다.
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, json=payload)  # 실제로 메시지를 전송합니다.

# [함수] 뉴스 제목에 섞여 있는 HTML 태그와 특수기호를 제거해 깨끗하게 만듭니다.
def clean_title(title):
    return title.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()

# [함수] 영어 날짜 형식을 한국 사람이 읽기 편한 형식으로 변환합니다.
def format_date_kor(date_str):
    try:
        # 요일 변환을 위한 사전입니다 (예: Sat -> 토).
        weekday_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
        # 네이버 날짜 형식(예: Sat, 31 Jan 2026...)을 파이썬 시간 객체로 바꿉니다.
        dt_obj = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S +0900')
        eng_w = dt_obj.strftime('%a')  # 영어 요일을 추출합니다.
        kor_w = weekday_map.get(eng_w, eng_w)  # 한국어 요일로 바꿉니다.
        # 최종적으로 2026.01.31.(토) 22:10 형태의 문자열을 만듭니다.
        return dt_obj.strftime(f'%Y.%m.%d.({kor_w}) %H:%M')
    except:
        return date_str  # 변환에 실패하면 원래의 영어 날짜를 그대로 보여줍니다.

# --- [메인 실행 로직 시작] ---

# 1. 한국 시간대(KST)를 기준으로 설정합니다.
korea_tz = pytz.timezone('Asia/Seoul')
now_korea = datetime.now(korea_tz)

# 2. 새벽 발송 제한: 0시부터 5시 59분 사이라면 알림을 보내지 않고 프로그램을 종료합니다.
if 0 <= now_korea.hour < 6:
    print(f"현재 {now_korea.hour}시입니다. 새벽에는 쉬어갑니다.")
    exit()

# 3. 기간 필터 기준: 현재 시간으로부터 정확히 7일(일주일) 전 시간을 계산합니다.
one_week_ago = now_korea - timedelta(days=7)

# 4. 저장된 기사 링크 로드: 중복 발송을 막기 위해 이전에 보냈던 링크들을 읽어옵니다.
KEYWORDS = load_keywords()  # 키워드 목록 불러오기
DB_FILE = "sent_links.txt"  # 링크를 저장해두는 텍스트 파일 이름
sent_links = set()          # 검색 속도를 높이기 위해 집합(set) 자료형을 사용합니다.
if os.path.exists(DB_FILE):  # 파일이 존재하면
    with open(DB_FILE, "r") as f:
        sent_links = set(f.read().splitlines())  # 한 줄씩 읽어서 집합에 저장합니다.

all_final_articles = []  # 모든 검증(일주일 이내, 제목 일치, 중복 제거)을 통과한 기사 바구니

# 5. 모든 키워드에 대해 순차적으로 검색을 수행합니다.
for kw in KEYWORDS:
    # 유사도순(sim) 30개와 최신순(date) 30개를 각각 가져와서 합칩니다 (총 60개 후보).
    raw_candidates = get_news(kw, "sim") + get_news(kw, "date")
    current_titles = []  # 같은 실행 안에서 제목이 겹치는 것을 막기 위한 임시 리스트
    
    for item in raw_candidates:
        link = item['link']  # 기사 링크
        title = clean_title(item['title'])  # 깨끗하게 정리된 제목
        pub_date_raw = item.get('pubDate', '')  # 원본 날짜 문자열
        
        # [검증 1] 일주일 이내의 기사인지 확인합니다.
        try:
            pub_dt = datetime.strptime(pub_date_raw, '%a, %d %b %Y %H:%M:%S +0900')
            pub_dt = korea_tz.localize(pub_dt)  # 시간대 정보 입히기
            if pub_dt < one_week_ago:  # 일주일보다 더 오래된 기사라면
                continue  # 다음 기사로 건너뜁니다.
        except:
            pass  # 날짜 계산에 오류가 나면 일단 통과시킵니다.

        # [검증 2] 이미 텔레그램으로 보냈던 링크인지 확인합니다.
        if link in sent_links:
            continue
            
        # [검증 3] 제목에 키워드가 정확히 포함되어 있는지 다시 한번 확인합니다.
        if kw.lower() not in title.lower():
            continue

        # [검증 4] 제목 앞 15글자가 이미 바구니에 담긴 기사와 겹치는지 확인합니다 (도배 방지).
        is_title_duplicate = False
        title_prefix = title[:15]  # 제목의 앞부분 15자만 따옵니다.
        for existing_title in current_titles:
            if title_prefix in existing_title:  # 15자가 겹치는 제목이 이미 있다면
                is_title_duplicate = True
                break
        
        if not is_title_duplicate:  # 모든 검증을 통과했다면!
            current_titles.append(title)  # 중복 방지 리스트에 제목 추가
            kor_date = format_date_kor(pub_date_raw)  # 날짜를 한국식으로 변환
            
            # 최종 발송 바구니에 기사 정보를 저장합니다.
            all_final_articles.append({
                "keyword": kw,
                "title": title,
                "link": link,
                "date": kor_date
            })
            sent_links.add(link)  # 이 링크는 보낸 것으로 처리합니다.

# 6. 최종 선별된 기사가 있다면 텔레그램으로 보냅니다.
if all_final_articles:
    formatted_list = []  # 텔레그램용으로 예쁘게 꾸민 문자열 리스트
    for art in all_final_articles:
        # 기사 하나당 양식: • [키워드] 제목 / 시간 / 링크 순서입니다.
        formatted_list.append(f"• <b>[{art['keyword']}]</b> {art['title']}\n  🕒 {art['date']}\n  <a href='{art['link']}'>기사보기</a>")

    # 10개씩 묶어서 메시지를 전송합니다 (메시지 도배 방지).
    for i in range(0, len(formatted_list), 10):
        chunk = formatted_list[i:i + 10]
        final_message = "<b>[검증된 뉴스 리포트]</b>\n\n" + "\n\n".join(chunk)
        send_tg(final_message)

    # 7. 발송 기록을 파일에 저장합니다. 최신 250개까지만 유지하여 파일 용량을 관리합니다.
    with open(DB_FILE, "w") as f:
        f.write("\n".join(list(sent_links)[-250:]))
    print(f"작업 완료: {len(all_final_articles)}건의 뉴스를 보냈습니다.")
else:
    # 보낼 기사가 없을 때 로그에 찍히는 메시지입니다.
    print("새로운 조건 일치 기사가 없어 종료합니다.")
