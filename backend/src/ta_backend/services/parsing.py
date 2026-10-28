"""输入文件边界：格式、资源上限与可见的部分提取报告。"""

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader
from pypdf.errors import PdfReadError

PARSER_VERSION = "paragraph-v1"


class ParseError(ValueError):
    pass


@dataclass
class ParsedChunk:
    text: str
    locator: str
    section_path: list[str] = field(default_factory=list)
    page_from: int | None = None
    page_to: int | None = None
    paragraph_locator: str | None = None


@dataclass
class ParseResult:
    chunks: list[ParsedChunk]
    warnings: list[str]


def validate_file(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".docx", ".pdf", ".txt", ".md"}:
        raise ParseError("仅支持 DOCX、文本 PDF、TXT 和 Markdown")
    if suffix == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise ParseError("文件内容不是有效的 Word 文档")
                if sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                    raise ParseError("文档解压后超过 100 MB，请拆分后上传")
        except BadZipFile as error:
            raise ParseError("文件内容与 DOCX 格式不符") from error
    elif suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ParseError("文件内容与 PDF 格式不符")
    else:
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ParseError("文本需要使用 UTF-8 编码，请转换后重试") from error
        if "\x00" in decoded or content.startswith((b"%PDF-", b"PK\x03\x04")):
            raise ParseError("文件内容不是纯文本")
    return suffix


def split_text(text: str, limit: int = 600) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[。！？!?；;\n])", text):
        if current and len(current) + len(sentence) > limit:
            pieces.append(current)
            current = current[-60:]
        while len(sentence) > limit:
            pieces.append(sentence[:limit])
            sentence = sentence[limit - 60 :]
        current += sentence
    if current.strip():
        pieces.append(current.strip())
    return pieces


def parse_file(path: Path) -> ParseResult:
    chunks: list[ParsedChunk] = []
    warnings: list[str] = []

    def append(text: str, locator: str, sections: list[str], page: int | None = None):
        for part in split_text(text):
            chunks.append(
                ParsedChunk(part, locator, sections.copy(), page, page, None if page else locator)
            )

    if path.suffix.lower() == ".docx":
        try:
            document = Document(path)
        except (BadZipFile, KeyError, ValueError) as error:
            raise ParseError("Word 文档损坏，无法解析") from error
        sections: list[str] = []
        for index, block in enumerate(document.iter_inner_content(), 1):
            locator = f"段落 {index}"
            if isinstance(block, Table):
                rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in block.rows]
                append("\n".join(rows), f"表格 {index}", sections)
                continue
            text = block.text.strip()
            style = block.style.name if block.style else ""
            match = re.match(r"(?:Heading|标题)\s*(\d+)", style)
            if match and text:
                level = int(match.group(1))
                sections = sections[: level - 1] + [text]
                continue
            if text:
                append(text, locator, sections)
        if document.inline_shapes:
            warnings.append(f"含 {len(document.inline_shapes)} 张图片，未提取图中内容")
        xml = document.element.xml
        if "<m:oMath" in xml:
            warnings.append("含 Word 公式，公式内容需人工核查")
    elif path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ParseError("PDF 已加密，请先导出未加密版本")
            if len(reader.pages) > 100:
                raise ParseError("PDF 超过 100 页，请按章节拆分")
            for page_number, page in enumerate(reader.pages, 1):
                stream = page.get_contents()
                if stream and len(stream.get_data()) > 20 * 1024 * 1024:
                    warnings.append(f"第 {page_number} 页内容流过大，未提取")
                    continue
                text = page.extract_text() or ""
                if not text.strip():
                    warnings.append(f"第 {page_number} 页未提取到文字，可能为扫描页")
                else:
                    for paragraph in re.split(r"\n\s*\n", text):
                        append(paragraph, f"第 {page_number} 页", [], page_number)
        except PdfReadError as error:
            raise ParseError("PDF 损坏或无法读取") from error
    else:
        sections = []
        blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig"))
        for index, block in enumerate(blocks, 1):
            lines = block.strip().splitlines()
            if lines and (heading := re.match(r"^(#{1,6})\s+(.+)$", lines[0])):
                sections = sections[: len(heading.group(1)) - 1] + [heading.group(2)]
                block = "\n".join(lines[1:])
            append(block, f"段落 {index}", sections)
    if not chunks:
        raise ParseError("未提取到可用文字；扫描资料请先 OCR，或上传文本版本")
    return ParseResult(chunks, warnings)
