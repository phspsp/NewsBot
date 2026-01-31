import requests
import os

# 환경 변수 불러오기
NAVER_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 검색할 키워드 (원하는 대로 수정하세요)
KEYWORD = "인공지능" 

def get_news():
    url = f"https://openapi.naver.com/v1/search/news.json?query={KEYWORD}&display=10&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    res = requests.get(url, headers=headers)
    return res.json().get('items', [])

def send_tg(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

# 중복 방지 로직
last_link = ""
if os.path.exists("last_link.txt"):
    with open("last_link.txt", "r") as f:
        last_link = f.read().strip()

news_items = get_news()
if not news_items:
    print("뉴스 결과가 없습니다.")
    exit()

new_articles = []
for item in news_items:
    if item['link'] == last_link:
        break
    new_articles.append(item)

if new_articles:
    for article in reversed(new_articles):
        # 타이틀에 포함된 HTML 태그(<b> 등) 제거 후 전송
        title = article['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
        msg = f"<b>[신규 뉴스 알림]</b>\n\n{title}\n\n<a href='{article['link']}'>기사 바로가기</a>"
        send_tg(msg)
    
    with open("last_link.txt", "w") as f:
        f.write(news_items[0]['link'])
    print(f"{len(new_articles)}개의 새로운 기사를 보냈습니다.")
else:
    print("새로운 기사가 없습니다.")
