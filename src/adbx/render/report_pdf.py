"""Scrittura PDF dei report (O7): testo monospaziato, una pagina per foglio.

Non è un motore di layout: le pagine arrivano già composte dal report engine.
Qui si sceglie il formato (letter o landscape per i report larghi), si scala
il font Courier per far entrare la larghezza e si emette un PDF 1.4 minimale
senza dipendenze esterne.
"""

from __future__ import annotations

from pathlib import Path

from ..data.report_engine import ReportOutput


def _escape(text: str) -> str:
    body = text.encode("latin-1", "replace").decode("latin-1")
    return body.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_report_pdf(output: ReportOutput, path: str | Path,
                     title: str = "Report", *, font_size: float | None = None,
                     landscape: bool | None = None,
                     driver=None) -> Path:
    target = Path(path)
    width = 792 if landscape is None and output.width > 100 else 612
    height = 612 if width == 792 else 792
    if landscape is False:
        width, height = 612, 792
    elif landscape is True:
        width, height = 792, 612
    margin = 36.0
    usable = width - margin * 2
    if font_size is None:
        font_size = max(4.0, min(10.0, usable / max(1, output.width) / 0.6))
    leading = font_size * 1.25
    if driver is None:
        try:
            from ..config.printers import current_printer
            driver = current_printer()
        except ImportError:  # pragma: no cover
            driver = None
    left_margin = margin
    top_margin = margin
    if driver is not None:
        left_margin = max(6.0, min(width / 3,
                                   driver.margin_left * font_size * 0.6 + 6.0))
        max(6.0, min(width / 3,
                                    driver.margin_right * font_size * 0.6 + 6.0))
        top_margin = max(6.0, min(height / 3,
                                  driver.margin_top * leading + 6.0))
        max(6.0, min(height / 3,
                                     driver.margin_bottom * leading + 6.0))

    objects: list[bytes] = []

    def add(body: str | bytes) -> int:
        data = body.encode("latin-1") if isinstance(body, str) else body
        objects.append(data)
        return len(objects)

    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
                  "/Encoding /WinAnsiEncoding >>")
    page_ids: list[int] = []
    content_ids: list[int] = []
    for page in output.pages:
        commands = ["BT", f"/F1 {font_size:.2f} Tf", f"{leading:.2f} TL",
                    f"1 0 0 1 {left_margin:.2f} "
                    f"{height - top_margin:.2f} Tm"]
        for line in page.lines:
            commands.append(f"({_escape(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands)
        content_ids.append(add(
            f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n"
            f"{stream}\nendstream"))
        page_ids.append(0)
    pages_id = len(objects) + len(output.pages) + 2
    for index, content_id in enumerate(content_ids):
        page_ids[index] = add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox "
            f"[0 0 {width} {height}] /Resources << /Font << /F1 {font_id} 0 R "
            f">> >> /Contents {content_id} 0 R >>")
    # l'id della pagina radice è calcolato prima di aggiungerla
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    actual_pages_id = add(f"<< /Type /Pages /Kids [{kids}] "
                          f"/Count {len(page_ids)} >>")
    catalog_id = add(f"<< /Type /Catalog /Pages {actual_pages_id} 0 R >>")
    info_id = add(f"<< /Title ({_escape(title)}) /Producer (adbx) >>")
    # se il calcolo preventivo non coincide, correggi il Parent di ogni pagina
    if actual_pages_id != pages_id:
        for index in range(len(page_ids)):
            objects[page_ids[index]] = objects[page_ids[index]].replace(
                f"/Parent {pages_id} 0 R".encode(),
                f"/Parent {actual_pages_id} 0 R".encode())

    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(buffer))
        buffer += f"{number} 0 obj\n".encode()
        buffer += body
        buffer += b"\nendobj\n"
    xref = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode()
    buffer += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        buffer += f"{offset:010d} 00000 n \n".encode()
    buffer += (f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R "
               f"/Info {info_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
    target.write_bytes(bytes(buffer))
    return target


__all__ = ["write_report_pdf"]
