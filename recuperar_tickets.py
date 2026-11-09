#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitario de diagnostico e recuperacao de tickets do JiraBot via Snapshots.
Permite listar as secoes salvas, inspecionar quais tickets
estavam gravados em cada momento e restaurar todos os tickets ou um ticket unitariamente.
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Garante que o diretorio do JiraBot esteja no PATH de imports
CUR_DIR = Path(__file__).resolve().parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))

try:
    from storage import StateManager
except ImportError as err:
    print(f"Erro ao carregar modulo de armazenamento: {err}")
    sys.exit(1)


def listar_pontos(date_str: Optional[str] = None):
    mgr = StateManager()
    snaps = mgr.list_snapshots(date_str=date_str)
    return snaps


def formatar_tabela(snaps):
    if not snaps:
        return "Nenhum ponto de restauracao encontrado."

    linhas = []
    linhas.append("=" * 88)
    linhas.append(f"{'#':<4} | {'HORA':<8} | {'DATA':<10} | {'TICKETS':<8} | {'TEMPO':<8} | {'MOTIVO'}")
    linhas.append("-" * 88)

    for i, s in enumerate(snaps):
        idx_str = f"[{i}]"
        hora = s.get("time_hm") or "--:--:--"
        data = s.get("date_str") or "----/--/--"
        qtd = f"{s.get('tickets_count', 0)} tkts"
        tempo = s.get("total_formatted") or "0m"
        motivo = s.get("reason_label") or s.get("reason") or "Snapshot"
        preview = s.get("tickets_preview") or ""
        
        info = f"{idx_str:<4} | {hora:<8} | {data:<10} | {qtd:<8} | {tempo:<8} | {motivo}"
        if preview and preview != "Nenhum ticket":
            info += f"\n       --> Tickets gravados: {preview}"
            
        tds = s.get("tickets_detail", [])
        if tds:
            for td in tds:
                comm_str = f" ({td['comment']})" if td.get("comment") else ""
                info += f"\n           * {td['issue_key']}: {td['formatted']} [{td['intervals_count']} intervalo(s)]{comm_str}"

        if s.get("reason") == "pre_restore":
            info += "\n       [DESTAQUE] Estado salvo imediatamente antes da ultima restauracao"
        elif s.get("reason") == "pre_restore_ticket":
            info += "\n       [DESTAQUE] Estado salvo antes de restauracao de chamado especifico"
        linhas.append(info)

    linhas.append("=" * 88)
    return "\n".join(linhas)


def restaurar_ponto_por_indice_ou_id(identificador: str, ticket_key: Optional[str] = None):
    mgr = StateManager()
    snaps = mgr.list_snapshots()
    
    target_id = None
    snap_escolhido = None
    if identificador.isdigit():
        idx = int(identificador)
        if 0 <= idx < len(snaps):
            target_id = snaps[idx]["id"]
            snap_escolhido = snaps[idx]
        else:
            print(f"Indice {idx} invalido. Total disponivel: {len(snaps)}.")
            return False
    else:
        target_id = identificador.strip()
        snap_escolhido = next((s for s in snaps if s["id"] == target_id), None)

    if not target_id:
        print("Ponto de restauracao nao especificado.")
        return False

    print(f"\nIniciando restauracao do ponto: {target_id}...")
    if snap_escolhido:
        print(f"- Data/Hora: {snap_escolhido.get('date_str')} {snap_escolhido.get('time_hm')}")
        print(f"- Motivo: {snap_escolhido.get('reason_label')}")
        print(f"- Tickets nesta secao: {snap_escolhido.get('tickets_preview')}")
        print(f"- Tempo Total: {snap_escolhido.get('total_formatted')}")
        if ticket_key:
            print(f"- Modo: Restauracao UNITARIA do ticket: {ticket_key}")
        else:
            print("- Modo: Restauracao COMPLETA de todos os tickets")

    res = mgr.restore_snapshot(target_id, ticket_key=ticket_key)
    if res.get("success"):
        print("\nSUCESSO: " + res.get("message", "Estado restaurado com sucesso!"))
        print("DICA: Atualize a pagina do JiraBot no navegador (F5) para ver os dados restaurados.")
        return True
    else:
        print("\nFALHA: " + res.get("error", "Nao foi possivel restaurar o estado."))
        return False


def restaurar_mais_recente_com_tickets(ticket_key: Optional[str] = None):
    mgr = StateManager()
    snaps = mgr.list_snapshots()
    candidato = None
    for s in snaps:
        if ticket_key:
            tds = [td["issue_key"].upper() for td in s.get("tickets_detail", [])]
            if ticket_key.upper() in tds:
                candidato = s
                break
        elif s.get("tickets_count", 0) > 0:
            candidato = s
            break
            
    if not candidato:
        if ticket_key:
            print(f"Nenhum snapshot encontrado que contenha o ticket {ticket_key}.")
        else:
            print("Nenhum snapshot encontrado que contenha tickets registrados.")
        return False

    print(f"Snapshot localizado: {candidato['id']} ({candidato['time_hm']})")
    return restaurar_ponto_por_indice_ou_id(candidato["id"], ticket_key=ticket_key)


def main():
    args = sys.argv[1:]

    ticket_arg = None
    if "--ticket" in args:
        t_idx = args.index("--ticket")
        if t_idx + 1 < len(args):
            ticket_arg = args[t_idx + 1].strip().upper()
            args = [a for i, a in enumerate(args) if i not in (t_idx, t_idx + 1)]

    if "--help" in args or "-h" in args:
        print("Uso do utilitario recuperar_tickets.py:")
        print("  python recuperar_tickets.py                     # Modo interativo (lista secoes e tickets)")
        print("  python recuperar_tickets.py --list              # Apenas lista os pontos disponiveis")
        print("  python recuperar_tickets.py --auto              # Restaura o snapshot mais recente com tickets")
        print("  python recuperar_tickets.py --auto --ticket ABC # Restaura unitariamente o ticket mais recente")
        print("  python recuperar_tickets.py <INDICE_OU_ID>      # Restaura completo o indice informado")
        print("  python recuperar_tickets.py <ID> --ticket ABC   # Restaura apenas o ticket ABC daquele ID")
        return

    if "--auto" in args or "--latest-tickets" in args:
        restaurar_mais_recente_com_tickets(ticket_key=ticket_arg)
        return

    if "--list" in args or "-l" in args:
        snaps = listar_pontos()
        print(formatar_tabela(snaps))
        return

    if len(args) == 1 and not args[0].startswith("-"):
        restaurar_ponto_por_indice_ou_id(args[0], ticket_key=ticket_arg)
        return

    # Modo interativo padrao
    snaps = listar_pontos()
    if not snaps:
        print("Nenhum ponto de restauracao encontrado em ~/.jirabot/state_history/.")
        return

    print("\n--- SECOES DE RESTAURACAO DISPONIVEIS (JIRABOT) ---")
    print(formatar_tabela(snaps))
    print("\nOpcoes:")
    print("- Digite o numero da secao (ex: 0, 1) para seleciona-la.")
    print("- Digite 'auto' para restaurar o snapshot mais recente que possui tickets.")
    print("- Pressione ENTER sem digitar nada para cancelar.")

    try:
        escolha = input("\nEscolha a secao para restaurar: ").strip()
        if not escolha:
            print("Operacao cancelada pelo usuario.")
            return

        if escolha.lower() == "auto":
            restaurar_mais_recente_com_tickets(ticket_key=ticket_arg)
            return

        if escolha.isdigit():
            idx = int(escolha)
            if 0 <= idx < len(snaps):
                snap_sel = snaps[idx]
                tds = snap_sel.get("tickets_detail", [])
                if len(tds) > 1 and not ticket_arg:
                    print(f"\nEsta secao possui {len(tds)} chamados registrados:")
                    for j, td in enumerate(tds):
                        print(f"  [{j + 1}] {td['issue_key']} ({td['formatted']}) - {td['intervals_count']} intervalo(s)")
                    print("  [T] Restaurar TODOS os tickets desta secao")
                    sub_esc = input("\nDeseja restaurar todos [T] ou um chamado especifico [1.." + str(len(tds)) + "]? ").strip().upper()
                    if sub_esc != "T" and sub_esc.isdigit():
                        s_idx = int(sub_esc) - 1
                        if 0 <= s_idx < len(tds):
                            ticket_arg = tds[s_idx]["issue_key"]

        restaurar_ponto_por_indice_ou_id(escolha, ticket_key=ticket_arg)
    except KeyboardInterrupt:
        print("\nOperacao cancelada.")


if __name__ == "__main__":
    main()
