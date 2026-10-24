from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
INLINE_TAG_RE = re.compile(r"(?<![\w/])#([\w\-\u4e00-\u9fff/]+)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+] |\d+[.)] )")


@dataclass
class ParsedChunk:
    heading: str
    content: str
    line_start: int
    line_end: int


@dataclass
class ParsedDocument:
    title: str
    tags: list[str]
    chunks: list[ParsedChunk]


def _frontmatter(lines: list[str]) -> tuple[dict[str, str | list[str]], int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0
    data: dict[str, str | list[str]] = {}
    index = 1
    while index < len(lines) and lines[index].strip() != "---":
        line = lines[index].strip()
        if ":" in line:
            key, value = line.split(":", 1)
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                data[key.strip().lower()] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            else:
                data[key.strip().lower()] = value.strip("'\"")
        index += 1
    return data, min(index + 1, len(lines))


def parse_markdown(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    meta, body_start = _frontmatter(lines)
    title = str(meta.get("title", "")).strip() or path.stem
    raw_tags = meta.get("tags", [])
    if isinstance(raw_tags, str):
        tags = [tag.strip().lstrip("#") for tag in raw_tags.split(",") if tag.strip()]
    else:
        tags = [str(tag).strip().lstrip("#") for tag in raw_tags if str(tag).strip()]
    tags.extend(INLINE_TAG_RE.findall(text))
    tags = sorted(set(tags), key=str.casefold)

    headings: list[tuple[int, str]] = []
    chunks: list[ParsedChunk] = []
    buffer: list[str] = []
    start_line = body_start + 1

    def flush(end_line: int) -> None:
        nonlocal buffer, start_line
        content = "\n".join(buffer).strip()
        if content:
            heading = " › ".join(label for _, label in headings) or title
            chunks.append(ParsedChunk(heading=heading, content=content, line_start=start_line, line_end=end_line))
        buffer = []

    for offset, line in enumerate(lines[body_start:], start=body_start + 1):
        match = HEADING_RE.match(line)
        if match:
            flush(offset - 1)
            level, label = len(match.group(1)), match.group(2).strip()
            headings = [(depth, name) for depth, name in headings if depth < level]
            headings.append((level, label))
            if level == 1 and title == path.stem:
                title = label
            start_line = offset + 1
            continue

        is_boundary = not line.strip() and buffer and any(part.strip() for part in buffer)
        if is_boundary:
            flush(offset - 1)
            start_line = offset + 1
        else:
            if not buffer and not line.strip():
                start_line = offset + 1
            else:
                buffer.append(line)
    flush(len(lines))

    return ParsedDocument(title=title, tags=tags, chunks=chunks)

