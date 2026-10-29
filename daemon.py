"""
Modulo de gerenciamento e execucao do servico em segundo plano (Daemon) para o JiraBot.
Possui protecao de instancia unica via Win32 Named Mutex.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from config import BotConfig, get_default_config_dir
from engine import BotEngine
from jira_client import JiraClient
from storage import StateManager
from tray import SystemTrayIcon
from watcher import SessionWatcher

logger = logging.getLogger("JiraBot.Daemon")

MUTEX_NAME = "Local\\JiraBot_SingleInstance_Mutex_Session"
ERROR_ALREADY_EXISTS = 183


def get_pid_file() -> Path:
    """Retorna o caminho do arquivo de PID do servico JiraBot."""
    return get_default_config_dir() / "jirabot.pid"


def get_log_file() -> Path:
    """Retorna o caminho do arquivo de log do JiraBot."""
    return get_default_config_dir() / "jirabot.log"


def is_process_running(pid: int) -> bool:
    """Verifica com precisao se um processo com o PID informado ainda esta em execucao no Windows."""
    if pid <= 0:
        return False
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def kill_process(pid: int) -> bool:
    """Finaliza um processo com garantia no Windows utilizando Win32 API."""
    if not is_process_running(pid):
        return True
    try:
        PROCESS_TERMINATE = 0x0001
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            kernel32.TerminateProcess(handle, 1)
            kernel32.CloseHandle(handle)
            time.sleep(0.5)
            return not is_process_running(pid)
    except Exception:
        pass
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    return not is_process_running(pid)


def get_source_files_mtime() -> float:
    """Retorna o timestamp mais recente de modificacao dos arquivos .py do projeto."""
    project_dir = Path(__file__).parent
    mtimes = []
    for p in project_dir.glob("*.py"):
        try:
            mtimes.append(p.stat().st_mtime)
        except Exception:
            pass
    return max(mtimes) if mtimes else 0.0


def setup_logging(log_to_file: bool = True) -> None:
    """Configura o sistema de logs do JiraBot."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_to_file:
        handlers.append(logging.FileHandler(get_log_file(), encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


class JiraBotService:
    """Servico principal que integra o Watcher, Engine, TrayIcon e JiraClient."""

    def __init__(self, enable_tray: bool = True):
        self.config = BotConfig.load()
        self.state_manager = StateManager()
        self.jira_client = JiraClient(self.config.jira, self.state_manager)

        self.engine = BotEngine(
            config=self.config,
            state_manager=self.state_manager,
            on_worklog_trigger=self._handle_worklog_trigger,
        )

        self.watcher = SessionWatcher(
            on_lock=self.engine.handle_lock,
            on_unlock=self.engine.handle_unlock,
            on_shutdown=self.engine.handle_shutdown,
        )

        self.enable_tray = enable_tray
        self.tray = SystemTrayIcon(engine=self.engine, on_exit_request=self.stop) if enable_tray else None
        self._running = False
        self._mutex_handle = None
        self._web_server = None
        self._start_mtime = get_source_files_mtime()

    def _handle_worklog_trigger(
        self,
        issue_key: str,
        total_seconds: int,
        started_iso: str,
        comment: Optional[str] = None,
    ) -> bool:
        """Callback acionado pelo Engine quando um worklog deve ser enviado."""
        try:
            is_empty = (comment == "__EMPTY__")
            res = self.jira_client.submit_worklog(
                issue_key=issue_key,
                time_spent_seconds=total_seconds,
                started_iso=started_iso,
                comment="" if is_empty else (comment or self.config.jira.default_comment),
                no_comment=is_empty,
            )
            ok = res.get("status") == "success"
            wid = str(res.get("worklog_id") or "")
            if ok and wid and self.engine and self.engine.state:
                if wid not in self.engine.state.jira_worklog_ids:
                    self.engine.state.jira_worklog_ids.append(wid)
                shift_times = self.engine.state.get_shift_times_summary()
                if shift_times.get("start_hm"):
                    self.state_manager.save_worklog_schedule(wid, shift_times)
                    self.state_manager.save_day_shift_schedule(self.engine.state.date_str, shift_times)
            return ok
        except Exception as e:
            logger.warning(f"Envio imediato falhou para {issue_key}, item sera mantido na fila offline: {e}")
            return False

    def _trigger_auto_reload(self) -> None:
        """Reinicia o servico de forma transparente ao detectar mudanca de codigo no disco."""
        logger.info("Reiniciando servico automaticamente para carregar o novo codigo...")
        self.stop()
        time.sleep(1.0)
        if len(sys.argv) > 1 and sys.argv[1] == "run-daemon":
            start_background()
        else:
            subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    def run_foreground(self) -> None:
        """Executa o servico garantindo instancia unica via Mutex Win32."""
        kernel32 = ctypes.windll.kernel32
        self._mutex_handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.warning("Outra instancia do JiraBot ja esta em execucao. Encerrando instancia duplicada.")
            return

        pid = os.getpid()
        get_pid_file().write_text(str(pid), encoding="utf-8")
        self._running = True

        try:
            from mini_window import _attach_to_interactive_desktop
            _attach_to_interactive_desktop()
        except Exception:
            pass

        logger.info(f"Iniciando JiraBot Service (PID: {pid})...")
        logger.info(f"Perfil ativo: {self.config.active_profile}")

        if self.config.auto_update_on_start and self.config.update_source:
            try:
                from updater import perform_update
                upd_res = perform_update(self.config.update_source)
                if upd_res.get("updated_count", 0) > 0:
                    logger.info(f"Auto-update aplicado na inicializacao: {upd_res.get('message')}")
                    self._start_mtime = get_source_files_mtime()
            except Exception as e:
                logger.debug(f"Falha ao verificar auto-update na inicializacao: {e}")

        try:
            self.engine.refresh_state()
            if (
                self.engine.state.status == "COMPLETED"
                and not self.engine.state.is_logged
                and self.config.auto_log_on_exit
                and self.engine.state.get_total_seconds() > 0
            ):
                logger.info("Expediente de hoje ja concluido (ex: desligamento do PC) e pendente de envio. Sincronizando...")
                self.engine._trigger_worklog_all_issues()
            elif (
                self.engine.state.status == "PAUSED_AWAY"
                and self.engine.state.last_event == "PAUSED_SHUTDOWN"
            ):
                logger.info("Retomando contagem apos reinicializacao do sistema no meio do expediente...")
                self.engine.handle_unlock()

            self.jira_client.flush_queue()
        except Exception as e:
            logger.debug(f"Erro ao sincronizar fila inicial: {e}")

        # Inicia o servidor HTTP do Painel Web em thread daemon integrada ao servico
        try:
            from web_panel import start_embedded_web_server
            self._web_server = start_embedded_web_server(port=8765)
        except Exception as e:
            logger.warning(f"Nao foi possivel iniciar servidor Web integrado na porta 8765: {e}")

        self.watcher.start()
        if self.tray:
            self.tray.start()

        def signal_handler(signum, frame):
            logger.info("Sinal de interrupcao recebido. Encerrando servico...")
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while self._running:
                time.sleep(15)
                try:
                    # Watchdog de codigo: detecta se os arquivos .py foram alterados no disco
                    current_mtime = get_source_files_mtime()
                    if self._start_mtime > 0 and current_mtime > self._start_mtime:
                        logger.info("Detectada atualizacao nos arquivos de codigo (.py). Aguardando estabilizacao...")
                        time.sleep(2.0)
                        self._trigger_auto_reload()
                        break

                    self.engine.check_scheduled_transitions()
                    self.jira_client.flush_queue()
                except Exception:
                    pass
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Finaliza o servico graciosamente e libera o Mutex."""
        if not self._running:
            return
        self._running = False
        self.watcher.stop()
        if self.tray:
            self.tray.stop()
        if self._web_server:
            try:
                self._web_server.shutdown()
                self._web_server.server_close()
            except Exception:
                pass
            self._web_server = None

        if self._mutex_handle:
            ctypes.windll.kernel32.ReleaseMutex(self._mutex_handle)
            ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None

        pid_file = get_pid_file()
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass
        logger.info("JiraBot Service finalizado com sucesso.")


def start_background() -> int:
    """Inicia o servico desacoplado em segundo plano usando pythonw.exe com protecao anti-duplicidade."""
    pid_file = get_pid_file()
    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text().strip())
            if is_process_running(existing_pid):
                return existing_pid
        except Exception:
            pass

    python_exe = sys.executable
    pythonw_exe = Path(python_exe).parent / "pythonw.exe"
    executable = str(pythonw_exe) if pythonw_exe.exists() else python_exe

    script_path = Path(__file__).resolve()
    cmd = [executable, str(script_path), "run-daemon"]

    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0

    proc = subprocess.Popen(
        cmd,
        cwd=str(script_path.parent),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )

    time.sleep(1.0)
    pid = proc.pid
    pid_file.write_text(str(pid), encoding="utf-8")
    return pid


def stop_background() -> bool:
    """Interrompe todas as instancias em segundo plano com garantia de encerramento."""
    pid_file = get_pid_file()
    killed = False

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            killed = kill_process(pid)
        except Exception:
            pass
        finally:
            if pid_file.exists():
                try:
                    pid_file.unlink()
                except Exception:
                    pass

    return killed


def restart_background() -> int:
    """Interrompe a instancia atual em segundo plano e inicia uma nova instancia limpa."""
    stop_background()
    time.sleep(1.0)
    return start_background()


def get_status() -> dict:
    """Retorna o status operacional do servico."""
    pid_file = get_pid_file()
    is_running = False
    pid = None

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            is_running = is_process_running(pid)
            if not is_running:
                pid_file.unlink()
                pid = None
        except Exception:
            pid = None

    state_mgr = StateManager()
    state = state_mgr.load_state()
    queue = state_mgr.load_queue()
    config = BotConfig.load()

    return {
        "is_running": is_running,
        "pid": pid,
        "active_profile": config.active_profile,
        "daily_status": state.status,
        "date": state.date_str,
        "total_seconds": state.get_total_seconds(),
        "is_logged": state.is_logged,
        "target_issue": state.target_issue or config.jira.default_issue,
        "seconds_by_issue": state.get_seconds_by_issue(default_issue=config.jira.default_issue),
        "last_event": state.last_event,
        "last_event_time": state.last_event_time,
        "pending_queue_count": len(queue),
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run-daemon":
        setup_logging(log_to_file=True)
        service = JiraBotService(enable_tray=True)
        service.run_foreground()
