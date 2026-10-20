"""
Modulo de Atualizacao Automatica e Isolamento Multi-Usuario do JiraBot.
Permite que todos os usuarios atualizem os arquivos de codigo do aplicativo (.py, .bat, assets)
via Repositorio Git, Pasta Compartilhada na Rede ou Pacote ZIP, mantendo 100% intactas e
isoladas as configuracoes e tokens individuais em %USERPROFILE%\\.jirabot\\config.json.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import io
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
import urllib.request
import zipfile

from config import BotConfig, get_default_config_dir

logger = logging.getLogger("JiraBot.Updater")

APP_VERSION = "2.2.0"
APP_DIR = Path(__file__).parent.resolve()

# Lista branca estrita de extensoes e arquivos de codigo permitidos em atualizacoes/publicacoes
ALLOWED_CODE_EXTENSIONS = {".py", ".bat", ".ico", ".png"}
ALLOWED_DOC_FILES = {"requirements.txt", "README.md", ".gitignore"}
FORBIDDEN_NAMES = {".env", "config.json", "state.json", "queue.json", "history.json", "worklog_schedules.json", "jirabot.pid", "jirabot.log"}
FORBIDDEN_DIRS = {"relatorios", "backupP", "backupCore", "__pycache__", ".git", ".venv", "venv"}


def _file_sha256(filepath: Path) -> str:
    """Calcula o hash SHA-256 de um arquivo para comparacao segura de versao."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_allowed_app_file(rel_path: Path) -> bool:
    """Verifica se um caminho relativo pertence estritamente ao codigo do aplicativo (sem dados sensiveis)."""
    for part in rel_path.parts:
        if part in FORBIDDEN_DIRS or part.startswith(".env"):
            return False
    if rel_path.name in FORBIDDEN_NAMES:
        return False
    if rel_path.suffix.lower() in ALLOWED_CODE_EXTENSIONS or rel_path.name in ALLOWED_DOC_FILES:
        return True
    return False


def list_local_app_files(base_dir: Path = APP_DIR) -> List[Path]:
    """Lista todos os arquivos de codigo/distribuicao limpos do aplicativo."""
    files: List[Path] = []
    for item in base_dir.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(base_dir)
        if is_allowed_app_file(rel):
            files.append(rel)
    files.sort()
    return files


def get_version_info() -> Dict[str, Any]:
    """Retorna metadados da versao atual, isolamento de configuracao do usuario e fonte de atualizacao."""
    cfg = BotConfig.load()
    user_cfg_dir = get_default_config_dir()
    has_git = (APP_DIR / ".git").exists()

    mtimes = []
    for rel in list_local_app_files(APP_DIR):
        try:
            mtimes.append((APP_DIR / rel).stat().st_mtime)
        except Exception:
            pass
    last_mod_str = datetime.fromtimestamp(max(mtimes)).strftime("%d/%m/%Y %H:%M:%S") if mtimes else "-"

    return {
        "version": APP_VERSION,
        "last_modified": last_mod_str,
        "app_dir": str(APP_DIR),
        "user_config_dir": str(user_cfg_dir),
        "user_config_file": str(user_cfg_dir / "config.json"),
        "current_windows_user": os.environ.get("USERNAME") or Path.home().name,
        "has_git": has_git,
        "update_source": cfg.update_source,
        "auto_update_on_start": cfg.auto_update_on_start,
    }


def check_for_updates(update_source: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifica se existem atualizacoes disponiveis na origem configurada (Pasta de Rede/Local, Git ou URL).
    """
    cfg = BotConfig.load()
    src = (update_source if update_source is not None else cfg.update_source).strip()

    # 1. Caso haja um caminho de pasta compartilhada / diretorio informado
    if src and not src.startswith(("http://", "https://", "git@")):
        src_path = Path(src)
        if not src_path.exists() or not src_path.is_dir():
            return {
                "success": False,
                "has_update": False,
                "message": f"Caminho de atualizacao nao encontrado ou inacessivel: {src}",
            }

        changed_files: List[str] = []
        remote_files = list_local_app_files(src_path)
        for rel in remote_files:
            remote_f = src_path / rel
            local_f = APP_DIR / rel
            if not local_f.exists():
                changed_files.append(str(rel))
            else:
                if _file_sha256(remote_f) != _file_sha256(local_f):
                    changed_files.append(str(rel))

        if changed_files:
            return {
                "success": True,
                "has_update": True,
                "mode": "folder",
                "changed_files": changed_files,
                "message": f"Atualizacao disponivel! {len(changed_files)} arquivo(s) modificado(s) na origem: {', '.join(changed_files)}",
            }
        return {
            "success": True,
            "has_update": False,
            "mode": "folder",
            "changed_files": [],
            "message": "Seu aplicativo ja esta na versao mais recente disponivel na pasta de origem.",
        }

    # 2. Caso seja um repositorio Git local
    if (APP_DIR / ".git").exists():
        try:
            subprocess.run(["git", "fetch"], cwd=str(APP_DIR), capture_output=True, text=True, timeout=15)
            proc = subprocess.run(
                ["git", "rev-list", "HEAD...@{u}", "--count"],
                cwd=str(APP_DIR),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                behind = int(proc.stdout.strip() or "0")
                if behind > 0:
                    return {
                        "success": True,
                        "has_update": True,
                        "mode": "git",
                        "behind_commits": behind,
                        "message": f"Atualizacao disponivel via Git ({behind} novo(s) commit(s) no repositorio remoto).",
                    }
                return {
                    "success": True,
                    "has_update": False,
                    "mode": "git",
                    "message": "Seu aplicativo ja esta atualizado com a ultima versao do repositorio Git.",
                }
        except Exception as e:
            return {"success": False, "has_update": False, "message": f"Erro ao consultar Git: {e}"}

    # 3. Caso seja uma URL HTTP/HTTPS de pacote .zip
    if src.startswith(("http://", "https://")) and src.lower().endswith(".zip"):
        return {
            "success": True,
            "has_update": True,
            "mode": "zip_url",
            "message": f"Pacote remoto configurado ({src}). Clique em 'Atualizar Aplicativo Agora' para baixar e aplicar.",
        }

    return {
        "success": False,
        "has_update": False,
        "message": "Nenhuma fonte de atualizacao configurada. Informe uma Pasta Compartilhada na Rede, URL de pacote .zip ou inicialize um repositorio Git.",
    }


def perform_update(update_source: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa a atualizacao dos arquivos do aplicativo preservando 100% das configuracoes
    individuais e tokens de cada usuario em %USERPROFILE%\\.jirabot.
    """
    cfg = BotConfig.load()
    src = (update_source if update_source is not None else cfg.update_source).strip()
    if update_source is not None and src != cfg.update_source:
        cfg.update_source = src
        cfg.save()

    # Modo 1: Pasta Compartilhada na Rede / Diretorio Local (OneDrive, SharePoint, SMB)
    if src and not src.startswith(("http://", "https://", "git@")):
        src_path = Path(src)
        if not src_path.exists() or not src_path.is_dir():
            return {"success": False, "message": f"Pasta de origem nao encontrada: {src}"}

        updated_files: List[str] = []
        for rel in list_local_app_files(src_path):
            remote_f = src_path / rel
            local_f = APP_DIR / rel
            if not local_f.exists() or _file_sha256(remote_f) != _file_sha256(local_f):
                local_f.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(remote_f, local_f)
                updated_files.append(str(rel))

        if not updated_files:
            return {
                "success": True,
                "updated_count": 0,
                "message": "Nenhum arquivo precisou ser atualizado. Voce ja possui a versao mais recente!",
            }
        return {
            "success": True,
            "updated_count": len(updated_files),
            "updated_files": updated_files,
            "message": f"Aplicativo atualizado com sucesso! {len(updated_files)} arquivo(s) atualizado(s) ({', '.join(updated_files)}). Suas configuracoes pessoais e token foram preservados.",
        }

    # Modo 2: URL HTTP/HTTPS apontando para um pacote .zip
    if src.startswith(("http://", "https://")) and src.lower().endswith(".zip"):
        try:
            req = urllib.request.Request(src, headers={"User-Agent": f"JiraBot-Updater/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                zip_bytes = resp.read()

            updated_files = []
            with tempfile.TemporaryDirectory() as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                    zf.extractall(tmp_dir)

                # Localiza a raiz dos arquivos .py dentro do zip
                root_dir = tmp_dir
                sub_items = [p for p in tmp_dir.iterdir() if p.is_dir()]
                if len(sub_items) == 1 and not list(tmp_dir.glob("*.py")):
                    root_dir = sub_items[0]

                for rel in list_local_app_files(root_dir):
                    remote_f = root_dir / rel
                    local_f = APP_DIR / rel
                    if not local_f.exists() or _file_sha256(remote_f) != _file_sha256(local_f):
                        local_f.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(remote_f, local_f)
                        updated_files.append(str(rel))

            return {
                "success": True,
                "updated_count": len(updated_files),
                "updated_files": updated_files,
                "message": f"Atualizacao via pacote ZIP concluida! {len(updated_files)} arquivo(s) atualizado(s). Configuracoes individuais preservadas.",
            }
        except Exception as e:
            return {"success": False, "message": f"Falha ao baixar/extrair pacote de atualizacao: {e}"}

    # Modo 3: Repositorio Git
    if (APP_DIR / ".git").exists():
        try:
            proc = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(APP_DIR),
                capture_output=True,
                text=True,
                timeout=25,
            )
            if proc.returncode == 0:
                out = (proc.stdout or "").strip()
                return {
                    "success": True,
                    "message": f"Atualizacao via Git concluida com sucesso!\n{out}\nSuas configuracoes pessoais em ~/.jirabot foram preservadas.",
                }
            return {
                "success": False,
                "message": f"Nao foi possivel executar git pull automaticamente: {proc.stderr or proc.stdout}",
            }
        except Exception as e:
            return {"success": False, "message": f"Erro ao executar git pull: {e}"}

    return {
        "success": False,
        "message": "Configure primeiro uma Pasta de Origem na Rede ou inicialize um repositorio Git para atualizar.",
    }


def publish_clean_release(target_dir: str) -> Dict[str, Any]:
    """
    Publica/copia apenas os arquivos de codigo limpos (.py, .bat, assets, README, requirements)
    para uma pasta compartilhada de distribuicao, garantindo que NENHUM token, .env, config.json
    ou relatorio pessoal seja enviado.
    """
    clean_target = (target_dir or "").strip()
    if not clean_target:
        return {"success": False, "message": "Informe o caminho da pasta compartilhada de destino."}

    dest_path = Path(clean_target).resolve()
    if dest_path == APP_DIR:
        return {"success": False, "message": "A pasta de destino nao pode ser a propria pasta local de execucao."}

    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        copied_files: List[str] = []
        for rel in list_local_app_files(APP_DIR):
            src_f = APP_DIR / rel
            dst_f = dest_path / rel
            dst_f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_f, dst_f)
            copied_files.append(str(rel))

        return {
            "success": True,
            "published_count": len(copied_files),
            "published_files": copied_files,
            "target_dir": str(dest_path),
            "message": f"Publicacao limpa concluida! {len(copied_files)} arquivo(s) do aplicativo copiados para '{dest_path}' (zero tokens ou dados pessoais incluidos).",
        }
    except Exception as e:
        return {"success": False, "message": f"Erro ao publicar arquivos na pasta de destino: {e}"}
