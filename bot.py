import os
import asyncio
from collections import defaultdict
import base64

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

from tutor import answer_question

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
conversation_locks = defaultdict(asyncio.Lock)

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
    print(f"위키 단일 에이전트 로그인 성공: {bot.user}", flush=True)

# Discord 긴 답변 분할 전송
async def send_long_message(interaction, answer):
    for i in range(0, len(answer), 1900):
        await interaction.followup.send(
            answer[i:i + 1900]
        )

# 이전 대화 ID를 활용한 AI 요청
async def ask_ai(user_id, user_input, image_data_url=None):

    async with conversation_locks[user_id]:
        result = await answer_question(
            ai, MODEL, user_input, image_data_url=image_data_url,
            previous_id=conversation_history.get(user_id),
        )
        conversation_history[user_id] = result.response_id
        return result.answer


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
            f"문제 풀이 오류: {type(error).__name__}"
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
            f"일반 질문 오류: {type(error).__name__}"
        )

        await interaction.followup.send(
            "질문에 답변하는 도중 오류가 발생했어. "
            "잠시 후 다시 시도해 줘."
        )

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
