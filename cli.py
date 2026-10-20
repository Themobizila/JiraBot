"""
Interface de Linha de Comando (CLI) e Menu Interativo do JiraBot.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import winreg
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from config import (
    BotConfig,
    ShiftProfile,
    TimeWindow,
    get_default_config_dir,
    make_custom_profile,
)
from daemon import (
    get_status,
    setup_logging,
    start_background,
    stop_background,
    restart_background,
    JiraBotService,
)
from engine import BotEngine, format_duration
from history import generate_report
from jira_client import JiraClient
from storage import StateManager, TimeInterval


AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_APP_NAME = "JiraBotBackgroundService"


def is_setup_completed() -> bool:
    """Verifica se o setup basico de credenciais ja foi preenchido."""
    config = BotConfig.load()
    if not config.jira.email or not config.jira.api_token:
        return False
    if "seu-dominio" in config.jira.base_url:
        return False
    return True


def set_windows_autostart(enable: bool = True) -> bool:
    """Configura ou remove o JiraBot da inicializacao automatica do Windows no registro HKCU."""
    python_exe = sys.executable
    pythonw_exe = Path(python_exe).parent / "pythonw.exe"
    executable = str(pythonw_exe) if pythonw_exe.exists() else python_exe

    daemon_path = Path(__file__).parent / "daemon.py"
    cmd = f'"{executable}" "{daemon_path}" run-daemon'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, AUTOSTART_APP_NAME, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            return True
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return True
    except Exception as e:
        print(f"Erro ao alterar registro do Windows: {e}")
        return False


def prompt_custom_profile() -> ShiftProfile:
    """Assistente interativo para definicao de horarios e folgas/tolerancias personalizadas."""
    print("\n--- CONFIGURACAO DE TURNO PERSONALIZADO E FOLGAS ---")
    print("Informe os horarios base e as folgas de tempo (antes e depois):\n")

    # 1. Entrada
    entry_hm = input("  1. Horario previsto de Entrada (ex: 07:45) [padrao: 07:45]: ").strip() or "07:45"
    e_before = input("     - Folga permitida ANTES da entrada (minutos) [padrao: 20]: ").strip() or "20"
    e_after = input("     - Folga permitida DEPOIS da entrada (minutos) [padrao: 20]: ").strip() or "20"

    # 2. Saida Almoco
    lunch_s_hm = input("\n  2. Horario previsto de Saida para Almoco (ex: 12:00) [padrao: 12:00]: ").strip() or "12:00"
    ls_before = input("     - Folga permitida ANTES do almoco (minutos) [padrao: 20]: ").strip() or "20"
    ls_after = input("     - Folga permitida DEPOIS do almoco (minutos) [padrao: 20]: ").strip() or "20"

    # 3. Retorno Almoco
    lunch_e_hm = input("\n  3. Horario previsto de Retorno do Almoco (ex: 13:30) [padrao: 13:30]: ").strip() or "13:30"
    le_before = input("     - Folga permitida ANTES do retorno (minutos) [padrao: 10]: ").strip() or "10"
    le_after = input("     - Folga permitida DEPOIS do retorno (minutos) [padrao: 10]: ").strip() or "10"

    # 4. Saida Fim de Expediente
    exit_hm = input("\n  4. Horario previsto de Saida / Fim de Expediente (ex: 15:30) [padrao: 15:30]: ").strip() or "15:30"
    ex_before = input("     - Folga permitida ANTES da saida (minutos) [padrao: 15]: ").strip() or "15"
    ex_after = input("     - Folga permitida DEPOIS da saida (minutos) [padrao: 30]: ").strip() or "30"

    # 5. Meta de Horas
    target_str = input("\n  5. Meta total de horas do turno (ex: 6.0 ou 8.0) [padrao: 6.0]: ").strip() or "6.0"
    try:
        target_hours = float(target_str.replace(",", "."))
    except ValueError:
        target_hours = 6.0

    try:
        eb = int(e_before)
        ea = int(e_after)
        lsb = int(ls_before)
        lsa = int(ls_after)
        leb = int(le_before)
        lea = int(le_after)
        exb = int(ex_before)
        exa = int(ex_after)
    except ValueError:
        eb, ea, lsb, lsa, leb, lea, exb, exa = 20, 20, 20, 20, 10, 10, 15, 30

    profile = make_custom_profile(
        name="custom",
        target_hours=target_hours,
        entry_hm=entry_hm,
        lunch_start_hm=lunch_s_hm,
        lunch_end_hm=lunch_e_hm,
        exit_hm=exit_hm,
        entry_tol_before=eb,
        entry_tol_after=ea,
        lunch_start_tol_before=lsb,
        lunch_start_tol_after=lsa,
        lunch_end_tol_before=leb,
        lunch_end_tol_after=lea,
        exit_tol_before=exb,
        exit_tol_after=exa,
        description=f"Turno Personalizado {target_hours}h (Entrada {entry_hm}, Retorno {lunch_e_hm}, Saida {exit_hm})",
    )

    print(f"\nTurno personalizado configurado com sucesso!")
    print(f"  - Entrada : {profile.entry_window.start_str} ate {profile.entry_window.end_str} (Alvo: {entry_hm})")
    print(f"  - Almoco  : {profile.lunch_start_window.start_str} ate {profile.lunch_start_window.end_str} (Alvo: {lunch_s_hm})")
    print(f"  - Retorno : {profile.lunch_end_window.start_str} ate {profile.lunch_end_window.end_str} (Alvo: {lunch_e_hm})")
    print(f"  - Saida   : {profile.exit_window.start_str} ate {profile.exit_window.end_str} (Alvo: {exit_hm})")
    return profile


def cmd_setup(args: Optional[argparse.Namespace] = None) -> None:
    """Assistente interativo de configuracao do JiraBot via terminal."""
    print("\n" + "=" * 60)
    print("          ASSISTENTE DE CONFIGURACAO - JIRABOT")
    print("=" * 60)
    print("Configure o perfil de turno e a sua conta de acesso ao Jira.\n")

    config = BotConfig.load()

    # 1. Perfil de Turno
    print("[1/4] Selecione o perfil de turno de trabalho:")
    print("  1) Turno de 8h (Entrada ~07:42, Almoco 11:45/13:00, Saida ~17:30-18:10)")
    print("  2) Turno de 6h Cedo (Entrada ~07:45, Almoco 11:45/13:00, Saida ~15:15-15:30)")
    print("  3) Turno de 6h Padrao (Entrada ~08:00, Almoco 11:45/13:00, Saida ~15:30)")
    print("  4) Personalizado (Definir seus proprios horarios e tolerancias)")
    choice = input(f"Escolha [1, 2, 3 ou 4] (atual: {config.active_profile}): ").strip()

    if choice == "1":
        config.active_profile = "8h"
    elif choice == "2":
        config.active_profile = "6h_0745"
    elif choice == "3":
        config.active_profile = "6h_0800"
    elif choice == "4":
        custom_prof = prompt_custom_profile()
        config.profiles["custom"] = custom_prof
        config.active_profile = "custom"

    # 2. Ticket padrao
    print("\n[2/4] Configuracao do Ticket Jira Padrao:")
    current_issue = config.jira.default_issue or "Nenhum"
    issue_input = input(f"Chave da tarefa/ticket (ex: PROJ-1234) [atual: {current_issue}]: ").strip()
    if issue_input:
        config.jira.default_issue = issue_input.upper()

    # 3. URL do Jira e Credenciais
    print("\n[3/4] Configuracao de Acesso ao Jira:")
    current_url = config.jira.base_url
    url_input = input(f"URL Base do Jira (ex: https://sua-empresa.atlassian.net) [atual: {current_url}]: ").strip()
    if url_input:
        config.jira.base_url = url_input.rstrip("/")

    current_email = config.jira.email or "Nao configurado"
    email_input = input(f"Email corporativo do Jira [atual: {current_email}]: ").strip()
    if email_input:
        config.jira.email = email_input

    token_prompt = "API Token do Jira (Enter para manter o atual): " if config.jira.api_token else "API Token do Jira: "
    token_input = getpass.getpass(token_prompt).strip()
    if token_input:
        config.jira.api_token = token_input

    # 4. Modo de bloqueio intermediario
    print("\n[4/4] Comportamento para saidas rapidas fora das janelas (ex: banheiro/agua):")
    print("  1) Pausar contagem durante o bloqueio e retomar ao desbloquear (Modo Recomendado)")
    print("  2) Ignorar bloqueios rapidos fora das janelas (manter contagem continua)")
    mode_choice = input(f"Escolha [1 ou 2] (atual: {config.intermediate_lock_mode}): ").strip()
    if mode_choice == "1":
        config.intermediate_lock_mode = "pause"
    elif mode_choice == "2":
        config.intermediate_lock_mode = "ignore"

    config.save()
    print("\n" + "=" * 60)
    print("Configuracao gravada com sucesso em ~/.jirabot/config.json")
    print("=" * 60)

    # Teste de conexao opcional
    test_choice = input("\nDeseja testar a conexao com o Jira agora? [S/n]: ").strip().lower()
    if test_choice != "n":
        client = JiraClient(config.jira)
        res = client.test_connection()
        print(f"Resultado do Teste: {res['message']}")


def cmd_status(args: Optional[argparse.Namespace] = None) -> None:
    """Exibe o painel de status em tempo real do JiraBot."""
    status = get_status()
    config = BotConfig.load()
    profile = config.get_current_profile()
    state_mgr = StateManager()
    state = state_mgr.load_state()
    from review_dialog import get_fallback_description
    from jira_client import JiraClient
    client = JiraClient(config.jira)

    print("\n" + "=" * 60)
    print("                    STATUS DO JIRABOT")
    print("=" * 60)

    servico_str = f"EM EXECUCAO (PID: {status['pid']})" if status["is_running"] else "PARADO"
    print(f"Servico em Background : {servico_str}")
    print(f"Perfil Ativo          : {status['active_profile']} ({profile.description})")
    print(f"Usuario Conectado     : {config.jira.email or 'Nao configurado'}")
    print(f"Data Atual            : {status['date']}")
    print(f"Estado do Cronometro  : {status['daily_status']}")

    total_str = format_duration(status["total_seconds"])
    meta_str = f"{profile.target_hours}h"
    print(f"Tempo Acumulado Hoje  : {total_str} (Meta: {meta_str})")

    active_issue = status['target_issue'] or config.jira.default_issue
    custom_desc = state.get_issue_comment(active_issue)
    if state.no_comment:
        desc_display = "(Configurado para enviar SEM DESCRICAO)"
    elif custom_desc:
        desc_display = f"\"{custom_desc}\""
    else:
        fb = get_fallback_description(active_issue, client)
        desc_display = f"(Padrao: [{fb}])"

    print(f"Ticket Ativo          : {active_issue}")
    print(f"Descricao da Atividade: {desc_display}")

    by_issue = status.get("seconds_by_issue", {})
    if len(by_issue) > 1 or (len(by_issue) == 1 and list(by_issue.keys())[0] != status["target_issue"]):
        print("Detalhamento por Ticket:")
        for issue, sec in by_issue.items():
            if state.no_comment:
                desc_sub = " - (SEM DESCRICAO)"
            else:
                issue_desc = state.get_issue_comment(issue)
                desc_sub = f" - \"{issue_desc}\"" if issue_desc else ""
            print(f"  - {issue}: {format_duration(sec)}{desc_sub}")

    logged_str = "SIM (Ja enviado ao Jira)" if status["is_logged"] else "NAO (Pendente para o final do turno)"
    print(f"Worklog Lancado       : {logged_str}")
    print(f"Fila Offline Pendente : {status['pending_queue_count']} item(ns)")
    print(f"Ultimo Evento         : {status['last_event']} ({status['last_event_time']})")
    print("=" * 60)


def cmd_adjust_start(time_str: Optional[str] = None) -> None:
    """Permite ajustar o horario do primeiro inicio do dia (ex: 07:45)."""
    target = time_str
    if not target:
        target = input("\nInforme o horario real de inicio de hoje (formato HH:MM, ex: 07:45): ").strip()

    if not target or ":" not in target:
        print("Horario invalido. Operacao cancelada.")
        return

    try:
        h, m = map(int, target.split(":"))
        today = date.today()
        new_start_dt = datetime(today.year, today.month, today.day, h, m, 0)
        new_start_iso = new_start_dt.isoformat()

        mgr = StateManager()
        state = mgr.load_state()

        if not state.intervals:
            state.intervals.append(TimeInterval(start=new_start_iso, issue_key=state.target_issue))
            state.status = "RUNNING"
        else:
            state.intervals[0].start = new_start_iso

        state.last_event = "ADJUST_START_TIME"
        state.last_event_time = datetime.now().isoformat()
        mgr.save_state(state)

        total_str = format_duration(state.get_total_seconds())
        print(f"\nHorario de inicio ajustado com sucesso para {target}!")
        print(f"Novo tempo total recalculado para hoje: {total_str}")

    except Exception as e:
        print(f"Erro ao ajustar horario: {e}")


def cmd_test_jira(args: Optional[argparse.Namespace] = None) -> None:
    """Testa a conectividade e autenticacao com a API do Jira."""
    config = BotConfig.load()
    print("\nTestando conexao com o Jira...")
    print(f"URL: {config.jira.base_url}")
    print(f"Email: {config.jira.email or 'Nao configurado'}")

    client = JiraClient(config.jira)
    res = client.test_connection()

    if res["success"]:
        print(f"\n[SUCESSO] {res['message']}")
    else:
        print(f"\n[FALHA] {res['message']}")


def cmd_comment(args: Optional[argparse.Namespace] = None, text: Optional[str] = None) -> None:
    """Define ou edita a descricao da atividade atual, ou define envio sem descricao."""
    state_mgr = StateManager()
    state = state_mgr.load_state()
    config = BotConfig.load()
    active_issue = state.target_issue or config.jira.default_issue

    if args and getattr(args, "clear", False):
        state.no_comment = True
        state_mgr.save_state(state)
        print(f"\n[SUCESSO] Horarios de hoje serao enviados ao Jira SEM NENHUMA DESCRICAO.")
        return

    comment_text = text
    if args and getattr(args, "text", None):
        comment_text = args.text

    if not comment_text:
        current_c = state.get_issue_comment(active_issue)
        print(f"\n--- DEFINIR DESCRICAO DA ATIVIDADE ({active_issue}) ---")
        if state.no_comment:
            print("Estado atual: Configurado para enviar SEM DESCRICAO")
        elif current_c:
            print(f"Descricao atual salva: \"{current_c}\"")

        print("\nEscolha:")
        print("  1) Digitar nova descricao detalhada")
        print("  2) Enviar horarios SEM NENHUMA DESCRICAO (limpar e desativar padrao)")
        c_opt = input("Opcao [1 ou 2] (padrao: 1): ").strip()

        if c_opt == "2":
            state.no_comment = True
            state_mgr.save_state(state)
            print(f"\n[SUCESSO] Configurado para enviar os horarios de hoje SEM NENHUMA DESCRICAO.")
            return

        comment_text = input("Digite a nova descricao detalhada da atividade: ").strip()

    if not comment_text:
        print("Nenhuma descricao informada. Operacao cancelada.")
        return

    state.no_comment = False
    state_mgr.save_state(state)
    engine = BotEngine(config=config, state_manager=state_mgr)
    engine.set_comment(comment_text)
    print(f"\n[SUCESSO] Descricao da atividade para {active_issue} salva como:")
    print(f"  \"{comment_text}\"")


def cmd_review_comments(args: Optional[argparse.Namespace] = None) -> None:
    """Abre o menu de revisao e listagem de descricoes de todos os tickets do dia."""
    from review_dialog import prompt_review_cli
    prompt_review_cli()


def cmd_edit_worklogs(args: Optional[argparse.Namespace] = None) -> None:
    """Abre o menu interativo para listar e editar descricoes de lancamentos anteriores no Jira."""
    from review_dialog import prompt_history_worklogs_cli
    days = args.days if args and getattr(args, "days", None) else 14
    prompt_history_worklogs_cli(default_days=days)


def cmd_switch(
    args: Optional[argparse.Namespace] = None,
    issue_name: Optional[str] = None,
    comment: Optional[str] = None,
) -> None:
    """Altera a tarefa/ticket ativa em tempo real com opcao de descricao."""
    target_issue = issue_name
    custom_comment = comment

    if args:
        if getattr(args, "issue", None):
            target_issue = args.issue
        if getattr(args, "comment", None):
            custom_comment = args.comment

    if not target_issue:
        target_issue = input("\nDigite a chave do novo ticket (ex: CONSISABI-390): ").strip()

    if not target_issue:
        print("Operacao cancelada. Nenhuma chave informada.")
        return

    if custom_comment is None:
        custom_comment = input("Descricao do que sera feito nesta tarefa (opcional / Enter para manter padrao): ").strip()

    new_issue = target_issue.strip().upper()
    state_mgr = StateManager()
    config = BotConfig.load()
    engine = BotEngine(config=config, state_manager=state_mgr)

    engine.switch_ticket(new_issue, comment=custom_comment if custom_comment else None)
    print(f"\nTicket ativo alterado com sucesso para: {new_issue}")
    if custom_comment:
        print(f"Descricao registrada: \"{custom_comment}\"")
    print("Os proximos minutos de trabalho serao contabilizados para este novo ticket.")


def parse_time_input(text: str) -> Optional[int]:
    """Converte strings como '01:30', '1h30m', '45m', '2h', '1.5h' em total de segundos."""
    s = text.strip().lower()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            sec = int(parts[2]) if len(parts) > 2 else 0
            return h * 3600 + m * 60 + sec
        except ValueError:
            return None

    import re
    total = 0
    h_match = re.search(r"(\d+(?:\.\d+)?)\s*h", s)
    m_match = re.search(r"(\d+)\s*m", s)
    s_match = re.search(r"(\d+)\s*s", s)
    if h_match:
        total += int(float(h_match.group(1)) * 3600)
    if m_match:
        total += int(m_match.group(1)) * 60
    if s_match:
        total += int(s_match.group(1))
    if total > 0:
        return total
    try:
        val = float(s.replace(",", "."))
        if val <= 24:
            return int(val * 3600)
        else:
            return int(val * 60)
    except ValueError:
        return None


def _transfer_today_flow(args: Optional[argparse.Namespace] = None) -> None:
    """Fluxo guiado para transferir horas da sessao de hoje."""
    state_mgr = StateManager()
    config = BotConfig.load()
    engine = BotEngine(config=config, state_manager=state_mgr)
    state = state_mgr.load_state()

    by_issue = state.get_seconds_by_issue(default_issue=config.jira.default_issue)
    valid_issues = [(k, v) for k, v in by_issue.items() if v > 0 and k != "SEM_TICKET"]

    if not valid_issues:
        print("\nNenhum ticket com horas contabilizadas hoje para transferir.")
        return

    src_issue = getattr(args, "source", None) if args else None
    tgt_issue = getattr(args, "target", None) if args else None
    time_str = getattr(args, "time", None) if args else None
    transfer_all = getattr(args, "all", False) if args else False

    if not src_issue:
        print("\n--- TICKETS COM HORAS CONTABILIZADAS HOJE ---")
        for idx, (issue, sec) in enumerate(valid_issues, 1):
            print(f"  [{idx}] {issue}: {format_duration(sec)}")

        choice = input(f"\nEscolha o ticket de ORIGEM [1-{len(valid_issues)}] ou digite a chave: ").strip()
        if not choice:
            print("Operacao cancelada.")
            return

        if choice.isdigit() and 1 <= int(choice) <= len(valid_issues):
            src_issue = valid_issues[int(choice) - 1][0]
        else:
            src_issue = choice.upper()

    src_issue = src_issue.strip().upper()
    src_total = by_issue.get(src_issue, 0)
    if src_total <= 0:
        print(f"\nO ticket {src_issue} nao possui horas contabilizadas hoje.")
        return

    if not tgt_issue:
        # Prepara sugestoes de destino: outros tickets com horas hoje, ticket ativo e padrao
        dest_candidates: List[str] = []
        for issue, _ in valid_issues:
            if issue != src_issue and issue not in dest_candidates:
                dest_candidates.append(issue)
        curr_active = (state.target_issue or "").strip().upper()
        if curr_active and curr_active != src_issue and curr_active not in dest_candidates:
            dest_candidates.append(curr_active)
        default_iss = (config.jira.default_issue or "").strip().upper()
        if default_iss and default_iss != src_issue and default_iss not in dest_candidates:
            dest_candidates.append(default_iss)

        print("\n--- ESCOLHA O TICKET DE DESTINO ---")
        if dest_candidates:
            for idx, cand in enumerate(dest_candidates, 1):
                tag = " (Ticket Ativo)" if cand == curr_active else ""
                print(f"  [{idx}] {cand}{tag}")
            p_msg = f"Escolha o destino [1-{len(dest_candidates)}] ou digite a chave (ex: CONSISABI-427): "
        else:
            p_msg = "Digite a chave do ticket de DESTINO (ex: CONSISABI-427): "

        tgt_input = input(f"\n{p_msg}").strip()
        if not tgt_input:
            print("Operacao cancelada.")
            return

        if tgt_input.isdigit():
            val = int(tgt_input)
            if dest_candidates and 1 <= val <= len(dest_candidates):
                tgt_issue = dest_candidates[val - 1]
            elif valid_issues and 1 <= val <= len(valid_issues):
                tgt_issue = valid_issues[val - 1][0]
            else:
                print(f"\n[ERRO] Opcao numerica '{tgt_input}' invalida. Por favor, informe a chave real do Jira (ex: CONSISABI-427).")
                return
        else:
            tgt_issue = tgt_input.upper()

    tgt_issue = tgt_issue.strip().upper()
    if tgt_issue.isdigit():
        print(f"\n[ERRO] '{tgt_issue}' e invalido. Chaves de ticket do Jira contem letras e numeros (ex: CONSISABI-427).")
        return

    if src_issue == tgt_issue:
        print("\nO ticket de origem e destino nao podem ser iguais.")
        return

    seconds_to_transfer = None
    if not transfer_all:
        if time_str:
            seconds_to_transfer = parse_time_input(time_str)
        else:
            print(f"\nHoras disponiveis em {src_issue}: {format_duration(src_total)}")
            print("  [1] Transferir TODO o tempo acumulado")
            print("  [2] Transferir apenas uma parte (informar tempo)")
            q_opt = input("Opcao [1 ou 2] (padrao: 1): ").strip()
            if q_opt == "2":
                p_time = input("Informe o tempo a transferir (ex: 01:00, 45m, 1.5h): ").strip()
                seconds_to_transfer = parse_time_input(p_time)
                if not seconds_to_transfer or seconds_to_transfer <= 0:
                    print("Tempo invalido. Operacao cancelada.")
                    return

    transferred = engine.transfer_today_hours(
        source_issue=src_issue,
        target_issue=tgt_issue,
        seconds=seconds_to_transfer,
    )

    if transferred > 0:
        dur_str = format_duration(transferred)
        print(f"\n[SUCESSO] Transferido {dur_str} de {src_issue} para {tgt_issue}!")
        updated_state = state_mgr.load_state()
        new_by_issue = updated_state.get_seconds_by_issue(default_issue=config.jira.default_issue)
        print("\nDetalhamento atualizado de hoje:")
        for k, v in new_by_issue.items():
            if v > 0:
                print(f"  - {k}: {format_duration(v)}")
    else:
        print("\nNenhum tempo foi transferido.")


def _transfer_jira_flow(args: Optional[argparse.Namespace] = None) -> None:
    """Fluxo guiado para migrar worklogs historicos ja gravados no Jira."""
    config = BotConfig.load()
    client = JiraClient(config.jira)

    src_issue = getattr(args, "source", None) if args else None
    tgt_issue = getattr(args, "target", None) if args else None

    if not src_issue:
        src_issue = input("\nDigite a chave do ticket de ORIGEM no Jira (ex: CONSISABI-418): ").strip().upper()
    if not src_issue:
        print("Operacao cancelada.")
        return

    print(f"\nBuscando worklogs no ticket {src_issue}...")
    worklogs = client.get_issue_worklogs(src_issue)
    if not worklogs:
        print(f"Nenhum worklog encontrado no ticket {src_issue}.")
        return

    print(f"\n--- WORKLOGS ENCONTRADOS EM {src_issue} ---")
    for idx, w in enumerate(worklogs, 1):
        w_id = w.get("id")
        started = w.get("started", "")[:10]
        time_spent = w.get("timeSpent", "")
        comment = (w.get("comment", "") or "").strip()
        comment_preview = (comment[:45] + "...") if len(comment) > 45 else comment
        print(f"  [{idx}] ID: {w_id} | Data: {started} | Tempo: {time_spent} | \"{comment_preview}\"")

    w_choice = input(f"\nEscolha o worklog a migrar [1-{len(worklogs)}, ou 'T' para TODOS]: ").strip().upper()
    if not w_choice:
        print("Operacao cancelada.")
        return

    target_wls = []
    if w_choice == "T":
        target_wls = worklogs
    elif w_choice.isdigit() and 1 <= int(w_choice) <= len(worklogs):
        target_wls = [worklogs[int(w_choice) - 1]]
    else:
        print("Opcao invalida. Operacao cancelada.")
        return

    if not tgt_issue:
        tgt_issue = input(f"Digite a chave do ticket de DESTINO no Jira (ex: CONSISABI-426): ").strip().upper()
    if not tgt_issue:
        print("Operacao cancelada.")
        return

    tgt_issue = tgt_issue.strip().upper()
    if src_issue == tgt_issue:
        print("Ticket de origem e destino sao identicos. Operacao cancelada.")
        return

    confirm = input(f"\nConfirma a migracao de {len(target_wls)} worklog(s) de {src_issue} para {tgt_issue}? [S/n]: ").strip().lower()
    if confirm == "n":
        print("Migracao cancelada.")
        return

    migrated_count = 0
    for w in target_wls:
        w_id = str(w.get("id"))
        res = client.migrate_worklog(source_issue=src_issue, target_issue=tgt_issue, worklog_id=w_id)
        if res.get("success"):
            migrated_count += 1
            print(f"  [OK] {res['message']}")
        else:
            print(f"  [FALHA] {res['message']}")

    print(f"\nProcesso concluido: {migrated_count} de {len(target_wls)} worklog(s) migrado(s) com sucesso para {tgt_issue}.")


def cmd_transfer(args: Optional[argparse.Namespace] = None) -> None:
    """Ponto de entrada para transferencia e remanejamento de horas entre tickets."""
    print("\n" + "=" * 65)
    print("      TRANSFERENCIA E REMANEJAMENTO DE HORAS ENTRE TICKETS")
    print("=" * 65)

    mode = None
    if args:
        if getattr(args, "today", False):
            mode = "today"
        elif getattr(args, "jira", False):
            mode = "jira"

    if not mode:
        print("Escolha o tipo de transferencia:")
        print("  [1] Transferir horas de HOJE (sessao ativa ainda nao enviada ao Jira)")
        print("  [2] Migrar lancamento anterior diretamente no JIRA")
        print("  [0] Voltar ao Menu")
        t_opt = input("Opcao [1, 2 ou 0]: ").strip()
        if t_opt == "1":
            mode = "today"
        elif t_opt == "2":
            mode = "jira"
        else:
            return

    if mode == "today":
        _transfer_today_flow(args)
    elif mode == "jira":
        _transfer_jira_flow(args)


def cmd_report(args: Optional[argparse.Namespace] = None, days_count: int = 7) -> None:
    """Gera relatorio de horas trabalhadas."""
    days = days_count
    if args and getattr(args, "month", False):
        days = 30
    elif args and getattr(args, "days", None):
        days = args.days

    output = generate_report(days=days)
    print("\n" + output)


def cmd_start(args: Optional[argparse.Namespace] = None) -> None:
    """Inicia o servico do JiraBot."""
    if args and getattr(args, "foreground", False):
        print("\nIniciando JiraBot em primeiro plano com TrayIcon (Ctrl+C para encerrar)...")
        setup_logging(log_to_file=True)
        service = JiraBotService(enable_tray=True)
        service.run_foreground()
    else:
        pid = start_background()
        print(f"\nJiraBot iniciado com sucesso em segundo plano com Icone na Bandeja! (PID: {pid})")
        print("Ele ira cronometrar e lancar seus horarios automaticamente.")


def cmd_stop(args: Optional[argparse.Namespace] = None) -> None:
    """Interrompe o servico em segundo plano."""
    success = stop_background()
    if success:
        print("\nServico JiraBot encerrado com sucesso.")
    else:
        print("\nNenhum servico JiraBot em execucao foi encontrado.")


def cmd_restart(args: Optional[argparse.Namespace] = None) -> None:
    """Reinicia o servico do JiraBot em segundo plano com uma nova instancia limpa."""
    print("\nReiniciando servico JiraBot em segundo plano...")
    new_pid = restart_background()
    print(f"JiraBot reiniciado com sucesso! (Novo PID: {new_pid})")


def cmd_log_now(args: Optional[argparse.Namespace] = None, no_comment: bool = False) -> None:
    """Forca o encerramento do dia e lancamento imediato no Jira."""
    config = BotConfig.load()
    state_mgr = StateManager()
    client = JiraClient(config.jira, state_mgr)

    engine = BotEngine(
        config=config,
        state_manager=state_mgr,
        on_worklog_trigger=lambda issue, sec, start_iso, comment=None: client.submit_worklog(
            issue,
            sec,
            start_iso,
            comment="" if comment == "__EMPTY__" else comment,
            no_comment=(comment == "__EMPTY__"),
        ).get("status") == "success"
    )

    issue = getattr(args, "issue", None) or config.jira.default_issue
    comment = getattr(args, "comment", None)
    send_no_comment = no_comment or (args and getattr(args, "no_comment", False))

    print("\nCalculando horas e registrando worklog no Jira...")
    total_seconds = engine.manual_log(issue_key=issue, comment=comment, no_comment=send_no_comment)
    total_str = format_duration(total_seconds)

    desc_info = "SEM DESCRICAO" if send_no_comment else "com descricoes definidas"
    print(f"Processo concluido! Total de {total_str} processado para os tickets do dia ({desc_info}).")


def cmd_profile(args: Optional[argparse.Namespace] = None) -> None:
    """Altera ou visualiza o perfil de turno."""
    config = BotConfig.load()
    if args and getattr(args, "name", None):
        if args.name in config.profiles:
            config.active_profile = args.name
            config.save()
            print(f"\nPerfil de turno alterado para: {args.name}")
        elif args.name == "custom":
            custom_prof = prompt_custom_profile()
            config.profiles["custom"] = custom_prof
            config.active_profile = "custom"
            config.save()
            print("\nPerfil personalizado configurado e ativado!")
        else:
            print(f"\nPerfil '{args.name}' nao encontrado. Perfis disponiveis: {list(config.profiles.keys())}")
    else:
        print(f"\nPerfil ativo atual: {config.active_profile}")
        for name, prof in config.profiles.items():
            print(f"  - {name}: {prof.description}")


def cmd_autostart(args: Optional[argparse.Namespace] = None) -> None:
    """Configura ou remove o autostart do Windows."""
    if args and getattr(args, "action", None) == "enable":
        if set_windows_autostart(True):
            print("\nInicializacao automatica com o Windows habilitada com sucesso.")
    elif args and getattr(args, "action", None) == "disable":
        if set_windows_autostart(False):
            print("\nInicializacao automatica com o Windows desabilitada.")


def cmd_test_event(args: Optional[argparse.Namespace] = None) -> None:
    """Simula manualmente eventos de Lock ou Unlock para teste."""
    config = BotConfig.load()
    state_mgr = StateManager()
    engine = BotEngine(config=config, state_manager=state_mgr)

    if args and args.event == "lock":
        print("\nSimulando evento LOCK...")
        state = engine.handle_lock()
        print(f"Novo estado apos LOCK: {state.status} (Ultimo evento: {state.last_event})")
    elif args and args.event == "unlock":
        print("\nSimulando evento UNLOCK...")
        state = engine.handle_unlock()
        print(f"Novo estado apos UNLOCK: {state.status} (Ultimo evento: {state.last_event})")


def cmd_test_popup(args: Optional[argparse.Namespace] = None) -> None:
    """Dispara a janela grafica de revisao pre-saida para teste imediato."""
    print("\nDisparando janela grafica de revisao pre-saida...")
    from review_dialog import run_popup_gui
    run_popup_gui()
    print("Janela de revisao finalizada.")


def cmd_web(args: Optional[argparse.Namespace] = None) -> None:
    """Inicia o servidor do Painel Web Interativo do JiraBot e abre no navegador."""
    from web_panel import run_web_server
    port = getattr(args, "port", 8765) if args else 8765
    no_browser = getattr(args, "no_browser", False) if args else False
    run_web_server(port=port, open_browser=(not no_browser))


def cmd_update(args: Optional[argparse.Namespace] = None) -> None:
    """Verifica e aplica atualizacoes do aplicativo preservando configuracoes individuais."""
    from updater import check_for_updates, perform_update, publish_clean_release, get_version_info
    config = BotConfig.load()
    info = get_version_info()
    print("\n" + "=" * 60)
    print("       ATUALIZACAO DO APLICATIVO (MULTI-USUARIO)")
    print("=" * 60)
    print(f"  Versao Local Atual       : {info.get('version')}")
    print(f"  Pasta do Codigo          : {info.get('app_dir')}")
    print(f"  Pasta de Config Pessoal  : {info.get('user_config_dir')} (Isolada e Protegida)")
    source = (getattr(args, "source", None) if args else None) or config.update_source
    if args and getattr(args, "publish", None):
        res = publish_clean_release(args.publish)
        print(f"\n[{'OK' if res.get('success') else 'ERRO'}] {res.get('message')}")
        return
    if not source:
        print(f"  Fonte de Atualizacao     : {config.update_source or '(Apenas Git local)'}")
        src_in = input("\nInforme a pasta de rede/URL (ou Enter para usar Git/padrao salvo): ").strip()
        if src_in:
            source = src_in
            config.update_source = src_in
            config.save()
    chk = check_for_updates(source)
    print(f"\nStatus da verificacao: {chk.get('message')}")
    if chk.get("success"):
        confirm = input("Deseja aplicar a atualizacao agora? [S/N] (padrao: S): ").strip().upper()
        if confirm in ("", "S", "SIM", "Y"):
            res = perform_update(source)
            print(f"\n[{'OK' if res.get('success') else 'ERRO'}] {res.get('message')}")


def interactive_menu() -> None:
    """Menu interativo principal para execucao via batch (.bat) ou terminal sem parametros."""
    if not is_setup_completed():
        print("Configuracao inicial nao detectada. Abrindo assistente de setup...")
        cmd_setup()

    while True:
        status = get_status()
        config = BotConfig.load()
        state_mgr = StateManager()
        state = state_mgr.load_state()

        print("\n" + "=" * 60)
        print("                 PAINEL PRINCIPAL - JIRABOT")
        print("=" * 60)
        dur = format_duration(status['total_seconds']) if status.get('total_seconds') else "0m"
        target_issue = status.get('target_issue') or config.jira.default_issue or "Nao definido"
        print(f"  Servico Ativo : {'SIM (PID: ' + str(status['pid']) + ')' if status['is_running'] else 'NAO (Parado)'}")
        print(f"  Perfil Ativo  : {status.get('active_profile', 'N/A')}")
        print(f"  Estado Atual  : {status.get('daily_status', 'N/A')}")
        print(f"  Horas Hoje    : {dur}")
        print(f"  Ticket Ativo  : {target_issue}")
        print("-" * 60)
        print(" [W] Abrir Painel Web Interativo no Navegador (Interface Visual)")
        print(" [1] Iniciar Bot em Background (com Icone na Bandeja)")
        print(" [2] Parar Bot em Background")
        print(" [X] Reiniciar Bot em Background (restart)")
        print(" [3] Ver Status Completo do Dia")
        print(" [4] Trocar Ticket Ativo (switch)")
        print(" [M] Transferir / Remanejar Horas entre Tickets (transfer)")
        print(" [D] Definir / Editar Descricao da Atividade Atual (comment)")
        print(" [R] Revisar / Listar Descricoes de Todos os Tickets de Hoje (review)")
        print(" [E] Ver e Editar Descricoes de Lancamentos Anteriores (Jira)")
        print(" [5] Ver Relatorio Semanal de Horas (report)")
        print(" [6] Ver Relatorio Mensal (30 dias)")
        print(" [7] Forcar Lancamento de Horas no Jira Agora (log-now)")
        print(" [8] Testar Conexao com o Jira")
        print(" [9] Alternar / Criar Perfil de Turno (8h, 6h ou Personalizado)")
        print(" [T] Ajustar Horario de Inicio de Hoje (ex: 07:45)")
        print(" [P] Testar Janela Grafica de Revisao Pre-Saida (popup)")
        print(" [A] Habilitar / Desabilitar Inicializacao com o Windows")
        print(" [U] Verificar / Atualizar Aplicativo (Multi-Usuario)")
        print(" [C] Reconfigurar Dados de Acesso / Setup")
        print(" [0] Sair do Painel")
        print("=" * 60)

        choice = input("Escolha uma opcao [W, 0-9, D, R, E, M, T, P, A, U, C ou X]: ").strip().upper()

        if choice == "W":
            cmd_web()
        elif choice == "1":
            cmd_start()
        elif choice == "2":
            cmd_stop()
        elif choice == "X":
            cmd_restart()
        elif choice == "3":
            cmd_status()
        elif choice == "4":
            cmd_switch()
        elif choice == "M":
            cmd_transfer()
        elif choice == "D":
            cmd_comment()
        elif choice == "R":
            cmd_review_comments()
        elif choice == "E":
            cmd_edit_worklogs()
        elif choice == "P":
            cmd_test_popup()
        elif choice == "5":
            cmd_report(days_count=7)
        elif choice == "6":
            cmd_report(days_count=30)
        elif choice == "7":
            print("\nComo deseja enviar os horarios de hoje para o Jira?")
            print("  1) Enviar com as descricoes atuais (ou padrao do ticket)")
            print("  2) Enviar SEM nenhuma descricao")
            opt_l = input("Escolha [1 ou 2] (padrao: 1): ").strip()
            no_c = (opt_l == "2")
            cmd_log_now(no_comment=no_c)
        elif choice == "8":
            cmd_test_jira()
        elif choice == "9":
            print("\nSelecione o perfil desejado:")
            print("  1) Turno de 8h (Entrada ~07:42, Saida ~17:30-18:10)")
            print("  2) Turno de 6h Cedo (Entrada ~07:45, Saida ~15:15-15:30)")
            print("  3) Turno de 6h Padrao (Entrada ~08:00, Saida ~15:30)")
            print("  4) Criar / Editar Turno Personalizado")
            p_choice = input("Escolha [1, 2, 3 ou 4]: ").strip()
            if p_choice == "1":
                config.active_profile = "8h"
                config.save()
                print("Perfil alterado para: 8h")
            elif p_choice == "2":
                config.active_profile = "6h_0745"
                config.save()
                print("Perfil alterado para: 6h_0745")
            elif p_choice == "3":
                config.active_profile = "6h_0800"
                config.save()
                print("Perfil alterado para: 6h_0800")
            elif p_choice == "4":
                custom_prof = prompt_custom_profile()
                config.profiles["custom"] = custom_prof
                config.active_profile = "custom"
                config.save()
                print("Perfil personalizado ativado com sucesso!")
        elif choice == "T":
            cmd_adjust_start()
        elif choice == "A":
            print("\nGerenciar Inicializacao com o Windows:")
            print("  1) Habilitar (Iniciar sempre que ligar o PC)")
            print("  2) Desabilitar")
            auto_opt = input("Opcao [1 ou 2]: ").strip()
            if auto_opt == "1":
                set_windows_autostart(True)
                print("Inicializacao automatica habilitada.")
            elif auto_opt == "2":
                set_windows_autostart(False)
                print("Inicializacao automatica desabilitada.")
        elif choice == "U":
            cmd_update()
        elif choice == "C":
            cmd_setup()
        elif choice == "0":
            print("\nEncerrando painel. O servico em segundo plano continuara ativo se iniciado.")
            break
        else:
            print("\nOpcao invalida. Tente novamente.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jirabot",
        description="JiraBot - Gerenciador Inteligente de Horas e Worklog do Jira em Background",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponiveis")

    # menu
    subparsers.add_parser("menu", help="Abre o menu interativo no terminal")

    # web
    web_parser = subparsers.add_parser("web", help="Inicia o Painel Web Interativo do JiraBot no navegador")
    web_parser.add_argument("--port", "-p", type=int, default=8765, help="Porta HTTP local (padrao: 8765)")
    web_parser.add_argument("--no-browser", action="store_true", help="Inicia o servidor sem abrir o navegador automaticamente")

    # update
    upd_parser = subparsers.add_parser("update", help="Verifica e atualiza o aplicativo sem alterar configuracoes de usuario")
    upd_parser.add_argument("--source", "-s", type=str, help="Caminho de rede, pasta ou URL .zip da atualizacao")
    upd_parser.add_argument("--publish", type=str, help="Publica os arquivos limpos de codigo em uma pasta compartilhada")

    # setup
    subparsers.add_parser("setup", help="Assistente interativo de configuracao")

    # test-jira
    subparsers.add_parser("test-jira", help="Testa conectividade e credenciais com a API do Jira")

    # status
    subparsers.add_parser("status", help="Exibe o status atual do servico e cronometro")

    # comment
    comment_parser = subparsers.add_parser("comment", help="Define ou edita a descricao da atividade atual")
    comment_parser.add_argument("text", nargs="?", type=str, help="Descricao detalhada do trabalho realizado")
    comment_parser.add_argument("--clear", "--no-comment", "-n", action="store_true", help="Configura para enviar horarios sem nenhuma descricao")

    # review / review-comments
    subparsers.add_parser("review", help="Revisa e edita as descricoes de todos os tickets trabalhados hoje")
    subparsers.add_parser("review-comments", help="Revisa e edita as descricoes de todos os tickets trabalhados hoje")

    # edit-worklogs / history-comments
    edit_parser = subparsers.add_parser("edit-worklogs", help="Lista e edita descricoes de lancamentos anteriores no Jira")
    edit_parser.add_argument("--days", "-d", type=int, default=14, help="Numero de dias retroativos a consultar (padrao: 14)")
    subparsers.add_parser("history-comments", help="Lista e edita descricoes de lancamentos anteriores no Jira")

    # adjust-start
    adj_parser = subparsers.add_parser("adjust-start", help="Ajusta o horario de inicio de hoje")
    adj_parser.add_argument("time", nargs="?", type=str, help="Horario real de inicio (formato HH:MM, ex: 07:45)")

    # switch
    switch_parser = subparsers.add_parser("switch", help="Altera o ticket ativo em tempo real")
    switch_parser.add_argument("issue", type=str, help="Chave do novo ticket (ex: PROJ-5678)")
    switch_parser.add_argument("--comment", "-c", type=str, help="Descricao da atividade para esta tarefa")

    # transfer
    transfer_parser = subparsers.add_parser("transfer", help="Transfere e remaneja horarios entre tickets (hoje ou no Jira)")
    transfer_parser.add_argument("--today", action="store_true", help="Transfere horas da sessao de hoje")
    transfer_parser.add_argument("--jira", action="store_true", help="Migra lancamento anterior diretamente no Jira")
    transfer_parser.add_argument("--source", "-s", type=str, help="Ticket de origem (ex: ATIVDIV-32)")
    transfer_parser.add_argument("--target", "-t", type=str, help="Ticket de destino (ex: CONSISABI-427)")
    transfer_parser.add_argument("--all", "-a", action="store_true", help="Transfere todo o tempo do ticket de origem")
    transfer_parser.add_argument("--time", type=str, help="Quantidade de tempo a transferir (ex: 01:00, 45m)")

    # report
    report_parser = subparsers.add_parser("report", help="Exibe relatorio consolidado de horas")
    report_parser.add_argument("--days", "-d", type=int, help="Numero de dias a consultar (padrao: 7)")
    report_parser.add_argument("--month", "-m", action="store_true", help="Relatorio dos ultimos 30 dias")

    # start
    start_parser = subparsers.add_parser("start", help="Inicia o servico do JiraBot")
    start_parser.add_argument("--foreground", "-f", action="store_true", help="Executa no terminal em primeiro plano")

    # stop
    subparsers.add_parser("stop", help="Interrompe o servico em segundo plano")

    # restart
    subparsers.add_parser("restart", help="Reinicia o servico do JiraBot em segundo plano")

    # log-now
    log_parser = subparsers.add_parser("log-now", help="Forca o envio imediato do tempo acumulado ao Jira")
    log_parser.add_argument("--issue", "-i", type=str, help="Chave do ticket Jira (ex: PROJ-1234)")
    log_parser.add_argument("--comment", "-c", type=str, help="Comentario do worklog")
    log_parser.add_argument("--no-comment", "-n", action="store_true", help="Envia o apontamento sem nenhuma descricao")

    # profile
    prof_parser = subparsers.add_parser("profile", help="Visualiza ou altera o perfil de turno ativo")
    prof_parser.add_argument("name", nargs="?", help="Nome do perfil (8h, 6h_0745, 6h_0800, custom)")

    # autostart
    auto_parser = subparsers.add_parser("autostart", help="Gerencia inicializacao automatica com o Windows")
    auto_parser.add_argument("action", choices=["enable", "disable"], help="enable ou disable")

    # test-event
    test_parser = subparsers.add_parser("test-event", help="Simula eventos de Lock/Unlock para testes")
    test_parser.add_argument("event", choices=["lock", "unlock"], help="Tipo de evento a simular")

    # test-popup / popup
    subparsers.add_parser("test-popup", help="Dispara a janela grafica de revisao pre-saida para teste")
    subparsers.add_parser("popup", help="Dispara a janela grafica de revisao pre-saida")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "test-jira":
        cmd_test_jira(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "comment":
        cmd_comment(args)
    elif args.command in ["review", "review-comments"]:
        cmd_review_comments(args)
    elif args.command in ["edit-worklogs", "history-comments"]:
        cmd_edit_worklogs(args)
    elif args.command in ["test-popup", "popup"]:
        cmd_test_popup(args)
    elif args.command == "adjust-start":
        cmd_adjust_start(args.time)
    elif args.command == "switch":
        cmd_switch(args)
    elif args.command == "transfer":
        cmd_transfer(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "restart":
        cmd_restart(args)
    elif args.command == "log-now":
        cmd_log_now(args)
    elif args.command == "profile":
        cmd_profile(args)
    elif args.command == "autostart":
        cmd_autostart(args)
    elif args.command == "test-event":
        cmd_test_event(args)
    elif args.command == "menu":
        interactive_menu()
    else:
        interactive_menu()



if __name__ == "__main__":
    main()
