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
    if not text
