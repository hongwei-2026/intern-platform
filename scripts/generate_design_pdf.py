"""生成一份可下载的「项目设计」PDF 模板（无第三方依赖）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = [
    ROOT / "data" / "samples",
    ROOT / "apps" / "web" / "public" / "samples",
]

TITLE = "Open-Source Internship Project Design"
LINES = [
    "HUST OpenAtom Internship — Project Design Template",
    "",
    "1. Project Title",
    "   [Fill in your target project name]",
    "",
    "2. Background & Motivation",
    "   Describe why this project matters and your related experience.",
    "",
    "3. Goals & Deliverables",
    "   - Milestone 1 (Week 1-2): ...",
    "   - Milestone 2 (Week 3-5): ...",
    "   - Milestone 3 (Week 6-8): ...",
    "",
    "4. Technical Approach",
    "   Languages, repos, tests, CI, and architecture sketch.",
    "",
    "5. Schedule & Weekly Commitment",
    "   Estimated hours per week and risk buffer.",
    "",
    "6. References",
    "   Links to issues, docs, and prior work.",
    "",
    "Submit this PDF together with your resume when applying.",
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(lines: list[str]) -> bytes:
    # Simple one-page PDF with Helvetica text lines.
    y0 = 780
    content_lines = ["BT", "/F1 11 Tf", "14 TL", f"1 0 0 1 50 {y0} Tm"]
    for i, line in enumerate(lines):
        esc = _escape(line)
        if i == 0:
            content_lines.append(f"({esc}) Tj")
        else:
            content_lines.append("T*")
            content_lines.append(f"({esc}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode() + stream + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def main() -> None:
    pdf = build_pdf(LINES)
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        path = d / "project-design-template.pdf"
        path.write_bytes(pdf)
        print("wrote", path)


if __name__ == "__main__":
    main()
