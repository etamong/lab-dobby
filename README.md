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

뭘 쓸지 헷갈리면:

| 상황 | 권장 |
|---|---|
| `.py` 스크립트 한 방에 돌리고 결과만 알고 싶음 | `lab.watch()` |
| 학습 함수 하나가 메인이고 그게 끝나는 시점이 중요 | `@lab.on_finish` |
| 한 함수 안에 단계 여러 개 (전처리 / 학습 / 평가) — 단계별로 알리고 싶음 | `with lab.block(...)` |
| 그냥 한 마디 보내고 싶음 (체크포인트 저장됨 등) | `lab.notify(...)` |

---

### `@lab.on_finish` — 함수 끝/에러 자동 알림

함수 정의 위에 한 줄만 추가하면, 함수가 **정상 종료**되면 ✅ + 소요시간, **예외로 죽으면** ❌ + 마지막 트레이스백 한 줄을 자동으로 보냄.

```python
import labdobby as lab

@lab.on_finish
def train(model, loader, epochs=50):
    for epoch in range(epochs):
        for x, y in loader:
            ...
        lab.notify(f"epoch {epoch+1}/{epochs} loss={loss:.3f}")  # 중간 알림은 직접
    return model

train(model, loader)
```

학습이 끝까지 돌면 Slack에:
```
[t4-server] ✅ train done in 1h23m
```

중간에 OOM 같은 거 터지면:
```
[t4-server] ❌ train failed in 12m4s
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB
```
(예외는 알림 후 그대로 다시 raise되니까 본인 코드 흐름은 안 바뀜.)

**옵션:**

```python
@lab.on_finish(name="lr=1e-3 run", tag="lr_sweep_v2")
def train(): ...
```
- `name=`: 메시지에 표시될 이름. 안 주면 함수 이름(`train`) 그대로 사용.
- `tag=`: 실험 여러 개 동시에 돌릴 때 prefix로 구분. 메시지가 `[t4-server][lr_sweep_v2] ✅ ...` 형태가 됨.

> 함수가 너무 짧으면 (1초 안 걸리면) 알림 의미 없음. 길게 도는 함수에만 붙이기.

---

### `with lab.block(...)` — 코드 구간 끝/에러 자동 알림

함수가 아니라 **그냥 코드 한 구간**에 알림을 붙이고 싶을 때. 노트북에서 셀 한 두 개를 묶을 때 특히 유용.

```python
import labdobby as lab

with lab.block("데이터 전처리"):
    df = load_csv("raw.csv")
    df = clean(df)
    save(df, "clean.csv")
# → ✅ 데이터 전처리 done in 4m12s
```

**여러 단계 줄세우기:**

```python
with lab.block("전처리"):
    preprocess()

with lab.block("학습"):
    train()

with lab.block("평가"):
    evaluate()
```

각 블록 끝날 때마다 알림이 따로 오니까, 어디서 막혔는지 한눈에 보임.

**에러 케이스도 같음** — 블록 안에서 예외 나면 `❌ 학습 failed in 3m1s` + 트레이스백 마지막 줄. 예외는 그대로 위로 전파.

**옵션:**
```python
with lab.block("학습", tag="lr_sweep_v2"):
    ...
```
- 첫 인자(이름)는 필수. 안 주면 그냥 `block`이라 표시되니 의미 있는 이름 권장.
- `tag=`는 `@on_finish`와 동일.

---

### `@on_finish` vs `with block` — 언제 뭘?

| | `@on_finish` | `with block` |
|---|---|---|
| 대상 | 함수 정의 | 임의 코드 구간 |
| 어디 어울리나 | 메인 학습 함수처럼 한 덩어리로 도는 코드 | 노트북에서 셀 묶기, 한 함수 안의 단계 나누기 |
| 이름 | 함수 이름 자동 | 직접 지정 |

대충: **함수 단위 = `@on_finish`**, **그 외 구간 = `with block`**. 둘 다 같은 일을 하는 두 가지 표면이라 본인 코드 모양에 자연스러운 쪽으로.

---

### 조합 / 중첩

`watch` + `on_finish` + `block` 같이 써도 안전함:

```python
lab.watch()                    # 스크립트 전체 안전망

@lab.on_finish                 # 메인 함수 단위 알림
def main():
    with lab.block("전처리"):  # 단계별 알림
        preprocess()
    with lab.block("학습"):
        train()

main()
```

이 경우 단계 끝날 때마다 알림 + `main` 끝났을 때 알림 + 스크립트 종료 시 알림 — **세 번 받음**. 너무 시끄러우면 `watch()` 빼고 `@on_finish`만, 또는 그 반대로.

> `watch()`는 `.py` 스크립트 전용. Jupyter/Colab에서는 동작 안 함 — 노트북에서는 `notify` / `@on_finish` / `with block` 사용.

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
