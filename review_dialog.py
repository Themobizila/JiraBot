"""
Modulo de revisao interativa de descricoes de worklog antes do encerramento do dia.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from config import BotConfig
from jira_client import JiraClient
from notifier import send_notification
from storage import DailyState, StateManager

logger = logging.getLogger("JiraBot.ReviewDialog")


def format_seconds(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m"


def get_fallback_description(issue_key: str, jira_client: Optional[JiraClient] = None) -> str:
    """Busca o titulo do ticket no Jira para usar como fallback descritivo."""
    if not issue_key or issue_key == "SEM_TICKET":
        return "Lancamento automatico de expediente via JiraBot"
    if jira_client:
        try:
            summary = jira_client.get_issue_summary(issue_key)
            if summary:
                return summary.strip()
        except Exception:
            pass
    return f"Desenvolvimento e atividades no ticket {issue_key}"


def prompt_review_cli(state_manager: Optional[StateManager] = None) -> DailyState:
    """
    Menu interativo de revisao e edicao de descricoes de lancamento via CLI/Terminal.
    """
    mgr = state_manager or StateManager()
    cfg = BotConfig.load()
    client = JiraClient(cfg.jira)

    while True:
        state = mgr.load_state()
        active_issue = state.target_issue or cfg.jira.default_issue
        current_custom_desc = state.get_issue_comment(active_issue)
        fallback_desc = get_fallback_description(active_issue, client)

        if state.no_comment:
            status_desc_text = "NENHUMA (Configurado para enviar SEM descricao)"
        elif current_custom_desc:
            status_desc_text = f"\"{current_custom_desc}\""
        else:
            status_desc_text = f"Descricao nao adicionada, utilizando valor padrao: [{fallback_desc}]"

        print("\n" + "=" * 65)
        print("          REVISAO DE DESCRICOES DE LANCAMENTO - JIRABOT")
        print("=" * 65)
        print(f"Ticket Ativo Atual : {active_issue}")
        print(f"Descricao Atual    : {status_desc_text}\n")
        print("Escolha uma opcao:")
        print("  [1] Editar descricao do lancamento atual")
        print("  [2] Listar Tickets de lancamento do dia (visualizar e editar)")
        print("  [3] Definir envio SEM nenhuma descricao (desativar valor padrao)")
        print("  [0] Salvar e Concluir Revisao")
        print("=" * 65)

        opt = input("Opcao: ").strip()

        if opt == "1":
            print(f"\n--- EDITAR DESCRICAO DO TICKET ATUAL ({active_issue}) ---")
            print(f"Descricao salva atualmente: {status_desc_text}")
            new_desc = input("Digite a nova descricao detalhada da atividade (ou Enter para cancelar): ").strip()
            if new_desc:
                state.no_comment = False
                state.set_issue_comment(active_issue, new_desc)
                mgr.save_state(state)
                print(f"[OK] Descricao de {active_issue} atualizada para: \"{new_desc}\"")

        elif opt == "2":
            all_issues = state.get_all_issues_worked(default_issue=cfg.jira.default_issue)
            by_issue_seconds = state.get_seconds_by_issue(default_issue=cfg.jira.default_issue)

            if not all_issues:
                print("\nNenhum ticket trabalhado hoje ate o momento.")
                continue

            print("\n--- TICKETS DE LANCAMENTO DO DIA ---")
            for idx, issue in enumerate(all_issues, 1):
                sec = by_issue_seconds.get(issue, 0)
                time_str = format_seconds(sec)
                custom_desc = state.get_issue_comment(issue)
                if state.no_comment:
                    desc_display = "(SEM DESCRICAO)"
                elif custom_desc:
                    desc_display = f"\"{custom_desc}\""
                else:
                    fb = get_fallback_description(issue, client)
                    desc_display = f"(Descricao nao adicionada, utilizando valor padrao: [{fb}])"

                print(f"  [{idx}] {issue} ({time_str}): {desc_display}")

            choice = input("\nDigite o numero do ticket para editar a descricao (ou 0 para voltar): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(all_issues):
                selected_issue = all_issues[int(choice) - 1]
                print(f"\n--- EDITAR DESCRICAO DE {selected_issue} ---")
                current_c = state.get_issue_comment(selected_issue)
                if current_c:
                    print(f"Descricao atual: \"{current_c}\"")
                else:
                    fb = get_fallback_description(selected_issue, client)
                    print(f"Descricao atual: (Descricao nao adicionada, utilizando valor padrao: [{fb}])")

                new_desc = input(f"Digite a nova descricao para {selected_issue} (ou Enter para cancelar): ").strip()
                if new_desc:
                    state.no_comment = False
                    state.set_issue_comment(selected_issue, new_desc)
                    mgr.save_state(state)
                    print(f"[OK] Descricao de {selected_issue} atualizada com sucesso!")

        elif opt == "3":
            state.no_comment = True
            mgr.save_state(state)
            print("\n[OK] Opcao ativada: Os lancamentos de hoje serao enviados ao Jira SEM nenhuma descricao.")

        elif opt == "0" or not opt:
            print("\nRevisao de descricoes concluida com sucesso!")
            break

    return mgr.load_state()


def run_popup_gui(state_manager: Optional[StateManager] = None) -> None:
    """
    Executa a interface grafica nativa (Tkinter) de revisao pre-saida na thread principal.
    Apresenta uma janela moderna com titulo, ticket ativo, campo editavel para descricao
    e botoes de acao direta: Salvar, Manter Atual e Enviar sem Descricao.
    """
    try:
        import tkinter as tk
    except ImportError:
        logger.error("Tkinter nao esta disponivel neste ambiente.")
        return

    mgr = state_manager or StateManager()
    cfg = BotConfig.load()
    client = JiraClient(cfg.jira)

    state = mgr.load_state()
    active_issue = (state.target_issue or cfg.jira.default_issue or "SEM_TICKET").strip().upper()
    current_desc = state.get_issue_comment(active_issue)
    fallback_desc = get_fallback_description(active_issue, client)
    worked_seconds = state.get_total_seconds()
    worked_str = format_seconds(worked_seconds)

    root = tk.Tk()
    root.title("JiraBot - Revisao de Expediente")
    root.resizable(False, False)

    bg_color = "#f4f5f7"
    card_bg = "#ffffff"
    text_color = "#172b4d"
    subtext_color = "#5e6c84"
    primary_color = "#0052cc"
    danger_color = "#de350b"

    root.configure(bg=bg_color)

    w, h = 540, 420
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = max(0, (ws // 2) - (w // 2))
    y = max(0, (hs // 2) - (h // 2))
    root.geometry(f"{w}x{h}+{x}+{y}")

    # Garante que a janela suba para o topo
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()

    # Forca primeiro plano via API Win32
    try:
        import ctypes
        hwnd = root.winfo_id()
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.BringWindowToTop(hwnd)
    except Exception:
        pass

    # Sinal sonoro
    try:
        root.bell()
    except Exception:
        pass

    # Header Frame
    header_frame = tk.Frame(root, bg=bg_color, padx=20, pady=15)
    header_frame.pack(fill="x")

    lbl_title = tk.Label(
        header_frame,
        text="Encerramento de Expediente Proximo",
        font=("Segoe UI", 13, "bold"),
        fg=primary_color,
        bg=bg_color,
    )
    lbl_title.pack(anchor="w")

    lbl_sub = tk.Label(
        header_frame,
        text="Faltam aproximadamente 5 minutos para a janela de encerramento do seu turno.",
        font=("Segoe UI", 9),
        fg=subtext_color,
        bg=bg_color,
    )
    lbl_sub.pack(anchor="w", pady=(2, 0))

    # Card Frame
    card_frame = tk.Frame(root, bg=card_bg, padx=15, pady=12, relief="solid", bd=1)
    card_frame.pack(fill="x", padx=20, pady=5)

    info_text = f"Ticket Ativo: {active_issue}    |    Tempo Hoje: {worked_str}"
    lbl_info = tk.Label(
        card_frame,
        text=info_text,
        font=("Segoe UI", 10, "bold"),
        fg=text_color,
        bg=card_bg,
    )
    lbl_info.pack(anchor="w", pady=(0, 8))

    lbl_desc_prompt = tk.Label(
        card_frame,
        text="Descricao detalhada da atividade para o Jira Worklog:",
        font=("Segoe UI", 9),
        fg=subtext_color,
        bg=card_bg,
    )
    lbl_desc_prompt.pack(anchor="w", pady=(0, 4))

    txt_desc = tk.Text(card_frame, height=4, font=("Segoe UI", 9), wrap="word", relief="groove", bd=1)
    txt_desc.pack(fill="x")

    initial_text = current_desc if current_desc else (fallback_desc or "")
    if state.no_comment:
        initial_text = ""
    txt_desc.insert("1.0", initial_text)
    txt_desc.focus_set()

    lbl_status = tk.Label(root, text="", font=("Segoe UI", 8), fg="#00875a", bg=bg_color)
    lbl_status.pack(anchor="w", padx=25, pady=(4, 0))

    def on_save():
        new_text = txt_desc.get("1.0", "end-1c").strip()
        st = mgr.load_state()
        if new_text:
            st.no_comment = False
            st.set_issue_comment(active_issue, new_text)
        else:
            st.no_comment = False
        mgr.save_state(st)
        lbl_status.config(text=f"Descricao de {active_issue} salva com sucesso!", fg="#00875a")
        root.after(400, root.destroy)

    def on_keep():
        st = mgr.load_state()
        st.no_comment = False
        mgr.save_state(st)
        root.destroy()

    def on_no_comment():
        st = mgr.load_state()
        st.no_comment = True
        mgr.save_state(st)
        lbl_status.config(text="Configurado para enviar SEM descricao!", fg=danger_color)
        root.after(400, root.destroy)

    btn_frame = tk.Frame(root, bg=bg_color, padx=20, pady=12)
    btn_frame.pack(fill="x", side="bottom")

    btn_no_comment = tk.Button(
        btn_frame,
        text="Enviar sem Descricao",
        font=("Segoe UI", 9),
        fg=danger_color,
        bg="#ffffff",
        activebackground="#ffebe6",
        relief="groove",
        bd=1,
        padx=8,
        pady=5,
        command=on_no_comment,
    )
    btn_no_comment.pack(side="left")

    btn_save = tk.Button(
        btn_frame,
        text="Salvar Descricao",
        font=("Segoe UI", 9, "bold"),
        fg="#ffffff",
        bg=primary_color,
        activebackground="#0747a6",
        activeforeground="#ffffff",
        relief="flat",
        padx=12,
        pady=5,
        command=on_save,
    )
    btn_save.pack(side="right", padx=(6, 0))

    btn_keep = tk.Button(
        btn_frame,
        text="Manter Atual",
        font=("Segoe UI", 9),
        fg=text_color,
        bg="#ffffff",
        activebackground="#ebecf0",
        relief="groove",
        bd=1,
        padx=10,
        pady=5,
        command=on_keep,
    )
    btn_keep.pack(side="right")

    root.mainloop()


def show_pre_exit_popup(state_manager: Optional[StateManager] = None) -> None:
    """
    Dispara o popup grafico pre-saida em um processo GUI independente,
    garantindo execucao na thread principal e foco forcado no Windows 11.
    """
    try:
        cfg = BotConfig.load()
        send_notification(
            "JiraBot - Revisao de Expediente",
            "Faltam 5 minutos para o encerramento. Revise a descricao na janela aberta.",
            cfg.notifications_enabled,
        )

        python_exe = sys.executable
        pythonw = Path(python_exe).parent / "pythonw.exe"
        exe = str(pythonw) if pythonw.exists() else python_exe
        script = Path(__file__).resolve()

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [exe, str(script), "popup"],
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        logger.info("Processo GUI do popup pre-saida disparado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao disparar processo do popup pre-saida: {e}")


def prompt_history_worklogs_cli(default_days: int = 14) -> None:
    """
    Interface interativa de terminal para listar e editar descricoes de lancamentos
    anteriores (ultimos 7, 14, 30 dias ou periodo personalizado) diretamente no Jira.
    """
    cfg = BotConfig.load()
    client = JiraClient(cfg.jira)

    print("\n" + "=" * 70)
    print("      GERENCIADOR DE DESCRICOES DE LANCAMENTOS ANTERIORES NO JIRA")
    print("=" * 70)
    print("Escolha o periodo de busca:")
    print("  [1] Ultimos 7 dias (Semanal)")
    print("  [2] Ultimos 14 dias (Quinzena)")
    print("  [3] Ultimos 30 dias (Mensal)")
    print("  [4] Digitar quantidade de dias personalizada")
    print("  [0] Voltar ao Menu Principal")
    print("=" * 70)

    period_choice = input("Opcao [1-4 ou 0]: ").strip()
    if period_choice == "1":
        days = 7
    elif period_choice == "2":
        days = 14
    elif period_choice == "3":
        days = 30
    elif period_choice == "4":
        custom_input = input("Informe o numero de dias retroativos (ex: 45): ").strip()
        days = int(custom_input) if custom_input.isdigit() and int(custom_input) > 0 else default_days
    elif period_choice == "0" or not period_choice:
        return
    else:
        days = default_days

    print(f"\nBuscando lancamentos no Jira para os ultimos {days} dias...")
    worklogs = client.get_user_recent_worklogs(days=days)

    if not worklogs:
        print(f"\nNenhum lancamento de horas encontrado para o seu usuario nos ultimos {days} dias.")
        input("\nPressione Enter para voltar...")
        return

    while True:
        print("\n" + "=" * 75)
        print(f"       LANCAMENTOS ENCONTRADOS NO JIRA (ULTIMOS {days} DIAS) - TOTAL: {len(worklogs)}")
        print("=" * 75)

        for idx, w in enumerate(worklogs, 1):
            comment = w.get("comment", "").strip() or "(Sem descricao registrada)"
            if len(comment) > 65:
                comment_disp = comment[:62] + "..."
            else:
                comment_disp = comment

            print(f" [{idx:2d}] {w['date']} | {w['issue_key']:<13} | {w['time_spent']:<6} | \"{comment_disp}\"")

        print("=" * 75)
        sel = input("Digite o numero do lancamento para editar a descricao (ou 0 para voltar): ").strip()

        if not sel or sel == "0":
            break

        if not sel.isdigit() or int(sel) < 1 or int(sel) > len(worklogs):
            print("Numero invalido. Tente novamente.")
            continue

        selected_item = worklogs[int(sel) - 1]
        print("\n" + "-" * 65)
        print(f"--- EDITAR DESCRICAO DO LANCAMENTO #{sel} ---")
        print(f"Ticket        : {selected_item['issue_key']} - {selected_item.get('summary', '')}")
        print(f"Data / Tempo  : {selected_item['date']} | Tempo Apontado: {selected_item['time_spent']}")
        print(f"ID no Jira    : {selected_item['id']}")
        print(f"Descricao Atual: \"{selected_item.get('comment', '')}\"")
        print("-" * 65)

        new_comment = input("Digite a nova descricao detalhada (ou Enter para cancelar): ").strip()
        if not new_comment:
            print("Edicao cancelada. Nenhuma alteracao realizada.")
            continue

        print("\nEnviando atualizacao para o Jira...")
        success = client.update_worklog_comment(
            issue_key=selected_item["issue_key"],
            worklog_id=selected_item["id"],
            new_comment=new_comment,
        )

        if success:
            selected_item["comment"] = new_comment
            print(f"\n[SUCESSO] Descricao do lancamento #{sel} ({selected_item['issue_key']}) atualizada no Jira com sucesso!")
        else:
            print(f"\n[FALHA] Nao foi possivel atualizar o worklog no Jira. Verifique os logs para mais detalhes.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "popup":
        run_popup_gui()
    else:
        prompt_review_cli()

