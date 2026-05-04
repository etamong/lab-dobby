# lab-dobby 🧦

> K대 아날로그 회로 연구실에서 회로와 함께 밤을 지새는 친구를 위한 작은 알림 도구.
> 도비의 양말은 자유롭지 못해도, 알림은 자유롭게.

긴 학습/실험이 끝나거나 에러가 났을 때 Slack으로 알림을 보냅니다.
**Colab**과 **SSH 서버(Tesla T4 등)** 양쪽에서 같은 코드로 동작.

```python
import labdobby as lab
lab.watch()           # 스크립트 끝/에러 자동 알림 (이 두 줄만 추가하면 끝)

# ↓ 원래 본인 코드 그대로
train_model()
```

---

## 설정

### Colab

1. 노트북 좌측 사이드바의 🔑 **Secrets** 클릭 → **새 보안 비밀** 추가
   - 이름: `SLACK_WEBHOOK_URL`
   - 값: 친구한테 받은 webhook URL (`https://hooks.slack.com/services/...`)
   - **노트북 액세스** 토글 ON
2. 셀에서 설치:
   ```python
   !pip install -q git+https://github.com/etamong/lab-dobby.git
   ```
3. 테스트:
   ```python
   import labdobby as lab
   lab.notify("도비 테스트")
   ```
   Slack에 메시지 오면 끝.

> [Open in Colab](https://colab.research.google.com/github/etamong/lab-dobby/blob/main/setup_colab.ipynb) 으로 한 번에 가능.

### 서버 (T4 등, VS Code Remote-SSH)

> ⚠️ Remote-SSH로 접속한 경우, 아래는 모두 **서버 쪽 터미널**에서 실행해야 합니다 (로컬 노트북 X).

```bash
# 1. webhook URL 저장
echo 'SLACK_WEBHOOK_URL=받은_URL_여기에' > ~/.labdobby.env
chmod 600 ~/.labdobby.env

# 2. 설치
pip install git+https://github.com/etamong/lab-dobby.git

# 3. 테스트
python -m labdobby "도비 테스트"
```

### Claude Code 사용자라면 (서버 쪽만)

```bash
git clone https://github.com/etamong/lab-dobby.git
bash lab-dobby/install-skill.sh
```

이제 Claude Code에서 `/setup-labdobby` 치면 위의 모든 단계를 대화로 안내받을 수 있어요.

---

## 사용 패턴

| 상황 | 코드 |
|---|---|
| 스크립트 전체 감싸기 (가장 쉬움) | `lab.watch()` 한 줄 |
| 한 번 보내기 | `lab.notify("epoch 10 done")` |
| 함수 끝/에러 자동 | `@lab.on_finish` |
| 코드 블록 끝/에러 자동 | `with lab.block("preprocessing"):` |

```python
import labdobby as lab

# 1. 스크립트 전체 감싸기 (.py 스크립트에서 추천)
lab.watch()

# 2. 임의의 메시지
lab.notify("epoch 10/50 done, loss=0.23")
lab.notify("checkpoint 저장됨", tag="lr_sweep_v2")  # 실험 여러 개일 때 prefix

# 3. 함수 데코레이터
@lab.on_finish
def train():
    ...

# 4. 코드 블록
with lab.block("preprocessing"):
    ...
```

> `watch()`는 `.py` 스크립트 전용. Jupyter/Colab에서는 셀 단위로 동작 안 함.
> 노트북에서는 `notify` / `@on_finish` / `with block` 사용.

---

## 메시지 형식

알림에는 자동으로 hostname prefix가 붙어 어디서 온 건지 한눈에 보임:
```
[colab] ✅ train done in 12m34s
[t4-server] [lr_sweep_v2] epoch 10 done
[t4-server] ❌ train failed in 3m1s
RuntimeError: CUDA out of memory
```

---

## 시크릿 위생

- ✅ webhook URL은 **항상 환경 변수 / Colab Secrets / `~/.labdobby.env`** 에만.
- ❌ `.py` 파일이나 노트북 셀에 직접 박지 마세요.
- ❌ git에 올라가는 파일에 절대 X. (`.gitignore`가 `*.env`를 막아둠)
- 만약 실수로 노출됐다면: Slack 워크스페이스에서 webhook URL **revoke** 후 재발급.

---

## 트러블슈팅

| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError: labdobby` | `pip install`이 다른 Python 환경에서 실행됨. `which python` 확인. |
| Slack에 메시지 안 옴, stderr에 "401" 또는 "404" | webhook URL 만료/오타. 친구한테 새 URL 받기. |
| `[lab-dobby] ⚠️  Webhook URL이 없어요.` 경고 | Colab이면 Secrets 추가 빠짐 / 서버면 `~/.labdobby.env` 파일 없음. 위 설정 단계 다시. |
| Colab에서 `userdata.get` 에러 | Secret의 **노트북 액세스** 토글이 OFF. Secret 옆 토글 켜주기. |

---

## 라이선스

MIT.

---

🤖 *이 도구는 [Claude Code](https://claude.com/claude-code)로 만들어졌습니다.*
