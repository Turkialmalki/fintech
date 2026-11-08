"""File validation and text extraction that preserves pages and sections."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from app.core.errors import AppError

ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

HEADING = re.compile(
    r"^\s*((المادة|الماده|الفصل|الباب|القسم|البند)\s+[؀-ۿ0-9٠-٩]+.*|"
    r"(Article|Section|Chapter|Part)\s+[\w.\-]+.*|"
    r"#{1,4}\s+.+|"
    r"([0-9٠-٩]{1,2}(\.[0-9٠-٩]{1,2}){0,3})[\.\-–)]\s+\S.{0,120})$"
)


@dataclass
class Page:
    number: int
    text: str


@dataclass
class Block:
    page: int | None
    section: str
    text: str


@dataclass
class Extracted:
    pages: list[Page]
    blocks: list[Block] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


class InvalidFile(AppError):
    status_code = 415
    code = "INVALID_FILE"


def validate_file(filename: str, data: bytes, max_mb: int) -> str:
    """Extension whitelist + magic-byte sniffing + size limit. Returns canonical content type."""
    name = (filename or "").lower()
    ext = next((e for e in ALLOWED if name.endswith(e)), None)
    if ext is None:
        raise InvalidFile("Only PDF, DOCX and TXT files are accepted", "يُقبل فقط ملفات PDF وDOCX وTXT")
    if len(data) == 0:
        raise InvalidFile("File is empty", "الملف فارغ")
    if len(data) > max_mb * 1024 * 1024:
        raise InvalidFile(f"File exceeds {max_mb} MB", f"حجم الملف يتجاوز {max_mb} ميجابايت", status_code=413)
    if ext == ".pdf" and not data[:1024].lstrip().startswith(b"%PDF-"):
        raise InvalidFile("File content is not a valid PDF", "محتوى الملف ليس PDF صالحاً")
    if ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" not in z.namelist():
                    raise InvalidFile("File content is not a valid DOCX", "محتوى الملف ليس DOCX صالحاً")
                if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:
                    raise InvalidFile("DOCX archive is too large when expanded", "الملف المضغوط كبير جداً")
        except zipfile.BadZipFile as e:
            raise InvalidFile("File content is not a valid DOCX", "محتوى الملف ليس DOCX صالحاً") from e
    if ext == ".txt":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise InvalidFile("Text files must be UTF-8 encoded", "يجب أن تكون الملفات النصية بترميز UTF-8") from e
        if b"\x00" in data:
            raise InvalidFile("Binary content in text file", "يحتوي الملف النصي على بيانات ثنائية")
    return ALLOWED[ext]


def _blocks_from_lines(pages: list[Page]) -> list[Block]:
    blocks: list[Block] = []
    section = ""
    buf: list[str] = []
    page_of_buf: int | None = None

    def flush():
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            blocks.append(Block(page_of_buf, section, text))
        buf = []

    for p in pages:
        for raw in p.text.splitlines():
            line = raw.strip()
            if not line:
                if buf:
                    buf.append("")
                continue
            if HEADING.match(line) and len(line) < 160:
                flush()
                section = line.lstrip("# ").strip()
                page_of_buf = p.number
                buf = [line]
                continue
            if not buf:
                page_of_buf = p.number
            elif page_of_buf != p.number and len("\n".join(buf)) > 400:
                flush()
                page_of_buf = p.number
            buf.append(line)
        # paragraphs never span a page boundary without recording the start page
    flush()
    return blocks


def extract(filename: str, data: bytes) -> Extracted:
    name = filename.lower()
    meta: dict = {}
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise InvalidFile("Encrypted PDFs are not supported", "ملفات PDF المحمية بكلمة مرور غير مدعومة")
        pages = [Page(i + 1, (pg.extract_text() or "").strip()) for i, pg in enumerate(reader.pages)]
        info = reader.metadata or {}
        if info.get("/Title"):
            meta["title"] = str(info.get("/Title"))
        ex = Extracted(pages, metadata=meta)
        ex.blocks = _blocks_from_lines(pages)
        return ex
    if name.endswith(".docx"):
        import docx

        d = docx.Document(io.BytesIO(data))
        if d.core_properties.title:
            meta["title"] = d.core_properties.title
        blocks: list[Block] = []
        section = ""
        lines: list[str] = []
        buf: list[str] = []
        for para in d.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            lines.append(text)
            style = (para.style.name or "").lower() if para.style is not None else ""
            if style.startswith("heading") or style == "title" or HEADING.match(text):
                if buf:
                    blocks.append(Block(None, section, "\n".join(buf)))
                section, buf = text, [text]
            else:
                buf.append(text)
        for table in d.tables:
            rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
            if rows:
                buf.append("\n".join(rows))
                lines.extend(rows)
        if buf:
            blocks.append(Block(None, section, "\n".join(buf)))
        # DOCX has no fixed pagination; we do not fabricate page numbers.
        return Extracted([Page(1, "\n".join(lines))], blocks, {**meta, "paginated": False})
    text = data.decode("utf-8")
    raw_pages = text.split("\f") if "\f" in text else [text]
    pages = [Page(i + 1, t.strip()) for i, t in enumerate(raw_pages)]
    ex = Extracted(pages, metadata={"paginated": "\f" in text})
    ex.blocks = _blocks_from_lines(pages)
    if len(pages) == 1 and "\f" not in text:
        for b in ex.blocks:
            b.page = None  # no real pagination supplied
    return ex
