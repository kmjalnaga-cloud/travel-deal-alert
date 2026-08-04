# travel-deal-alert

여기어때 / 야놀자에서 등록한 숙소에 특가·할인 배지가 뜨면 텔레그램으로 알려주는 스크립트. GitHub Actions가 매시 정각에 자동으로 실행한다.

## 동작 방식

- `config.json`에 등록된 숙소별로 여기어때/야놀자 상품 페이지를 조회해 붙어있는 프로모션 배지(예: 당일특가, 반짝특가, 오픈런, 최저가, 시즌 캠페인 태그 등)를 전부 수집한다. 키워드로 걸러내지 않고 새로 뜨는 배지는 종류와 상관없이 알림 대상이다.
- 이전 실행 결과(`state.json`)와 비교해 **새로 나타난** 배지가 있을 때만 텔레그램 메시지를 보낸다. 배지가 계속 떠 있어도 매번 알림이 오지는 않는다.
- `state.json`은 워크플로우가 실행될 때마다 리포지토리에 자동 커밋된다.

## 최초 설정

### 1. 텔레그램 봇 만들기

1. 텔레그램에서 [@BotFather](https://t.me/BotFather)에게 `/newbot` 전송, 안내에 따라 봇 이름 설정
2. 발급받은 토큰(예: `123456:ABC-DEF...`)을 기록해둔다
3. 만든 봇과 대화를 한 번 시작한 뒤(`/start`), 아래 URL을 브라우저로 열어 `chat.id` 값을 확인한다
   `https://api.telegram.org/bot<토큰>/getUpdates`

### 2. GitHub Secrets 등록

리포지토리 루트에서 아래 명령을 실행하면 터미널에서 직접 값을 입력해 등록할 수 있다 (값이 채팅창에 남지 않음).

```bash
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
```

### 3. 워크플로우 활성화

리포지토리를 GitHub에 push하면 `.github/workflows/check-deals.yml`이 매시 정각(UTC 기준)에 자동 실행된다. 수동으로 바로 테스트하려면 GitHub 저장소의 Actions 탭 → `Check Travel Deals` → `Run workflow`.

## 숙소 추가/삭제

`config.json`의 `places` 배열에 항목을 추가하면 된다. 여기어때/야놀자 각각의 숙소 ID는 해당 사이트에서 숙소를 검색했을 때의 URL에서 확인할 수 있다.

- 여기어때: 검색 결과에서 숙소를 클릭하면 `/domestic-accommodations/{id}` 형태의 링크가 뜬다. `dong_code`는 지역 코드로, 검색 자동완성 API 응답의 `sigunguCode` 값을 사용한다.
- 야놀자: 숙소 상세 페이지 URL이 `https://nol.yanolja.com/stay/domestic/{id}` 형태다.

## 로컬 테스트

```bash
pip install -r requirements.txt
python scraper.py
```

`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` 환경변수가 없으면 실제 전송 없이 콘솔에만 결과를 출력한다(dry-run).

## 주의사항

이 스크립트는 여기어때/야놀자의 비공식 웹 응답 구조를 그대로 파싱한다. 사이트 개편으로 필드명이 바뀌면 `sites.py`의 파싱 로직을 수정해야 할 수 있다.
