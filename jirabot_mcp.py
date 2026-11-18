"""Servidor MCP local para sugerir trocas de ticket e preparar acréscimos na DDS."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from http.client import HTTPException
import re
from typing import Any
from uuid import uuid4
from time import monotonic, sleep

from mcp.server.fastmcp import Context, FastMCP
from ticket_focus import local_focus_request
from notifier import open_dds_review_window


panel_port = 8765
session_id = uuid4().hex
client_name = ""


def report_connection(event, client_name="", tool=""):
    try:
        local_focus_request(
            "/api/ticket-focus/connection",
            {"id": session_id, "event": event, "name": client_name, "tool": tool},
            port=panel_port, timeout=2,
        )
    except (OSError, HTTPException, ValueError):
        pass


@asynccontextmanager
async def monitor_connection(_server):
    stop = asyncio.Event()

    async def heartbeat():
        while not stop.is_set():
            if client_name:
                await asyncio.to_thread(report_connection, "heartbeat", client_name)
            try:
                await asyncio.wait_for(stop.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        stop.set()
        await task
        if client_name:
            await asyncio.to_thread(report_connection, "closed", client_name)


def report_client(ctx: Context, tool: str = ""):
    global client_name
    params = ctx.session.client_params
    if params:
        client_name = params.clientInfo.name.strip()[:80]
    if client_name:
        report_connection("tool" if tool else "heartbeat", client_name, tool)


class JiraBotMCP(FastMCP):
    async def list_tools(self):
        await asyncio.to_thread(report_client, self.get_context())
        return await super().list_tools()


server = JiraBotMCP(
    "JiraBot",
    lifespan=monitor_connection,
    instructions=(
        "Quando o usuário iniciar ou mudar de tarefa, inclusive ao pedir resumo da DDS, sugira o ticket "
        "antes de continuar o trabalho. Use a chave informada ou já estabelecida na conversa. Se o usuário "
        "mudar de BI ou subtarefa sem informar a chave, use buscar_tickets com poucas palavras do título "
        "ou nome do BI, sem enviar a DDS, código ou a conversa. Escolha uma chave apenas se o contexto "
        "identificar claramente a tarefa. Em caso de ambiguidade, continue o trabalho e peça a chave. "
        "Use sugerir_ticket uma vez por mudança de tarefa. A decisão fica com o usuário no JiraBot. "
        "Quando o usuário pedir um lançamento na DDS, use preparar_acrescimo_dds. "
        "Inclua prints reais disponíveis em evidencias. Se faltarem comprovações, peça os arquivos ao usuário. "
        "Informe que a proposta está pendente e chame consultar_revisao_dds com o ID para aguardar a decisão. "
        "Em revisão parcial, envie somente a substituição e o identificador em revisao_anterior."
    ),
)


def request_panel(path: str, payload: dict[str, Any], *, timeout: int = 20) -> dict[str, Any]:
    try:
        status, result = local_focus_request(path, payload, port=panel_port, timeout=timeout)
        if status == 200:
            return result
        if status in (400, 403, 404, 409, 502):
            return {"status": "rejected", "message": result.get("error", "O painel recusou a solicitação.")}
    except (OSError, HTTPException, ValueError):
        pass
    return {"status": "unavailable", "message": "A integração não está disponível no painel local do JiraBot."}


@server.tool()
def consultar_worklogs(data_inicio: str, data_fim: str, ctx: Context, chave: str = "") -> dict[str, Any]:
    """Consulta seus lançamentos em datas AAAA-MM-DD, até 31 dias inclusive. A chave é um filtro opcional."""
    report_client(ctx, "consultar_worklogs")
    return request_panel("/api/worklogs/mcp-query", {"start": data_inicio, "end": data_fim, "key": chave}, timeout=90)


@server.tool()
def editar_worklog(chave: str, worklog_id: str, ctx: Context, duracao_segundos: int | None = None,
                   inicio_iso: str | None = None, descricao: str | None = None) -> dict[str, Any]:
    """Edita um lançamento seu após pedido explícito. Use o ID da consulta; omita campos a manter.

    Informe início em ISO 8601 com fuso (ex.: 2026-11-17T09:00:00-03:00).
    Descrição vazia limpa o campo. A edição mantém o ticket e não cria lançamento.
    """
    report_client(ctx, "editar_worklog")
    return request_panel("/api/worklogs/mcp-edit", {
        "key": chave, "id": worklog_id, "seconds": duracao_segundos, "started": inicio_iso, "comment": descricao,
    }, timeout=50)


@server.tool()
def buscar_tickets(contexto: str, ctx: Context) -> dict[str, Any]:
    """Busca tickets abertos da conta conectada por palavras do título da tarefa ou do BI."""
    report_client(ctx, "buscar_tickets")
    query = contexto.strip()
    if not 2 <= len(query) <= 120:
        return {"status": "invalid", "message": "Informe de 2 a 120 caracteres do título da tarefa."}
    return request_panel("/api/ticket-focus/search", {"context": query})


@server.tool()
def preparar_acrescimo_dds(chave: str, detalhamento: str, ctx: Context, recomendacoes: str = "",
                           revisao_anterior: str = "", evidencias: list[dict[str, str]] | None = None,
                           autor_nome: str = "", data_preenchimento: str = "",
                           tamanho_fonte: int = 11, negrito: bool = False,
                           linhas_formatadas: list[list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Prepara um acréscimo para revisão humana. Evidências PNG/JPEG usam nome e conteudo_base64.

    Use !evidencia-1!, !evidencia-2! etc. em linhas próprias para posicionar
    imagens na ordem enviada. Sem marcador, a imagem aparece ao fim da entrada.
    Formatação inline suportada em detalhamento: **negrito**, [14pt]/[12pt]/[9pt],
    [tam=N]...[/tam] (8 a 36), # Título (14pt negrito), ## Subtítulo (12pt negrito),
    e \\t ou [tab] no início da linha para recuo. Opcionalmente informe autor_nome,
    data_preenchimento (DD/MM/AAAA ou DD/MM/AAAA - HH:MM), tamanho_fonte, negrito ou linhas_formatadas.
    """
    report_client(ctx, "preparar_acrescimo_dds")
    payload: dict[str, Any] = {
        "key": chave.strip().upper(),
        "implementacao_texto": detalhamento,
        "recomendacoes": recomendacoes,
        "revisao_anterior": revisao_anterior,
        "evidencias": evidencias or [],
        "font_size": tamanho_fonte,
        "bold": negrito,
    }
    if autor_nome.strip():
        payload["autor_nome"] = autor_nome.strip()
    if data_preenchimento.strip():
        payload["data_preenchimento"] = data_preenchimento.strip()
    if linhas_formatadas is not None:
        payload["implementacao_runs"] = linhas_formatadas
        if not detalhamento.strip():
            payload["skip_plain_match"] = True
    try:
        status, result = local_focus_request(
            "/api/jira/dds/append-propose",
            payload,
            port=panel_port, timeout=90,
        )
    except (OSError, HTTPException, ValueError):
        return {"status": "unavailable", "message": "Não foi possível consultar o painel local do JiraBot."}
    if status != 200:
        return {"status": "rejected", "message": result.get("error", "O painel recusou a proposta.")}
    url = f"http://127.0.0.1:{panel_port}/dds/revisao#revisar-dds={result['review_id']}"
    reused = result.get("reused_review", False)
    opened = not reused and open_dds_review_window(url)
    message = ("A nova versão está disponível na janela de revisão existente." if reused else
               "Revise e confirme no JiraBot." if opened else "Abra o endereço da revisão para conferir a proposta.")
    return {"status": "pending_confirmation", "message": message, "review_url": url, "window_launched": opened,
            "review_id": result["review_id"], "approved_example": result.get("approved_example")}


@server.tool()
def consultar_revisao_dds(identificador: str, ctx: Context, aguardar_segundos: int = 90) -> dict[str, Any]:
    """Aguarda feedback ou confirmação humana por até 180 segundos e retorna status 'approved' com 'confirmed': True quando gravado na DDS oficial."""
    report_client(ctx, "consultar_revisao_dds")
    deadline = monotonic() + min(180, max(0, aguardar_segundos))
    payload = {"review_id": identificador.strip()}
    while True:
        result = request_panel("/api/jira/dds/append-feedback-status", payload)
        remaining = deadline - monotonic()
        if result.get("status") != "pending_confirmation" or remaining <= 0:
            return result
        sleep(min(1, remaining))


@server.tool()
def sugerir_ticket(chave: str, ctx: Context, motivo: str = "") -> dict[str, str]:
    """Envia uma sugestão de ticket para o usuário confirmar no JiraBot."""
    report_client(ctx, "sugerir_ticket")
    issue = chave.strip().upper()
    reason = motivo.strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9]*-\d+", issue) or len(issue) > 40 or len(reason) > 160:
        return {"status": "invalid", "message": "Informe uma chave Jira válida e um motivo de até 160 caracteres."}

    result = request_panel("/api/ticket-focus/suggest", {"issue": issue, "reason": reason})
    return {"status": result["status"], "message": result["message"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=panel_port, metavar="PORTA")
    panel_port = parser.parse_args().port
    if not 1 <= panel_port <= 65535:
        parser.error("A porta precisa estar entre 1 e 65535.")
    server.run(transport="stdio")
