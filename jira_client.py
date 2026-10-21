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
from storage import QueueItem, StateManager

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


class JiraClient:
    """Cliente HTTP para envio de Worklogs ao Jira com auto-deteccao de protocolo de autenticacao."""

    def __init__(self, jira_config: JiraConfig, state_manager: Optional[StateManager] = None):
        self.config = jira_config
        self.state_manager = state_manager or StateManager()

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


    def get_user_analytics_data(self, days: int = 90) -> Dict[str, Any]:
        """
        Coleta os dados necessarios para o Dashboard Analitico: chamados em que o usuario lancou horas
        nos ultimos N dias (com tipo, status e historico de transicoes) e os worklogs do proprio usuario.

        Retorna {"issues": {chave: metadados}, "worklogs": [..]}. Levanta excecao se a consulta principal falhar.
        """
        import urllib.parse
        from concurrent.futures import ThreadPoolExecutor

        base_url = self.config.get_clean_base_url()
        headers = self._get_auth_headers()
        days = max(1, int(days))
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

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

        jql = f"worklogAuthor = currentUser() AND worklogDate >= -{days}d"
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
                    if day_str < cutoff:
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
