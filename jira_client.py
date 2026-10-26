"""
Modulo de integracao com a API REST do Jira com auto-negociacao de autenticacao e sincronizacao de fila offline.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

from config import JiraConfig
from storage import QueueItem, StateManager, clean_jira_issue_key

logger = logging.getLogger("JiraBot.JiraClient")


def format_iso_for_jira(iso_str: str) -> str:
    """
    Converte uma string ISO 8601 para o formato esperado pelo Jira REST API:
    Exemplo: 2026-08-31T07:45:00.000-0300
    """
    try:
        dt = datetime.fromisoformat(iso_str)
    except Exception:
        dt = datetime.now()

    tz_offset = dt.strftime("%z")
    if not tz_offset:
        tz_offset = "-0300"

    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.000{tz_offset}")


_DDS_BOILERPLATE_PATTERNS = [
    r"\*?\*?Detalhar com clareza quais s[ãa]o as necessidades[\s\S]*?compreens[ãa]o\.?\*?\*?\s*",
    r"\*?-?\s*\*?\*?O que:\*?\*?\s*Descreva a necessidade[^\n\r]*",
    r"\*?-?\s*\*?\*?Quando\s*/\s*Como:\*?\*?\s*Detalhe o momento[\s\S]*?compreens[ãa]o\.?\*?\*?\s*",
    r"\*?-?\s*\*?\*?Por qu[êe]:\*?\*?\s*Explique o motivo[^\n\r]*",
    r"\*?\*?Obs\.?:\*?\*?\s*Para os casos de melhoria[^\n\r]*",
    r"Nos casos que s[ãa]o chamados de representantes[^\n\r]*",
    r"Registre os testes e par[âa]metros[^\n\r]*",
    r"\*?\*?\(Per[íi]odo,\s*N[ºo°]\s*Nota,\s*Empregado[^\)]*\):?\*?\*?\s*",
    r"\*?\*?\(dados necess[áa]rios para encaminhamento ao teste de implementa[çc][ãa]o\)\*?\*?\s*",
]

_EMPTY_PLACEHOLDER_TOKENS = {
    "",
    "-",
    "--",
    "---",
    ".",
    "..",
    "...",
    "/",
    "//",
    "/ /",
    "n/a",
    "na",
    "n.a.",
    "não aplicável",
    "nao aplicavel",
    "sem informação",
    "sem informacao",
    "null",
    "none",
}


def _strip_dds_instructions(txt: str) -> str:
    """Remove textos fixos de instrucao do formulario padrao de DDS da Consisa."""
    import re

    if not txt:
        return ""
    cleaned = txt
    for pat in _DDS_BOILERPLATE_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.I)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _clean_dds_placeholder(val: str) -> str:
    """Limpa instrucoes de template e descarta marcadores vazios ('-', 'N/A', '//'), preservando imagens inline e negritos."""
    import re

    if not val:
        return ""
    cleaned = _strip_dds_instructions(val).strip()
    if not cleaned:
        return ""
    # Remove apenas pares de asteriscos sem texto dentro (ex: '**   **') sem remover '**texto**'
    no_empty_md = re.sub(r"\*\*+[ \t]+\*\*+", "", cleaned).strip()
    if "[[DOCX_IMG:" in no_empty_md:
        return no_empty_md
    if re.fullmatch(r"[\*\s]+", no_empty_md):
        return ""
    probe = re.sub(r"[\s\*_]+", " ", no_empty_md).strip().lower()
    if probe in _EMPTY_PLACEHOLDER_TOKENS:
        return ""
    if re.fullmatch(r"[-_./\s]+", probe):
        return ""
    return no_empty_md


def _clean_dds_date(val: str) -> str:
    """Retorna a data somente se contiver digitos reais (descarta '//', '/ /', '__/__/____', '-')."""
    import re

    if not val:
        return ""
    cleaned = re.sub(r"^\*?\*?Data:?\*?\*?\s*", "", val.strip(), flags=re.I).strip()
    cleaned = re.sub(r"[\*_]+", "", cleaned).strip()
    if not re.search(r"\d", cleaned):
        return ""
    bad_prefixes = ("resultado", "preenchido", "revisão", "revisao", "categoria", "padrão", "padrao", "nos casos", "registre")
    if any(cleaned.lower().startswith(p) for p in bad_prefixes):
        return ""
    return cleaned


def _clean_dds_person(val: str) -> str:
    """Higieniza o campo Nome do responsavel de cada etapa da DDS."""
    import re

    if not val:
        return ""
    cleaned = re.sub(r"^\*?\*?Nome:?\*?\*?\s*", "", val.strip(), flags=re.I).strip()
    # Se Data vier na mesma linha (ex: 'Nome: Joao Data: //'), corta antes de Data:
    cleaned = re.split(r"\s+\*?\*?Data:?\*?\*?(?:\s|$)", cleaned, maxsplit=1, flags=re.I)[0].strip()
    cleaned = _clean_dds_placeholder(cleaned)
    if not cleaned:
        return ""
    cleaned_plain = re.sub(r"\*+", "", cleaned).strip()
    bad_prefixes = (
        "data",
        "resultado",
        "preenchido",
        "revisão",
        "revisao",
        "categoria",
        "padrão",
        "padrao",
        "nos casos",
        "registre",
        "1",
        "requisito",
    )
    if any(cleaned_plain.lower().startswith(p) for p in bad_prefixes):
        return ""
    return cleaned_plain


def _classify_homologacao_tipo(detalhamento: str) -> str:
    """Classifica o resultado da homologacao entre 'Release' e 'Divergência'."""
    if not detalhamento:
        return "Release"
    lower_hom = detalhamento.lower()
    is_explicit_release = any(
        term in lower_hom
        for term in [
            "sem diverg",
            "nenhuma diverg",
            "liberado para release",
            "aprovado sem",
            "sem erro",
            "sem falha",
            "homologado com sucesso",
            "conferido",
            "release liberado",
        ]
    )
    has_divergence = any(
        term in lower_hom
        for term in [
            "diverg",
            "erro",
            "falha",
            "não aprovado",
            "nao aprovado",
            "reprovado",
            "inconsist",
            "pendente de ajuste",
            "retornado",
        ]
    )
    if has_divergence and not is_explicit_release:
        return "Divergência"
    return "Release"


def extrair_documento_docx_completo(conteudo_binario: bytes) -> Dict[str, Any]:
    """
    Motor OpenXML completo para documentos .docx de DDS:
    - Mapeia word/_rels/document.xml.rels na ordem real de leitura do documento.
    - Detecta e exclui o logotipo institucional do cabecalho (Tabela 0, Linha 0, Coluna 0) da galeria de evidencias.
    - Preserva negritos (**texto**), listas, hiperlinks e posiciona marcadores [[DOCX_IMG:docx-emb-N]]
      exatamente na secao onde cada captura de tela foi inserida.
    - Extrai todas as secoes da DDS diretamente das celulas das tabelas do Word (sem perda ou truncamento).
    - Gera representacao HTML visual fiel (document_html) com tabelas e imagens integradas.
    """
    import base64
    import html as html_lib
    import io
    import re
    import xml.etree.ElementTree as ET
    import zipfile

    empty_result: Dict[str, Any] = {
        "text": "",
        "embedded_images": [],
        "document_html": "",
        "structured_dds": None,
    }
    if not conteudo_binario:
        return empty_result

    W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
    V_NS = "urn:schemas-microsoft-com:vml"

    try:
        with zipfile.ZipFile(io.BytesIO(conteudo_binario)) as z:
            namelist = set(z.namelist())
            if "word/document.xml" not in namelist:
                # Fallback se nao houver document.xml
                fallback_imgs: List[Dict[str, Any]] = []
                for item in sorted(namelist):
                    if item.startswith("word/media/") and item.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                        raw_img = z.read(item)
                        ext = item.rsplit(".", 1)[-1].lower()
                        if ext == "jpg":
                            ext = "jpeg"
                        b64 = base64.b64encode(raw_img).decode("ascii")
                        fallback_imgs.append({
                            "id": f"docx-emb-{len(fallback_imgs) + 1}",
                            "filename": item.replace("word/media/", ""),
                            "data_url": f"data:image/{ext};base64,{b64}",
                            "size": len(raw_img),
                            "section": "Documento DDS",
                        })
                return {
                    "text": "",
                    "embedded_images": fallback_imgs,
                    "document_html": "",
                    "structured_dds": None,
                }

            # 1. Mapeia relacoes (imagens e links externos) em word/_rels/document.xml.rels
            rid_to_media: Dict[str, str] = {}
            rid_to_link: Dict[str, str] = {}
            if "word/_rels/document.xml.rels" in namelist:
                try:
                    rels_root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
                    for rel in rels_root.iter():
                        if not rel.tag.endswith("Relationship"):
                            continue
                        rid = rel.attrib.get("Id") or ""
                        target = rel.attrib.get("Target") or ""
                        t_mode = (rel.attrib.get("TargetMode") or "").lower()
                        if not rid or not target:
                            continue
                        if t_mode == "external" or target.startswith(("http://", "https://", "mailto:")):
                            rid_to_link[rid] = target
                        else:
                            norm = target.lstrip("/")
                            if norm.startswith("../"):
                                norm = norm.replace("../", "", 1)
                            if not norm.startswith("word/"):
                                norm = f"word/{norm}"
                            if norm in namelist:
                                rid_to_media[rid] = norm
                except Exception as ex_rel:
                    logger.debug("Aviso ao ler document.xml.rels: %s", ex_rel)

            root = ET.fromstring(z.read("word/document.xml"))
            body = root.find(f"{{{W_NS}}}body")
            if body is None:
                body = root

            def _iter_blip_rids(elem: ET.Element) -> List[str]:
                found: List[str] = []
                for sub in elem.iter():
                    if sub.tag == f"{{{A_NS}}}blip":
                        emb = sub.attrib.get(f"{{{R_NS}}}embed") or sub.attrib.get(f"{{{R_NS}}}link")
                        if emb:
                            found.append(emb)
                    elif sub.tag == f"{{{V_NS}}}imagedata":
                        emb = sub.attrib.get(f"{{{R_NS}}}id")
                        if emb:
                            found.append(emb)
                return found

            def _plain_text(elem: ET.Element, include_nested_tables: bool = True) -> str:
                parts: List[str] = []

                def _walk(node: ET.Element) -> None:
                    for ch in node:
                        if ch.tag == f"{{{W_NS}}}tbl" and not include_nested_tables:
                            continue
                        if ch.tag == f"{{{W_NS}}}t" and ch.text:
                            parts.append(ch.text)
                        elif ch.tag in (f"{{{W_NS}}}br", f"{{{W_NS}}}cr"):
                            parts.append("\n")
                        elif ch.tag == f"{{{W_NS}}}tab":
                            parts.append(" ")
                        elif ch.tag == f"{{{W_NS}}}p":
                            _walk(ch)
                            parts.append("\n")
                        else:
                            _walk(ch)

                _walk(elem)
                return re.sub(r"[ \t]+", " ", "".join(parts)).strip()

            # 2. Identifica o logotipo institucional na Tabela 0, Linha 0, Celula 0 do template Consisa
            logo_rids: set[str] = set()
            non_logo_rids: set[str] = set()
            top_tables = [ch for ch in body if ch.tag == f"{{{W_NS}}}tbl"]

            logo_cell_elem: Optional[ET.Element] = None
            if top_tables:
                first_tbl = top_tables[0]
                first_rows = [ch for ch in first_tbl if ch.tag == f"{{{W_NS}}}tr"]
                if first_rows:
                    r0_text = _plain_text(first_rows[0]).lower()
                    if "documento de detalhamento" in r0_text or "dds" in r0_text or "solicitação" in r0_text or "solicitacao" in r0_text:
                        r0_cells = [ch for ch in first_rows[0] if ch.tag == f"{{{W_NS}}}tc"]
                        if r0_cells:
                            logo_cell_elem = r0_cells[0]
                            for rid in _iter_blip_rids(logo_cell_elem):
                                logo_rids.add(rid)

            for elem in body.iter():
                if elem is logo_cell_elem:
                    continue
                if elem.tag == f"{{{A_NS}}}blip":
                    emb = elem.attrib.get(f"{{{R_NS}}}embed") or elem.attrib.get(f"{{{R_NS}}}link")
                    if emb:
                        non_logo_rids.add(emb)
                elif elem.tag == f"{{{V_NS}}}imagedata":
                    emb = elem.attrib.get(f"{{{R_NS}}}id")
                    if emb:
                        non_logo_rids.add(emb)

            # Se o rId aparece tambem fora da celula de logo, remove de logo_only
            # (Nota: verificamos contagem de ocorrencias totais vs ocorrencias na celula de logo)
            total_rid_counts: Dict[str, int] = {}
            for rid in _iter_blip_rids(body):
                total_rid_counts[rid] = total_rid_counts.get(rid, 0) + 1
            logo_cell_rid_counts: Dict[str, int] = {}
            if logo_cell_elem is not None:
                for rid in _iter_blip_rids(logo_cell_elem):
                    logo_cell_rid_counts[rid] = logo_cell_rid_counts.get(rid, 0) + 1

            logo_only_rids = {
                rid for rid, cnt in logo_cell_rid_counts.items()
                if total_rid_counts.get(rid, 0) <= cnt
            }
            logo_only_targets = {rid_to_media[rid] for rid in logo_only_rids if rid in rid_to_media}

            embedded_images: List[Dict[str, Any]] = []
            emitted_media_paths: set[str] = set()
            media_b64_cache: Dict[str, Tuple[str, int, str]] = {}

            def _get_media_data_uri(media_path: str) -> Optional[Tuple[str, int, str]]:
                if media_path in media_b64_cache:
                    return media_b64_cache[media_path]
                if media_path not in namelist:
                    return None
                if not media_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                    return None
                try:
                    raw_bytes = z.read(media_path)
                    ext = media_path.rsplit(".", 1)[-1].lower()
                    if ext == "jpg":
                        ext = "jpeg"
                    data_uri = f"data:image/{ext};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
                    fname = media_path.replace("word/media/", "")
                    info = (data_uri, len(raw_bytes), fname)
                    media_b64_cache[media_path] = info
                    return info
                except Exception:
                    return None

            def _register_inline_image(rid: str, section_label: str) -> Optional[Dict[str, Any]]:
                if rid in logo_only_rids:
                    return None
                media_path = rid_to_media.get(rid)
                if not media_path or media_path in logo_only_targets:
                    return None
                info = _get_media_data_uri(media_path)
                if not info:
                    return None
                data_uri, img_size, orig_fname = info
                emitted_media_paths.add(media_path)
                img_idx = len(embedded_images) + 1
                img_id = f"docx-emb-{img_idx}"
                entry = {
                    "id": img_id,
                    "filename": orig_fname,
                    "data_url": data_uri,
                    "size": img_size,
                    "section": section_label or "Documento DDS",
                }
                embedded_images.append(entry)
                return entry

            # 3. Renderizador de paragrafo <w:p> para Markdown rico + HTML
            def _is_prop_on(rpr: Optional[ET.Element], prop_name: str) -> bool:
                if rpr is None:
                    return False
                el = rpr.find(f"{{{W_NS}}}{prop_name}")
                if el is None:
                    return False
                val = (el.attrib.get(f"{{{W_NS}}}val") or "true").lower()
                return val not in ("0", "false", "off", "none")

            def _render_paragraph(p_elem: ET.Element, section_label: str, register_images: bool = True) -> Tuple[str, str]:
                ppr = p_elem.find(f"{{{W_NS}}}pPr")
                is_list = ppr is not None and ppr.find(f"{{{W_NS}}}numPr") is not None

                # Coleta segmentos [(texto, bold, italic, link_url, img_entry)]
                segments: List[Dict[str, Any]] = []

                def _walk_inline(container: ET.Element, active_link: str = "") -> None:
                    for ch in container:
                        if ch.tag == f"{{{W_NS}}}hyperlink":
                            h_rid = ch.attrib.get(f"{{{R_NS}}}id") or ""
                            link_url = rid_to_link.get(h_rid, "")
                            _walk_inline(ch, active_link=link_url)
                        elif ch.tag in (f"{{{W_NS}}}ins", f"{{{W_NS}}}smartTag", f"{{{W_NS}}}sdt", f"{{{W_NS}}}sdtContent"):
                            _walk_inline(ch, active_link=active_link)
                        elif ch.tag == f"{{{W_NS}}}r":
                            rpr = ch.find(f"{{{W_NS}}}rPr")
                            is_b = _is_prop_on(rpr, "b")
                            is_i = _is_prop_on(rpr, "i")
                            run_txt_parts: List[str] = []
                            for rch in ch:
                                if rch.tag == f"{{{W_NS}}}t" and rch.text:
                                    run_txt_parts.append(rch.text)
                                elif rch.tag in (f"{{{W_NS}}}br", f"{{{W_NS}}}cr"):
                                    run_txt_parts.append("\n")
                                elif rch.tag == f"{{{W_NS}}}tab":
                                    run_txt_parts.append(" ")
                                elif rch.tag in (f"{{{W_NS}}}drawing", f"{{{W_NS}}}pict"):
                                    if run_txt_parts:
                                        segments.append({
                                            "text": "".join(run_txt_parts),
                                            "bold": is_b,
                                            "italic": is_i,
                                            "link": active_link,
                                            "img": None,
                                        })
                                        run_txt_parts = []
                                    if register_images:
                                        for blip_rid in _iter_blip_rids(rch):
                                            img_entry = _register_inline_image(blip_rid, section_label)
                                            if img_entry:
                                                segments.append({"text": "", "bold": False, "italic": False, "link": "", "img": img_entry})
                            if run_txt_parts:
                                segments.append({
                                    "text": "".join(run_txt_parts),
                                    "bold": is_b,
                                    "italic": is_i,
                                    "link": active_link,
                                    "img": None,
                                })

                _walk_inline(p_elem)

                # Mescla segmentos adjacentes com mesma formatacao para evitar '**pal****avra**'
                merged: List[Dict[str, Any]] = []
                for seg in segments:
                    if seg["img"] is not None:
                        merged.append(seg)
                        continue
                    if (
                        merged
                        and merged[-1]["img"] is None
                        and merged[-1]["bold"] == seg["bold"]
                        and merged[-1]["italic"] == seg["italic"]
                        and merged[-1]["link"] == seg["link"]
                    ):
                        merged[-1]["text"] += seg["text"]
                    else:
                        merged.append(dict(seg))

                md_parts: List[str] = []
                html_parts: List[str] = []

                for seg in merged:
                    img_obj = seg.get("img")
                    if img_obj is not None:
                        img_id = img_obj["id"]
                        data_url = html_lib.escape(img_obj["data_url"], quote=True)
                        fname = html_lib.escape(img_obj["filename"])
                        sec_esc = html_lib.escape(img_obj.get("section") or "DDS")
                        md_parts.append(f"\n[[DOCX_IMG:{img_id}]]\n")
                        html_parts.append(
                            f'<figure class="docx-inline-figure" data-docx-img-id="{img_id}">'
                            f'<img src="{data_url}" alt="{fname}" class="docx-inline-img" loading="lazy">'
                            f'<figcaption class="docx-inline-caption">{fname} ({sec_esc}) - Clique para ampliar</figcaption>'
                            f"</figure>"
                        )
                        continue

                    txt = seg["text"]
                    if not txt:
                        continue

                    esc_html = html_lib.escape(txt).replace("\n", "<br>")
                    md_piece = txt

                    if seg["bold"] and txt.strip():
                        m_ws = re.match(r"^(\s*)([\s\S]*?)(\s*)$", txt)
                        if m_ws:
                            lead, core, trail = m_ws.group(1), m_ws.group(2), m_ws.group(3)
                            # Evita envolver quebras de linha dentro de **...**
                            core_lines = [f"**{ln.strip()}**" if ln.strip() else "" for ln in core.split("\n")]
                            md_piece = f"{lead}" + "\n".join(core_lines) + f"{trail}"
                        esc_html = f"<strong>{esc_html}</strong>"

                    if seg["italic"] and not seg["bold"] and txt.strip():
                        esc_html = f"<em>{esc_html}</em>"

                    if seg["link"]:
                        safe_href = html_lib.escape(seg["link"], quote=True)
                        clean_lbl = md_piece.strip() or seg["link"]
                        md_piece = f"[{clean_lbl}]({seg['link']})"
                        esc_html = f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" class="dds-rich-link">{esc_html}</a>'

                    md_parts.append(md_piece)
                    html_parts.append(esc_html)

                md_str = "".join(md_parts).strip()
                html_str = "".join(html_parts).strip()

                if is_list and md_str and not md_str.startswith(("-", "*", "[[DOCX_IMG:")):
                    md_str = f"- {md_str}"
                if is_list and html_str:
                    html_html = f'<div class="docx-p docx-list-item">&bull; {html_str}</div>'
                elif html_str:
                    html_html = f'<div class="docx-p">{html_str}</div>'
                else:
                    html_html = ""

                return md_str, html_html

            # 4. Percorre o documento na ordem real para construir:
            #    - structured_dds (extracao direta das celulas das tabelas Consisa + paragrafos fora de tabela)
            #    - document_html (visualizacao fiel com tabelas e imagens)
            #    - all_md_blocks (texto integral enriquecido)
            SECTION_TITLES_HUMAN = {
                "header": "Cabeçalho da DDS",
                "especificacao": "Especificação dos Dados",
                "necessidade": "Necessidade do Cliente",
                "resultado_esperado": "Resultado Esperado",
                "suporte": "Suporte Técnico",
                "team_lider": "Team Líder",
                "teste_validade": "Teste de Validade",
                "analise_negocios": "Análise de Negócios",
                "analise_sistemas": "Análise de Sistemas",
                "team_leader": "Team Leader",
                "desenvolvimento": "Desenvolvimento",
                "dev_recomendacoes": "Recomendações ao Teste",
                "teste_implementacao": "Teste de Implementação",
                "resultado_homologacao": "Resultado da Homologação",
            }

            s_data: Dict[str, Any] = {
                "solicitacao": "",
                "solicitante": "",
                "empresa": "",
                "contato": "",
                "data_solicitacao": "",
                "tipo": "",
                "sistema": "",
                "opcao": "",
                "versao": "",
                "empresa_filial": "",
                "especificacao_dados": "",
                "necessidade_cliente": "",
                "resultado_esperado": "",
                "suporte": {"responsavel": "", "data": "", "detalhamento": ""},
                "team_leader": {"responsavel": "", "data": "", "detalhamento": ""},
                "teste_validade": {"responsavel": "", "data": "", "detalhamento": ""},
                "analise_negocios": {"responsavel": "", "data": "", "detalhamento": ""},
                "analise_sistemas": {"responsavel": "", "data": "", "detalhamento": ""},
                "desenvolvimento": {"responsavel": "", "data": "", "detalhamento": "", "recomendacoes": ""},
                "teste_implementacao": {"responsavel": "", "data": "", "detalhamento": ""},
                "resultado_homologacao": {"tipo": "Release", "detalhamento": ""},
                "checklist": [],
            }

            section_buffers: Dict[str, List[str]] = {k: [] for k in SECTION_TITLES_HUMAN}
            all_md_blocks: List[str] = []
            doc_html_blocks: List[str] = []
            active_section = "header"
            found_consisa_template = False

            def _append_section_md(sec_key: str, md_val: str) -> None:
                cleaned = _clean_dds_placeholder(md_val)
                if cleaned:
                    section_buffers.setdefault(sec_key, []).append(cleaned)

            def _parse_checklist_nested_table(tbl_elem: ET.Element) -> str:
                """Extrai itens da tabela aninhada 'Revisao final' (suportando layouts de 2, 3 ou 4+ colunas) e retorna HTML."""
                rows_html: List[str] = []
                current_cat = "Geral"
                for tr in [c for c in tbl_elem if c.tag == f"{{{W_NS}}}tr"]:
                    tcs = [c for c in tr if c.tag == f"{{{W_NS}}}tc"]
                    vals = [_plain_text(tc).strip() for tc in tcs]
                    if not any(vals):
                        continue
                    joined_low = " ".join(v for v in vals if v).lower()
                    if "revisão final" in joined_low or "revisao final" in joined_low:
                        continue
                    if "categoria" in joined_low and "descri" in joined_low:
                        continue

                    q_idx = next((i for i, v in enumerate(vals) if "?" in v), None)
                    if q_idx is None:
                        if len(vals) >= 3:
                            q_idx = len(vals) - 2
                        elif len(vals) == 2:
                            q_idx = 0
                        else:
                            continue

                    for pre_v in vals[:q_idx]:
                        if pre_v and not pre_v.isdigit():
                            current_cat = pre_v

                    q_cell = vals[q_idx]
                    ans_cell = ""
                    for post_v in vals[q_idx + 1 :]:
                        if post_v and post_v not in ("-", "--", "---", "//", "/ /"):
                            ans_cell = post_v
                            break

                    if q_cell and ans_cell:
                        s_data["checklist"].append({
                            "categoria": current_cat,
                            "pergunta": q_cell,
                            "resposta": ans_cell,
                        })
                        rows_html.append(
                            f"<tr><td>{html_lib.escape(current_cat)}</td>"
                            f"<td>{html_lib.escape(q_cell)}</td>"
                            f"<td><strong>{html_lib.escape(ans_cell)}</strong></td></tr>"
                        )

                if not rows_html:
                    return ""
                return (
                    '<table class="docx-render-table docx-nested-checklist">'
                    "<thead><tr><th>Categoria</th><th>Descrição</th><th>Revisão</th></tr></thead>"
                    f"<tbody>{''.join(rows_html)}</tbody></table>"
                )

            def _parse_generic_nested_table(tbl_elem: ET.Element, sec_label: str) -> Tuple[str, str]:
                """Converte tabelas auxiliares (ex: requisitos do Team Leader ou tabelas coladas pelo dev) em MD e HTML."""
                md_rows: List[str] = []
                html_rows: List[str] = []
                is_tl_req_table = False

                trs = [c for c in tbl_elem if c.tag == f"{{{W_NS}}}tr"]
                for r_idx, tr in enumerate(trs):
                    tcs = [c for c in tr if c.tag == f"{{{W_NS}}}tc"]
                    cell_mds: List[str] = []
                    cell_htmls: List[str] = []
                    for tc in tcs:
                        p_mds: List[str] = []
                        p_htmls: List[str] = []
                        for ch in tc:
                            if ch.tag == f"{{{W_NS}}}p":
                                pm, ph = _render_paragraph(ch, sec_label, register_images=True)
                                if pm:
                                    p_mds.append(pm)
                                if ph:
                                    p_htmls.append(ph)
                        cell_mds.append(" ".join(p_mds).strip())
                        cell_htmls.append("".join(p_htmls))

                    plain_join = " | ".join(re.sub(r"\*+", "", c).strip() for c in cell_mds if c.strip())
                    if r_idx == 0 and "requisito" in plain_join.lower() and "entendimento" in plain_join.lower():
                        is_tl_req_table = True
                        html_rows.append("<tr>" + "".join(f"<th>{ch or ''}</th>" for ch in cell_htmls) + "</tr>")
                        continue

                    # Na tabela padrao do Team Leader, ignora a linha vazia que contem apenas o indice '1'
                    if is_tl_req_table:
                        non_empty = [re.sub(r"\*+", "", c).strip() for c in cell_mds if c.strip()]
                        if not non_empty or (len(non_empty) == 1 and non_empty[0].isdigit()):
                            continue

                    if any(c.strip() for c in cell_mds):
                        md_rows.append(" | ".join(c for c in cell_mds if c.strip()))
                        html_rows.append("<tr>" + "".join(f"<td>{ch or ''}</td>" for ch in cell_htmls) + "</tr>")

                md_out = "\n".join(md_rows).strip()
                html_out = f'<table class="docx-render-table">{"".join(html_rows)}</table>' if html_rows else ""
                return md_out, html_out

            def _render_cell_contents(tc_elem: ET.Element, sec_key: str) -> Tuple[str, str]:
                """Renderiza todos os paragrafos e tabelas aninhadas de uma celula <w:tc>."""
                sec_human = SECTION_TITLES_HUMAN.get(sec_key, "Documento DDS")
                md_chunks: List[str] = []
                html_chunks: List[str] = []

                for ch in tc_elem:
                    if ch.tag == f"{{{W_NS}}}p":
                        pm, ph = _render_paragraph(ch, sec_human, register_images=True)
                        if pm:
                            md_chunks.append(pm)
                        if ph:
                            html_chunks.append(ph)
                    elif ch.tag == f"{{{W_NS}}}tbl":
                        nested_plain = _plain_text(ch).lower()
                        if "revisão final" in nested_plain or "padrão de codificação" in nested_plain or "padrao de codificacao" in nested_plain:
                            chk_html = _parse_checklist_nested_table(ch)
                            if chk_html:
                                html_chunks.append(chk_html)
                        else:
                            n_md, n_html = _parse_generic_nested_table(ch, sec_human)
                            if n_md:
                                md_chunks.append(n_md)
                            if n_html:
                                html_chunks.append(n_html)

                return "\n\n".join(md_chunks).strip(), "".join(html_chunks)

            def _get_cell_gridspan(tc_elem: ET.Element) -> int:
                tcpr = tc_elem.find(f"{{{W_NS}}}tcPr")
                if tcpr is not None:
                    gs = tcpr.find(f"{{{W_NS}}}gridSpan")
                    if gs is not None:
                        try:
                            return max(1, int(gs.attrib.get(f"{{{W_NS}}}val", "1")))
                        except ValueError:
                            pass
                return 1

            def _is_vmerge_continue(tc_elem: ET.Element) -> bool:
                tcpr = tc_elem.find(f"{{{W_NS}}}tcPr")
                if tcpr is not None:
                    vm = tcpr.find(f"{{{W_NS}}}vMerge")
                    if vm is not None:
                        val = (vm.attrib.get(f"{{{W_NS}}}val") or "").lower()
                        return val != "restart"
                return False

            def _detect_section_switch(row_plain_text: str, current_sec: str = "header") -> Optional[str]:
                low = row_plain_text.strip().lower()
                if not low:
                    return None
                if re.match(r"^especifica[çc][ãa]o dos dados", low):
                    return "especificacao"
                if re.match(r"^detalhar com clareza", low):
                    return "necessidade"
                if re.match(r"^resultado esperado\b", low) and current_sec in ("header", "especificacao", "necessidade"):
                    return "resultado_esperado"
                if re.match(r"^preenchido pel[oa]\s+suporte", low):
                    return "suporte"
                if re.match(r"^preenchido pel[oa]\s+team\s+l[íi]der\b", low):
                    return "team_lider"
                if re.match(r"^preenchido pel[oa]\s+teste de validade", low):
                    return "teste_validade"
                if re.match(r"^preenchido pel[oa]\s+an[áa]lise de neg[óo]cios", low):
                    return "analise_negocios"
                if re.match(r"^preenchido pel[oa]\s+an[áa]lise de sistemas", low):
                    return "analise_sistemas"
                if re.match(r"^preenchido pel[oa]\s+team\s+leader\b", low):
                    return "team_leader"
                if re.match(r"^preenchido pel[oa]\s+desenvolvimento", low):
                    return "desenvolvimento"
                if re.match(r"^recomenda[çc][õo]es ao teste", low):
                    return "dev_recomendacoes"
                if re.match(r"^preenchido pel[oa]\s+teste de implementa[çc][ãa]o", low):
                    return "teste_implementacao"
                if re.match(r"^resultado\s*\(release ou diverg", low):
                    return "resultado_homologacao"
                return None

            SectionTargetMap = {
                "suporte": "suporte",
                "team_lider": "team_leader",
                "team_leader": "team_leader",
                "teste_validade": "teste_validade",
                "analise_negocios": "analise_negocios",
                "analise_sistemas": "analise_sistemas",
                "desenvolvimento": "desenvolvimento",
                "teste_implementacao": "teste_implementacao",
            }

            # Percorre todos os elementos de primeiro nivel de <w:body>
            for child in body:
                if child.tag == f"{{{W_NS}}}p":
                    p_plain = _plain_text(child).strip()
                    p_low = p_plain.lower()
                    switched = _detect_section_switch(p_plain, active_section)
                    if switched:
                        found_consisa_template = True
                        active_section = switched

                    if re.search(r"solicita[çc][ãa]o\s*n[ºo°]?", p_low) and not s_data["solicitacao"]:
                        found_consisa_template = True
                        cand_sol = re.sub(r"^[\s\S]*?solicita[çc][ãa]o\s*n[ºo°]?[:\s]*", "", p_plain, flags=re.I).strip()
                        if cand_sol:
                            s_data["solicitacao"] = _clean_dds_placeholder(cand_sol)

                    pm, ph = _render_paragraph(child, SECTION_TITLES_HUMAN.get(active_section, "Documento DDS"), register_images=True)
                    if pm:
                        all_md_blocks.append(pm)
                        if found_consisa_template and active_section != "header":
                            if switched:
                                rem_p = re.sub(
                                    r"^\*?\*?(?:Especifica[çc][ãa]o dos dados|Detalhar com clareza|Resultado Esperado|Preenchido pel[oa]|Recomenda[çc][õo]es ao teste|Resultado\s*\(release ou diverg)[^\n\r]*",
                                    "",
                                    pm,
                                    flags=re.I,
                                ).strip()
                                if rem_p:
                                    _append_section_md(active_section, rem_p)
                            elif p_low.startswith("nome:") or p_low.startswith("data:"):
                                target_dict_key = SectionTargetMap.get(active_section)
                                if target_dict_key:
                                    sec_obj = s_data[target_dict_key]
                                    if p_low.startswith("nome:"):
                                        person = _clean_dds_person(p_plain)
                                        if person and not sec_obj["responsavel"]:
                                            sec_obj["responsavel"] = person
                                    if "data:" in p_low:
                                        dt = _clean_dds_date(re.split(r"\bdata:?", p_plain, maxsplit=1, flags=re.I)[-1])
                                        if dt and not sec_obj["data"]:
                                            sec_obj["data"] = dt
                            else:
                                _append_section_md(active_section, pm)
                    if ph:
                        doc_html_blocks.append(ph)

                elif child.tag == f"{{{W_NS}}}tbl":
                    tbl_rows_html: List[str] = []
                    trs = [c for c in child if c.tag == f"{{{W_NS}}}tr"]
                    tbl_plain_intro = _plain_text(child, include_nested_tables=False)[:400].lower()
                    is_main_header_tbl = (
                        "documento de detalhamento" in tbl_plain_intro
                        or "dados do solicitante" in tbl_plain_intro
                        or "selecione o tipo desta solicitação" in tbl_plain_intro
                        or "selecione o tipo desta solicitacao" in tbl_plain_intro
                    )
                    if is_main_header_tbl:
                        found_consisa_template = True
                        active_section = "header"

                    for tr in trs:
                        tcs = [c for c in tr if c.tag == f"{{{W_NS}}}tc"]
                        visible_tcs = [tc for tc in tcs if not _is_vmerge_continue(tc)]
                        if not visible_tcs:
                            continue

                        cells_plain = [_plain_text(tc, include_nested_tables=False) for tc in visible_tcs]
                        row_plain = " ".join(c for c in cells_plain if c).strip()
                        row_low = row_plain.lower()

                        # Verifica mudanca de secao na linha atual
                        switched = _detect_section_switch(row_plain, active_section)
                        if switched:
                            found_consisa_template = True
                            active_section = switched

                        # Renderiza cada celula (gerando imagens inline na secao correta!)
                        rendered_cells = [_render_cell_contents(tc, active_section) for tc in visible_tcs]
                        cells_md = [rc[0] for rc in rendered_cells]
                        cells_html = [rc[1] for rc in rendered_cells]

                        # Acumula texto rico global para copia / texto bruto
                        row_md_joined = "\n".join(cm for cm in cells_md if cm).strip()
                        if row_md_joined:
                            all_md_blocks.append(row_md_joined)

                        # Monta linha HTML da tabela
                        is_banner_row = bool(
                            switched
                            or "documento de detalhamento" in row_low
                            or row_low in ("dados do solicitante", "preenchido pelo solicitante")
                        )
                        tr_cls = ' class="docx-tr-section"' if is_banner_row else ""
                        tds_html: List[str] = []
                        for tc_el, ch_html in zip(visible_tcs, cells_html):
                            if tc_el is logo_cell_elem and not ch_html.strip():
                                continue
                            span = _get_cell_gridspan(tc_el)
                            colspan_attr = f' colspan="{span}"' if span > 1 else ""
                            tds_html.append(f"<td{colspan_attr}>{ch_html or '&nbsp;'}</td>")
                        if tds_html:
                            tbl_rows_html.append(f"<tr{tr_cls}>{''.join(tds_html)}</tr>")

                        # Populacao estruturada dos metadados de cabecalho da tabela principal (apenas enquanto active_section == "header")
                        if is_main_header_tbl and active_section == "header":
                            _HEADER_LABEL_STARTS = (
                                "solicitação n",
                                "solicitacao n",
                                "dados do solicitante",
                                "nome do solicitante",
                                "código",
                                "codigo",
                                "nome do contato",
                                "data:",
                                "preenchido pel",
                                "selecione o tipo",
                                "correção",
                                "correcao",
                                "alteração",
                                "alteracao",
                                "implementação",
                                "implementacao",
                                "sistema /",
                                "opção",
                                "opcao",
                                "versão",
                                "versao",
                                "foram testadas",
                                "em caso de bug",
                                "local onde",
                                "usuário",
                                "usuario",
                                "empresa / filial",
                                "especificação",
                                "especificacao",
                                "detalhar com clareza",
                                "resultado esperado",
                            )

                            def _is_other_header_label(txt_candidate: str) -> bool:
                                low_cand = txt_candidate.strip().lower()
                                return any(low_cand.startswith(p) for p in _HEADER_LABEL_STARTS)

                            def _extract_hdr_val(match_re: str, strip_re: str, is_date: bool = False) -> str:
                                for idx_c, cp_item in enumerate(cells_plain):
                                    if re.search(match_re, cp_item, flags=re.I):
                                        inline_rem = re.sub(strip_re, "", cp_item, count=1, flags=re.I).strip()
                                        cleaned_inline = (
                                            _clean_dds_date(inline_rem)
                                            if is_date
                                            else _clean_dds_placeholder(inline_rem)
                                        )
                                        if cleaned_inline:
                                            return cleaned_inline
                                        if idx_c + 1 < len(cells_plain):
                                            nxt_cell = cells_plain[idx_c + 1].strip()
                                            if nxt_cell and not _is_other_header_label(nxt_cell):
                                                cleaned_nxt = (
                                                    _clean_dds_date(nxt_cell)
                                                    if is_date
                                                    else _clean_dds_placeholder(nxt_cell)
                                                )
                                                if cleaned_nxt:
                                                    return cleaned_nxt
                                return ""

                            sol_val = _extract_hdr_val(
                                r"solicita[çc][ãa]o\s*n",
                                r"^[\s\S]*?solicita[çc][ãa]o\s*n[ºo°]?[:\s]*",
                            )
                            if sol_val:
                                s_data["solicitacao"] = sol_val

                            sol_nome = _extract_hdr_val(
                                r"nome do solicitante",
                                r"^[\s\S]*?setor:?\s*",
                            )
                            if sol_nome:
                                s_data["solicitante"] = sol_nome

                            emp_val = _extract_hdr_val(
                                r"c[óo]digo\s*/\s*empresa cliente",
                                r"^[\s\S]*?empresa cliente:?\s*",
                            )
                            if emp_val:
                                s_data["empresa"] = emp_val

                            contato_val = _extract_hdr_val(
                                r"nome do contato",
                                r"^[\s\S]*?nome do contato(?:\s+na\s+empresa\s+cliente)?:?\s*",
                            )
                            if contato_val:
                                s_data["contato"] = contato_val

                            dt_sol_val = _extract_hdr_val(
                                r"^data:",
                                r"^data:?\s*",
                                is_date=True,
                            )
                            if dt_sol_val:
                                s_data["data_solicitacao"] = dt_sol_val

                            # Checkbox de Tipo (CORRECAO / ALTERACAO / IMPLEMENTACAO)
                            opt_indices = [
                                i_opt
                                for i_opt, cp_opt in enumerate(cells_plain)
                                if any(
                                    k in cp_opt.lower()
                                    for k in (
                                        "correção",
                                        "correcao",
                                        "alteração",
                                        "alteracao",
                                        "implementação",
                                        "implementacao",
                                    )
                                )
                            ]
                            if opt_indices:
                                if len(opt_indices) == 1:
                                    only_idx = opt_indices[0]
                                    only_low = cells_plain[only_idx].lower()
                                    has_mark = any(
                                        cp.strip().upper() in ("X", "[X]", "(X)")
                                        or bool(re.search(r"[\[\(]\s*x\s*[\]\)]", cp, re.I))
                                        or bool(re.search(r"(?:^|\n)\s*x\s*(?:$|\n)", cp, re.I))
                                        for cp in cells_plain
                                    )
                                    if has_mark:
                                        if "corre" in only_low:
                                            s_data["tipo"] = "CORREÇÃO"
                                        elif "alter" in only_low:
                                            s_data["tipo"] = "ALTERAÇÃO"
                                        elif "implem" in only_low:
                                            s_data["tipo"] = "IMPLEMENTAÇÃO"
                                else:
                                    last_i = opt_indices[-1]
                                    mark_before = last_i == len(cells_plain) - 1
                                    for idx_opt in opt_indices:
                                        cp_opt = cells_plain[idx_opt]
                                        opt_low = cp_opt.lower()
                                        inline_x = bool(
                                            re.search(r"[\[\(]\s*x\s*[\]\)]", cp_opt, re.I)
                                            or re.search(r"(?:^|\n)\s*x\s*(?:$|\n)", cp_opt, re.I)
                                        )
                                        adj_x = False
                                        if mark_before and idx_opt > 0:
                                            adj_x = cells_plain[idx_opt - 1].strip().upper() in ("X", "[X]", "(X)")
                                        elif not mark_before and idx_opt + 1 < len(cells_plain):
                                            adj_x = cells_plain[idx_opt + 1].strip().upper() in ("X", "[X]", "(X)")
                                        if inline_x or adj_x:
                                            if "corre" in opt_low:
                                                s_data["tipo"] = "CORREÇÃO"
                                            elif "alter" in opt_low:
                                                s_data["tipo"] = "ALTERAÇÃO"
                                            elif "implem" in opt_low:
                                                s_data["tipo"] = "IMPLEMENTAÇÃO"

                            sis_val = _extract_hdr_val(
                                r"sistema\s*/\s*m[óo]dulo",
                                r"^[\s\S]*?m[óo]dulo:?\s*",
                            )
                            if sis_val:
                                s_data["sistema"] = sis_val

                            opc_val = _extract_hdr_val(
                                r"^op[çc][ãa]o",
                                r"^op[çc][ãa]o(?:\s*\([^\)]*\))?:?\s*",
                            )
                            if opc_val:
                                s_data["opcao"] = opc_val

                            ver_val = _extract_hdr_val(
                                r"^vers[ãa]o atual",
                                r"^vers[ãa]o atual(?:\s*do sistema)?(?:\s*\([^\)]*\))?:?\s*",
                            )
                            if ver_val:
                                s_data["versao"] = ver_val

                            emp_fil_val = _extract_hdr_val(
                                r"^empresa\s*/\s*filial",
                                r"^empresa\s*/\s*filial:?\s*",
                            )
                            if emp_fil_val:
                                s_data["empresa_filial"] = emp_fil_val

                            continue

                        # Processamento das Secoes de Conteudo e Etapas Tecnicas (Especificacao, Necessidade, Resultado Esperado, Suporte, Analise, Dev, Teste, Resultado)
                        if switched:
                            # Caso o usuario tenha escrito na mesma celula ou em celula adjacente logo ao lado do titulo
                            rem_md = "\n\n".join(cm for cm in cells_md if cm)
                            rem_md = re.sub(r"^\*?\*?Especifica[çc][ãa]o dos dados[^\n\r]*", "", rem_md, flags=re.I)
                            rem_md = re.sub(r"^\*?\*?Detalhar com clareza[^\n\r]*", "", rem_md, flags=re.I)
                            rem_md = re.sub(r"^\*?\*?Resultado Esperado:?\*?\*?\s*", "", rem_md, flags=re.I)
                            rem_md = re.sub(r"^\*?\*?Preenchido pel[oa][^\n\r]*", "", rem_md, flags=re.I)
                            rem_md = re.sub(r"^\*?\*?Recomenda[çc][õo]es ao teste[^\n\r]*:?\*?\*?", "", rem_md, flags=re.I)
                            rem_md = re.sub(r"^\*?\*?Resultado\s*\(release ou diverg[^\)]*\):?\*?\*?", "", rem_md, flags=re.I)
                            _append_section_md(active_section, rem_md)
                            continue

                        # Linha de Nome / Data
                        if any(cp.strip().lower().startswith("nome:") for cp in cells_plain) or (
                            len(cells_plain) <= 3 and row_low.startswith("data:")
                        ):
                            target_dict_key = SectionTargetMap.get(active_section)
                            if target_dict_key:
                                sec_obj = s_data[target_dict_key]
                                for cp in cells_plain:
                                    cp_s = cp.strip()
                                    if re.search(r"\bnome:", cp_s, re.I):
                                        person = _clean_dds_person(cp_s)
                                        if person and not sec_obj["responsavel"]:
                                            sec_obj["responsavel"] = person
                                    if re.search(r"\bdata:", cp_s, re.I):
                                        dt = _clean_dds_date(re.split(r"\bdata:?", cp_s, maxsplit=1, flags=re.I)[-1])
                                        if dt and not sec_obj["data"]:
                                            sec_obj["data"] = dt
                            continue

                        # Sub-rotulo 'Resultado esperado:' dentro de Analise de Negocios ou Analise de Sistemas
                        if row_low.startswith("resultado esperado") and active_section in ("analise_negocios", "analise_sistemas"):
                            rem_md = "\n\n".join(cm for cm in cells_md if cm)
                            rem_md = re.sub(r"^\*?\*?Resultado esperado:?\*?\*?\s*", "", rem_md, flags=re.I).strip()
                            cleaned_rem = _clean_dds_placeholder(rem_md)
                            if cleaned_rem:
                                if section_buffers.get(active_section):
                                    section_buffers[active_section].append(f"**Resultado Esperado:**\n{cleaned_rem}")
                                else:
                                    section_buffers[active_section].append(cleaned_rem)
                            continue

                        # Cabecalho vazio padrao da grade de requisitos do Team Leader na tabela principal
                        if active_section in ("team_lider", "team_leader"):
                            tl_probe = re.sub(r"[\s\*|]+", " ", row_plain).strip().lower()
                            if tl_probe.isdigit() or (
                                "requisito" in tl_probe
                                and "entendimento do team" in tl_probe
                                and "implementa" in tl_probe
                                and len(tl_probe) < 130
                            ):
                                continue

                        # Linha de conteudo normal da etapa ativa
                        if active_section != "header":
                            body_md = "\n\n".join(cm for cm in cells_md if cm)
                            _append_section_md(active_section, body_md)

                    if tbl_rows_html:
                        doc_html_blocks.append(f'<table class="docx-render-table"><tbody>{"".join(tbl_rows_html)}</tbody></table>')

            # 5. Caso existam imagens em word/media/ nao referenciadas por blip (e que nao sejam o logo do cabecalho),
            #    preserva compatibilidade total adicionando-as ao final.
            for item in sorted(namelist):
                if (
                    item.startswith("word/media/")
                    and item not in logo_only_targets
                    and item not in emitted_media_paths
                    and item.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
                ):
                    info = _get_media_data_uri(item)
                    if info:
                        data_uri, img_size, orig_fname = info
                        embedded_images.append({
                            "id": f"docx-emb-{len(embedded_images) + 1}",
                            "filename": orig_fname,
                            "data_url": data_uri,
                            "size": img_size,
                            "section": "Documento DDS",
                        })

            # Consolida buffers das secoes extraidas via XML
            structured_out: Optional[Dict[str, Any]] = None
            if found_consisa_template:
                s_data["especificacao_dados"] = "\n\n".join(section_buffers["especificacao"]).strip()
                s_data["necessidade_cliente"] = "\n\n".join(section_buffers["necessidade"]).strip()
                s_data["resultado_esperado"] = "\n\n".join(section_buffers["resultado_esperado"]).strip()
                s_data["suporte"]["detalhamento"] = "\n\n".join(section_buffers["suporte"]).strip()

                tl_parts = section_buffers["team_lider"] + section_buffers["team_leader"]
                tl_joined = "\n\n".join(tl_parts).strip()
                tl_probe_final = re.sub(r"[\s\*|]+", " ", tl_joined).strip().lower()
                if tl_probe_final in (
                    "1",
                    "1 requisito entendimento do team leader cartão pacote fonte implementação",
                    "1 requisito entendimento do team leader cartao pacote fonte implementacao",
                    "requisito entendimento do team leader cartão pacote fonte implementação",
                    "requisito entendimento do team leader cartao pacote fonte implementacao",
                ):
                    tl_joined = ""
                s_data["team_leader"]["detalhamento"] = tl_joined
                s_data["teste_validade"]["detalhamento"] = "\n\n".join(section_buffers["teste_validade"]).strip()
                s_data["analise_negocios"]["detalhamento"] = "\n\n".join(section_buffers["analise_negocios"]).strip()
                s_data["analise_sistemas"]["detalhamento"] = "\n\n".join(section_buffers["analise_sistemas"]).strip()
                s_data["desenvolvimento"]["detalhamento"] = "\n\n".join(section_buffers["desenvolvimento"]).strip()
                s_data["desenvolvimento"]["recomendacoes"] = "\n\n".join(section_buffers["dev_recomendacoes"]).strip()
                s_data["teste_implementacao"]["detalhamento"] = "\n\n".join(section_buffers["teste_implementacao"]).strip()

                hom_det = "\n\n".join(section_buffers["resultado_homologacao"]).strip()
                s_data["resultado_homologacao"]["detalhamento"] = hom_det
                s_data["resultado_homologacao"]["tipo"] = _classify_homologacao_tipo(hom_det)
                s_data["tipo"] = s_data["tipo"] or "NÃO DEFINIDO"

                has_struct = bool(
                    s_data["solicitacao"]
                    or s_data["necessidade_cliente"]
                    or s_data["resultado_esperado"]
                    or s_data["suporte"]["detalhamento"]
                    or s_data["suporte"]["responsavel"]
                    or s_data["team_leader"]["detalhamento"]
                    or s_data["analise_negocios"]["detalhamento"]
                    or s_data["analise_negocios"]["responsavel"]
                    or s_data["analise_sistemas"]["detalhamento"]
                    or s_data["analise_sistemas"]["responsavel"]
                    or s_data["desenvolvimento"]["detalhamento"]
                    or s_data["desenvolvimento"]["responsavel"]
                    or s_data["desenvolvimento"]["recomendacoes"]
                    or s_data["teste_implementacao"]["detalhamento"]
                    or s_data["teste_implementacao"]["responsavel"]
                    or s_data["resultado_homologacao"]["detalhamento"]
                )
                s_data["has_structured_data"] = has_struct
                structured_out = s_data

            full_text = "\n\n".join(b for b in all_md_blocks if b.strip())
            document_html = f'<div class="docx-document-root">{"".join(doc_html_blocks)}</div>' if doc_html_blocks else ""

            return {
                "text": full_text,
                "embedded_images": embedded_images,
                "document_html": document_html,
                "structured_dds": structured_out,
            }
    except Exception as e:
        logger.warning("Erro ao extrair dados completos do DOCX: %s", e)
        return empty_result


def extrair_texto_docx(conteudo_binario: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extrai texto enriquecido e imagens embutidas de um arquivo .docx sem dependencias externas.
    Retorna (texto_extraido, lista_de_imagens_base64).
    """
    parsed = extrair_documento_docx_completo(conteudo_binario)
    return parsed.get("text") or "", parsed.get("embedded_images") or []


def obter_dds_cache_local(chave_ou_url: str) -> Optional[str]:
    """Busca DDS pre-extraida no SQLite teams_messages.db (cache do leitor local / MCP)."""
    import base64
    import os
    import sqlite3

    db_path = r"c:\dev\Python Projects\Reader\teams_messages.db"
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        clean_param = (chave_ou_url or "").strip()
        if not clean_param:
            conn.close()
            return None

        candidatos = [clean_param]
        if "?" in clean_param:
            candidatos.append(clean_param.split("?")[0])

        if "sharepoint.com" in clean_param.lower():
            for u in [clean_param, clean_param.split("?")[0]]:
                try:
                    u_bytes = u.encode("utf-8")
                    # Formato padrao Microsoft Graph (base64url)
                    b64_std = base64.urlsafe_b64encode(u_bytes).decode("ascii").rstrip("=")
                    candidatos.append("u!" + b64_std)
                    # Compatibilidade legada
                    b64_leg = base64.b64encode(u_bytes).decode("ascii").rstrip("=").replace("+", "_").replace("/", "-")
                    if ("u!" + b64_leg) not in candidatos:
                        candidatos.append("u!" + b64_leg)
                except Exception:
                    pass

        for c in candidatos:
            cur.execute(
                "SELECT conteudo_bruto FROM cache_jira_dds WHERE chave = ? ORDER BY data_criacao DESC LIMIT 1",
                (c,),
            )
            row = cur.fetchone()
            if row and row[0]:
                conn.close()
                return str(row[0])

        for c in candidatos:
            if len(c) > 6:
                cur.execute(
                    "SELECT conteudo_bruto FROM cache_jira_dds WHERE chave LIKE ? ORDER BY data_criacao DESC LIMIT 1",
                    (f"%{c}%",),
                )
                row = cur.fetchone()
                if row and row[0]:
                    conn.close()
                    return str(row[0])

        conn.close()
    except Exception as e:
        logger.warning(f"Erro ao consultar cache local do DDS: {e}")
    return None


def estruturar_conteudo_dds(raw_text: str) -> Dict[str, Any]:
    """
    Analisa o texto extraido do template padrao de DDS da Consisa e organiza
    os campos em um modelo estruturado com higienizacao estrita de placeholders ('//', '-', 'N/A'),
    suporte a todas as etapas (Suporte, Team Leader, Analise de Negocios, Analise de Sistemas,
    Desenvolvimento, Checklist, Teste de Implementacao e Resultado da Homologacao).
    """
    import re

    if not raw_text or not raw_text.strip():
        return {"has_structured_data": False, "raw_text": ""}

    # Versao limpa de asteriscos de titulos apenas para facilitar ancoras de cabecalho sem perder o raw_text
    norm_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw_text)

    tipo_selecionado = ""
    for candidate in ["IMPLEMENTAÇÃO", "IMPLEMENTACAO", "CORREÇÃO", "CORRECAO", "ALTERAÇÃO", "ALTERACAO"]:
        cand_esc = re.escape(candidate)
        if re.search(rf"\[\s*[xX]\s*\]\s*{cand_esc}", norm_text, re.I) or re.search(rf"\(\s*[xX]\s*\)\s*{cand_esc}", norm_text, re.I):
            tipo_selecionado = (
                candidate.upper()
                .replace("IMPLEMENTACAO", "IMPLEMENTAÇÃO")
                .replace("CORRECAO", "CORREÇÃO")
                .replace("ALTERACAO", "ALTERAÇÃO")
            )
            break

    if not tipo_selecionado:
        m_tipo = re.search(r"(?:^|\n)\s*([xX])\s*\n+\s*(CORRE[ÇC][ÃA]O|ALTERA[ÇC][ÃA]O|IMPLEMENTA[ÇC][ÃA]O)", norm_text)
        if not m_tipo:
            m_tipo = re.search(r"(CORRE[ÇC][ÃA]O|ALTERA[ÇC][ÃA]O|IMPLEMENTA[ÇC][ÃA]O)[^\n\r]{0,80}?\n+\s*([xX])\s*(?:\n|$)", norm_text)
        if m_tipo:
            raw_t = m_tipo.group(1) if m_tipo.group(1).upper() != "X" else m_tipo.group(2)
            raw_t = raw_t.upper()
            if "CORRE" in raw_t:
                tipo_selecionado = "CORREÇÃO"
            elif "ALTER" in raw_t:
                tipo_selecionado = "ALTERAÇÃO"
            elif "IMPLEM" in raw_t:
                tipo_selecionado = "IMPLEMENTAÇÃO"

    labels_ignoradas = [
        "Solicitação N",
        "Solicitacao N",
        "Dados do Solicitante",
        "Nome do solicitante",
        "Código / Empresa",
        "Codigo / Empresa",
        "Nome do contato",
        "Preenchido pel",
        "Selecione o Tipo",
        "CORREÇÃO",
        "CORRECAO",
        "ALTERAÇÃO",
        "ALTERACAO",
        "IMPLEMENTAÇÃO",
        "IMPLEMENTACAO",
        "Sistema / Módulo",
        "Sistema / Modulo",
        "Opção",
        "Opcao",
        "Versão atual",
        "Versao atual",
        "Foram testadas",
        "Em caso de bug",
        "Local onde está",
        "Local onde esta",
        "Versão e Distribuição",
        "Usuário / Senha",
        "Usuario / Senha",
        "Empresa / Filial",
        "Especificação dos dados",
        "Especificacao dos dados",
        "Detalhar com clareza",
        "Resultado Esperado",
        "Revisão final",
        "Revisao final",
        "Padrão de codificação",
        "Data:",
    ]

    def _extract_field(pattern: str) -> str:
        m = re.search(pattern, norm_text, re.I)
        if not m:
            return ""
        val = _clean_dds_placeholder(m.group(1).strip())
        if not val:
            return ""
        for lbl in labels_ignoradas:
            if val.lower().startswith(lbl.lower()) or val.lower() == lbl.lower():
                return ""
        return val

    solicitacao_num = _extract_field(r"Solicita[çc][ãa]o\s*N[ºo°]?[:\s]*(?:\n+)?([^\n\r]+)")
    solicitante_nome = _extract_field(r"Nome do solicitante\s*/\s*Setor:?[:\s]*(?:\n+)?([^\n\r]+)")
    empresa_cliente = _extract_field(r"C[óo]digo\s*/\s*Empresa Cliente:?[:\s]*(?:\n+)?([^\n\r]+)")
    contato_cliente = _extract_field(r"Nome do contato na Empresa Cliente:?[:\s]*(?:\n+)?([^\n\r]+)")
    sistema_modulo = _extract_field(r"Sistema\s*/\s*M[óo]dulo:?[:\s]*(?:\n+)?([^\n\r]+)")
    opcao_caminho = _extract_field(r"Op[çc][ãa]o\s*\(caminho[^\)]*\):?[:\s]*(?:\n+)?([^\n\r]+)")
    versao_sistema = _extract_field(r"Vers[ãa]o atual do sistema[^\n\r]*:?[:\s]*(?:\n+)?([^\n\r]+)")
    empresa_filial = _extract_field(r"Empresa\s*/\s*Filial:?[:\s]*(?:\n+)?([^\n\r]+)")

    especificacao_dados = ""
    m_esp = re.search(
        r"\*?\*?Especifica[çc][ãa]o dos dados\*?\*?[\s\S]*?(?=\*?\*?Detalhar com clareza|\*?\*?Resultado Esperado:)",
        raw_text,
        re.I,
    )
    if m_esp:
        esp_raw = re.sub(r"\*?\*?Especifica[çc][ãa]o dos dados[^\n\r]*", "", m_esp.group(0), flags=re.I)
        especificacao_dados = _clean_dds_placeholder(esp_raw)

    necessidade_cliente = ""
    m_nec = re.search(r"\*?\*?Detalhar com clareza[\s\S]*?(?=\*?\*?Resultado Esperado:)", raw_text, re.I)
    if m_nec:
        nec_raw = re.sub(r"^\*?\*?Detalhar com clareza[^\n\r]*:?\*?\*?", "", m_nec.group(0), flags=re.I)
        necessidade_cliente = _clean_dds_placeholder(nec_raw)

    resultado_esperado = ""
    m_res = re.search(r"\*?\*?Resultado Esperado:\*?\*?[\s\S]*?(?=\*?\*?Preenchido pel[oa]|\*?\*?Revis[ãa]o final|$)", raw_text, re.I)
    if m_res:
        res_raw = re.sub(r"^\*?\*?Resultado Esperado:\*?\*?\s*", "", m_res.group(0), flags=re.I)
        resultado_esperado = _clean_dds_placeholder(res_raw)

    def _parse_standard_section(block_raw: str, header_regex: str) -> Dict[str, str]:
        sec = {"responsavel": "", "data": "", "detalhamento": ""}
        if not block_raw:
            return sec
        m_nome = re.search(r"\*?\*?Nome:\*?\*?\s*([^\n\r]*)", block_raw, re.I)
        m_dt = re.search(r"\*?\*?Data:\*?\*?\s*([^\n\r]*)", block_raw, re.I)
        if m_nome:
            sec["responsavel"] = _clean_dds_person(m_nome.group(1))
        if m_dt:
            sec["data"] = _clean_dds_date(m_dt.group(1))

        body = re.sub(header_regex, "", block_raw, flags=re.I)
        body = re.sub(r"\*?\*?Nome:\*?\*?[^\n\r]*", "", body, flags=re.I)
        body = re.sub(r"\*?\*?Data:\*?\*?[^\n\r]*", "", body, flags=re.I)
        # Se terminar apenas com o rotulo vazio 'Resultado esperado:', remove-o
        body = re.sub(r"\n*\s*\*?\*?Resultado esperado:\*?\*?\s*$", "", body, flags=re.I)
        # Se houver conteudo real apos 'Resultado esperado:', mantem formatado
        body = re.sub(r"^\s*\*?\*?Resultado esperado:\*?\*?\s*", "", body, flags=re.I)
        det = _clean_dds_placeholder(body)
        if det:
            sec["detalhamento"] = det
        return sec

    NEXT_SEC_LOOKAHEAD = r"(?=\n\s*\*?\*?Preenchido pel[oa]|\n\s*\*?\*?Revis[ãa]o final|$)"

    # Suporte
    m_sup = re.search(rf"\*?\*?Preenchido pel[oa] Suporte[\s\S]*?{NEXT_SEC_LOOKAHEAD}", raw_text, re.I)
    suporte = _parse_standard_section(m_sup.group(0) if m_sup else "", r"\*?\*?Preenchido pel[oa] Suporte:?(\*\*)?")

    # Teste de Validade
    m_val = re.search(rf"\*?\*?Preenchido pel[oa] Teste de Validade[\s\S]*?{NEXT_SEC_LOOKAHEAD}", raw_text, re.I)
    teste_validade = _parse_standard_section(m_val.group(0) if m_val else "", r"\*?\*?Preenchido pel[oa] Teste de Validade:?(\*\*)?")

    # Analise de Negocios
    m_an = re.search(rf"\*?\*?Preenchido pel[oa] An[áa]lise de Neg[óo]cios[\s\S]*?{NEXT_SEC_LOOKAHEAD}", raw_text, re.I)
    analise_negocios = _parse_standard_section(
        m_an.group(0) if m_an else "", r"\*?\*?Preenchido pel[oa] An[áa]lise de Neg[óo]cios:?(\*\*)?"
    )

    # Analise de Sistemas
    m_as = re.search(rf"\*?\*?Preenchido pel[oa] An[áa]lise de Sistemas[\s\S]*?{NEXT_SEC_LOOKAHEAD}", raw_text, re.I)
    analise_sistemas = _parse_standard_section(
        m_as.group(0) if m_as else "", r"\*?\*?Preenchido pel[oa] An[áa]lise de Sistemas:?(\*\*)?"
    )

    # Team Lider / Team Leader
    team_leader = {"responsavel": "", "data": "", "detalhamento": ""}
    tl_dets: List[str] = []
    for m_tl in re.finditer(rf"\*?\*?Preenchido pel[oa] Team (?:L[íi]der|Leader)[\s\S]*?{NEXT_SEC_LOOKAHEAD}", raw_text, re.I):
        parsed_tl = _parse_standard_section(m_tl.group(0), r"\*?\*?Preenchido pel[oa] Team (?:L[íi]der|Leader):?(\*\*)?")
        if parsed_tl["responsavel"] and not team_leader["responsavel"]:
            team_leader["responsavel"] = parsed_tl["responsavel"]
        if parsed_tl["data"] and not team_leader["data"]:
            team_leader["data"] = parsed_tl["data"]
        det_tl = parsed_tl["detalhamento"]
        # Ignora cabecalho vazio da tabela padrao de requisitos do Team Leader
        det_tl_probe = re.sub(r"[\s\*|]+", " ", det_tl).strip().lower()
        if det_tl and det_tl_probe not in (
            "1 requisito entendimento do team leader cartão pacote fonte implementação",
            "1 requisito entendimento do team leader cartao pacote fonte implementacao",
        ):
            tl_dets.append(det_tl)
    if tl_dets:
        team_leader["detalhamento"] = "\n\n".join(tl_dets)

    # Checklist de Revisao Final
    checklist_items: List[Dict[str, str]] = []
    m_rev_idx = re.search(r"(?:Revis[ãa]o final|Padr[ãa]o de codifica[çc][ãa]o)", norm_text, re.I)
    if m_rev_idx:
        rev_part = norm_text[m_rev_idx.start():]
        # Limita ate Recomendacoes ou Teste de Implementacao
        rev_part = re.split(r"Recomenda[çc][õo]es ao teste|Preenchido pel[oa] Teste", rev_part, maxsplit=1, flags=re.I)[0]
        lines = [line.strip() for line in rev_part.splitlines() if line.strip()]
        categoria_atual = "Geral"
        i = 0
        while i < len(lines):
            l_cur = lines[i]
            if l_cur in ["Padrão de codificação", "Persistência de dados", "SQL", "Interface", "Envio para teste"]:
                categoria_atual = l_cur
                i += 1
                continue
            if l_cur.endswith("?") and i + 1 < len(lines):
                resp = lines[i + 1]
                if not resp.endswith("?") and resp not in ["Padrão de codificação", "Persistência de dados", "SQL", "Interface", "Envio para teste"]:
                    checklist_items.append({"categoria": categoria_atual, "pergunta": l_cur, "resposta": resp})
                    i += 2
                    continue
            i += 1

    # Desenvolvimento
    desenvolvimento = {"responsavel": "", "data": "", "detalhamento": "", "recomendacoes": ""}
    m_dev = re.search(
        r"\*?\*?Preenchido pel[oa] Desenvolvimento[^\n\r]*[\s\S]*?(?=\n\s*\*?\*?Preenchido pel[oa] Teste de Implementa[çc][ãa]o|$)",
        raw_text,
        re.I,
    )
    if m_dev:
        dev_raw = m_dev.group(0)
        m_nome = re.search(r"\*?\*?Nome:\*?\*?\s*([^\n\r]*)", dev_raw, re.I)
        m_dt = re.search(r"\*?\*?Data:\*?\*?\s*([^\n\r]*)", dev_raw, re.I)
        if m_nome:
            desenvolvimento["responsavel"] = _clean_dds_person(m_nome.group(1))
        if m_dt:
            desenvolvimento["data"] = _clean_dds_date(m_dt.group(1))

        m_rec = re.search(
            r"\*?\*?Recomenda[çc][õo]es ao teste[^\n\r]*:?\*?\*?\s*([\s\S]*?)(?=\n\s*\*?\*?Preenchido pel[oa] Teste|$)",
            dev_raw,
            re.I,
        )
        if m_rec:
            rec_clean = _clean_dds_placeholder(m_rec.group(1))
            if rec_clean and not rec_clean.lower().startswith("preenchido"):
                desenvolvimento["recomendacoes"] = rec_clean

        dev_corpo = re.split(
            r"\n\s*\*?\*?(?:Revis[ãa]o final|Padr[ãa]o de codifica[çc][ãa]o|Recomenda[çc][õo]es ao teste)",
            dev_raw,
            maxsplit=1,
            flags=re.I,
        )[0]
        dev_corpo = re.sub(r"\*?\*?Preenchido pel[oa] Desenvolvimento[^\n\r]*", "", dev_corpo, flags=re.I)
        dev_corpo = re.sub(r"\*?\*?Nome:\*?\*?[^\n\r]*", "", dev_corpo, flags=re.I)
        dev_corpo = re.sub(r"\*?\*?Data:\*?\*?[^\n\r]*", "", dev_corpo, flags=re.I)
        det_dev = _clean_dds_placeholder(dev_corpo)
        if det_dev:
            desenvolvimento["detalhamento"] = det_dev

    # Teste de Implementacao e Resultado da Homologacao (separacao segura sem truncar a palavra 'resultado' no meio do texto)
    teste_implementacao = {"responsavel": "", "data": "", "detalhamento": ""}
    resultado_homologacao = {"tipo": "Release", "detalhamento": ""}
    m_test = re.search(r"\*?\*?Preenchido pel[oa] Teste de Implementa[çc][ãa]o[\s\S]*?$", raw_text, re.I)
    if m_test:
        test_raw = m_test.group(0)
        m_nome = re.search(r"\*?\*?Nome:\*?\*?\s*([^\n\r]*)", test_raw, re.I)
        m_dt = re.search(r"\*?\*?Data:\*?\*?\s*([^\n\r]*)", test_raw, re.I)
        if m_nome:
            teste_implementacao["responsavel"] = _clean_dds_person(m_nome.group(1))
        if m_dt:
            teste_implementacao["data"] = _clean_dds_date(m_dt.group(1))

        # Divide somente no cabecalho oficial da secao Resultado (release ou divergencia...) ou 'Resultado:' em inicio de linha
        split_hom = re.split(
            r"\n\s*\*?\*?Resultado(?:\s*\(release ou diverg[êe]ncia[^\)]*\))?\s*:?\*?\*?(?:\s*\n|\s+)",
            test_raw,
            maxsplit=1,
            flags=re.I,
        )
        test_corpo = split_hom[0]
        # Remove rotulo final vazio caso o documento termine em 'Resultado (...):' sem conteúdo depois
        test_corpo = re.sub(
            r"\n\s*\*?\*?Resultado\s*\(release ou diverg[êe]ncia[^\)]*\)\s*:?\*?\*?\s*$",
            "",
            test_corpo,
            flags=re.I,
        )
        test_corpo = re.sub(r"\*?\*?Preenchido pel[oa] Teste de Implementa[çc][ãa]o:?(\*\*)?", "", test_corpo, flags=re.I)
        test_corpo = re.sub(r"\*?\*?Nome:\*?\*?[^\n\r]*", "", test_corpo, flags=re.I)
        test_corpo = re.sub(r"\*?\*?Data:\*?\*?[^\n\r]*", "", test_corpo, flags=re.I)
        det_test = _clean_dds_placeholder(test_corpo)
        if det_test:
            teste_implementacao["detalhamento"] = det_test

        if len(split_hom) > 1:
            det_hom = _clean_dds_placeholder(split_hom[1])
            if det_hom:
                resultado_homologacao["detalhamento"] = det_hom
                resultado_homologacao["tipo"] = _classify_homologacao_tipo(det_hom)

    has_structured = bool(
        solicitacao_num
        or necessidade_cliente
        or resultado_esperado
        or suporte.get("detalhamento")
        or suporte.get("responsavel")
        or team_leader.get("detalhamento")
        or analise_negocios.get("detalhamento")
        or analise_negocios.get("responsavel")
        or analise_sistemas.get("detalhamento")
        or analise_sistemas.get("responsavel")
        or desenvolvimento.get("detalhamento")
        or desenvolvimento.get("responsavel")
        or desenvolvimento.get("recomendacoes")
        or teste_implementacao.get("detalhamento")
        or teste_implementacao.get("responsavel")
        or resultado_homologacao.get("detalhamento")
    )

    return {
        "has_structured_data": has_structured,
        "solicitacao": solicitacao_num,
        "solicitante": solicitante_nome,
        "empresa": empresa_cliente,
        "contato": contato_cliente,
        "tipo": tipo_selecionado or "NÃO DEFINIDO",
        "sistema": sistema_modulo,
        "opcao": opcao_caminho,
        "versao": versao_sistema,
        "empresa_filial": empresa_filial,
        "especificacao_dados": especificacao_dados,
        "necessidade_cliente": necessidade_cliente,
        "resultado_esperado": resultado_esperado,
        "analise_negocios": analise_negocios,
        "analise_sistemas": analise_sistemas,
        "teste_validade": teste_validade,
        "suporte": suporte,
        "team_leader": team_leader,
        "desenvolvimento": desenvolvimento,
        "teste_implementacao": teste_implementacao,
        "resultado_homologacao": resultado_homologacao,
        "checklist": checklist_items,
    }


class JiraClient:
    """Cliente HTTP para envio de Worklogs ao Jira com auto-deteccao de protocolo de autenticacao."""

    _account_id_cache: Dict[str, str] = {}

    def __init__(self, jira_config: JiraConfig, state_manager: Optional[StateManager] = None):
        self.config = jira_config
        self.state_manager = state_manager or StateManager()

    def resolve_jira_account_id(self, account_id: str) -> str:
        """Resolve um Atlassian accountId para o nome exibivel (displayName) do usuario."""
        clean_id = (account_id or "").strip()
        if not clean_id:
            return ""
        if clean_id in JiraClient._account_id_cache:
            return JiraClient._account_id_cache[clean_id]

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()
        endpoint = f"{base_url}/rest/api/2/user?accountId={urllib.parse.quote(clean_id)}"
        req = urllib.request.Request(endpoint, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                u_data = json.loads(resp.read().decode("utf-8"))
                disp = u_data.get("displayName") or clean_id
                JiraClient._account_id_cache[clean_id] = disp
                return disp
        except Exception as e:
            logger.debug(f"Nao foi possivel resolver accountId '{clean_id}': {e}")
            JiraClient._account_id_cache[clean_id] = clean_id
            return clean_id

    def _build_headers(self, strategy: str) -> Dict[str, str]:
        """Gera os headers HTTP para cada uma das estrategias de autenticacao suportadas."""
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "JiraBot/1.0",
            "X-Atlassian-Token": "no-check",
        }
        email = self.config.get_clean_email()
        token = self.config.get_clean_token()
        username = email.split("@")[0] if "@" in email else email

        if strategy == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif strategy == "basic_email" and email and token:
            auth_str = f"{email}:{token}"
            b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {b64_auth}"
        elif strategy == "basic_user" and username and token:
            auth_str = f"{username}:{token}"
            b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {b64_auth}"
        elif token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _get_auth_headers(self) -> Dict[str, str]:
        """Retorna os headers com base no modo autenticado ou modo padrao."""
        auth_type = self.config.auth_type
        if auth_type in ["bearer", "basic_email", "basic_user"]:
            return self._build_headers(auth_type)
        if "@" in self.config.get_clean_email():
            return self._build_headers("basic_email")
        return self._build_headers("bearer")

    def test_connection(self) -> Dict[str, Any]:
        """
        Executa uma auto-negociacao de autenticacao testando as estrategias possiveis
        (Bearer Token, Basic Auth com Email e Basic Auth com Username) e salvando a que funcionar.
        """
        base_url = self.config.get_clean_base_url()
        email = self.config.get_clean_email()
        token = self.config.get_clean_token()

        if not base_url or "seu-dominio" in base_url:
            return {
                "success": False,
                "message": "URL do Jira ainda nao foi configurada. Execute a opcao [C] Reconfigurar Setup.",
            }
        if not token:
            return {
                "success": False,
                "message": "API Token do Jira nao foi informado. Execute a opcao [C] Reconfigurar Setup.",
            }

        endpoint = f"{base_url}/rest/api/2/myself"

        # Estrategias ordenadas de teste
        strategies: List[Tuple[str, str]] = [
            ("bearer", "Token Bearer (Personal Access Token / PAT)"),
            ("basic_email", f"Basic Auth ({email}:Token)"),
            ("basic_user", f"Basic Auth com Usuario ({email.split('@')[0] if '@' in email else email}:Token)"),
        ]

        last_error = ""
        for strat_name, strat_desc in strategies:
            headers = self._build_headers(strat_name)
            req = urllib.request.Request(endpoint, headers=headers, method="GET")

            try:
                with urllib.request.urlopen(req, timeout=12) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    user_name = resp_data.get("displayName") or resp_data.get("name") or "Usuario Jira"
                    user_email = resp_data.get("emailAddress") or email

                    # Salva a estrategia vencedora na configuracao do usuario
                    self.config.auth_type = strat_name
                    from config import BotConfig
                    bot_cfg = BotConfig.load()
                    bot_cfg.jira.auth_type = strat_name
                    bot_cfg.save()

                    return {
                        "success": True,
                        "message": f"Conexao autenticada com sucesso via {strat_desc}!\nUsuario: {user_name} ({user_email})",
                        "user": user_name,
                        "strategy": strat_name,
                    }

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                continue
            except urllib.error.URLError as e:
                return {
                    "success": False,
                    "message": f"Nao foi possivel conectar na URL '{base_url}'. Verifique a conexao ou VPN: {e.reason}",
                }
            except Exception as e:
                last_error = str(e)
                continue

        diag_msg = (
            f"Falha de autenticacao no Jira ({last_error}).\n\n"
            f"O JiraBot tentou automaticamente:\n"
            f"1. Bearer Token (PAT)\n"
            f"2. Basic Auth com Email ({email})\n"
            f"3. Basic Auth com Usuario ({email.split('@')[0] if '@' in email else email})\n\n"
            f"Dicas para resolver:\n"
            f"- Verifique se a URL '{base_url}' e exatamente a mesma que voce usa no navegador.\n"
            f"- Verifique se o e-mail informado confere com o da sua conta no Jira.\n"
            f"- Confirme se o token foi colado integralmente sem caracteres faltando."
        )
        return {"success": False, "message": diag_msg}

    def resolve_issue_key(self, term_or_key: str) -> str:
        """
        Verifica se a chave informada existe diretamente no Jira ou busca pelo numero/texto (ex: TICKET-380374 -> CDG-7668).
        """
        import urllib.parse

        clean = term_or_key.strip().upper()
        if not clean:
            return self.config.default_issue

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()

        # 1. Tenta verificar se a chave e valida diretamente
        try:
            req = urllib.request.Request(f"{base_url}/rest/api/2/issue/{clean}?fields=id,key,summary", headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("key", clean)
        except Exception:
            pass

        # 2. Se falhar (ex: TICKET-380374 ou numero puro 380374), busca por JQL
        num_part = "".join(c for c in clean if c.isdigit())
        search_terms = [clean]
        if num_part and num_part != clean:
            search_terms.append(num_part)

        for term in search_terms:
            jql = f'text ~ "{term}" OR summary ~ "{term}"'
            query_url = f"{base_url}/rest/api/2/search/jql?jql={urllib.parse.quote(jql)}&maxResults=1&fields=id,key,summary"
            try:
                req = urllib.request.Request(query_url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    issues = data.get("issues", [])
                    if issues:
                        found_key = issues[0].get("key")
                        logger.info(f"Termo '{term_or_key}' resolvido automaticamente para o ticket '{found_key}'.")
                        return found_key
            except Exception:
                pass

        return clean

    def get_issue_summary(self, issue_key: str) -> str:
        """Busca o titulo/resumo do ticket no Jira para uso como fallback inteligente."""
        clean = issue_key.strip().upper()
        if not clean or clean == "SEM_TICKET":
            return ""

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()
        endpoint = f"{base_url}/rest/api/2/issue/{clean}?fields=summary"
        try:
            req = urllib.request.Request(endpoint, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("fields", {}).get("summary", "")
        except Exception:
            return ""

    @staticmethod
    def _extract_adf_text(node: Any) -> str:
        """Extrai texto legivel de nos no formato Atlassian Document Format (ADF)."""
        if not node:
            return ""
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return "\n".join(JiraClient._extract_adf_text(item) for item in node if item)
        if isinstance(node, dict):
            node_type = node.get("type", "")
            if node_type == "text":
                return node.get("text", "")
            content = node.get("content", [])
            children_text = " ".join(JiraClient._extract_adf_text(c) for c in content if c)
            if node_type in ("paragraph", "heading"):
                return f"\n{children_text}\n"
            elif node_type == "bulletList":
                return f"\n{children_text}\n"
            elif node_type == "listItem":
                return f"* {children_text}"
            return children_text
        return ""

    def get_my_assigned_tickets(
        self,
        max_results: int = 50,
        status_filter: str = "open",
        query_text: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Retorna a lista de tickets atribuidos ao usuario autenticado no Jira.
        Suporta filtro por status ('open', 'done', 'all') e busca por texto/chave.
        """
        import re
        import urllib.parse

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()

        status_filter = (status_filter or "open").lower().strip()
        jql_parts = ["assignee = currentUser()"]

        if status_filter == "open":
            jql_parts.append("statusCategory != Done")
        elif status_filter == "done":
            jql_parts.append("statusCategory = Done")

        q_clean = (query_text or "").strip().replace('"', '\\"')
        if q_clean:
            jql_parts.append(f'(text ~ "{q_clean}" OR key = "{q_clean.upper()}" OR summary ~ "{q_clean}")')

        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
        limit = min(max(1, max_results), 100)
        fields = "key,summary,status,issuetype,priority,created,updated,description,customfield_11200,customfield_12600,parent"

        url_api = f"{base_url}/rest/api/2/search/jql?jql={urllib.parse.quote(jql)}&maxResults={limit}&fields={fields}"
        req = urllib.request.Request(url_api, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Falha na consulta de tickets do usuario: %s", e)
            return []

        issues = data.get("issues", [])
        formatted_list: List[Dict[str, Any]] = []

        for issue in issues:
            k = (issue.get("key") or "").strip().upper()
            if not k:
                continue
            f = issue.get("fields", {}) or {}
            st = f.get("status") or {}
            st_name = st.get("name") or "Sem status"
            st_cat = ((st.get("statusCategory") or {}).get("key")) or "indeterminate"

            it = f.get("issuetype") or {}
            it_name = it.get("name") or "Tarefa"
            it_icon = it.get("iconUrl") or ""

            pr = f.get("priority") or {}
            pr_name = pr.get("name") or "Normal"
            pr_icon = pr.get("iconUrl") or ""

            parent_raw = f.get("parent") or {}
            parent_key = (parent_raw.get("key") or "").strip().upper()
            parent_summary = (parent_raw.get("fields") or {}).get("summary") or ""
            is_subtask = bool(it.get("subtask") or parent_key)

            desc_raw = f.get("description")
            if isinstance(desc_raw, dict):
                desc_str = self._extract_adf_text(desc_raw)
            else:
                desc_str = str(desc_raw or "")

            summary = f.get("summary") or "Sem título"

            dds_cf1 = str(f.get("customfield_11200") or "")
            dds_cf2 = str(f.get("customfield_12600") or "")
            combined_text = f"{summary} {desc_str} {dds_cf1} {dds_cf2}".lower()

            has_dds = bool(
                "sharepoint.com" in combined_text
                or "dds" in combined_text
                or ":w:" in combined_text
                or ".docx" in combined_text
            )

            movidesk_num = ""
            m_match = re.search(r'(?:ticket|movidesk)[\s#:-]*(\d{5,7})', f"{summary} {desc_str}", re.I)
            if m_match:
                movidesk_num = m_match.group(1)

            created_raw = f.get("created") or ""
            updated_raw = f.get("updated") or ""

            formatted_list.append({
                "key": k,
                "summary": summary,
                "status": st_name,
                "status_category": st_cat,
                "issue_type": it_name,
                "issue_type_icon": it_icon,
                "priority": pr_name,
                "priority_icon": pr_icon,
                "created": created_raw[:10] if len(created_raw) >= 10 else created_raw,
                "updated": updated_raw[:10] if len(updated_raw) >= 10 else updated_raw,
                "has_dds": has_dds,
                "dds_from_parent": False,
                "parent_key": parent_key,
                "parent_summary": parent_summary,
                "is_subtask": is_subtask,
                "movidesk_ticket": movidesk_num,
                "url": f"{base_url}/browse/{k}",
            })

        # Checagem em lote otimizada de DDS nos tickets pai para subtarefas
        parents_to_check = {item["parent_key"] for item in formatted_list if item.get("parent_key")}
        if parents_to_check:
            try:
                jql_parents = f'key in ({",".join(parents_to_check)})'
                url_parents = f"{base_url}/rest/api/2/search/jql?jql={urllib.parse.quote(jql_parents)}&fields=key,customfield_11200,customfield_12600,attachment,description,summary"
                req_parents = urllib.request.Request(url_parents, headers=headers, method="GET")
                with urllib.request.urlopen(req_parents, timeout=10) as r_p:
                    p_data = json.loads(r_p.read().decode("utf-8"))
                    parents_with_dds = set()
                    for p_iss in p_data.get("issues", []):
                        p_key = (p_iss.get("key") or "").upper()
                        p_f = p_iss.get("fields", {}) or {}
                        p_cf1 = str(p_f.get("customfield_11200") or "")
                        p_cf2 = str(p_f.get("customfield_12600") or "")
                        p_desc = str(p_f.get("description") or "")
                        p_atts = [a.get("filename") or "" for a in p_f.get("attachment", []) or []]
                        has_p_docx = any(a.lower().endswith((".docx", ".doc")) for a in p_atts)
                        has_p_sp = any("sharepoint" in x.lower() or "dds" in x.lower() for x in [p_cf1, p_cf2, p_desc])
                        if has_p_docx or has_p_sp:
                            parents_with_dds.add(p_key)
                    for item in formatted_list:
                        if item.get("parent_key") in parents_with_dds:
                            item["has_dds"] = True
                            item["dds_from_parent"] = True
            except Exception as ex:
                logger.debug("Falha na checagem em lote de tickets pai: %s", ex)

        return formatted_list

    def get_ticket_dds_details(
        self,
        issue_key: str,
        is_parent_call: bool = False,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Consulta detalhes completos de um ticket no Jira, isolando a descricao,
        links do SharePoint (DDS / Word), anexos, imagens, historico de comunicacoes
        ('Quem Mandou o Que') e conteudo integral da DDS extraido nativamente.
        Prioriza a versao viva do SharePoint Online (quando conectado via Microsoft Graph)
        ou .docx importado localmente sobre anexos antigos do Jira, sem inventar dados sinteticos.
        """
        import re

        clean = clean_jira_issue_key(issue_key)
        if not clean or clean == "SEM_TICKET":
            return {"error": "Chave de ticket inválida."}

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()

        endpoint = f"{base_url}/rest/api/2/issue/{clean}?fields=*all"
        req = urllib.request.Request(endpoint, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": f"Não foi possível carregar o ticket {clean}: {e}"}

        f = data.get("fields", {}) or {}
        st = f.get("status") or {}
        st_name = st.get("name") or "Sem status"
        st_cat = ((st.get("statusCategory") or {}).get("key")) or "indeterminate"

        parent_raw = f.get("parent") or {}
        parent_key = (parent_raw.get("key") or "").strip().upper()
        parent_fields = parent_raw.get("fields") or {}
        parent_summary = parent_fields.get("summary") or ""
        dds_inherited_from_parent = False

        it = f.get("issuetype") or {}
        it_name = it.get("name") or "Tarefa"

        pr = f.get("priority") or {}
        pr_name = pr.get("name") or "Normal"

        assignee = (f.get("assignee") or {}).get("displayName") or "Não atribuído"
        reporter = (f.get("reporter") or {}).get("displayName") or "Não informado"

        desc_raw = f.get("description")
        if isinstance(desc_raw, dict):
            desc_text = self._extract_adf_text(desc_raw).strip()
        else:
            desc_text = str(desc_raw or "").strip()

        dds_links: List[Dict[str, str]] = []
        seen_urls = set()

        def add_url(url: str, title: str = "Documento DDS"):
            clean_url = url.strip().rstrip(").,;")
            if clean_url and clean_url not in seen_urls and clean_url.startswith("http"):
                seen_urls.add(clean_url)
                doc_type = "sharepoint"
                if ":w:" in clean_url or clean_url.endswith(".docx") or clean_url.endswith(".doc"):
                    doc_type = "word"
                elif ":f:" in clean_url:
                    doc_type = "folder"

                embed_url = clean_url
                if "sharepoint.com" in clean_url.lower():
                    if "action=" in clean_url:
                        embed_url = re.sub(r'action=[a-zA-Z0-9_-]+', 'action=embedview', clean_url)
                    else:
                        sep = "&" if "?" in clean_url else "?"
                        embed_url = f"{clean_url}{sep}action=embedview"

                dds_links.append({
                    "url": clean_url,
                    "embed_url": embed_url,
                    "title": title,
                    "type": doc_type,
                })

        for cf_id in ["customfield_11200", "customfield_12600"]:
            val = f.get(cf_id)
            if val and isinstance(val, str) and "sharepoint" in val.lower():
                for part in re.findall(r'https?://[^\s<>"]+', val):
                    add_url(part, "Link Oficial do DDS (SharePoint)")

        for k, v in f.items():
            if k not in ["customfield_11200", "customfield_12600"] and v and isinstance(v, str) and "sharepoint" in v.lower():
                for part in re.findall(r'https?://[^\s<>"]+', v):
                    add_url(part, "Link SharePoint")

        if desc_text:
            for part in re.findall(r'https?://[^\s<>"]+', desc_text):
                if "sharepoint.com" in part.lower():
                    add_url(part, "Link SharePoint na Descrição")

        def _dds_rank(item: Dict[str, Any]) -> int:
            t = item.get("type", "")
            if t == "word":
                return 0
            if t in ["excel", "powerpoint", "pdf"]:
                return 1
            if t == "folder":
                return 3
            return 2

        dds_links.sort(key=_dds_rank)

        # 1. Separacao de Anexos e Imagens com suporte a proxy autenticado
        images_list: List[Dict[str, Any]] = []
        files_list: List[Dict[str, Any]] = []

        for att in f.get("attachment", []) or []:
            name = att.get("filename") or "anexo"
            size = att.get("size") or 0
            content_url = att.get("content") or ""
            thumb_url = att.get("thumbnail") or content_url
            mime = (att.get("mimeType") or "").lower()

            proxy_url = f"/api/jira/attachment?url={urllib.parse.quote(content_url)}"
            thumb_proxy_url = f"/api/jira/attachment?url={urllib.parse.quote(thumb_url)}"

            is_img = mime.startswith("image/") or name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"))

            item_info = {
                "id": str(att.get("id") or ""),
                "name": name,
                "size": size,
                "url": content_url,
                "proxy_url": proxy_url,
                "created": att.get("created") or "",
                "author": (att.get("author") or {}).get("displayName") or "",
            }

            if is_img:
                item_info["thumbnail_url"] = thumb_proxy_url
                item_info["is_embedded"] = False
                images_list.append(item_info)
            else:
                item_info["is_doc"] = name.lower().endswith((".docx", ".doc", ".pdf", ".xlsx", ".pbix"))
                files_list.append(item_info)

            if name.lower().endswith((".docx", ".doc")) and "dds" in name.lower():
                add_url(content_url, f"Anexo DDS: {name}")

        # 2. Extracao de Comentarios ('Quem Mandou o Que') com resolucao de @mencoes
        comments_timeline: List[Dict[str, Any]] = []
        raw_comments = (f.get("comment", {}) or {}).get("comments", []) or []
        for c in raw_comments:
            author_obj = c.get("author") or {}
            disp_name = author_obj.get("displayName") or "Usuário"
            avatars = author_obj.get("avatarUrls") or {}
            avatar_url = avatars.get("48x48") or avatars.get("32x32") or avatars.get("24x24") or ""
            created_dt = c.get("created") or ""

            body_raw = c.get("body")
            if isinstance(body_raw, dict):
                body_text = self._extract_adf_text(body_raw).strip()
            else:
                body_text = str(body_raw or "").strip()

            # Substitui mencoes de usuarios Atlassian [~accountid:XYZ] ou [~XYZ] pelo nome real do usuario
            found_mentions: List[str] = []

            def _replace_mention(match: re.Match) -> str:
                aid = match.group(1).strip()
                name = self.resolve_jira_account_id(aid)
                if name and name not in found_mentions:
                    found_mentions.append(name)
                return f"@{name}"

            resolved_body = re.sub(r'\[~accountid:([^\]]+)\]', _replace_mention, body_text, flags=re.I)
            resolved_body = re.sub(r'\[~([^\]:]+)\]', _replace_mention, resolved_body)

            movidesk_sender = ""
            clean_body = resolved_body
            is_movidesk = False
            if "#MovideskAction#" in clean_body:
                is_movidesk = True
                clean_body = clean_body.replace("#MovideskAction#", "").strip()

            # Isola textos padroes de boilerplate legal e LGPD do Movidesk
            is_disclaimer = bool(
                "compliance interno conforme a LGPD" in clean_body
                or "pesquisa de satisfação referente a cada chamado que o Movidesk envia" in clean_body
            )
            disclaimer_note = ""
            if is_disclaimer:
                m_disc = re.search(r'(Estamos empenhados em aprimorar[\s\S]+)', clean_body)
                if m_disc:
                    disclaimer_note = m_disc.group(1).strip()
                    clean_body = clean_body.replace(disclaimer_note, "").strip()
                if not clean_body or clean_body.startswith("Aaah"):
                    clean_body = "Mensagem automática de abertura e compliance LGPD do atendimento Movidesk."

            lines = clean_body.splitlines()
            if lines and ":" in lines[0] and len(lines[0]) < 80 and not lines[0].lower().startswith("http"):
                first_line = lines[0].strip()
                parts = first_line.split(":", 1)
                if len(parts) == 2 and not parts[0].isdigit():
                    movidesk_sender = parts[0].strip()
                    rest = parts[1].strip()
                    remaining_lines = lines[1:]
                    if rest:
                        remaining_lines.insert(0, rest)
                    clean_body = "\n".join(remaining_lines).strip()
                    is_movidesk = True

            comments_timeline.append({
                "id": str(c.get("id") or ""),
                "author": disp_name,
                "avatar_url": avatar_url,
                "created": created_dt,
                "body": clean_body,
                "raw_body": body_text,
                "movidesk_sender": movidesk_sender,
                "is_movidesk": is_movidesk,
                "is_disclaimer": is_disclaimer,
                "disclaimer_note": disclaimer_note,
                "mentions": found_mentions,
            })

        # 3. Extracao Nativa de Conteudo DDS (Prioridade: SharePoint Vivo -> Upload Manual -> Anexo Jira -> Cache Local -> Descricao)
        from sharepoint_client import SharePointManager

        sp_mgr = SharePointManager(base_dir=self.state_manager.base_dir if self.state_manager else None)
        dds_extracted_text = ""
        dds_document_html = ""
        xml_structured_dds: Optional[Dict[str, Any]] = None
        embedded_images: List[Dict[str, Any]] = []
        dds_source = "none"
        dds_doc_name = ""
        sp_docx_meta: Dict[str, Any] = {}

        # 3.1. Prioridade 1: Documento .docx Vivo no SharePoint Online (via Microsoft Graph API)
        has_own_sp_link = any("sharepoint.com" in (l.get("url") or "").lower() for l in dds_links)
        if has_own_sp_link:
            try:
                sp_fetch = sp_mgr.fetch_dds_from_sharepoint_links(dds_links, force_refresh=force_refresh)
                if sp_fetch.get("docx_bytes"):
                    parsed_sp = extrair_documento_docx_completo(sp_fetch["docx_bytes"])
                    if parsed_sp.get("text"):
                        dds_extracted_text = parsed_sp["text"]
                        dds_document_html = parsed_sp.get("document_html") or ""
                        xml_structured_dds = parsed_sp.get("structured_dds")
                        embedded_images.extend(parsed_sp.get("embedded_images") or [])
                        dds_source = "sharepoint_live"
                        sp_docx_meta = sp_fetch.get("docx_meta") or {}
                        dds_doc_name = sp_docx_meta.get("filename") or "DDS SharePoint Online.docx"
                for f_img in sp_fetch.get("folder_images") or []:
                    if not any(i.get("name") == f_img.get("name") for i in images_list):
                        images_list.append(f_img)
                for f_att in sp_fetch.get("folder_files") or []:
                    if not any(a.get("name") == f_att.get("name") for a in files_list):
                        files_list.append(f_att)
            except Exception as ex_sp:
                logger.warning("Aviso na sincronizacao SharePoint do ticket %s: %s", clean, ex_sp)

        # 3.2. Prioridade 2: Documento .docx ou texto colado importado manualmente pelo usuario para este ticket
        if dds_source == "none":
            manual_loaded = sp_mgr.load_manual_docx(clean)
            if manual_loaded:
                m_bytes, m_meta = manual_loaded
                parsed_m = extrair_documento_docx_completo(m_bytes)
                if parsed_m.get("text"):
                    dds_extracted_text = parsed_m["text"]
                    dds_document_html = parsed_m.get("document_html") or ""
                    xml_structured_dds = parsed_m.get("structured_dds")
                    embedded_images.extend(parsed_m.get("embedded_images") or [])
                    dds_source = "manual_docx"
                    dds_doc_name = m_meta.get("filename") or f"DDS-{clean}.docx"
            else:
                pasted_loaded = sp_mgr.load_pasted_text(clean)
                if pasted_loaded:
                    dds_extracted_text = pasted_loaded
                    dds_source = "pasted_text"
                    dds_doc_name = f"DDS Colada ({clean})"

        # 3.3. Prioridade 3: Anexo .docx salvo diretamente no Jira
        docx_attachments = [a for a in f.get("attachment", []) or [] if (a.get("filename") or "").lower().endswith((".docx", ".doc"))]
        docx_dds = [a for a in docx_attachments if "dds" in (a.get("filename") or "").lower()]
        target_att = docx_dds[0] if docx_dds else (docx_attachments[0] if docx_attachments else None)

        if dds_source == "none" and target_att and target_att.get("content"):
            try:
                import requests

                email = self.config.get_clean_email()
                token = self.config.get_clean_token()
                r = requests.get(target_att["content"], auth=(email, token), timeout=15)
                if r.status_code == 200:
                    parsed_att = extrair_documento_docx_completo(r.content)
                    if parsed_att.get("text"):
                        dds_extracted_text = parsed_att["text"]
                        dds_document_html = parsed_att.get("document_html") or ""
                        xml_structured_dds = parsed_att.get("structured_dds")
                        embedded_images.extend(parsed_att.get("embedded_images") or [])
                        dds_source = "docx_attachment"
                        dds_doc_name = target_att.get("filename") or "DDS.docx"
            except Exception as e:
                logger.warning("Erro ao baixar e extrair anexo docx do ticket %s: %s", clean, e)

        # 3.4. Prioridade 4: Cache textual local SQLite (MCP Reader) caso mais completo que rascunho vazio
        if dds_source not in ("sharepoint_live", "manual_docx"):
            local_cached = obter_dds_cache_local(clean)
            if not local_cached and dds_links:
                for l in dds_links:
                    local_cached = obter_dds_cache_local(l.get("url", ""))
                    if local_cached:
                        break
            if local_cached and (not dds_extracted_text or len(local_cached) > len(dds_extracted_text) + 200):
                dds_extracted_text = local_cached
                xml_structured_dds = None
                dds_source = "local_cache"
                dds_doc_name = "DDS do SharePoint (Cache Local)"

        # 3.5. Prioridade 5: Descricao nativa do Jira
        if not dds_extracted_text and desc_text:
            dds_extracted_text = desc_text
            dds_source = "jira_description"
            dds_doc_name = "Requisitos do Jira"

        # 3.6. Heranca automatica de DDS a partir do Ticket Pai quando o chamado for uma subtarefa
        parent_details: Optional[Dict[str, Any]] = None
        if not is_parent_call and parent_key and dds_source in ("none", "jira_description"):
            try:
                parent_details = self.get_ticket_dds_details(parent_key, is_parent_call=True, force_refresh=force_refresh)
                if parent_details and not parent_details.get("error"):
                    p_text = parent_details.get("dds_extracted_text") or ""
                    p_source = parent_details.get("dds_source") or ""
                    p_struct = parent_details.get("structured_dds") or {}

                    if (
                        p_source in ("sharepoint_live", "manual_docx", "docx_attachment", "local_cache")
                        or p_struct.get("has_structured_data")
                        or parent_details.get("dds_links")
                    ):
                        dds_extracted_text = p_text
                        dds_document_html = parent_details.get("dds_document_html") or dds_document_html
                        if p_struct and p_struct.get("has_structured_data"):
                            xml_structured_dds = p_struct
                        dds_source = f"parent_{p_source}" if p_source else "parent_dds"
                        p_doc = parent_details.get("dds_doc_name") or "DDS.docx"
                        dds_doc_name = f"{p_doc} (Herdada do Pai {parent_key})"
                        dds_inherited_from_parent = True
                        p_sp_status = parent_details.get("sharepoint_status") or {}
                        if p_sp_status.get("docx_meta") and not sp_docx_meta:
                            sp_docx_meta = p_sp_status["docx_meta"]

                        for pl in parent_details.get("dds_links", []):
                            if pl.get("url") and pl["url"] not in seen_urls:
                                dds_links.append(pl)
                                seen_urls.add(pl["url"])

                        for p_img in parent_details.get("images", []):
                            p_img_id = p_img.get("id") or ""
                            if not any((i.get("id") == p_img_id and p_img_id) or (i.get("name") == p_img.get("name") and not p_img.get("is_embedded")) for i in images_list):
                                p_img_copy = dict(p_img)
                                orig_author = p_img_copy.get("author") or "DDS"
                                p_img_copy["author"] = f"Pai {parent_key} • {orig_author}"
                                images_list.append(p_img_copy)

                        for p_att in parent_details.get("attachments", []):
                            if not any(a.get("name") == p_att.get("name") for a in files_list):
                                files_list.append(p_att)
            except Exception as ex:
                logger.warning("Erro ao herdar DDS do ticket pai %s: %s", parent_key, ex)

        # Adiciona imagens embutidas do DOCX proprio (com identificacao da secao exata e sem logotipo do cabecalho)
        for idx, emb in enumerate(embedded_images):
            emb_id = emb.get("id") or f"docx-emb-{idx + 1}"
            sec_name = emb.get("section") or "Documento DDS"
            if not any(i.get("id") == emb_id for i in images_list):
                images_list.append({
                    "id": emb_id,
                    "name": emb.get("filename") or f"evidencia_dds_{idx + 1}.png",
                    "size": emb.get("size") or 0,
                    "url": emb.get("data_url"),
                    "proxy_url": emb.get("data_url"),
                    "thumbnail_url": emb.get("data_url"),
                    "created": "",
                    "author": f"DDS • {sec_name}",
                    "section": sec_name,
                    "is_embedded": True,
                })

        # 4. Estruturacao Fiel da DDS (Sem qualquer injecao de textos hardcoded ou falsos!)
        regex_structured = estruturar_conteudo_dds(dds_extracted_text)
        if xml_structured_dds and xml_structured_dds.get("has_structured_data"):
            structured_dds = xml_structured_dds
            if not structured_dds.get("solicitacao") and regex_structured.get("solicitacao"):
                structured_dds["solicitacao"] = regex_structured["solicitacao"]
            if structured_dds.get("tipo") in ("", "NÃO DEFINIDO") and regex_structured.get("tipo") not in ("", "NÃO DEFINIDO"):
                structured_dds["tipo"] = regex_structured["tipo"]
        else:
            structured_dds = regex_structured

        # 5. Extracao de Metadados do Movidesk
        summary = f.get("summary") or "Sem título"
        movidesk_num = ""
        m_match = re.search(r"(?:ticket|movidesk)[\s#:-]*(\d{5,7})", f"{summary} {desc_text}", re.I)
        if m_match:
            movidesk_num = m_match.group(1)

        movidesk_info = {
            "ticket": structured_dds.get("solicitacao") or movidesk_num,
            "solicitante": structured_dds.get("solicitante") or "",
            "empresa": structured_dds.get("empresa") or "",
            "aberto_por": reporter,
        }

        combined_text = f"{summary}\n{desc_text}"
        if dds_extracted_text:
            combined_text += f"\n{dds_extracted_text[:3000]}"
        for c in comments_timeline:
            combined_text += f"\n{c['raw_body']}"

        if not movidesk_info["solicitante"]:
            sol_match = re.search(r"(?:Nome do solicitante(?:\s*/\s*Setor)?|Solicitante)[\s:]*([^\n\r,;]+)", combined_text, re.I)
            if sol_match:
                cand_sol = _clean_dds_placeholder(sol_match.group(1).strip())
                if cand_sol and not cand_sol.lower().startswith(("código", "codigo", "data", "empresa")):
                    movidesk_info["solicitante"] = cand_sol
            if not movidesk_info["solicitante"] and comments_timeline:
                for c in comments_timeline:
                    if c.get("movidesk_sender"):
                        movidesk_info["solicitante"] = c["movidesk_sender"]
                        break

        if not movidesk_info["empresa"]:
            emp_match = re.search(r"(?:Código\s*/\s*Empresa Cliente|Empresa Cliente|Empresa|Cliente)[\s:]*([^\n\r;]+)", combined_text, re.I)
            if emp_match:
                cand_emp = _clean_dds_placeholder(emp_match.group(1).strip())
                if cand_emp and not cand_emp.lower().startswith(("nome", "data", "preenchido")):
                    movidesk_info["empresa"] = cand_emp
            else:
                ola_match = re.search(r"Ol[áa]\s+[^,\n]+,\s*([^,\n]+),\s*Tudo bem", combined_text, re.I)
                if ola_match:
                    movidesk_info["empresa"] = ola_match.group(1).strip()

        if parent_details and not parent_details.get("error"):
            p_mov = parent_details.get("movidesk_info") or {}
            if not movidesk_info.get("solicitante") and p_mov.get("solicitante"):
                movidesk_info["solicitante"] = p_mov["solicitante"]
            if not movidesk_info.get("empresa") and p_mov.get("empresa"):
                movidesk_info["empresa"] = p_mov["empresa"]
            if not movidesk_info.get("ticket") and p_mov.get("ticket"):
                movidesk_info["ticket"] = p_mov["ticket"]
            if not movidesk_num and p_mov.get("ticket"):
                movidesk_num = p_mov["ticket"]

        aberto_match = re.search(r"(?:Aberto por|Criado por)[\s:]*([^\n\r,;]+)", combined_text, re.I)
        if aberto_match:
            movidesk_info["aberto_por"] = aberto_match.group(1).strip()

        has_sharepoint_dds = any("sharepoint.com" in (l.get("url") or "").lower() for l in dds_links)
        primary_sp_link = dds_links[0] if dds_links else None

        sp_pub_status = sp_mgr.get_status()
        synced_live = dds_source in ("sharepoint_live", "parent_sharepoint_live")
        is_manual_override = dds_source in ("manual_docx", "parent_manual_docx")
        sharepoint_status = {
            "has_sharepoint_link": has_sharepoint_dds,
            "connected": bool(sp_pub_status.get("connected")),
            "account": sp_pub_status.get("account") or "",
            "synced_live": synced_live,
            "needs_auth_notice": bool(has_sharepoint_dds and not sp_pub_status.get("connected") and not is_manual_override),
            "docx_meta": sp_docx_meta,
            "auth_in_progress": bool(sp_pub_status.get("auth_in_progress")),
            "pending_device_flow": sp_pub_status.get("pending_device_flow"),
            "last_error": sp_pub_status.get("last_error") or "",
        }

        return {
            "key": clean,
            "summary": summary,
            "status": st_name,
            "status_category": st_cat,
            "issue_type": it_name,
            "priority": pr_name,
            "assignee": assignee,
            "reporter": reporter,
            "created": f.get("created") or "",
            "updated": f.get("updated") or "",
            "description": desc_text or "Sem descrição cadastrada.",
            "dds_links": dds_links,
            "has_sharepoint_dds": has_sharepoint_dds,
            "primary_sharepoint_link": primary_sp_link,
            "sharepoint_status": sharepoint_status,
            "attachments": files_list,
            "images": images_list,
            "comments_timeline": comments_timeline,
            "movidesk_info": movidesk_info,
            "dds_source": dds_source,
            "dds_doc_name": dds_doc_name,
            "dds_extracted_text": dds_extracted_text,
            "dds_document_html": dds_document_html,
            "structured_dds": structured_dds,
            "movidesk_ticket": movidesk_info.get("ticket") or movidesk_num,
            "parent_key": parent_key,
            "parent_summary": parent_summary or (parent_details.get("summary", "") if parent_details else ""),
            "dds_inherited_from_parent": dds_inherited_from_parent,
            "url": f"{base_url}/browse/{clean}",
        }

    def submit_worklog(
        self,
        issue_key: str,
        time_spent_seconds: int,
        started_iso: str,
        comment: Optional[str] = None,
        no_comment: bool = False,
    ) -> Dict[str, Any]:
        """
        Envia o lancamento de horas para o endpoint do Jira:
        POST /rest/api/2/issue/{issue_key}/worklog
        """
        if time_spent_seconds <= 0:
            logger.warning("Tempo de trabalho zerado ou negativo. Envio ignorado.")
            return {"status": "skipped", "reason": "zero_time"}

        base_url = self.config.get_clean_base_url()
        target_key = issue_key

        jira_started = format_iso_for_jira(started_iso)

        payload: Dict[str, Any] = {
            "timeSpentSeconds": time_spent_seconds,
            "started": jira_started,
        }

        if not no_comment and comment != "__EMPTY__":
            payload["comment"] = comment or self.config.default_comment

        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = self._get_auth_headers()

        def _do_post(key_to_use: str) -> Dict[str, Any]:
            endpoint = f"{base_url}/rest/api/2/issue/{key_to_use}/worklog"
            req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                worklog_id = resp_data.get("id")
                logger.info(f"Worklog registrado com sucesso no ticket {key_to_use}! ID: {worklog_id}")
                return {"status": "success", "worklog_id": worklog_id, "data": resp_data}

        try:
            return _do_post(target_key)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Tenta resolver o ticket caso tenha sido informado texto/numero interno
                resolved = self.resolve_issue_key(target_key)
                if resolved and resolved != target_key:
                    logger.info(f"Ticket 404 '{target_key}' resolvido para '{resolved}'. Reenviando worklog...")
                    try:
                        return _do_post(resolved)
                    except Exception as e2:
                        logger.error(f"Erro na tentativa com ticket resolvido {resolved}: {e2}")

            err_msg = f"HTTP {e.code}: {e.reason}"
            try:
                err_body = e.read().decode("utf-8")
                err_msg += f" - {err_body}"
            except Exception:
                pass
            logger.error(f"Erro ao enviar worklog ao Jira: {err_msg}")
            raise RuntimeError(err_msg)

        except urllib.error.URLError as e:
            err_msg = f"Erro de conexao com Jira: {e.reason}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        except Exception as e:
            err_msg = f"Erro inesperado no envio de worklog: {e}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

    def delete_worklog(self, issue_key: str, worklog_id: str) -> bool:
        """Exclui um worklog especifico de uma tarefa no Jira."""
        base_url = self.config.get_clean_base_url()
        endpoint = f"{base_url}/rest/api/2/issue/{issue_key}/worklog/{worklog_id}"
        headers = self._get_auth_headers()
        req = urllib.request.Request(endpoint, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                logger.info(f"Worklog {worklog_id} excluido de {issue_key} com sucesso.")
                return response.status in [200, 204]
        except Exception as e:
            logger.error(f"Erro ao excluir worklog {worklog_id} de {issue_key}: {e}")
            return False

    def get_issue_worklogs(self, issue_key: str) -> List[Dict[str, Any]]:
        """Busca todos os worklogs de uma tarefa especifica no Jira."""
        base_url = self.config.get_clean_base_url()
        clean = issue_key.strip().upper()
        endpoint = f"{base_url}/rest/api/2/issue/{clean}/worklog"
        headers = self._get_auth_headers()
        try:
            req = urllib.request.Request(endpoint, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("worklogs", [])
        except Exception as e:
            logger.warning(f"Erro ao buscar worklogs de {clean}: {e}")
            return []

    def get_formatted_issue_worklogs(self, issue_key: str) -> List[Dict[str, Any]]:
        """Busca e formata os worklogs de um ticket especifico no padrao unificado do painel."""
        clean = issue_key.strip().upper()
        if not clean:
            return []
        summary = self.get_issue_summary(clean)
        raw_worklogs = self.get_issue_worklogs(clean)
        results: List[Dict[str, Any]] = []
        for w in raw_worklogs:
            started_str = w.get("started", "")
            results.append({
                "id": str(w.get("id")),
                "issue_key": clean,
                "summary": summary,
                "date": started_str[:10] if len(started_str) >= 10 else "",
                "started": started_str,
                "time_spent": w.get("timeSpent", ""),
                "time_spent_seconds": w.get("timeSpentSeconds", 0),
                "comment": w.get("comment", "") or "",
                "author": w.get("author", {}).get("displayName", ""),
            })
        results.sort(key=lambda x: x.get("started", ""), reverse=True)
        return results

    def migrate_worklog(
        self,
        source_issue: str,
        target_issue: str,
        worklog_id: str,
        override_seconds: Optional[int] = None,
        override_started_iso: Optional[str] = None,
        override_comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Migra um worklog de uma tarefa de origem para uma tarefa de destino no Jira:
        1. Consulta o worklog na tarefa de origem para capturar started, timeSpentSeconds e comment.
        2. Aplica eventuais substituicoes informadas pelo usuario (tempo, inicio, comentario).
        3. Cria o worklog na tarefa de destino.
        4. Se criado com sucesso, exclui o worklog original da tarefa de origem.
        """
        base_url = self.config.get_clean_base_url()
        src_clean = source_issue.strip().upper()
        tgt_clean = target_issue.strip().upper()

        if src_clean == tgt_clean:
            return {"success": False, "message": "O ticket de origem e destino sao identicos."}

        # 1. Obter detalhes do worklog na origem
        endpoint_get = f"{base_url}/rest/api/2/issue/{src_clean}/worklog/{worklog_id}"
        headers = self._get_auth_headers()
        try:
            req_get = urllib.request.Request(endpoint_get, headers=headers, method="GET")
            with urllib.request.urlopen(req_get, timeout=12) as resp:
                wl_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"success": False, "message": f"Falha ao consultar worklog {worklog_id} em {src_clean}: {e}"}

        time_spent_seconds = override_seconds if (override_seconds is not None and override_seconds > 0) else wl_data.get("timeSpentSeconds", 0)
        started_iso = override_started_iso if override_started_iso else wl_data.get("started", "")
        comment = override_comment if override_comment is not None else wl_data.get("comment", "")

        if time_spent_seconds <= 0:
            return {"success": False, "message": "Worklog possui duracao zerada ou invalida."}

        # 2. Criar no destino
        try:
            submit_res = self.submit_worklog(
                issue_key=tgt_clean,
                time_spent_seconds=time_spent_seconds,
                started_iso=started_iso,
                comment=comment,
                no_comment=(not comment),
            )
            new_id = submit_res.get("worklog_id")
        except Exception as e:
            return {"success": False, "message": f"Falha ao criar worklog em {tgt_clean}: {e}"}

        # 3. Excluir na origem
        deleted = self.delete_worklog(src_clean, worklog_id)
        if not deleted:
            return {
                "success": True,
                "warning": True,
                "new_worklog_id": new_id,
                "message": f"Worklog criado em {tgt_clean} (ID: {new_id}), mas a exclusao na origem {src_clean} falhou."
            }

        return {
            "success": True,
            "new_worklog_id": new_id,
            "message": f"Worklog {worklog_id} migrado com sucesso de {src_clean} para {tgt_clean} (Novo ID: {new_id})."
        }

    def flush_queue(self) -> int:
        """
        Tenta enviar todos os itens pendentes na fila offline.
        Retorna o numero de itens sincronizados com sucesso.
        """
        queue = self.state_manager.load_queue()
        if not queue:
            return 0

        logger.info(f"Processando fila de contingencia ({len(queue)} itens pendentes)...")
        success_count = 0

        for item in list(queue):
            try:
                self.submit_worklog(
                    issue_key=item.issue_key,
                    time_spent_seconds=item.time_spent_seconds,
                    started_iso=item.started_iso,
                    comment=item.comment,
                )
                self.state_manager.remove_from_queue(item.id)
                success_count += 1
                logger.info(f"Item {item.id} sincronizado e removido da fila.")
            except Exception as e:
                item.retry_count += 1
                item.last_error = str(e)
                logger.warning(f"Tentativa {item.retry_count} falhou para item {item.id}: {e}")

        remaining = [q for q in queue if q.id in [x.id for x in self.state_manager.load_queue()]]
        self.state_manager.save_queue(remaining)
        return success_count

    def update_worklog_full(
        self,
        issue_key: str,
        worklog_id: str,
        time_spent_seconds: Optional[int] = None,
        started_iso: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Atualiza de forma unificada comentario, duracao (timeSpentSeconds) e/ou horario de inicio (started)
        de um worklog existente via PUT /rest/api/2/issue/{issue_key}/worklog/{worklog_id}.
        """
        base_url = self.config.get_clean_base_url()
        clean_key = issue_key.strip().upper()
        endpoint = f"{base_url}/rest/api/2/issue/{clean_key}/worklog/{worklog_id}"
        headers = self._get_auth_headers()

        payload: Dict[str, Any] = {}
        if time_spent_seconds is not None and int(time_spent_seconds) > 0:
            payload["timeSpentSeconds"] = int(time_spent_seconds)
        if started_iso:
            payload["started"] = format_iso_for_jira(started_iso)
        if comment is not None:
            payload["comment"] = comment

        if not payload:
            return {"success": False, "message": "Nenhum campo informado para atualizacao."}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="PUT")
            with urllib.request.urlopen(req, timeout=12) as response:
                resp_data = {}
                try:
                    raw_bytes = response.read()
                    if isinstance(raw_bytes, (bytes, bytearray)):
                        resp_raw = raw_bytes.decode("utf-8")
                        resp_data = json.loads(resp_raw) if resp_raw else {}
                except Exception:
                    resp_data = {}
                logger.info(f"Worklog {worklog_id} em {clean_key} atualizado com sucesso (campos: {list(payload.keys())}).")
                return {
                    "success": response.status in [200, 204],
                    "message": f"Worklog {worklog_id} ({clean_key}) atualizado com sucesso.",
                    "data": resp_data,
                }
        except Exception as e:
            logger.error(f"Erro ao atualizar worklog {worklog_id} em {clean_key}: {e}")
            return {"success": False, "message": f"Falha ao atualizar worklog no Jira: {e}"}

    def update_worklog_comment(self, issue_key: str, worklog_id: str, new_comment: str) -> bool:
        """
        Atualiza o comentario/descricao de um worklog existente via PUT:
        PUT /rest/api/2/issue/{issue_key}/worklog/{worklog_id}
        """
        res = self.update_worklog_full(issue_key=issue_key, worklog_id=worklog_id, comment=new_comment)
        return bool(res.get("success"))

    def update_worklog_time(self, issue_key: str, worklog_id: str, new_seconds: int) -> bool:
        """
        Atualiza a duracao em segundos de um worklog existente via PUT:
        PUT /rest/api/2/issue/{issue_key}/worklog/{worklog_id}
        """
        if new_seconds <= 0:
            logger.warning("Tempo em segundos zerado ou negativo.")
            return False
        res = self.update_worklog_full(issue_key=issue_key, worklog_id=worklog_id, time_spent_seconds=new_seconds)
        return bool(res.get("success"))

    def get_user_recent_worklogs(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Busca todos os worklogs lancados pelo usuario logado nos ultimos N dias.
        Retorna lista de dicionarios ordenada por data decrescente.
        """
        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()

        # 1. Obter accountId do usuario logado
        my_account_id = None
        try:
            myself_url = f"{base_url}/rest/api/2/myself"
            req = urllib.request.Request(myself_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                my_data = json.loads(resp.read().decode("utf-8"))
                my_account_id = my_data.get("accountId")
        except Exception as e:
            logger.warning(f"Nao foi possivel obter perfil do usuario: {e}")

        # 2. Buscar chamados onde o usuario registrou horas nos ultimos N dias
        jql = f"worklogAuthor = currentUser() AND worklogDate >= -{days}d"
        search_url = f"{base_url}/rest/api/2/search/jql?jql={urllib.parse.quote(jql)}&maxResults=50&fields=key,summary"

        issues_found = []
        try:
            req = urllib.request.Request(search_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                issues_found = data.get("issues", [])
        except Exception as e:
            logger.error(f"Erro ao buscar chamados via JQL: {e}")
            return []

        # 3. Para cada chamado, extrair os worklogs do usuario no periodo
        cutoff_date = (datetime.now() - timedelta(days=days)).date()
        results: List[Dict[str, Any]] = []

        for issue in issues_found:
            key = issue.get("key", "")
            summary = issue.get("fields", {}).get("summary", "")
            worklog_url = f"{base_url}/rest/api/2/issue/{key}/worklog"

            try:
                w_req = urllib.request.Request(worklog_url, headers=headers, method="GET")
                with urllib.request.urlopen(w_req, timeout=10) as w_resp:
                    w_data = json.loads(w_resp.read().decode("utf-8"))
                    worklogs = w_data.get("worklogs", [])

                    for w in worklogs:
                        started_str = w.get("started", "")
                        if not started_str:
                            continue

                        # Validar se o autor eh o usuario logado
                        author_acc = w.get("author", {}).get("accountId")
                        if my_account_id and author_acc != my_account_id:
                            continue

                        # Validar se esta dentro do periodo de dias
                        try:
                            w_date = datetime.fromisoformat(started_str[:10]).date()
                            if w_date < cutoff_date:
                                continue
                        except Exception:
                            pass

                        results.append({
                            "id": str(w.get("id")),
                            "issue_key": key,
                            "summary": summary,
                            "date": started_str[:10],
                            "started": started_str,
                            "time_spent": w.get("timeSpent", ""),
                            "time_spent_seconds": w.get("timeSpentSeconds", 0),
                            "comment": w.get("comment", "") or "",
                        })
            except Exception as e:
                logger.warning(f"Erro ao obter worklogs de {key}: {e}")

        # Ordena do mais recente para o mais antigo
        results.sort(key=lambda x: x.get("started", ""), reverse=True)
        return results

    def get_user_worklogs_by_date_range(self, start_date_str: str, end_date_str: str) -> List[Dict[str, Any]]:
        """
        Busca todos os worklogs lancados pelo usuario logado dentro de um intervalo de datas especifico
        (start_date_str ate end_date_str no formato YYYY-MM-DD).
        """
        import urllib.parse

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()
        s_clean = (start_date_str or date.today().isoformat())[:10]
        e_clean = (end_date_str or date.today().isoformat())[:10]

        my_account_id = None
        try:
            myself_url = f"{base_url}/rest/api/2/myself"
            req = urllib.request.Request(myself_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                my_data = json.loads(resp.read().decode("utf-8"))
                my_account_id = my_data.get("accountId")
        except Exception as e:
            logger.warning(f"Nao foi possivel obter perfil do usuario: {e}")

        jql = f'worklogAuthor = currentUser() AND worklogDate >= "{s_clean}" AND worklogDate <= "{e_clean}"'
        search_url = f"{base_url}/rest/api/2/search/jql?jql={urllib.parse.quote(jql)}&maxResults=60&fields=key,summary"

        issues_found = []
        try:
            req = urllib.request.Request(search_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                issues_found = data.get("issues", [])
        except Exception as e:
            logger.warning(f"Erro ao buscar chamados por intervalo de datas via JQL: {e}")
            return []

        results: List[Dict[str, Any]] = []
        for issue in issues_found:
            key = issue.get("key", "")
            summary = issue.get("fields", {}).get("summary", "")
            worklog_url = f"{base_url}/rest/api/2/issue/{key}/worklog"

            try:
                w_req = urllib.request.Request(worklog_url, headers=headers, method="GET")
                with urllib.request.urlopen(w_req, timeout=10) as w_resp:
                    w_data = json.loads(w_resp.read().decode("utf-8"))
                    worklogs = w_data.get("worklogs", [])

                    for w in worklogs:
                        started_str = w.get("started", "")
                        if not started_str:
                            continue
                        author_acc = w.get("author", {}).get("accountId")
                        if my_account_id and author_acc != my_account_id:
                            continue

                        w_date_str = started_str[:10]
                        if not (s_clean <= w_date_str <= e_clean):
                            continue

                        results.append({
                            "id": str(w.get("id")),
                            "issue_key": key,
                            "summary": summary,
                            "date": w_date_str,
                            "started": started_str,
                            "time_spent": w.get("timeSpent", ""),
                            "time_spent_seconds": w.get("timeSpentSeconds", 0),
                            "comment": w.get("comment", "") or "",
                        })
            except Exception as e:
                logger.warning(f"Erro ao obter worklogs de {key}: {e}")

        results.sort(key=lambda x: x.get("started", ""), reverse=True)
        return results


    def get_user_analytics_data(
        self,
        days: int = 90,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coleta os dados necessarios para o Dashboard Analitico: chamados em que o usuario lancou horas
        no periodo solicitado (com tipo, status e historico de transicoes) e os worklogs do proprio usuario.

        Aceita start_date e end_date (formato 'YYYY-MM-DD') ou days (padrao 90).
        Retorna {"issues": {chave: metadados}, "worklogs": [..]}. Levanta excecao se a consulta principal falhar.
        """
        import urllib.parse
        from concurrent.futures import ThreadPoolExecutor

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()

        if start_date and end_date:
            s_str = str(start_date)[:10]
            e_str = str(end_date)[:10]
            if s_str > e_str:
                s_str, e_str = e_str, s_str
            cutoff_start = s_str
            cutoff_end = e_str
            if cutoff_start == cutoff_end:
                jql = f'worklogAuthor = currentUser() AND worklogDate = "{cutoff_start}"'
            else:
                jql = f'worklogAuthor = currentUser() AND worklogDate >= "{cutoff_start}" AND worklogDate <= "{cutoff_end}"'
        else:
            days = max(1, int(days))
            cutoff_start = (datetime.now() - timedelta(days=days)).date().isoformat()
            cutoff_end = datetime.now().date().isoformat()
            jql = f"worklogAuthor = currentUser() AND worklogDate >= -{days}d"

        me: Dict[str, Any] = {}
        try:
            req = urllib.request.Request(f"{base_url}/rest/api/2/myself", headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                me = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Nao foi possivel obter perfil do usuario para analise: {e}")

        my_ids = {str(v) for v in (me.get("accountId"), me.get("name"), me.get("key")) if v}

        def is_mine(author: Optional[Dict[str, Any]]) -> bool:
            if not my_ids:
                return True
            author = author or {}
            return any(str(author.get(k)) in my_ids for k in ("accountId", "name", "key") if author.get(k))

        fields = "key,summary,issuetype,status,resolution,resolutiondate,assignee,created"

        def fetch_issues(with_changelog: bool) -> List[Dict[str, Any]]:
            found: List[Dict[str, Any]] = []
            page_token = ""
            for _ in range(6):
                url = (
                    f"{base_url}/rest/api/2/search/jql?jql={urllib.parse.quote(jql)}"
                    f"&maxResults=100&fields={fields}"
                )
                if with_changelog:
                    url += "&expand=changelog"
                if page_token:
                    url += f"&nextPageToken={urllib.parse.quote(page_token)}"
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                found.extend(data.get("issues", []))
                page_token = data.get("nextPageToken") or ""
                if not page_token or data.get("isLast"):
                    break
            return found

        try:
            raw_issues = fetch_issues(with_changelog=True)
        except urllib.error.HTTPError as e:
            if e.code in (400, 422):
                raw_issues = fetch_issues(with_changelog=False)
            else:
                raise

        issues_meta: Dict[str, Dict[str, Any]] = {}
        for issue in raw_issues:
            key = str(issue.get("key") or "").upper()
            if not key:
                continue
            f = issue.get("fields", {}) or {}
            status = f.get("status") or {}
            status_name = status.get("name") or ""
            category = ((status.get("statusCategory") or {}).get("key")) or ""

            completed_date = ""
            completed_by_me = False
            if category == "done":
                histories = ((issue.get("changelog") or {}).get("histories")) or []
                last_hist = None
                for hist in sorted(histories, key=lambda h: h.get("created", "")):
                    for item in hist.get("items", []) or []:
                        if item.get("field") == "status" and item.get("toString") == status_name:
                            last_hist = hist
                if last_hist:
                    completed_date = str(last_hist.get("created") or "")[:10]
                    completed_by_me = is_mine(last_hist.get("author"))
                else:
                    completed_date = str(f.get("resolutiondate") or "")[:10]
                    assignee = f.get("assignee")
                    completed_by_me = bool(assignee) and is_mine(assignee)

            issues_meta[key] = {
                "summary": f.get("summary") or "",
                "issue_type": (f.get("issuetype") or {}).get("name") or "Sem tipo",
                "status": status_name,
                "status_category": category,
                "completed_date": completed_date,
                "completed_by_me": completed_by_me,
            }

        def fetch_worklogs(key: str) -> List[Dict[str, Any]]:
            rows: List[Dict[str, Any]] = []
            try:
                w_req = urllib.request.Request(
                    f"{base_url}/rest/api/2/issue/{key}/worklog", headers=headers, method="GET"
                )
                with urllib.request.urlopen(w_req, timeout=15) as w_resp:
                    w_data = json.loads(w_resp.read().decode("utf-8"))
                for w in w_data.get("worklogs", []):
                    started = w.get("started", "")
                    if not started or not is_mine(w.get("author")):
                        continue
                    day_str = started[:10]
                    if not (cutoff_start <= day_str <= cutoff_end):
                        continue
                    rows.append({
                        "id": str(w.get("id")),
                        "issue_key": key,
                        "date": day_str,
                        "time_spent_seconds": int(w.get("timeSpentSeconds", 0) or 0),
                        "comment": w.get("comment", "") or "",
                    })
            except Exception as e:
                logger.warning(f"Erro ao obter worklogs de {key} para analise: {e}")
            return rows

        worklogs: List[Dict[str, Any]] = []
        keys = list(issues_meta.keys())
        if keys:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for chunk in pool.map(fetch_worklogs, keys):
                    worklogs.extend(chunk)

        return {"issues": issues_meta, "worklogs": worklogs}
