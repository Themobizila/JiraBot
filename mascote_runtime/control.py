"""Preferências, eventos e processo do mascote. Não lê configuração do Jira."""
import argparse
from functools import wraps
from contextlib import contextmanager
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

BASE = Path.home() / ".jirabot"
PROJECT = Path(__file__).resolve().parent.parent
DEFAULTS = {"enabled": False, "theme": "auto", "web_theme": "auto", "size": 180,
            "reduced_motion": False, "roaming": False, "position": None}


def read_json(path, fallback):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return value if isinstance(value, type(fallback)) else fallback
    except (OSError, ValueError):
        return fallback


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


@contextmanager
def settings_lock(base, timeout=5):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    with (base / "mascote.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b"0")
            stream.flush()
        if sys.platform == "win32":
            import msvcrt
            until = time.monotonic() + timeout
            while True:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= until:
                        raise TimeoutError("Controle do mascote ocupado. Tente novamente.")
                    time.sleep(0.03)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def preferences(base=BASE):
    data = read_json(Path(base) / "mascote_settings.json", {})
    result = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in data:
            try:
                validate_changes({key: data[key]})
                result[key] = data[key]
            except (ValueError, TypeError):
                pass
    return result


def validate_changes(changes):
    if not isinstance(changes, dict) or set(changes) - set(DEFAULTS):
        raise ValueError("Opção de mascote desconhecida.")
    for key in ("enabled", "reduced_motion", "roaming"):
        if key in changes and type(changes[key]) is not bool:
            raise ValueError(key + " deve ser booleano.")
    if changes.get("roaming") is True:
        raise ValueError("O passeio no solo é automático; use movimento reduzido para pausá-lo.")
    for key in ("theme", "web_theme"):
        if key in changes and changes[key] not in {"auto", "normal", "dark", "light", "halloween", "natal", "ano_novo", "pascoa"}:
            raise ValueError("Tema desconhecido.")
    if "size" in changes and (type(changes["size"]) is not int or not 96 <= changes["size"] <= 320):
        raise ValueError("Tamanho deve estar entre 96 e 320.")
    if "position" in changes and changes["position"] is not None:
        p = changes["position"]
        if not isinstance(p, list) or len(p) != 2 or any(type(v) is not int or abs(v) > 100000 for v in p):
            raise ValueError("Posição inválida.")


def update_preferences(changes, base=BASE):
    validate_changes(changes)
    with settings_lock(base):
        prefs = preferences(base)
        prefs.update(changes)
        atomic_json(Path(base) / "mascote_settings.json", prefs)
    return prefs


def status(base=BASE):
    prefs = preferences(base)
    runtime = read_json(Path(base) / "mascote_runtime.json", {})
    heartbeat = runtime.get("heartbeat", 0)
    fresh = isinstance(heartbeat, (int, float)) and 0 <= time.time() - heartbeat < 4
    phase = runtime.get("phase", "stopped") if fresh or runtime.get("phase") == "error" else "stopped"
    return {"preferences": prefs, "running": phase == "running" and runtime.get("visible", False), "visible": bool(fresh and runtime.get("visible", False)), "phase": phase,
            "message": runtime.get("message", "") if fresh or runtime.get("phase") == "error" else "",
            "action": runtime.get("action", "idle") if fresh else "idle"}


def launch(base=BASE, activate=True):
    base = Path(base)
    from .catalog import load_catalog
    load_catalog()  # Valida arquivos antes de criar processo ou ativar preferência.
    with settings_lock(base):
        prefs = preferences(base)
        if not activate and not prefs["enabled"]:
            return status(base)
        prefs["enabled"] = True
        atomic_json(base / "mascote_settings.json", prefs)
        current = status(base)
        if current["phase"] in {"starting", "running", "suspended"}:
            return current
        atomic_json(base / "mascote_runtime.json", {"phase": "starting", "heartbeat": time.time(), "message": "Abrindo mascote..."})
        exe = Path(sys.executable)
        if exe.with_name("pythonw.exe").exists():
            exe = exe.with_name("pythonw.exe")
        try:
            startup = None
            if sys.platform == "win32":
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 4  # Mostra o personagem sem tomar foco.
            with (base / "mascote_errors.log").open("a", encoding="utf-8") as errors:
                subprocess.Popen([str(exe), "-m", "mascote_runtime", "run", "--base", str(base)],
                                 cwd=str(PROJECT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=errors, startupinfo=startup,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            atomic_json(base / "mascote_runtime.json", {"phase": "error", "heartbeat": time.time(), "message": "Não foi possível abrir o processo do mascote."})
            raise RuntimeError("Não foi possível iniciar o mascote.") from exc
    return status(base)


def configure(changes, base=BASE):
    validate_changes(changes)
    # Confirmar disponibilidade antes de persistir a ativação.
    if changes.get("enabled") is True:
        from .catalog import load_catalog
        load_catalog()
    update_preferences(changes, base)
    if preferences(base)["enabled"]:
        return launch(base, activate=False)
    return status(base)


def publish_event(name, base=BASE, activity_id=None):
    """Melhor esforço; erros visuais nunca interrompem operação de horas."""
    try:
        if not preferences(base)["enabled"]:
            return
        with settings_lock(base, timeout=0.05):
            path = Path(base) / "mascote_events.json"
            events = read_json(path, [])[-31:]
            events.append({"id": uuid.uuid4().hex, "name": name, "day": date.today().isoformat(), "at": time.time(), "activity_id": activity_id})
            atomic_json(path, events)
    except Exception:
        pass


def worklog_activity(method):
    """Publica somente início/fim e identificador aleatório, sem payload do Jira."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        operation = uuid.uuid4().hex
        manager = getattr(self, "state_manager", None)
        if manager is None:
            return method(self, *args, **kwargs)
        base = manager.base_dir
        try:
            publish_event("jira_request_start", base, activity_id=operation)
        except Exception:
            pass
        try:
            return method(self, *args, **kwargs)
        finally:
            try:
                publish_event("jira_request_end", base, activity_id=operation)
            except Exception:
                pass
    return wrapped


def snapshot(base=BASE):
    """Lê somente estado diário; nunca lê configuração ou dados de acesso."""
    data = read_json(Path(base) / "state.json", {})
    service = read_json(Path(base) / "mascote_service.json", {})
    if service and (not service.get("running") or time.time() - service.get("heartbeat", 0) > 40):
        return {"date_str": date.today().isoformat(), "status": "IDLE", "target_issue": ""}
    if data.get("date_str") != date.today().isoformat():
        return {"date_str": date.today().isoformat(), "status": "IDLE", "target_issue": ""}
    return {k: data.get(k) for k in ("date_str", "status", "target_issue")}


def service_heartbeat(running, base=BASE):
    try:
        atomic_json(Path(base) / "mascote_service.json", {"running": running, "heartbeat": time.time()})
    except OSError:
        pass


def command(argv=None):
    parser = argparse.ArgumentParser(description="Mascote do JiraBot")
    parser.add_argument("action", nargs="?", default="status", choices=["status", "on", "off", "toggle", "run", "demo"])
    parser.add_argument("--theme", choices=["auto", "normal", "halloween", "natal", "ano_novo", "pascoa"])
    parser.add_argument("--size", type=int)
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--seconds", type=int, default=0, help="Duração da demonstração; 0 mantém aberta")
    args = parser.parse_args(argv)
    if args.action in {"run", "demo"}:
        from .window import run
        if args.action == "demo" and args.base == BASE:
            import tempfile
            with tempfile.TemporaryDirectory(prefix="jirabot-mascote-demo-") as temp:
                run(Path(temp), demo=True, seconds=args.seconds, theme=args.theme or "normal")
        else:
            run(args.base, demo=args.action == "demo", seconds=args.seconds, theme=args.theme)
        return
    changes = {}
    if args.theme:
        changes["theme"] = args.theme
    if args.size:
        changes["size"] = args.size
    if args.reduced_motion:
        changes["reduced_motion"] = True
    if args.action != "status":
        changes["enabled"] = args.action == "on" or (args.action == "toggle" and not preferences(args.base)["enabled"])
    try:
        result = configure(changes, args.base) if changes else status(args.base)
        label = "ativo" if result["running"] else ("iniciando" if result["phase"] == "starting" else "fechado")
        print("Mascote: " + label + "; preferência: " + ("ativado" if result["preferences"]["enabled"] else "desativado"))
        if result["message"]:
            print(result["message"])
    except (ValueError, RuntimeError, OSError) as exc:
        print("Mascote: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
