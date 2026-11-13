"""Acrescenta uma entrada à DDS preservando as partes existentes do pacote Word."""

import base64
import io
import re
import unicodedata
from datetime import datetime
from uuid import uuid4
from xml.dom import minidom
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


def prepare_entry(payload, local_images):
    date = (payload.get("data_preenchimento") or "").strip()
    try:
        date_format = "%d/%m/%Y - %H:%M:%S" if " - " in date else "%d/%m/%Y"
        date = datetime.strptime(date, date_format).strftime(date_format)
    except ValueError:
        raise ValueError("Informe DD/MM/AAAA ou DD/MM/AAAA - HH:MM:SS com valores válidos.") from None
    author = (payload.get("autor_nome") or "").strip()
    text = (payload.get("implementacao_texto") or "").strip()
    if not author or not text:
        raise ValueError("Informe o responsável e o detalhamento da implementação.")
    details = text.splitlines()
    formatted = payload.get("implementacao_runs")
    if formatted is not None:
        if not isinstance(formatted, list) or any(
            not isinstance(line, list) or any(
                not isinstance(run, dict) or not isinstance(run.get("text"), str)
                or type(run.get("bold")) is not bool or any(c in run["text"] for c in "\r\n")
                or ("font_size" in run and (type(run["font_size"]) is not int or not 8 <= run["font_size"] <= 36))
                for run in line
            ) for line in formatted
        ):
            raise ValueError("A formatação do detalhamento é inválida.")
        plain = ["".join(run["text"] for run in line) for line in formatted]
        if "\n".join(plain).strip() != text:
            raise ValueError("O texto formatado diverge do detalhamento.")
        while plain and not plain[0].strip():
            plain.pop(0)
            formatted = formatted[1:]
        while plain and not plain[-1].strip():
            plain.pop()
            formatted = formatted[:-1]
        details = plain
    else:
        formatted = details
    header = payload.get("development_header", {})
    if not isinstance(header, dict):
        raise ValueError("Formato do nome e da data inválido.")
    layout = header.get("layout", "date_first")
    date_text, _, time = date.partition(" - ")
    common_size = header.get("font_size", 11)
    author_size = header.get("author_size", common_size)
    date_size = header.get("date_size", common_size)
    time_size = header.get("time_size", common_size) if time else common_size
    time_layout = header.get("time_layout", "inline") if time else "inline"
    if (
        layout not in ("date_first", "author_first", "same_line")
        or time_layout not in ("inline", "below")
        or any(type(size) is not int or not 8 <= size <= 36 for size in (author_size, date_size, time_size))
    ):
        raise ValueError("Escolha uma disposição e um tamanho entre 8 e 36 pt.")
    date_label = header.get("date_label", "-")
    author_label = header.get("author_label", "Responsável:")
    if any(not isinstance(label, str) or len(label) > 60 or any(c in label for c in "\r\n")
           for label in (date_label, author_label)):
        raise ValueError("Informe rótulos válidos para a data e o nome.")
    date_lines = [[{"text": f"{date_label.strip()} {date_text}".strip(),
                    "bold": header.get("date_bold") is True, "font_size": date_size}]]
    if time:
        time_run = {"text": time, "bold": header.get("time_bold", header.get("date_bold")) is True, "font_size": time_size}
        if time_layout == "below":
            date_lines.append([time_run])
        else:
            date_lines[0].extend([{"text": " - ", "bold": False, "font_size": date_size}, time_run])
    author_run = {"text": f"{author_label.strip()} {author}".strip(),
                  "bold": header.get("author_bold") is True, "font_size": author_size}
    if layout == "same_line":
        date_lines[0].extend([{"text": " | ", "bold": False, "font_size": date_size}, author_run])
        lines = date_lines
    elif layout == "author_first":
        lines = [[author_run], *date_lines]
    else:
        lines = [*date_lines, [author_run]]
    if payload.get("pacote"):
        lines.append("Pacote / cartão / branch: " + payload["pacote"].strip())
    lines.extend(formatted[1:] if details[0].strip() == f"- {date}" else formatted)
    if payload.get("recomendacoes"):
        lines.extend(["Instruções de teste desta entrega:", *payload["recomendacoes"].splitlines()])
    if payload.get("incluir_checklist") and payload.get("checklist"):
        lines.append("Revisão de código desta entrega:")
        lines.extend(f'{row["pergunta"]} — {row["resposta"]}' for row in payload["checklist"])
    images = {}
    preview = []
    for line in lines:
        plain_line = line if isinstance(line, str) else "".join(run["text"] for run in line)
        marker = re.fullmatch(r"!(.+)!", plain_line.strip())
        if not marker:
            preview.append({"runs": [{"text": line}] if isinstance(line, str) else line})
            continue
        name = marker.group(1)
        exact = [image for image in local_images if image["filename"] == name]
        matches = exact or [image for image in local_images if image["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"A imagem {name} está ausente ou tem nome duplicado. Insira o marcador novamente.")
        image = matches[0]
        images[name] = base64.b64decode(image["url"].split(",", 1)[1])
        preview.append({"image": image["url"], "name": image["name"]})
    return lines, images, preview


def paragraph_text(paragraph):
    return "".join(t.firstChild.data for t in paragraph.getElementsByTagNameNS(W, "t") if t.firstChild)


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)).strip()


def append_development(original, lines, images, *, font_size=11, bold=False):
    return append_section(original, lines, images, "Desenvolvimento", font_size=font_size, bold=bold)


def append_section(original, lines, images, section, *, font_size=11, bold=False):
    """Retorna um novo DOCX e o contexto do ponto de inserção."""
    if type(font_size) is not int or not 8 <= font_size <= 36 or type(bold) is not bool:
        raise ValueError("Escolha um tamanho de 8 a 36 pt e uma opção válida de negrito.")
    def render_run(text, strong, size):
        return (
            f'<w:r><w:rPr><w:b w:val="{int(strong)}"/><w:sz w:val="{size * 2}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
        )
    with ZipFile(io.BytesIO(original)) as source:
        doc = minidom.parseString(source.read("word/document.xml"))
        paragraphs = list(doc.getElementsByTagNameNS(W, "p"))
        headings = [normalized(paragraph_text(p)) for p in paragraphs]
        start, boundary = _section_bounds(headings, section)
        content = paragraphs[start:boundary]
        previous = next(p for p in reversed(content) if paragraph_text(p).strip() or
                        p.getElementsByTagNameNS(W, "drawing") or p.getElementsByTagNameNS(W, "pict"))
        anchor = paragraphs[boundary] if boundary < len(paragraphs) else None
        parent = previous.parentNode
        if parent.localName not in ("body", "tc"):
            raise ValueError("O último bloco da seção está em um formato não reconhecido.")
        insert_before = previous.nextSibling

        changes = {}
        if images:
            relationships = minidom.parseString(source.read("word/_rels/document.xml.rels"))
            content_types = minidom.parseString(source.read("[Content_Types].xml"))
        drawing_id = max((int(p.getAttribute("id")) for p in doc.getElementsByTagNameNS(WP, "docPr")
                          if p.getAttribute("id").isdigit()), default=0)
        for line in lines:
            plain_line = line if isinstance(line, str) else "".join(run["text"] for run in line)
            match = re.fullmatch(r"!(.+)!", plain_line.strip())
            if match:
                name = match.group(1)
                drawing_id += 1
                markup = _embed_image(images[name], name, drawing_id, relationships, content_types, changes)
            else:
                runs = [{"text": line, "bold": bold}] if isinstance(line, str) else line
                markup = "".join(render_run(run["text"], run["bold"], run.get("font_size", font_size)) for run in runs)
            paragraph = minidom.parseString(
                f'<w:p xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}">{markup}</w:p>'
            ).documentElement
            parent.insertBefore(doc.importNode(paragraph, True), insert_before)
        changes["word/document.xml"] = doc.toxml(encoding="utf-8")
        if images:
            changes["word/_rels/document.xml.rels"] = relationships.toxml(encoding="utf-8")
            changes["[Content_Types].xml"] = content_types.toxml(encoding="utf-8")
        output = io.BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info, changes.pop(info.filename) if info.filename in changes else source.read(info))
            for name, data in changes.items():
                target.writestr(name, data)
        before = paragraph_text(previous).strip() or "Imagem no fim da seção"
        return output.getvalue(), before[-300:], paragraph_text(anchor) if anchor else "Fim do documento"


def _section_bounds(headings, section):
    header = r"^preenchido pel[oa] "
    target = header + re.escape(normalized(section)) + r"\b"
    starts = [i for i, text in enumerate(headings) if re.match(target, text)]
    if len(starts) != 1:
        raise ValueError(f"Não foi possível identificar uma única seção de {section}.")
    start = starts[0]
    auxiliary = r"^(?:revisao final\b|checklist\b|recomendacoes (?:e|para|de)\b)"
    boundary = next((i for i in range(start + 1, len(headings))
                     if re.match(header, headings[i]) or re.match(auxiliary, headings[i])), len(headings))
    return start, boundary


def _embed_image(raw, name, drawing_id, relationships, content_types, changes):
    with Image.open(io.BytesIO(raw)) as image:
        width, height = image.size
        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
    uid = uuid4().hex
    rid = f"rIdDDS{uid}"
    filename = f"media/dds-{uid}.png"
    changes[f"word/{filename}"] = buffer.getvalue()
    rel_prefix = relationships.documentElement.prefix
    relationship = relationships.createElementNS(RELS, f"{rel_prefix}:Relationship" if rel_prefix else "Relationship")
    relationship.setAttribute("Id", rid)
    relationship.setAttribute("Type", f"{R}/image")
    relationship.setAttribute("Target", filename)
    relationships.documentElement.appendChild(relationship)
    type_prefix = content_types.documentElement.prefix
    part = content_types.createElementNS(TYPES, f"{type_prefix}:Override" if type_prefix else "Override")
    part.setAttribute("PartName", f"/word/{filename}")
    part.setAttribute("ContentType", "image/png")
    content_types.documentElement.appendChild(part)
    scale = min(9525, 5200000 / width, 6500000 / height)
    cx, cy = max(1, int(width * scale)), max(1, int(height * scale))
    label = quoteattr(name)
    return (
        f'<w:r><w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:docPr id="{drawing_id}" name={label}/><a:graphic><a:graphicData uri="{PIC}">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{drawing_id}" name={label}/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
    )
