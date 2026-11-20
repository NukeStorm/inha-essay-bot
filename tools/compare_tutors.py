"""Run both tutors on the same synthetic questions. Run with python -m tools.compare_tutors."""

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError, AsyncOpenAI

from tools.wiki import ROOT
from tutor import answer_question
from wiki_tools import page_image


# Each rubric is for post-run review and is never sent to either tutor.
CASES = {
    "ambiguous": [
        ("의예 1-3에서 막혔어. 첫 힌트 하나만 줘.",
         "학년도·시험 또는 원문을 묻고, 특정 문항의 풀이와 답을 미리 주지 않는다."),
        ("2027 모의야. 우미분계수를 f′(a)−8이라고 썼는데 부호가 왜 틀렸는지만 알려줘.",
         "오른쪽 g(x)=−8x를 빼므로 +8임을 설명하고 정정 원문을 정확히 인용한다. 최종 해는 주지 않는다."),
    ],
    "deduction": [
        ("2027 인하대 모의 자연 일반 1-2에서 도함수 0인 것만 보고 곧바로 최솟값이라고 했어. "
         "다른 부분은 보여주지 않았는데, 이 생략 자체의 공식 감점은 몇 점이야?",
         "증감 확인 누락은 정확히 3점 감점임을 말하고 공식 해설 2쪽을 인용한다. 총점을 단정하지 않는다."),
    ],
    "alternative": [
        ("2026 인하대 자연 오후 기출 2-2를 산술기하평균으로 풀었어. 미분 안 하면 감점이야?",
         "공식 별해를 인정하고 등호·최대 조건을 확인한다. 가이드북 PDF 50~51쪽의 근거를 준다."),
    ],
    "unavailable": [
        ("2025학년도 인하대 의예 1번에서 계산 한 줄을 빠뜨렸어. 공식적으로 몇 점 감점인지 알려줘.",
         "공식 감점을 추정하지 않고, 해당 문항의 문제지·채점표 또는 답안을 요청한다."),
    ],
    "image_hint": [
        ("첨부한 인하대 2027 모의 일반 문제지의 2-3에서 2/π까지 나왔어. 다음 한 단계만 힌트 줘. 최종값은 말하지 마.",
         "2/π가 로그의 극한이라는 사실이나 역변환을 짚되 곱의 최종값을 공개하지 않는다."),
    ],
    "humanities": [
        ("인하대 2027 모의 인문 2번에서 (나), (라)는 잘 골랐고 자료 설명은 비웠어. "
         "국가군 선택 항목만 몇 점인지랑 어디 나오는지만 알려줘.",
         "각 4점, 선택 항목 합계 8점 및 인문 해설 PDF 10쪽을 정확히 안내한다."),
    ],
    "plain_math": [
        ("특정 학교 문제는 아니야. 미분계수가 0이어도 극값이 아닐 수 있는 예를 하나만 짧게 들어줘.",
         "올바른 반례에서 도함수 0과 극값이 아닌 이유를 간결히 설명한다."),
    ],
}


async def compare(output):
    load_dotenv(ROOT / ".env")
    model = os.getenv("OPENAI_MODEL") or "gpt-6.2-sol"
    image = page_image("math-paper", 4)
    failures = []
    limit = asyncio.Semaphore(3)
    async with AsyncOpenAI(timeout=90, max_retries=1) as client:
        with output.open("x", encoding="utf-8") as log:
            async def run(case, variant):
                async with limit:
                    prior = None
                    for number, (question, rubric) in enumerate(CASES[case], start=1):
                        row = dict(case=case, turn=number, variant=variant, model=model,
                                   question=question, rubric=rubric)
                        if case == "image_hint":
                            row["image"] = "math-paper PDF 4"
                        started = time.monotonic()
                        try:
                            async with asyncio.timeout(240):
                                result = await answer_question(
                                    client, model, question, agent=variant == "agent", previous_id=prior,
                                    image_data_url=image if case == "image_hint" else None)
                            prior = result.response_id
                            values = asdict(result)
                            del values["response_id"]
                            row.update(values)
                        except (APIError, TimeoutError, RuntimeError) as err:
                            row["error"] = f"{type(err).__name__} {getattr(err, 'code', '')}"
                            failures.append((case, number, variant))
                        row["seconds"] = round(time.monotonic() - started, 2)
                        log.write(json.dumps(row, ensure_ascii=False) + "\n")
                        log.flush()
                        print(case, number, variant, row.get("error", "ok"), row["seconds"], flush=True)
                        if "error" in row:
                            break
            await asyncio.gather(*(run(case, variant) for case in CASES for variant in ("baseline", "agent")))
    return int(bool(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="새 JSONL 파일 경로")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(compare(args.output)))
