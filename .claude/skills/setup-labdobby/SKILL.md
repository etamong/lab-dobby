---
description: lab-dobby (Slack 알림 라이브러리) 셋업을 한국어로 단계별 안내. 사용자가 "도비 셋업", "lab-dobby 설치", "노예 봇 설정" 같은 말을 할 때 자동 호출. 슬래시 커맨드 /setup-labdobby 로도 호출 가능.
---

# lab-dobby 셋업 안내

너는 비개발자 연구자가 lab-dobby (Slack 알림 라이브러리)를 셋업하도록 돕는다.

## 원칙

- **한국어**로 대화한다.
- 한 번에 한 단계씩. 단계마다 사용자 확인을 받고 다음으로 넘어간다.
- 친절하게. 사용자는 개발자가 아니다. 명령어는 그대로 복사할 수 있게 코드 블록에 담아 보여준다.
- 시크릿(webhook URL)을 사용자가 채팅에 그대로 붙여넣지 않게 주의시킨다. 파일 / Secrets에만 들어가야 함.

## 0. 환경 확인

먼저 어디서 셋업하는지 묻는다:

> 지금 셋업하려는 환경이 어디예요?
> 1. **Colab** 노트북
> 2. **본인 서버** (T4 등, VS Code Remote-SSH로 접속한 곳)

답에 따라 1번이면 [Colab 경로](#colab-경로), 2번이면 [서버 경로](#서버-경로) 진행.

## 1. Webhook URL 확보

> Slack webhook URL 받으셨어요? `https://hooks.slack.com/services/...` 로 시작하는 URL이에요.

- 받았으면 → 안전하게 보관 중인지 확인 후 다음 단계로.
- 못 받았으면 →
  > 친구분(이 도구 만든 분)한테 받아야 해요. 친구분 Slack 워크스페이스에 초대받고, 알림용 채널의 Incoming Webhook URL을 받으세요. 받고 나면 다시 와서 `/setup-labdobby` 치시면 돼요.

URL은 사용자가 본인 메모장이나 비밀번호 매니저에 임시 저장하게 하고, **채팅에 직접 붙여넣지 말라**고 안내. (Skill이 직접 받을 거면 받지만, 가능한 한 사용자가 직접 파일/Secrets에 넣게.)

## Colab 경로

### a. Secrets에 URL 저장 (사용자가 직접 해야 함, Claude Code가 못 함)

> Colab 노트북 좌측 사이드바에서 🔑 (열쇠) 아이콘 클릭 → **새 보안 비밀** 추가
> - 이름: `SLACK_WEBHOOK_URL`
> - 값: 받은 webhook URL
> - **노트북 액세스** 토글: ON
>
> 다 됐으면 알려주세요.

### b. 설치 + 테스트 셀

사용자한테 노트북 셀에 다음 코드 붙여넣고 실행하라고 안내:

```python
!pip install -q git+https://github.com/etamong/lab-dobby.git

import labdobby as lab
lab.notify("도비 셋업 테스트")
```

> Slack 알림 채널에 메시지 왔어요?

- 왔으면 → [사용 패턴](#사용-패턴-안내)으로.
- 안 왔으면 → [트러블슈팅](#트러블슈팅) 단계로.

## 서버 경로

VS Code Remote-SSH로 접속 중인지 다시 한 번 확인:

> 지금 VS Code 터미널이 **서버에 붙어 있는** 상태인가요? 터미널 프롬프트에 서버 호스트명 보이면 OK. 본인 노트북 터미널이면 서버에 SSH 먼저 들어가야 해요.

서버 터미널에서 아래를 한 줄씩 실행하게 안내. 한 줄 하고 결과 확인 후 다음.

### a. webhook URL을 `~/.labdobby.env` 에 저장

사용자한테 webhook URL을 묻고 (직접 받아도 OK), 다음 명령 실행:

```bash
cat > ~/.labdobby.env <<'EOF'
SLACK_WEBHOOK_URL=여기에_받은_URL_그대로_붙여넣기
EOF
chmod 600 ~/.labdobby.env
```

또는 사용자가 직접 편집하게:
```bash
nano ~/.labdobby.env
# 안에 한 줄: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
chmod 600 ~/.labdobby.env
```

확인:
```bash
cat ~/.labdobby.env
```
첫 줄이 `SLACK_WEBHOOK_URL=https://hooks.slack.com/...` 형태인지 같이 보기. 따옴표나 공백 섞이면 안 됨.

### b. 설치

```bash
pip install git+https://github.com/etamong/lab-dobby.git
```

`pip` 못 찾으면 `pip3` 시도. conda/venv 환경인지도 확인 (`which python`).

### c. 테스트

```bash
python -m labdobby "도비 셋업 테스트"
```

> Slack 알림 채널에 메시지 왔어요?

- 왔으면 → [사용 패턴](#사용-패턴-안내)으로.
- 안 왔으면 → [트러블슈팅](#트러블슈팅).

## 사용 패턴 안내

성공했으면 사용자한테 자기 코드에서 어떻게 쓸지 알려주기. **딱 한 가지부터** 보여주고 (`watch()` 또는 `notify`), 나머지는 README 링크로 넘기기.

### 본인이 .py 스크립트를 돌린다면 (서버에서 흔함)

본인 스크립트 맨 위에 두 줄만 추가:

```python
import labdobby as lab
lab.watch()
```

이러면 스크립트 끝나거나 에러 나면 자동으로 Slack에 알림. **본인 코드는 한 줄도 안 바꿔도 됨.**

### 본인이 노트북(Colab/Jupyter)을 쓴다면

원하는 자리에:

```python
import labdobby as lab

lab.notify("epoch 10 done")          # 단발 알림

@lab.on_finish                        # 함수 끝/에러 자동
def train():
    ...

with lab.block("preprocessing"):      # 블록 끝/에러 자동
    ...
```

> 노트북에서는 `lab.watch()` 안 됨 (셀 단위 실행이라).

## 트러블슈팅

### `[lab-dobby] ⚠️  Webhook URL이 없어요.` 경고
- Colab: 🔑 Secrets에 `SLACK_WEBHOOK_URL` 추가 빠짐 / 노트북 액세스 토글 OFF
- 서버: `~/.labdobby.env` 없음 또는 키 이름 오타. `cat ~/.labdobby.env` 로 확인.

### Slack에 메시지 안 오는데 stderr에 "401" 또는 "404"
webhook URL이 잘못됐거나 revoke됨. 친구한테 새 URL 받기.

### `ModuleNotFoundError: labdobby`
`pip install`이 다른 Python 환경에서 됨. `which python`, `which pip` 비교. conda env / venv 확인.

### Colab에서 `userdata.SecretNotFoundError` 또는 `NotebookAccessError`
Secret의 **노트북 액세스** 토글 OFF. Secret 옆 토글 켜고 셀 다시 실행.

### `git+https://...` clone에서 인증 요구
Public repo라 인증 필요 없음. URL에 오타 있는지 확인 (etamong/lab-dobby).

## 마무리

성공했으면 사용자한테 한마디:

> 셋업 끝! 자세한 사용법이랑 트러블슈팅은 README 보면 돼요:
> https://github.com/etamong/lab-dobby
>
> 도비가 자유롭진 못해도, 알림은 자유롭게 보내드릴게요.
