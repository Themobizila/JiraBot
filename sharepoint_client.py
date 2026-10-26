"""
Modulo de integracao nativa com Microsoft SharePoint Online / OneDrive via Microsoft Graph API.
Utiliza MSAL PublicClientApplication com cache persistente por usuario (%USERPROFILE%\\.jirabot)
para baixar documentos .docx vivos da DDS e imagens de pastas compartilhadas sem expor tokens.
"""

from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from config import get_default_config_dir

logger = logging.getLogger("JiraBot.SharePointClient")

# Client ID oficial do Microsoft Graph Command Line Tools (o dono no Azure AD e o proprio Microsoft Graph, evitando AADSTS65002)
MS_GRAPH_CLI_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
# Client ID publico oficial do Azure CLI (amplamente pre-autorizado em locatarios corporativos)
AZURE_CLI_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
# ID publico do Microsoft Office (legado)
MS_OFFICE_CLIENT_ID = "d3590ed6-52b3-4102-aeff-aad2292ab01c"

DEFAULT_CLIENT_ID = MS_GRAPH_CLI_CLIENT_ID

# Escopos delegados de menor privilegio (Files.Read permite leitura de arquivos aos quais o usuario ja tem acesso, sem exigir consentimento de admin)
SHAREPOINT_SCOPES = [
    "https://graph.microsoft.com/Files.Read",
    "https://graph.microsoft.com/User.Read",
]
DEFAULT_AUTHORITY = "https://login.microsoftonline.com/organizations"


def encode_sharepoint_sharing_url(url: str) -> str:
    """
    Codifica uma URL de compartilhamento do SharePoint/OneDrive no formato oficial shareId (u!base64url)
    exigido pelo endpoint /v1.0/shares/{shareId}/driveItem do Microsoft Graph.
    """
    clean = (url or "").strip()
    encoded = base64.urlsafe_b64encode(clean.encode("utf-8")).decode("ascii").rstrip("=")
    return f"u!{encoded}"


def build_candidate_share_ids(url: str) -> List[str]:
    """Gera candidatos de shareId preservando primeiro o token ?e=... e depois a URL limpa."""
    raw = (url or "").strip()
    if not raw:
        return []

    candidates_urls: List[str] = []

    # Remove apenas action=embedview caso tenha sido anexado artificialmente
    cleaned_embed = re.sub(r"([?&])action=embedview(&?)", lambda m: m.group(1) if m.group(2) else "", raw)
    cleaned_embed = cleaned_embed.rstrip("?&")
    if cleaned_embed:
        candidates_urls.append(cleaned_embed)

    if raw not in candidates_urls:
        candidates_urls.append(raw)

    base_no_query = raw.split("?")[0].strip()
    if base_no_query and base_no_query not in candidates_urls:
        candidates_urls.append(base_no_query)

    share_ids: List[str] = []
    for u in candidates_urls:
        sid = encode_sharepoint_sharing_url(u)
        if sid not in share_ids:
            share_ids.append(sid)
    return share_ids


class SharePointManager:
    """
    Gerencia autenticacao OAuth2 Microsoft 365 (com renovacao automatica via Refresh Token)
    e sincronizacao de documentos .docx e evidencias do SharePoint Online.
    """

    _lock = threading.Lock()
    _pending_flow: Optional[Dict[str, Any]] = None
    _last_auth_error: str = ""
    _auth_in_progress: bool = False

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_default_config_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.token_cache_path = self.base_dir / "msal_sharepoint_cache.bin"
        self.auth_meta_path = self.base_dir / "sharepoint_auth_meta.json"
        self.docx_cache_dir = self.base_dir / "dds_docx_cache"
        self.docx_cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_auth_meta(self) -> Dict[str, Any]:
        if self.auth_meta_path.exists():
            try:
                return json.loads(self.auth_meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_auth_meta(self, meta: Dict[str, Any]) -> None:
        try:
            self.auth_meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Falha ao salvar metadados de sessao SharePoint: %s", e)

    def _load_msal_cache(self):
        try:
            import msal
        except ImportError:
            raise RuntimeError("Biblioteca 'msal' nao encontrada. Execute 'pip install -r requirements.txt' para habilitar a integracao com o SharePoint Online.")

        cache = msal.SerializableTokenCache()
        if self.token_cache_path.exists():
            try:
                cache.deserialize(self.token_cache_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Cache MSAL corrompido ou invalido, reiniciando cache: %s", e)
        return cache

    def _save_msal_cache(self, cache: Any) -> None:
        if getattr(cache, "has_state_changed", False):
            try:
                self.token_cache_path.write_text(cache.serialize(), encoding="utf-8")
            except Exception as e:
                logger.warning("Falha ao persistir cache MSAL: %s", e)

    def _build_app(self, client_id: Optional[str] = None, authority: Optional[str] = None):
        try:
            import msal
        except ImportError:
            raise RuntimeError("Biblioteca 'msal' nao encontrada. Execute 'pip install -r requirements.txt' para habilitar a integracao com o SharePoint Online.")

        meta = self._load_auth_meta()
        cid = client_id or meta.get("client_id") or MS_OFFICE_CLIENT_ID
        auth = authority or meta.get("authority") or DEFAULT_AUTHORITY
        cache = self._load_msal_cache()
        app = msal.PublicClientApplication(cid, authority=auth, token_cache=cache)
        return app, cache, cid, auth

    def _acquire_silent_token(self) -> Tuple[Optional[str], str]:
        """
        Tenta obter token valido silenciosamente via MSAL (usa Refresh Token automaticamente).
        Retorna (token_ou_None, email_da_conta). Nunca registra o valor do token em logs.
        """
        try:
            for candidate_cid in [None, MS_GRAPH_CLI_CLIENT_ID, AZURE_CLI_CLIENT_ID, MS_OFFICE_CLIENT_ID]:
                app, cache, _, _ = self._build_app(client_id=candidate_cid)
                accounts = app.get_accounts()
                if not accounts:
                    continue
                for acc in accounts:
                    res = app.acquire_token_silent(SHAREPOINT_SCOPES, account=acc)
                    if res and "access_token" in res:
                        self._save_msal_cache(cache)
                        username = acc.get("username") or self._load_auth_meta().get("account") or "Conta Microsoft 365"
                        return res["access_token"], username
        except Exception as e:
            logger.warning("Falha ao renovar sessao silenciosa do SharePoint: %s", e)
        return None, ""

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status publico e seguro da conexao Microsoft 365 (sem jamais incluir tokens)."""
        token, username = self._acquire_silent_token()
        connected = bool(token)
        # Descarta referencia local imediatamente
        token = None

        with SharePointManager._lock:
            pending = None
            if SharePointManager._pending_flow and SharePointManager._auth_in_progress:
                expires_at = SharePointManager._pending_flow.get("expires_at", 0)
                if time.time() < expires_at:
                    pending = {
                        "user_code": SharePointManager._pending_flow.get("user_code", ""),
                        "verification_uri": SharePointManager._pending_flow.get("verification_uri", "https://microsoft.com/devicelogin"),
                        "expires_in": max(0, int(expires_at - time.time())),
                    }
                else:
                    SharePointManager._pending_flow = None
                    SharePointManager._auth_in_progress = False

            last_err = SharePointManager._last_auth_error

        return {
            "connected": connected,
            "account": username if connected else "",
            "auth_in_progress": bool(SharePointManager._auth_in_progress),
            "pending_device_flow": pending,
            "last_error": "" if connected else last_err,
        }

    def disconnect(self) -> Dict[str, Any]:
        """Remove o cache de autenticacao Microsoft 365 do usuario local."""
        with SharePointManager._lock:
            SharePointManager._pending_flow = None
            SharePointManager._auth_in_progress = False
            SharePointManager._last_auth_error = ""
        try:
            if self.token_cache_path.exists():
                self.token_cache_path.unlink()
            if self.auth_meta_path.exists():
                self.auth_meta_path.unlink()
        except Exception as e:
            return {"success": False, "error": f"Falha ao desconectar conta Microsoft 365: {e}"}
        return {"success": True, "message": "Conta Microsoft 365 desconectada com sucesso."}

    def start_login(
        self,
        mode: str = "device",
        login_hint: str = "",
        profile: str = "graph_cli",
        custom_client_id: str = "",
    ) -> Dict[str, Any]:
        """
        Inicia a autenticacao OAuth2 Microsoft 365 em background:
        - profile='graph_cli': Microsoft Graph Command Line Tools (14d82eec-204b-4c2f-b7e8-296a70dab67e, nativo do Graph, sem erro AADSTS65002).
        - profile='azure_cli': Microsoft Azure CLI (04b07795-8ddb-461a-bbee-02f9e1bf7b46).
        - custom_client_id: Client ID proprio cadastrado no Azure Portal.
        - mode='device': Device Code Flow (padrao).
        - mode='interactive': Loopback SSO no navegador padrao.
        """
        token, username = self._acquire_silent_token()
        if token:
            token = None
            return {
                "success": True,
                "already_connected": True,
                "connected": True,
                "account": username,
                "message": f"Já conectado ao Microsoft 365 ({username}).",
            }

        authority = DEFAULT_AUTHORITY
        clean_hint = (login_hint or "").strip()

        if custom_client_id and custom_client_id.strip():
            target_cid = custom_client_id.strip()
        elif profile == "azure_cli":
            target_cid = AZURE_CLI_CLIENT_ID
        elif profile == "office":
            target_cid = MS_OFFICE_CLIENT_ID
        else:
            target_cid = MS_GRAPH_CLI_CLIENT_ID

        if mode == "interactive":
            with SharePointManager._lock:
                SharePointManager._last_auth_error = ""
                SharePointManager._auth_in_progress = True
                SharePointManager._pending_flow = None

            def _run_interactive() -> None:
                try:
                    app, cache, cid, auth = self._build_app(client_id=target_cid, authority=authority)
                    kwargs: Dict[str, Any] = {"scopes": SHAREPOINT_SCOPES, "timeout": 180}
                    if clean_hint and "@" in clean_hint:
                        kwargs["login_hint"] = clean_hint
                    res = app.acquire_token_interactive(**kwargs)
                    if res and "access_token" in res:
                        self._save_msal_cache(cache)
                        claims = res.get("id_token_claims") or {}
                        acc_name = claims.get("preferred_username") or claims.get("upn") or clean_hint or "Microsoft 365"
                        self._save_auth_meta({
                            "client_id": cid,
                            "authority": auth,
                            "account": acc_name,
                            "connected_at": datetime.now().isoformat(),
                        })
                        with SharePointManager._lock:
                            SharePointManager._last_auth_error = ""
                    else:
                        err_desc = (res or {}).get("error_description") or (res or {}).get("error") or "Autenticação cancelada ou recusada."
                        with SharePointManager._lock:
                            SharePointManager._last_auth_error = str(err_desc).splitlines()[0][:240]
                except Exception as e:
                    with SharePointManager._lock:
                        SharePointManager._last_auth_error = f"Falha no login interativo: {e}"
                finally:
                    with SharePointManager._lock:
                        SharePointManager._auth_in_progress = False

            t = threading.Thread(target=_run_interactive, daemon=True)
            t.start()
            return {
                "success": True,
                "mode": "interactive",
                "client_id": target_cid,
                "message": "Janela de login Microsoft 365 aberta no seu navegador padrão. Conclua a seleção da conta.",
            }

        # Modo padrao recomendado: Device Code Flow com Microsoft Graph CLI (ou Azure CLI)
        with SharePointManager._lock:
            if SharePointManager._pending_flow and SharePointManager._auth_in_progress:
                expires_at = SharePointManager._pending_flow.get("expires_at", 0)
                if time.time() < expires_at - 30:
                    return {
                        "success": True,
                        "mode": "device",
                        "user_code": SharePointManager._pending_flow["user_code"],
                        "verification_uri": SharePointManager._pending_flow["verification_uri"],
                        "expires_in": int(expires_at - time.time()),
                        "message": "Use o código abaixo na página da Microsoft para conectar o SharePoint.",
                    }

        try:
            app, cache, cid, auth = self._build_app(client_id=target_cid, authority=authority)
            flow = app.initiate_device_flow(scopes=SHAREPOINT_SCOPES)
        except Exception as e:
            return {"success": False, "error": str(e)}
        if "user_code" not in flow:
            err_msg = flow.get("error_description") or flow.get("error") or "Não foi possível iniciar o código de autenticação Microsoft."
            return {"success": False, "error": str(err_msg)}

        expires_in = int(flow.get("expires_in", 900))
        verification_uri = flow.get("verification_uri") or "https://microsoft.com/devicelogin"
        user_code = flow["user_code"]

        with SharePointManager._lock:
            SharePointManager._last_auth_error = ""
            SharePointManager._auth_in_progress = True
            SharePointManager._pending_flow = {
                "user_code": user_code,
                "verification_uri": verification_uri,
                "expires_at": time.time() + expires_in,
            }

        def _wait_device_flow() -> None:
            try:
                res = app.acquire_token_by_device_flow(flow)
                if res and "access_token" in res:
                    self._save_msal_cache(cache)
                    claims = res.get("id_token_claims") or {}
                    acc_name = claims.get("preferred_username") or claims.get("upn") or clean_hint or "Microsoft 365"
                    self._save_auth_meta({
                        "client_id": cid,
                        "authority": auth,
                        "account": acc_name,
                        "connected_at": datetime.now().isoformat(),
                    })
                    with SharePointManager._lock:
                        SharePointManager._last_auth_error = ""
                else:
                    err_desc = (res or {}).get("error_description") or (res or {}).get("error") or "Tempo esgotado ou login não confirmado."
                    with SharePointManager._lock:
                        SharePointManager._last_auth_error = str(err_desc).splitlines()[0][:240]
            except Exception as e:
                with SharePointManager._lock:
                    SharePointManager._last_auth_error = f"Erro na validação Microsoft 365: {e}"
            finally:
                with SharePointManager._lock:
                    SharePointManager._auth_in_progress = False
                    SharePointManager._pending_flow = None

        t = threading.Thread(target=_wait_device_flow, daemon=True)
        t.start()

        return {
            "success": True,
            "mode": "device",
            "client_id": target_cid,
            "user_code": user_code,
            "verification_uri": verification_uri,
            "expires_in": expires_in,
            "message": "Código gerado! Confirme sua conta Microsoft 365 na janela aberta.",
        }

    # ==================== CACHE MANUAL E AUTOMATICO DE DOCX ====================

    def _safe_key(self, raw: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", (raw or "").strip())[:80]

    def save_manual_docx(self, issue_key: str, filename: str, content_bytes: bytes) -> Dict[str, Any]:
        """Salva um arquivo .docx importado manualmente pelo usuario para determinado ticket."""
        import zipfile
        import io

        clean_key = self._safe_key(issue_key.upper())
        if not clean_key:
            return {"success": False, "error": "Chave do ticket inválida."}
        if not content_bytes or len(content_bytes) < 100:
            return {"success": False, "error": "Arquivo vazio ou inválido."}

        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                if "word/document.xml" not in zf.namelist():
                    return {"success": False, "error": "O arquivo enviado não é um documento Word (.docx) válido."}
        except Exception:
            return {"success": False, "error": "Formato inválido. Envie um arquivo .docx válido do Microsoft Word."}

        docx_path = self.docx_cache_dir / f"manual_{clean_key}.docx"
        meta_path = self.docx_cache_dir / f"manual_{clean_key}.meta.json"
        docx_path.write_bytes(content_bytes)
        meta = {
            "issue_key": issue_key.upper(),
            "filename": filename or f"DDS-{issue_key.upper()}.docx",
            "uploaded_at": datetime.now().isoformat(),
            "size": len(content_bytes),
            "source": "manual_upload",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "meta": meta}

    def detect_and_import_from_downloads(
        self,
        issue_key: str,
        ticket_summary: str = "",
        explicit_filename: str = "",
    ) -> Dict[str, Any]:
        """
        Localiza automaticamente na pasta Downloads do usuario o arquivo .docx mais aderente
        ao chamado (comparando numero do ticket, resumo e data recente) e realiza a importacao local.
        Nao requer permissao do Azure AD nem aprovacao de TI.
        """
        import os
        from pathlib import Path

        downloads_dir = Path(os.environ.get("USERPROFILE", "")) / "Downloads"
        if not downloads_dir.exists():
            downloads_dir = Path.home() / "Downloads"
        if not downloads_dir.exists():
            return {"success": False, "error": "Pasta Downloads não encontrada."}

        clean_key = self._safe_key(issue_key.upper())

        # Caso tenha sido solicitado importar um arquivo especifico da lista de sugestoes
        if explicit_filename:
            target_file = downloads_dir / explicit_filename
            if not target_file.exists():
                cand = [f for f in downloads_dir.glob("*.docx") if f.name == explicit_filename]
                if cand:
                    target_file = cand[0]
            if target_file.exists() and target_file.suffix.lower() == ".docx":
                try:
                    data = target_file.read_bytes()
                    res = self.save_manual_docx(issue_key, target_file.name, data)
                    if res.get("success"):
                        res["filename"] = target_file.name
                        res["message"] = f"Arquivo '{target_file.name}' importado de Downloads com sucesso."
                    return res
                except Exception as e:
                    return {"success": False, "error": f"Falha ao ler arquivo '{explicit_filename}': {e}"}

        # Extrai numeros de 5 a 7 digitos associados ao chamado (ex: 379353 em TICKET-379353)
        tokens_num: List[str] = re.findall(r"\b\d{5,7}\b", f"{issue_key} {ticket_summary}")
        m_k = re.search(r"-(\d+)$", issue_key)
        if m_k:
            tokens_num.append(m_k.group(1))

        now_ts = time.time()
        max_age_sec = 14 * 86400
        candidates: List[Tuple[int, float, Path]] = []
        recent_all: List[Path] = []

        try:
            for p in downloads_dir.glob("*.docx"):
                if p.name.startswith("~$") or p.name.startswith("."):
                    continue
                try:
                    mtime = p.stat().st_mtime
                    size = p.stat().st_size
                except Exception:
                    continue
                if size < 100:
                    continue
                age = now_ts - mtime
                if age > max_age_sec:
                    continue

                recent_all.append(p)
                p_name_low = p.name.lower()
                score = 0

                # 1. Correspondencia exata por numero do chamado
                for num_tok in tokens_num:
                    if num_tok in p_name_low:
                        score = max(score, 100)
                if issue_key.lower() in p_name_low:
                    score = max(score, 100)

                # 2. DDS ou Detalhamento baixado recentemente
                if "dds" in p_name_low or "detalhamento" in p_name_low:
                    if age < 3600:
                        score = max(score, 70)
                    elif age < 86400:
                        score = max(score, 50)
                    else:
                        score = max(score, 30)

                # 3. Qualquer docx baixado nos ultimos 15 minutos
                if age < 900:
                    score = max(score, 40)

                if score > 0:
                    candidates.append((score, mtime, p))
        except Exception as ex_scan:
            return {"success": False, "error": f"Erro ao escanear pasta Downloads: {ex_scan}"}

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        recent_all.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        if candidates and candidates[0][0] >= 80:
            best_file = candidates[0][2]
            try:
                data = best_file.read_bytes()
                res = self.save_manual_docx(issue_key, best_file.name, data)
                if res.get("success"):
                    res["auto_imported"] = True
                    res["filename"] = best_file.name
                    res["message"] = f"Arquivo '{best_file.name}' detectado em Downloads e vinculado ao ticket com sucesso!"
                return res
            except Exception as e:
                return {"success": False, "error": f"Falha ao ler arquivo detectado '{best_file.name}': {e}"}

        items_suggest = []
        for p in (recent_all[:6]):
            try:
                mt = datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m %H:%M")
                items_suggest.append({
                    "filename": p.name,
                    "size": p.stat().st_size,
                    "modified": mt,
                })
            except Exception:
                pass

        return {
            "success": False,
            "candidates": items_suggest,
            "message": "Nenhum arquivo com o número da demanda foi identificado automaticamente em Downloads.",
        }

    def save_pasted_text(self, issue_key: str, text: str) -> Dict[str, Any]:
        """Salva texto colado manualmente da DDS (copiado do Word Online)."""
        clean_key = self._safe_key(issue_key.upper())
        if not clean_key:
            return {"success": False, "error": "Chave do ticket inválida."}
        clean_txt = (text or "").strip()
        if not clean_txt or len(clean_txt) < 20:
            return {"success": False, "error": "Texto muito curto para ser uma DDS válida."}

        txt_path = self.docx_cache_dir / f"pasted_{clean_key}.txt"
        meta_path = self.docx_cache_dir / f"pasted_{clean_key}.meta.json"
        txt_path.write_text(clean_txt, encoding="utf-8")
        meta = {
            "issue_key": issue_key.upper(),
            "uploaded_at": datetime.now().isoformat(),
            "length": len(clean_txt),
            "source": "pasted_text",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "message": "Texto da DDS salvo com sucesso!", "meta": meta}

    def load_pasted_text(self, issue_key: str) -> Optional[str]:
        """Carrega texto colado da DDS se disponivel."""
        clean_key = self._safe_key(issue_key.upper())
        txt_path = self.docx_cache_dir / f"pasted_{clean_key}.txt"
        if txt_path.exists():
            try:
                return txt_path.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def load_manual_docx(self, issue_key: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """Carrega .docx importado manualmente para um ticket, caso exista."""
        clean_key = self._safe_key(issue_key.upper())
        docx_path = self.docx_cache_dir / f"manual_{clean_key}.docx"
        meta_path = self.docx_cache_dir / f"manual_{clean_key}.meta.json"
        if not docx_path.exists():
            return None
        try:
            data = docx_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"filename": docx_path.name}
            return data, meta
        except Exception:
            return None

    # ==================== DOWNLOAD VIA MICROSOFT GRAPH API ====================

    def _download_drive_item_bytes(
        self,
        item: Dict[str, Any],
        headers: Dict[str, str],
        fallback_content_url: str = "",
        force_refresh: bool = False,
    ) -> Optional[bytes]:
        import requests

        item_id = str(item.get("id") or "")
        last_mod = str(item.get("lastModifiedDateTime") or "")
        size = int(item.get("size") or 0)
        cache_hash = hashlib.sha256(f"{item_id}:{fallback_content_url}".encode("utf-8")).hexdigest()[:24]
        bin_path = self.docx_cache_dir / f"sp_{cache_hash}.bin"
        meta_path = self.docx_cache_dir / f"sp_{cache_hash}.meta.json"

        if not force_refresh and bin_path.exists() and meta_path.exists():
            try:
                cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if cached_meta.get("lastModifiedDateTime") == last_mod and cached_meta.get("size") == size and last_mod:
                    return bin_path.read_bytes()
            except Exception:
                pass

        download_url = item.get("@microsoft.graph.downloadUrl")
        content_bytes: Optional[bytes] = None
        if download_url:
            r = requests.get(download_url, timeout=25)
            if r.status_code == 200:
                content_bytes = r.content

        if content_bytes is None and fallback_content_url:
            r2 = requests.get(fallback_content_url, headers=headers, timeout=25, allow_redirects=True)
            if r2.status_code == 200:
                content_bytes = r2.content

        if content_bytes:
            try:
                bin_path.write_bytes(content_bytes)
                meta_path.write_text(
                    json.dumps(
                        {
                            "id": item_id,
                            "name": item.get("name") or "",
                            "lastModifiedDateTime": last_mod,
                            "size": len(content_bytes),
                            "cached_at": datetime.now().isoformat(),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
        return content_bytes

    def fetch_dds_from_sharepoint_links(
        self,
        dds_links: List[Dict[str, Any]],
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Consulta os links do SharePoint (:w: documento Word e/ou :f: pasta de documentacao)
        via Microsoft Graph API e retorna o binario .docx mais recente + imagens avulsas da pasta.
        """
        sp_links = [
            lnk for lnk in (dds_links or [])
            if "sharepoint.com" in (lnk.get("url") or "").lower()
        ]
        if not sp_links:
            return {"has_sharepoint_link": False, "connected": False, "synced": False}

        token, account = self._acquire_silent_token()
        if not token:
            return {
                "has_sharepoint_link": True,
                "connected": False,
                "synced": False,
                "account": "",
                "error": "not_authenticated",
            }

        import requests

        headers = {
            "Authorization": f"Bearer {token}",
            "Prefer": "redeemSharingLinkIfNecessary",
            "Accept": "application/json",
        }
        # Remove referencia explicita da variavel local apos montar headers
        token = None

        best_docx_bytes: Optional[bytes] = None
        best_docx_meta: Dict[str, Any] = {}
        folder_images: List[Dict[str, Any]] = []
        folder_files: List[Dict[str, Any]] = []
        errors: List[str] = []

        # Ordena links para resolver :w: (documento direto) primeiro e :f: (pasta) em seguida
        sorted_links = sorted(
            sp_links,
            key=lambda x: 0 if (x.get("type") == "word" or ":w:" in (x.get("url") or "")) else 1,
        )

        seen_item_ids: set[str] = set()

        for lnk in sorted_links:
            raw_url = (lnk.get("url") or "").strip()
            if not raw_url:
                continue

            item_json: Optional[Dict[str, Any]] = None
            matched_sid = ""
            last_http_status = 0

            for sid in build_candidate_share_ids(raw_url):
                endpoint = f"https://graph.microsoft.com/v1.0/shares/{sid}/driveItem"
                try:
                    resp = requests.get(endpoint, headers=headers, timeout=18)
                    last_http_status = resp.status_code
                    if resp.status_code == 200:
                        item_json = resp.json()
                        matched_sid = sid
                        break
                except Exception as ex:
                    errors.append(str(ex))

            if not item_json:
                if last_http_status:
                    errors.append(f"HTTP {last_http_status} ao acessar link SharePoint")
                continue

            item_id = str(item_json.get("id") or "")
            item_name = str(item_json.get("name") or "")

            # Caso 1: O link aponta diretamente para um arquivo (.docx)
            if "file" in item_json:
                if item_id in seen_item_ids:
                    continue
                seen_item_ids.add(item_id)

                if item_name.lower().endswith(".docx"):
                    content_url = f"https://graph.microsoft.com/v1.0/shares/{matched_sid}/driveItem/content"
                    b_data = self._download_drive_item_bytes(
                        item_json, headers=headers, fallback_content_url=content_url, force_refresh=force_refresh
                    )
                    if b_data:
                        item_mod = str(item_json.get("lastModifiedDateTime") or "")
                        if best_docx_bytes is None or item_mod > best_docx_meta.get("lastModifiedDateTime", ""):
                            mod_by = ((item_json.get("lastModifiedBy") or {}).get("user") or {}).get("displayName") or ""
                            best_docx_bytes = b_data
                            best_docx_meta = {
                                "filename": item_name,
                                "lastModifiedDateTime": item_mod,
                                "lastModifiedBy": mod_by,
                                "webUrl": item_json.get("webUrl") or raw_url,
                                "size": len(b_data),
                            }

            # Caso 2: O link aponta para uma pasta (:f:) no SharePoint
            elif "folder" in item_json and matched_sid:
                children_url = f"https://graph.microsoft.com/v1.0/shares/{matched_sid}/driveItem/children?$top=100"
                try:
                    c_resp = requests.get(children_url, headers=headers, timeout=18)
                    if c_resp.status_code == 200:
                        children = (c_resp.json() or {}).get("value") or []
                        # Ordena candidatos .docx priorizando nome contendo 'dds' e data mais recente
                        docx_children = [
                            ch for ch in children
                            if "file" in ch and str(ch.get("name") or "").lower().endswith(".docx")
                        ]
                        docx_children.sort(
                            key=lambda ch: (
                                1 if "dds" in str(ch.get("name") or "").lower() else 0,
                                str(ch.get("lastModifiedDateTime") or ""),
                            ),
                            reverse=True,
                        )

                        for d_ch in docx_children[:1]:
                            ch_id = str(d_ch.get("id") or "")
                            if ch_id in seen_item_ids:
                                continue
                            seen_item_ids.add(ch_id)
                            ch_mod = str(d_ch.get("lastModifiedDateTime") or "")
                            if best_docx_bytes is None or ch_mod > best_docx_meta.get("lastModifiedDateTime", ""):
                                drive_id = ((d_ch.get("parentReference") or {}).get("driveId") or "")
                                fb_url = (
                                    f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{ch_id}/content"
                                    if drive_id and ch_id else ""
                                )
                                b_data = self._download_drive_item_bytes(
                                    d_ch, headers=headers, fallback_content_url=fb_url, force_refresh=force_refresh
                                )
                                if b_data:
                                    mod_by = ((d_ch.get("lastModifiedBy") or {}).get("user") or {}).get("displayName") or ""
                                    best_docx_bytes = b_data
                                    best_docx_meta = {
                                        "filename": str(d_ch.get("name") or "DDS.docx"),
                                        "lastModifiedDateTime": ch_mod,
                                        "lastModifiedBy": mod_by,
                                        "webUrl": d_ch.get("webUrl") or raw_url,
                                        "size": len(b_data),
                                    }

                        # Coleta imagens avulsas e anexos complementares presentes na pasta do SharePoint
                        for ch in children:
                            if "file" not in ch:
                                continue
                            ch_id = str(ch.get("id") or "")
                            ch_name = str(ch.get("name") or "")
                            low_name = ch_name.lower()
                            ch_size = int(ch.get("size") or 0)

                            if low_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) and ch_size <= 12 * 1024 * 1024:
                                if ch_id in seen_item_ids:
                                    continue
                                seen_item_ids.add(ch_id)
                                drive_id = ((ch.get("parentReference") or {}).get("driveId") or "")
                                fb_url = (
                                    f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{ch_id}/content"
                                    if drive_id and ch_id else ""
                                )
                                img_bytes = self._download_drive_item_bytes(
                                    ch, headers=headers, fallback_content_url=fb_url, force_refresh=force_refresh
                                )
                                if img_bytes:
                                    ext = low_name.rsplit(".", 1)[-1]
                                    if ext == "jpg":
                                        ext = "jpeg"
                                    b64_img = base64.b64encode(img_bytes).decode("ascii")
                                    data_uri = f"data:image/{ext};base64,{b64_img}"
                                    mod_by = ((ch.get("lastModifiedBy") or {}).get("user") or {}).get("displayName") or "SharePoint"
                                    folder_images.append({
                                        "id": f"sp-img-{ch_id[:12]}",
                                        "name": ch_name,
                                        "size": len(img_bytes),
                                        "url": data_uri,
                                        "proxy_url": data_uri,
                                        "thumbnail_url": data_uri,
                                        "created": str(ch.get("createdDateTime") or ""),
                                        "author": f"Pasta SharePoint ({mod_by})",
                                        "is_embedded": False,
                                    })
                            elif not low_name.endswith(".docx"):
                                folder_files.append({
                                    "id": f"sp-file-{ch_id[:12]}",
                                    "name": ch_name,
                                    "size": ch_size,
                                    "url": ch.get("webUrl") or raw_url,
                                    "proxy_url": ch.get("webUrl") or raw_url,
                                    "created": str(ch.get("createdDateTime") or ""),
                                    "author": "Pasta SharePoint",
                                    "is_doc": low_name.endswith((".doc", ".pdf", ".xlsx", ".pbix", ".csv", ".sql")),
                                })
                except Exception as ex_f:
                    errors.append(str(ex_f))

        return {
            "has_sharepoint_link": True,
            "connected": True,
            "account": account,
            "synced": best_docx_bytes is not None or bool(folder_images),
            "docx_bytes": best_docx_bytes,
            "docx_meta": best_docx_meta,
            "folder_images": folder_images,
            "folder_files": folder_files,
            "errors": errors,
        }
