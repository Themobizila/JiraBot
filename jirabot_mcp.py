"""Servidor MCP local para solicitar confirmação de troca de ticket."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from http.client import HTTPException
import re
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import Context, FastMCP
from ticket_focus import local_focus_request


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
        "Use sugerir_ticket uma vez por mudança de tarefa. A decisão fica com o usuário no JiraBot."
    ),
)


def request_panel(path: str, payload: dict[str, str]) -> dict[str, Any]:
    try:
        status, result = local_focus_request(path, payload, port=panel_port)
        if status == 200:
            return result
        if status in (400, 403):
            return {"status": "rejected", "message": result.get("error", "O painel recusou a solicitação.")}
    except (OSError, HTTPException, ValueError):
        pass
    return {"status": "unavailable", "message": "A integração não está disponível no painel local do JiraBot."}


@server.tool()
def buscar_tickets(contexto: str, ctx: Context) -> dict[str, Any]:
    """Busca tickets abertos da conta conectada por palavras do título da tarefa ou do BI."""
    report_client(ctx, "buscar_tickets")
    query = contexto.strip()
    if not 2 <= len(query) <= 120:
        return {"status": "invalid", "message": "Informe de 2 a 120 caracteres do título da tarefa."}
    return request_panel("/api/ticket-focus/search", {"context": query})


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
