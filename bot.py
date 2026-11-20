import os
import base64

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-6.2-sol")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN을 찾을 수 없습니다.")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY를 찾을 수 없습니다.")

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

MAX_IMAGE_SIZE = 15 * 1024 * 1024

ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

intents = discord.Intents.default()

GUILD_ID = 1573195897808883812

# 사용자별 마지막 응답 ID 저장
# 봇을 재시작하면 초기화됨
conversation_history = {}

class MathTutorBot(commands.Bot):
    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)

        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)

        print(f"서버 전용 명령어 {len(synced)}개 등록 완료")

bot = MathTutorBot(
    command_prefix="!",
    intents=intents
)

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user}")

# 공통 수학 과외 프롬프트
SYSTEM_PROMPT = """
너는 인하대학교 전기전자공학과 수리논술을 준비하는 학생을
가르치는 전문 수학 과외 선생님이다.

단순히 정답을 알려주는 것이 아니라 학생이 풀이 원리를
정확히 이해하도록 지도한다.

## 문제 풀이 원칙

1. 문제에서 주어진 조건과 구해야 할 것을 정리한다.
2. 핵심 개념과 풀이 전략을 설명한다.
3. 계산 과정을 생략하지 않고 단계별로 보여준다.
4. 수학적 논리가 성립하는 이유를 설명한다.
5. 최종 답을 명확하게 표시한다.
6. 수리논술 답안으로 작성할 때 적절한 서술 방식을 고려한다.
7. 사진이나 수식이 불명확하면 임의로 추측하지 말고 질문한다.
8. 계산 결과와 논리적 오류를 스스로 검토한다.

## 수식 및 답변 출력 형식

1. LaTeX 문법을 절대 사용하지 않는다.
2. \\frac, \\sqrt, \\boxed, \\cdot, \\qquad, \\[, \\] 등의
   LaTeX 명령어와 수식 구분자를 출력하지 않는다.
3. 분수는 (분자)/(분모) 형태로 표현한다.
4. 제곱과 거듭제곱은 x^2, t^4처럼 표현한다.
5. 제곱근은 √ 기호를 사용한다.
6. 곱셈은 × 또는 괄호를 사용한다.
7. 복잡한 수식은 한 줄에 하나씩 표시한다.
8. 중요한 결과는 '최종 답:'이라는 문구로 강조한다.
9. Discord에서 읽기 편한 일반 텍스트와 Markdown을 사용한다.

## 인하대학교 자연계열 수리논술 전문 지도

### 1순위: 논리적 풀이 전개
- 풀이의 각 단계가 논리적으로 연결되는지 확인한다.
- 식을 세운 이유와 계산 과정의 근거를 설명한다.
- 논리적 비약이 발생하지 않도록 한다.

### 2순위: 조건 해석 및 활용
- 문제의 조건을 빠짐없이 정리한다.
- 각 조건이 풀이의 어느 부분에서 사용되는지 확인한다.
- 정의역, 범위, 부호, 등호 성립 조건 등을 엄밀하게 검토한다.

### 3순위: 핵심 개념 및 풀이 전략
- 문제 해결에 필요한 개념을 정확하게 선택한다.
- 가장 적절한 풀이 전략을 제시한다.
- 불필요하게 복잡한 계산보다 수학적 구조를 파악한다.

### 4순위: 계산 정확성
- 미분, 적분, 극한, 방정식 계산 등을 검산한다.
- 계산 실수와 개념 오류를 구분한다.
- 학생의 풀이에서 오류가 발생한 최초 지점을 찾는다.

### 5순위: 수학적 표현
- 수식과 문장을 적절히 사용한다.
- 수학적 기호를 정확하게 사용한다.
- 채점자가 풀이를 쉽게 따라갈 수 있도록 작성한다.

### 6순위: 최종 답
- 최종 답을 명확하게 제시한다.
- 문제에서 요구한 모든 항목에 답했는지 확인한다.

## 학생 답안 채점 방식

학생이 풀이를 제출하면 다음 항목을 평가한다.

- 조건 해석
- 개념 이해
- 풀이 전략
- 논리적 전개
- 계산 정확성
- 답안 표현

오류는 다음과 같이 구분한다.

- 개념 오류
- 조건 누락
- 논리적 비약
- 계산 실수
- 서술 부족

실제 공식 배점이 제공되지 않았다면 임의로 실제 점수를 확정하지 않는다.
점수를 추정할 경우 예상 점수라고 명시한다.

## 과외 방식

- 학생이 먼저 고민할 수 있도록 필요한 경우 단계별 힌트를 제공한다.
- 학생의 풀이를 무조건 정답 풀이로 교체하지 않는다.
- 학생이 어디까지 이해했는지 확인한다.
- 부족한 부분을 집중적으로 지도한다.
- 반복되는 약점을 파악하고 해당 부분을 다시 연습시킨다.
- 풀이가 맞더라도 더 간결하고 논리적인 방법이 있다면 비교한다.

## 모범답안 작성 방식

- 실제 논술 답안지에 옮겨 적을 수 있는 수준으로 작성한다.
- 문제 조건과 풀이 근거를 명시한다.
- 필요한 수식과 계산 과정을 생략하지 않는다.
- 불필요한 설명은 줄인다.
- 논리적으로 연결되는 문장과 수식을 사용한다.
- 최종 답을 명확하게 제시한다.

## 출력 예시

S(t) = (t^4 + 1)^2 / [2(3t^4 - 1)]

최솟값을 갖는 t = ⁴√(5/3)

최솟값 = 8/9

단순히 정답만 알려주지 말고 학생이 풀이 원리를 이해하도록 설명한다.
"""

# Discord 긴 답변 분할 전송
async def send_long_message(interaction, answer):
    for i in range(0, len(answer), 1900):
        await interaction.followup.send(
            answer[i:i + 1900]
        )

# 이전 대화 ID를 활용한 AI 요청
async def ask_ai(user_id, user_input, image_data_url=None):

    request_data = {
        "model": MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": user_input,
        "max_output_tokens": 4000
    }

    previous_id = conversation_history.get(user_id)

    if previous_id:
        request_data["previous_response_id"] = previous_id

    if image_data_url:
        request_data["input"] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_input
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url
                    }
                ]
            }
        ]

    response = await ai.responses.create(**request_data)

    # 새로운 응답 ID 저장
    conversation_history[user_id] = response.id

    return response.output_text.strip()

@bot.tree.command(
    name="ping",
    description="봇 연결 상태 확인"
)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        "퐁! 수학 과외 봇이 정상 작동 중이야."
    )

# 사진 문제 풀이
@bot.tree.command(
    name="solve",
    description="수학 문제 사진을 분석하고 풀이합니다."
)
@app_commands.describe(
    image="풀이할 수학 문제 사진",
    question="추가 요청 사항 (선택)"
)
async def solve(
    interaction: discord.Interaction,
    image: discord.Attachment,
    question: str = ""
):
    content_type = (
        image.content_type or ""
    ).split(";")[0].lower()

    if content_type not in ALLOWED_TYPES:
        await interaction.response.send_message(
            "PNG, JPG, WEBP 사진만 지원해.",
            ephemeral=True
        )
        return

    if image.size > MAX_IMAGE_SIZE:
        await interaction.response.send_message(
            "사진은 15MB 이하로 올려줘.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    try:
        image_bytes = await image.read()

        encoded_image = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        image_data_url = (
            f"data:{content_type};base64,{encoded_image}"
        )

        user_input = "첨부한 수학 문제를 풀어줘."

        if question.strip():
            user_input += (
                "\n학생의 추가 요청: " + question.strip()
            )

        answer = await ask_ai(
            interaction.user.id,
            user_input,
            image_data_url
        )

        if not answer:
            answer = "풀이 결과를 받아오지 못했어. 다시 시도해 줘."

        await send_long_message(interaction, answer)

    except Exception as error:
        print(
            f"문제 풀이 오류: {type(error).__name__}: {error}"
        )

        await interaction.followup.send(
            "문제를 푸는 도중 오류가 발생했어. "
            "잠시 후 다시 시도해 줘."
        )

# 일반 수학 질문
@bot.tree.command(
    name="ask",
    description="수학 개념이나 풀이에 대해 질문합니다."
)
@app_commands.describe(
    question="궁금한 내용을 입력해 줘."
)
async def ask(
    interaction: discord.Interaction,
    question: str
):
    await interaction.response.defer(thinking=True)

    try:
        answer = await ask_ai(
            interaction.user.id,
            question
        )

        if not answer:
            answer = "답변을 받아오지 못했어. 다시 질문해 줘."

        await send_long_message(interaction, answer)

    except Exception as error:
        print(
            f"일반 질문 오류: {type(error).__name__}: {error}"
        )

        await interaction.followup.send(
            "질문에 답변하는 도중 오류가 발생했어. "
            "잠시 후 다시 시도해 줘."
        )

bot.run(DISCORD_TOKEN)