# 디스코드 수리논술 봇

사진 한 장으로 수학 문제를 풀고, 같은 학생이 텍스트로 후속 질문을 할 수 있는 봇입니다. Discord 서버 채널에서 사용합니다.

## 처음 연결할 때

1. [Discord 개발자 포털](https://discord.com/developers/applications)에서 앱을 만들고 **Bot** 메뉴에서 봇 토큰을 발급받습니다.
2. **Installation → Guild Install**에서 `bot`과 `applications.commands`를 선택합니다. 봇이 사용할 채널에 **View Channels**, **Send Messages** 권한을 주고, **Install Link**로 테스트 서버에 초대합니다. [Discord 설치 가이드](https://docs.discord.com/developers/quick-start/getting-started)
3. 현재 `bot.py`의 `GUILD_ID`는 **논술봇 연습실**(`1573195897808883812`)로 설정되어 있습니다. 다른 서버에서 실행할 때는 Discord 사용자 설정의 **고급 → 개발자 모드**를 켜고, 해당 서버 아이콘을 우클릭해 **서버 ID 복사**를 선택한 뒤 이 값을 바꿉니다.
4. 이 폴더의 `.env`에 `DISCORD_BOT_TOKEN`과 `OPENAI_API_KEY`를 입력합니다. 새로 복사한 프로젝트라면 `.env.example`을 `.env`로 복사합니다. 원본 모델 기본값은 `gpt-6.2-sol`이며, 계정에서 사용할 다른 이미지 입력 모델을 지정하려면 `OPENAI_MODEL`을 설정합니다.

## 실행

이 폴더에서 PowerShell을 열고 실행합니다.

```powershell
.\.venv\Scripts\python.exe .\bot.py
```

다른 PC에 처음 설치할 때는 Python 3.12를 준비하고 아래 명령으로 가상환경을 생성한 뒤 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

콘솔에 서버 전용 명령어 3개 등록과 로그인 성공이 표시되면, 해당 서버의 텍스트 채널에서 확인합니다.

| 명령 | 확인할 동작 |
| --- | --- |
| `/ping` | 봇이 “퐁!”으로 답합니다. OpenAI 호출 없이 Discord 연결을 확인합니다. |
| `/solve` | PNG, JPG, WebP 중 한 장을 첨부하면 풀이가 나옵니다. 봇의 사진 크기 제한은 15 MiB입니다. |
| `/ask` | “두 번째 식을 세운 이유가 뭐야?”라고 물어보면 같은 사용자의 직전 답변에 이어서 설명합니다. |

봇은 Python 프로세스가 실행되는 동안 응답합니다. PowerShell에서 실행했다면 `Ctrl+C`로 종료할 수 있습니다. 재시작하면 이전 대화 연결이 초기화됩니다.

## 인하대 논술 자료

[문항별 위키](wiki/README.md)에는 2026학년도 기출과 2027학년도 모의고사의 원문, 채점표, 정정 해설이 있습니다. `/ask`와 `/solve`는 기존 과외 지침에 [자료 활용 지침](AGENTS.md)을 더한 단일 튜터를 호출합니다. 튜터는 시험 정보로 로컬 위키를 검색하고, 보관한 PDF에서 필요한 쪽을 이미지로 읽어 입학처 링크와 함께 답합니다. 학생이 시험을 특정하지 못한 경우 후속 질문으로 이어갈 수 있습니다.

## 기존 봇과 비교

[실제 답변 비교](wiki/comparison.md)에서 질문별 판정, 모델 호출 수와 응답 시간을 확인할 수 있습니다. 같은 합성 질문으로 재실험하려면 아래 명령을 실행합니다. 기존 결과를 보존하도록 새 출력 파일 이름을 사용합니다. 두 버전 모두 프로젝트에 설정된 OpenAI 모델을 호출하여 API 사용량이 발생합니다.

```powershell
.\.venv\Scripts\python.exe -m tools.compare_tutors --output comparison-new.jsonl
```
