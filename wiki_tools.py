"""Read-only tools backed by the local Inha admissions archive."""

import base64
import io
import json
import re
from threading import Lock

import pypdfium2 as pdfium

from tools.wiki import QUESTION, WIKI, load_json, search


CATALOG = load_json("catalog.json")
SOURCES = load_json("sources.json")["sources"]
PDFS = {s["id"]: s for s in SOURCES if s["kind"] == "pdf"}
SOURCE_PATHS = {(WIKI / s["file"]).resolve(): s for s in SOURCES}
PDF_LOCK = Lock()  # PDFium requires serialized access even for different documents.


def tool(name, description, properties):
    return {
        "type": "function", "name": name, "description": description, "strict": True,
        "parameters": {
            "type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOLS = [
    tool("find_material", "인하대 자료 검색. 번호·학년도는 학생이 알려준 값만 사용한다. "
         "조건 없는 필드는 null, 검색어는 []로 둔다. 한 문항이면 카드와 출처가 반환된다.", {
             "section": {"type": "string", "enum": ["문항", "전형", "영상"]},
             "year": {"type": ["integer", "null"]},
             "exam": {"enum": ["모의", "기출", None], "type": ["string", "null"]},
             "track": {"enum": ["일반", "오전", "오후", "의예", "인문", "자연", None],
                       "type": ["string", "null"]},
             "question": {"type": ["string", "null"], "description": "예: 1 또는 1-3"},
             "terms": {"type": "array", "items": {"type": "string"},
                       "description": "문항 번호가 있으면 보통 []. 사진 식별 시 한국어 개념어 1~2개."},
         }),
    tool("read_page", "검색에서 찾은 공식 원본 PDF의 한 쪽을 이미지로 읽고 인용 URL을 얻는다.", {
        "source": {"type": "string", "enum": list(PDFS)},
        "page": {"type": "integer", "description": "표지를 포함하여 1부터 세는 PDF 뷰어 쪽수"},
    }),
]


def public_document(path):
    """Replace internal archive links with source identifiers usable in Discord."""
    def replace_link(match):
        label, href = match.groups()
        if href.startswith("https://"):
            return match.group()
        file, _, fragment = href.partition("#")
        source = SOURCE_PATHS.get((path.parent / file).resolve())
        if not source:
            return label
        url = source["url"] + ("#" + fragment if fragment else "")
        return f"[{label}]({url}) (source={source['id']})"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, path.read_text(encoding="utf-8"))


def find_material(section, year, exam, track, question, terms):
    if section in ("전형", "영상"):
        return public_document(WIKI / ("guide.md" if section == "전형" else "videos.md"))
    if section != "문항" or (question and not QUESTION.fullmatch(question)):
        raise ValueError("문항 번호는 1 또는 1-3 형태로 검색하세요.")
    hits = search(CATALOG, year, exam, track, question, terms)
    if len(hits) == 1:
        return public_document(WIKI / hits[0]["file"])
    if not hits:
        return "일치하는 문항 없음. 입력 정보는 유지하고 검색어를 줄이거나 학생에게 원문을 요청하세요."
    return "후보가 여러 개입니다.\n" + "\n".join(
        f'{" / ".join(card["routes"])} · {card["title"]}' for card in hits
    )


def page_image(source, page):
    if source not in PDFS or type(page) is not int or not 1 <= page <= PDFS[source]["pages"]:
        raise ValueError("출처 대장에 등록된 PDF와 쪽수를 확인하세요.")
    with PDF_LOCK, pdfium.PdfDocument(WIKI / PDFS[source]["file"]) as document:
        pdf_page = document[page - 1]
        bitmap = pdf_page.render(scale=2.4)
        try:
            with bitmap.to_pil() as image, io.BytesIO() as buffer:
                image.save(buffer, format="PNG")
                return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        finally:
            bitmap.close()
            pdf_page.close()


def run_tool(name, arguments):
    """Return the function result and a compact trace without student text or images."""
    try:
        args = json.loads(arguments)
        if name == "find_material":
            material = find_material(**args)
            return material, name
        if name == "read_page":
            image = page_image(**args)
            source, page = args["source"], args["page"]
            item = PDFS[source]
            citation = f'{item["title"]} · PDF {page}쪽 · {item["url"]}#page={page}'
            return [
                {"type": "input_text", "text": citation},
                {"type": "input_image", "detail": "high", "image_url": image},
            ], f"{source} p.{page}"
        raise ValueError("등록되지 않은 도구입니다.")
    except (ValueError, TypeError, KeyError, OSError, pdfium.PdfiumError):
        return "자료를 읽지 못했습니다. 출처·쪽수·검색 인자를 확인하세요.", f"{name} error"
