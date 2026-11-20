"""인하대 논술 위키를 오프라인에서 찾고 검증한다."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
TRACKS = {
    "자연": ("일반", "오전", "오후", "의예"),
    "일반": ("일반", "오전", "오후"),
    "의예과": ("의예",),
}
QUESTION = re.compile(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?")


def load_json(name):
    return json.loads((WIKI / name).read_text(encoding="utf-8"))


def question_number(value):
    if not QUESTION.fullmatch(value):
        raise argparse.ArgumentTypeError("문항 번호는 1 또는 1-3 형식으로 입력하세요.")
    return value


def search(cards, year=None, exam=None, track=None, question=None, terms=()):
    main, _, part = (question or "").partition("-")
    hits = []
    for card in cards:
        if part and int(part) > card["subquestions"]:
            continue
        for route in card["routes"]:
            route_year, route_exam, route_track, number = route.split()
            if (year is not None and str(year) != route_year) or (exam and exam != route_exam):
                continue
            if track and route_track not in TRACKS.get(track, (track,)):
                continue
            if main and main != number:
                continue
            searchable = " ".join([route, card["title"], *card["keywords"]]).casefold()
            if all(term.casefold() in searchable for term in terms):
                hits.append(card)
                break
    return hits


def display(cards, read):
    if not cards:
        print("보관 자료에서 일치하는 문항을 찾지 못했습니다. 학년도·시험·계열을 확인하세요.")
        return 1
    for card in cards:
        print(f'{" / ".join(card["routes"])}번 · {card["title"]} (wiki/{card["file"]})')
    if read and len(cards) == 1:
        print()
        print((WIKI / cards[0]["file"]).read_text(encoding="utf-8").rstrip())
    elif len(cards) > 1:
        print("여러 문항이 일치합니다. 학년도, 기출·모의, 계열·시간대 또는 문항을 확인하세요.")
    return 0


def compare_files(label, recorded, actual, errors):
    if len(recorded) != len(set(recorded)):
        errors.append(f"{label} 목록에 중복 항목이 있습니다.")
    for name in sorted(set(recorded) ^ set(actual)):
        errors.append(f"{label} 목록과 파일 불일치: {name}")


def check_links(sources, errors):
    pages = {(WIKI / s["file"]).resolve(): s["pages"] for s in sources if s["kind"] == "pdf"}
    docs = [ROOT / "README.md", ROOT / "AGENTS.md", *WIKI.rglob("*.md")]
    for doc in docs:
        for label, href in re.findall(r"\[([^\]\n]*)\]\(([^)\n]+)\)", doc.read_text(encoding="utf-8")):
            link = urlsplit(href.strip("<>"))
            if link.scheme or not link.path:
                continue
            target = (doc.parent / unquote(link.path)).resolve()
            if not target.is_file():
                errors.append(f"{doc.name}: 대상 없음 {href}")
            elif target.suffix == ".pdf" and link.fragment:
                page = re.fullmatch(r"page=(\d+)", link.fragment)
                if not page or not 1 <= int(page[1]) <= pages.get(target, 0):
                    errors.append(f"{doc.name}: PDF 쪽수 오류 {href}")
                    continue
                labeled = re.search(r"(\d+)(?:[–~](\d+))?쪽", label)
                if labeled and (int(labeled[1]) != int(page[1]) or
                                not int(page[1]) <= int(labeled[2] or labeled[1]) <= pages[target]):
                    errors.append(f"{doc.name}: 쪽수 표기 불일치 {label}")


def check(cards):
    sources = load_json("sources.json")["sources"]
    cases = load_json("evaluation.json")
    errors = []
    archived = [p.relative_to(WIKI).as_posix() for p in (WIKI / "originals").rglob("*") if p.is_file()]
    compare_files("원본", [s["file"] for s in sources], archived, errors)
    if len({s["id"] for s in sources}) != len(sources):
        errors.append("출처 ID 중복")
    for source in sources:
        path = WIKI / source["file"]
        if path.is_file():
            data = path.read_bytes()
            if len(data) != source["bytes"] or hashlib.sha256(data).hexdigest() != source["sha256"]:
                errors.append(f"원본 크기 또는 SHA-256 불일치: {path.name}")

    files = [p.relative_to(WIKI).as_posix() for p in (WIKI / "cards").glob("*.md")]
    compare_files("카드", [c["file"] for c in cards], files, errors)
    routes = [r for card in cards for r in card["routes"]]
    if len(routes) != len(set(routes)):
        errors.append("서로 다른 카드에 같은 시험 문항이 등록되어 있습니다.")
    index = (WIKI / "README.md").read_text(encoding="utf-8")
    for card in cards:
        path = WIKI / card["file"]
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        if f'({card["file"]})' not in index or not body.startswith("# " + card["title"] + "\n"):
            errors.append(f"카드 제목 또는 위키 색인 불일치: {path.name}")
        if ".pdf#page=" not in body or "채점" not in body:
            errors.append(f"PDF 또는 채점 근거 누락: {path.name}")
        if card["subquestions"] != len(re.findall(r"^## \d+-\d+ ·", body, re.MULTILINE)):
            errors.append(f"소문항 수 불일치: {path.name}")
    check_links(sources, errors)
    for case in cases:
        hits = search(cards, **case["query"])
        if {Path(c["file"]).stem for c in hits} != set(case["matches"]):
            errors.append(f'검색 결과 불일치: {case["name"]}')
        if case.get("evidence"):
            if len(hits) != 1:
                errors.append(f'{case["name"]}: 근거를 확인할 카드가 하나여야 합니다.')
                continue
            path = WIKI / hits[0]["file"]
            if not path.is_file():
                continue  # 카드 파일 누락은 목록 대조에서 보고한다.
            body = path.read_text(encoding="utf-8")
            for phrase in case["evidence"]:
                if phrase not in body:
                    errors.append(f'{case["name"]}: 근거 누락 {phrase}')
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    types = Counter(s["kind"] for s in sources)
    print(f'검증 통과 · PDF {types["pdf"]}개, 공지 {types["notice"]}건, 자막 {types["video"]}개, '
          f'문항 카드 {len(cards)}개, 시험지 문항 {len(routes)}개, 검증 사례 {len(cases)}개')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    find = modes.add_parser("find", help="시험 정보 또는 키워드로 문항 찾기")
    find.add_argument("terms", nargs="*", help="제목·키워드·시험 정보에 포함된 단어")
    find.add_argument("--year", type=int)
    find.add_argument("--exam", choices=["기출", "모의"])
    find.add_argument("--track", choices=["인문", "자연", "일반", "의예", "의예과", "오전", "오후"])
    find.add_argument("--question", type=question_number)
    find.add_argument("--read", action="store_true", help="한 문항으로 확인되면 카드를 출력")
    modes.add_parser("check", help="원본·문항 연결·쪽수·검색 사례 점검")
    args = parser.parse_args()
    cards = load_json("catalog.json")
    if args.mode == "check":
        return check(cards)
    return display(search(cards, args.year, args.exam, args.track, args.question, args.terms), args.read)


if __name__ == "__main__":
    # Windows에서 파이프로 연결해도 수학 기호와 한글을 온전히 전달한다.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
