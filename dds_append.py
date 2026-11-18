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


def prepare_mcp_evidence(items, previous=()):
    """Valida imagens da proposta sem ler arquivos por caminho nem persistir anexos."""
    if not isinstance(items, list) or len(items) + len(previous) > 5:
        raise ValueError("Envie até cinco imagens por proposta.")
    evidence = list(previous)
    total = sum(len(image["url"].split(",", 1)[1]) for image in evidence)
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Informe o nome e o conteúdo Base64 de cada imagem.")
        name, encoded = item.get("nome"), item.get("conteudo_base64")
        if (not isinstance(name, str) or not re.fullmatch(r"[^/\\<>\x00-\x1f]{1,120}", name)
                or not isinstance(encoded, str) or not encoded or len(encoded) > 7_000_000):
            raise ValueError("Informe um nome de imagem simples e até 5 MB por arquivo.")
        total += len(encoded)
        if total > 20_000_000:
            raise ValueError("As evidências excedem o limite total de 15 MB.")
        try:
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 5_000_000:
                raise ValueError
            with Image.open(io.BytesIO(raw), formats=["PNG", "JPEG"]) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError
                mime = "image/png" if image.format == "PNG" else "image/jpeg"
                image.load()
        except (ValueError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"Evidência inválida: {name}. Envie um PNG ou JPEG válido de até 5 MB.") from exc
        evidence.append({
            "name": name,
            "filename": f"evidencia-{len(evidence) + 1}",
            "url": f"data:{mime};base64,{encoded}",
        })
    return evidence


def _parse_leading_indent(line):
    indent = 0
    rest = line
    while indent < 6:
        if rest.startswith("\t"):
            rest = rest[1:]
            indent += 1
        elif rest[:5].lower() == "[tab]":
            rest = rest[5:]
            indent += 1
        elif rest.startswith("    "):
            rest = rest[4:]
            indent += 1
        else:
            break
    return indent, rest


def parse_rich_line(line, default_size=11, default_bold=False):
    """Interpreta marcacoes inline simples (**negrito**, [tam=N]/[Npt], #/##/###, Tab/[tab])."""
    stripped = line.strip()
    if re.fullmatch(r"!(.+)!", stripped):
        return stripped
    indent, rest = _parse_leading_indent(line)
    if not rest.strip():
        return []
    line_size = default_size
    line_bold = default_bold
    size_prefix = re.match(r"^\[(?:tam=)?(\d{1,2})(?:pt)?\]\s*", rest, flags=re.IGNORECASE)
    if size_prefix and 8 <= int(size_prefix.group(1)) <= 36:
        line_size = int(size_prefix.group(1))
        rest = rest[size_prefix.end():]
    elif rest.startswith("### "):
        line_size = 11
        line_bold = True
        rest = rest[4:]
    elif rest.startswith("## "):
        line_size = 12
        line_bold = True
        rest = rest[3:]
    elif rest.startswith("# "):
        line_size = 14
        line_bold = True
        rest = rest[2:]
    if not rest:
        return []
    rest = re.sub(r"\[tab\]", "\t", rest, flags=re.IGNORECASE)
    token_re = re.compile(
        r"(\*\*|\[/?b\]|\[(?:tam=)?\d{1,2}(?:pt)?\]|\[/(?:tam|\d{1,2}pt|pt)\])",
        flags=re.IGNORECASE,
    )
    bold_state = line_bold
    size_stack = [line_size]
    runs = []
    for part in token_re.split(rest):
        if not part:
            continue
        low = part.lower()
        if part == "**":
            bold_state = not bold_state
            continue
        if low == "[b]":
            bold_state = True
            continue
        if low == "[/b]":
            bold_state = line_bold
            continue
        open_size = re.fullmatch(r"\[(?:tam=)?(\d{1,2})(?:pt)?\]", low)
        if open_size:
            val = int(open_size.group(1))
            if 8 <= val <= 36:
                size_stack.append(val)
                continue
        if re.fullmatch(r"\[/(?:tam|\d{1,2}pt|pt)\]", low):
            if len(size_stack) > 1:
                size_stack.pop()
            continue
        runs.append({"text": part, "bold": bold_state, "font_size": size_stack[-1], "indent": indent})
    if not runs:
        return []
    return runs


def _normalize_formatted_runs(formatted):
    normalized_lines = []
    for line in formatted:
        if not line:
            normalized_lines.append([])
            continue
        first_indent = line[0].get("indent", 0)
        extra_tabs, remaining = _parse_leading_indent(line[0]["text"])
        tabs_only = 0
        raw_first = line[0]["text"]
        while tabs_only < 6 and raw_first.startswith("\t"):
            raw_first = raw_first[1:]
            tabs_only += 1
        line_indent = min(6, max(first_indent, 0) + tabs_only)
        new_line = []
        for idx, run in enumerate(line):
            item = dict(run)
            if idx == 0 and tabs_only:
                item["text"] = raw_first
            item["indent"] = line_indent if line_indent else item.get("indent", 0)
            if idx == 0 and tabs_only and not item["text"] and len(line) > 1:
                continue
            new_line.append(item)
        normalized_lines.append(new_line)
    return normalized_lines


def _parse_entry_date(raw_date):
    value = (raw_date or "").strip()
    formats = (
        ("%d/%m/%Y - %H:%M:%S", "%d/%m/%Y - %H:%M:%S"),
        ("%d/%m/%Y - %H:%M", "%d/%m/%Y - %H:%M"),
        ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y - %H:%M:%S"),
        ("%d/%m/%Y %H:%M", "%d/%m/%Y - %H:%M"),
        ("%d/%m/%Y", "%d/%m/%Y"),
    )
    for in_fmt, out_fmt in formats:
        try:
            return datetime.strptime(value, in_fmt).strftime(out_fmt)
        except ValueError:
            continue
    raise ValueError("Informe DD/MM/AAAA, DD/MM/AAAA - HH:MM ou DD/MM/AAAA - HH:MM:SS com valores válidos.")


def prepare_entry(payload, local_images):
    date = _parse_entry_date(payload.get("data_preenchimento"))
    author = (payload.get("autor_nome") or "").strip()
    text = (payload.get("implementacao_texto") or "").strip()
    default_size = payload.get("font_size", 11)
    default_bold = payload.get("bold") is True
    if type(default_size) is not int or not 8 <= default_size <= 36:
        default_size = 11
    formatted = payload.get("implementacao_runs")
    if formatted is not None:
        if not isinstance(formatted, list) or any(
            not isinstance(line, list) or any(
                not isinstance(run, dict) or not isinstance(run.get("text"), str)
                or type(run.get("bold")) is not bool or any(c in run["text"] for c in "\r\n")
                or ("font_size" in run and (type(run["font_size"]) is not int or not 8 <= run["font_size"] <= 36))
                or ("indent" in run and (type(run["indent"]) is not int or not 0 <= run["indent"] <= 8))
                for run in line
            ) for line in formatted
        ):
            raise ValueError("A formatação do detalhamento é inválida.")
        plain = ["".join(run["text"] for run in line) for line in formatted]
        if not payload.get("skip_plain_match") and "\n".join(plain).strip() != text:
            raise ValueError("O texto formatado diverge do detalhamento.")
        if not text and payload.get("skip_plain_match"):
            text = "\n".join(plain).strip()
        if not author or not text:
            raise ValueError("Informe o responsável e o detalhamento da implementação.")
        while plain and not plain[0].strip():
            plain.pop(0)
            formatted = formatted[1:]
        while plain and not plain[-1].strip():
            plain.pop()
            formatted = formatted[:-1]
        formatted = _normalize_formatted_runs(formatted)
        details = plain
    else:
        if not author or not text:
            raise ValueError("Informe o responsável e o detalhamento da implementação.")
        details = text.splitlines()
        formatted = [parse_rich_line(line, default_size=default_size, default_bold=default_bold) for line in details]
        while formatted and formatted[0] == []:
            formatted.pop(0)
        while formatted and formatted[-1] == []:
            formatted.pop()
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
                    "bold": header.get("date_bold") is True, "font_size": date_size,
                    "is_header": True, "header_author": author, "header_date": date}]]
    if time:
        time_run = {"text": time, "bold": header.get("time_bold", header.get("date_bold")) is True,
                    "font_size": time_size, "is_header": True, "header_author": author, "header_date": date}
        if time_layout == "below":
            date_lines.append([time_run])
        else:
            date_lines[0].extend([
                {"text": " - ", "bold": False, "font_size": date_size,
                 "is_header": True, "header_author": author, "header_date": date},
                time_run,
            ])
    author_run = {"text": f"{author_label.strip()} {author}".strip(),
                  "bold": header.get("author_bold") is True, "font_size": author_size,
                  "is_header": True, "header_author": author, "header_date": date}
    if layout == "same_line":
        date_lines[0].extend([
            {"text": " | ", "bold": False, "font_size": date_size,
             "is_header": True, "header_author": author, "header_date": date},
            author_run,
        ])
        lines = date_lines
    elif layout == "author_first":
        lines = [[author_run], *date_lines]
    else:
        lines = [*date_lines, [author_run]]
    if payload.get("pacote"):
        lines.append("Pacote / cartão / branch: " + payload["pacote"].strip())
    first_plain = ""
    if formatted:
        first_plain = formatted[0] if isinstance(formatted[0], str) else "".join(r["text"] for r in formatted[0])
    lines.extend(formatted[1:] if formatted and first_plain.strip() == f"- {date}" else formatted)
    if payload.get("recomendacoes"):
        lines.extend(["Instruções de teste desta entrega:", *payload["recomendacoes"].splitlines()])
    positioned = {line.strip() for line in text.splitlines()}
    positioned.update(line.strip() for line in (payload.get("recomendacoes") or "").splitlines())
    for image in payload.get("mcp_evidence", []):
        marker = f'!{image["filename"]}!'
        if marker not in positioned:
            lines.append(marker)
    if payload.get("incluir_checklist") and payload.get("checklist"):
        lines.append("Revisão de código desta entrega:")
        lines.extend(f'{row["pergunta"]} — {row["resposta"]}' for row in payload["checklist"])
    images = {}
    preview = []
    for line in lines:
        plain_line = line if isinstance(line, str) else "".join(run["text"] for run in line)
        marker = re.fullmatch(r"!(.+)!", plain_line.strip())
        if not marker:
            raw_runs = [{"text": line, "bold": default_bold, "font_size": default_size, "indent": 0}] if isinstance(line, str) else line
            line_indent = 0
            for r in raw_runs:
                if isinstance(r.get("indent"), int):
                    line_indent = max(line_indent, min(6, max(0, r["indent"])))
            clean_runs = []
            for r in raw_runs:
                item = {
                    "text": r["text"],
                    "bold": bool(r.get("bold", False)),
                    "font_size": r.get("font_size", default_size),
                }
                if line_indent:
                    item["indent"] = line_indent
                clean_runs.append(item)
            preview.append({"runs": clean_runs, "indent": line_indent})
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


def _extract_field_value(paragraph, label):
    match = re.match(rf"^\s*{re.escape(label)}\s*:\s*(.*)$", paragraph_text(paragraph), flags=re.IGNORECASE)
    if not match:
        return None
    val = match.group(1).strip()
    if val in ("", "-", "//", "/ /", "--"):
        return ""
    return val


def _set_paragraph_field_text(doc, paragraph, text_value):
    runs = [c for c in paragraph.childNodes if getattr(c, "localName", None) == "r"]
    if runs:
        first_r = runs[0]
        for extra_r in runs[1:]:
            paragraph.removeChild(extra_r)
        for child in list(first_r.childNodes):
            if getattr(child, "localName", None) in ("t", "tab", "br"):
                first_r.removeChild(child)
        prefix = first_r.prefix or paragraph.prefix or "w"
        t_el = doc.createElementNS(W, f"{prefix}:t" if prefix else "t")
        t_el.setAttribute("xml:space", "preserve")
        t_el.appendChild(doc.createTextNode(text_value))
        first_r.appendChild(t_el)
    else:
        prefix = paragraph.prefix or "w"
        r_el = doc.createElementNS(W, f"{prefix}:r" if prefix else "r")
        t_el = doc.createElementNS(W, f"{prefix}:t" if prefix else "t")
        t_el.setAttribute("xml:space", "preserve")
        t_el.appendChild(doc.createTextNode(text_value))
        r_el.appendChild(t_el)
        paragraph.appendChild(r_el)


def _cell_max_width_emu(parent):
    max_width_emu = 5200000
    if parent.localName != "tc":
        return max_width_emu
    tc_pr = next((c for c in parent.childNodes if getattr(c, "localName", None) == "tcPr"), None)
    if tc_pr is None:
        return max_width_emu
    tc_w = next((c for c in tc_pr.childNodes if getattr(c, "localName", None) == "tcW"), None)
    if tc_w is None:
        return max_width_emu
    w_val = tc_w.getAttributeNS(W, "w") or tc_w.getAttribute("w:w") or tc_w.getAttribute("w")
    w_type = (tc_w.getAttributeNS(W, "type") or tc_w.getAttribute("w:type") or tc_w.getAttribute("type") or "dxa").lower()
    if w_val.isdigit() and w_type in ("", "dxa"):
        return min(5200000, max(1200000, (int(w_val) - 240) * 635))
    return max_width_emu


def _find_section_header_fields(content):
    nome_p = None
    data_p = None
    for p in content[1:min(len(content), 6)]:
        if nome_p is None and _extract_field_value(p, "nome") is not None:
            nome_p = p
        elif data_p is None and _extract_field_value(p, "data") is not None:
            data_p = p
    return nome_p, data_p


def has_empty_section_header_fields(original, section="Desenvolvimento"):
    """Retorna True se os campos Nome: e Data: da secao estiverem ambos vazios."""
    with ZipFile(io.BytesIO(original)) as source:
        doc = minidom.parseString(source.read("word/document.xml"))
    paragraphs = list(doc.getElementsByTagNameNS(W, "p"))
    headings = [normalized(paragraph_text(p)) for p in paragraphs]
    start, boundary = _section_bounds(headings, section)
    nome_p, data_p = _find_section_header_fields(paragraphs[start:boundary])
    if nome_p is None or data_p is None:
        return False
    return _extract_field_value(nome_p, "nome") == "" and _extract_field_value(data_p, "data") == ""


def has_empty_development_header_fields(original):
    return has_empty_section_header_fields(original, "Desenvolvimento")


def append_development(original, lines, images, *, font_size=11, bold=False):
    return append_section(original, lines, images, "Desenvolvimento", font_size=font_size, bold=bold)


def append_section(original, lines, images, section, *, font_size=11, bold=False):
    """Retorna um novo DOCX e o contexto do ponto de inserção."""
    if type(font_size) is not int or not 8 <= font_size <= 36 or type(bold) is not bool:
        raise ValueError("Escolha um tamanho de 8 a 36 pt e uma opção válida de negrito.")

    def render_run(text, strong, size):
        parts = text.split("\t")
        inner = "<w:tab/>".join(f'<w:t xml:space="preserve">{escape(part)}</w:t>' for part in parts)
        return (
            f'<w:r><w:rPr><w:b w:val="{int(strong)}"/><w:sz w:val="{size * 2}"/><w:szCs w:val="{size * 2}"/></w:rPr>'
            f'{inner}</w:r>'
        )

    with ZipFile(io.BytesIO(original)) as source:
        doc = minidom.parseString(source.read("word/document.xml"))
        paragraphs = list(doc.getElementsByTagNameNS(W, "p"))
        headings = [normalized(paragraph_text(p)) for p in paragraphs]
        start, boundary = _section_bounds(headings, section)
        content = paragraphs[start:boundary]

        nome_p, data_p = _find_section_header_fields(content)

        header_author = ""
        header_date = ""
        for line in lines:
            if isinstance(line, list):
                for r in line:
                    if isinstance(r, dict) and r.get("is_header"):
                        header_author = header_author or r.get("header_author", "")
                        header_date = header_date or r.get("header_date", "")

        lines_to_insert = list(lines)
        if nome_p is not None and data_p is not None:
            nome_val = _extract_field_value(nome_p, "nome")
            data_val = _extract_field_value(data_p, "data")
            if nome_val == "" and data_val == "" and (header_author or header_date):
                if header_author:
                    _set_paragraph_field_text(doc, nome_p, f"Nome: {header_author}")
                if header_date:
                    date_only = header_date.partition(" - ")[0].strip()
                    _set_paragraph_field_text(doc, data_p, f"Data: {date_only}")
                lines_to_insert = [
                    line for line in lines_to_insert
                    if not (isinstance(line, list) and line and all(isinstance(r, dict) and r.get("is_header") for r in line))
                ]
                while lines_to_insert and lines_to_insert[0] == []:
                    lines_to_insert.pop(0)

        header_end_idx = (max(i for i, p in enumerate(content) if p in (nome_p, data_p)) + 1) if (nome_p or data_p) else 1
        body_content = content[header_end_idx:]
        non_empty_body = [
            p for p in body_content
            if paragraph_text(p).strip() or p.getElementsByTagNameNS(W, "drawing") or p.getElementsByTagNameNS(W, "pict")
        ]
        target_p = None
        if non_empty_body:
            previous = non_empty_body[-1]
            parent = previous.parentNode
            insert_before = previous.nextSibling
            before_text = paragraph_text(previous).strip() or "Imagem no fim da seção"
        elif body_content:
            target_p = body_content[0]
            parent = target_p.parentNode
            insert_before = target_p.nextSibling
            before_text = paragraph_text(data_p or nome_p or content[0]).strip() or "Campo de preenchimento"
        else:
            previous = next(p for p in reversed(content) if paragraph_text(p).strip() or
                            p.getElementsByTagNameNS(W, "drawing") or p.getElementsByTagNameNS(W, "pict"))
            parent = previous.parentNode
            insert_before = previous.nextSibling
            before_text = paragraph_text(previous).strip() or "Imagem no fim da seção"

        anchor = paragraphs[boundary] if boundary < len(paragraphs) else None
        if parent.localName not in ("body", "tc"):
            raise ValueError("O último bloco da seção está em um formato não reconhecido.")

        max_width_emu = _cell_max_width_emu(parent)
        changes = {}
        if images:
            relationships = minidom.parseString(source.read("word/_rels/document.xml.rels"))
            content_types = minidom.parseString(source.read("[Content_Types].xml"))
        drawing_id = max((int(p.getAttribute("id")) for p in doc.getElementsByTagNameNS(WP, "docPr")
                          if p.getAttribute("id").isdigit()), default=0)
        for line in lines_to_insert:
            plain_line = line if isinstance(line, str) else "".join(run["text"] for run in line)
            match = re.fullmatch(r"!(.+)!", plain_line.strip())
            if match:
                name = match.group(1)
                drawing_id += 1
                ppr = ""
                markup = _embed_image(images[name], name, drawing_id, relationships, content_types, changes, max_width_emu=max_width_emu)
            else:
                runs = [{"text": line, "bold": bold, "indent": 0}] if isinstance(line, str) else line
                line_indent = max((int(r.get("indent", 0)) for r in runs if isinstance(r, dict) and isinstance(r.get("indent"), int)), default=0)
                line_indent = min(6, max(0, line_indent))
                ppr = f'<w:pPr><w:ind w:left="{line_indent * 360}"/></w:pPr>' if line_indent > 0 else ""
                markup = "".join(render_run(run["text"], run["bold"], run.get("font_size", font_size)) for run in runs)
            paragraph = minidom.parseString(
                f'<w:p xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}">{ppr}{markup}</w:p>'
            ).documentElement
            parent.insertBefore(doc.importNode(paragraph, True), insert_before)
        if target_p is not None and target_p.parentNode is parent:
            parent.removeChild(target_p)
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
        return output.getvalue(), before_text[-300:], paragraph_text(anchor) if anchor else "Fim do documento"


def _section_bounds(headings, section):
    header = r"^preenchido pel[oa] "
    target = header + re.escape(normalized(section)) + r"\b"
    starts = [i for i, text in enumerate(headings) if re.match(target, text)]
    if len(starts) != 1:
        raise ValueError(f"Não foi possível identificar uma única seção de {section}.")
    start = starts[0]
    auxiliary = r"^(?:revisao final\b|checklist\b|recomendacoes (?:e|para|de|ao)\b)"
    boundary = next((i for i in range(start + 1, len(headings))
                     if re.match(header, headings[i]) or re.match(auxiliary, headings[i])), len(headings))
    return start, boundary


def _embed_image(raw, name, drawing_id, relationships, content_types, changes, *, max_width_emu=5200000):
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
    scale = min(9525, max_width_emu / width, 6500000 / height)
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
