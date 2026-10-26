"""
Testes unitarios para os modulos do JiraBot incluindo os recursos avancados e perfis customizados.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, time
from pathlib import Path
from unittest.mock import MagicMock, patch

from config import (
    BotConfig,
    ShiftProfile,
    TimeWindow,
    build_window,
    get_default_profiles,
    make_custom_profile,
)
from engine import BotEngine, format_duration
from history import generate_report
from jira_client import JiraClient, format_iso_for_jira
from storage import DailyState, DaySummary, StateManager, TimeInterval


class TestTimeWindowAndCustom(unittest.TestCase):
    def test_window_contains_regular(self):
        window = TimeWindow("07:15", "08:15")
        self.assertTrue(window.contains(time(7, 45)))
        self.assertTrue(window.contains(time(7, 42)))
        self.assertTrue(window.contains(time(7, 15)))
        self.assertTrue(window.contains(time(8, 15)))
        self.assertFalse(window.contains(time(7, 14)))
        self.assertFalse(window.contains(time(8, 16)))

    def test_build_window_tolerance(self):
        # Alvo 07:42 com 20 min de tolerancia: 07:22 as 08:02
        window = build_window("07:42", 20, 20)
        self.assertEqual(window.start_str, "07:22")
        self.assertEqual(window.end_str, "08:02")
        self.assertTrue(window.contains(time(7, 42)))
        self.assertTrue(window.contains(time(7, 25)))
        self.assertFalse(window.contains(time(7, 20)))

    def test_make_custom_profile(self):
        prof = make_custom_profile(
            name="custom_teste",
            target_hours=8.0,
            entry_hm="07:42",
            lunch_start_hm="11:45",
            lunch_end_hm="13:00",
            exit_hm="17:42",
            tolerance_minutes=15,
        )
        self.assertEqual(prof.entry_window.start_str, "07:27")
        self.assertEqual(prof.entry_window.end_str, "07:57")
        self.assertEqual(prof.exit_window.start_str, "17:27")
        self.assertEqual(prof.exit_window.end_str, "17:57")

    def test_profile_calculator_persists_after_reload(self):
        test_dir = Path(tempfile.mkdtemp())
        try:
            with patch("config.get_default_config_dir", return_value=test_dir):
                cfg = BotConfig(notifications_enabled=False)
                prof = ShiftProfile.from_dict({
                    "name": "custom",
                    "target_hours": 6,
                    "entry_window": {"start": "07:40", "end": "07:50"},
                    "lunch_start_window": {"start": "11:55", "end": "12:05"},
                    "lunch_end_window": {"start": "13:25", "end": "13:35"},
                    "exit_window": {"start": "15:10", "end": "15:20"},
                    "calculator": {
                        "entry_hm": "07:45", "entry_before": 5, "entry_after": 5,
                        "lunch_start_hm": "12:00", "lunch_start_before": 5, "lunch_start_after": 5,
                        "lunch_end_hm": "13:30", "lunch_end_before": 5, "lunch_end_after": 5,
                        "exit_hm": "15:15", "exit_before": 5, "exit_after": 5,
                        "chave_invalida": "ignorar",
                    },
                })
                cfg.profiles["custom"] = prof
                cfg.active_profile = "custom"
                cfg.save()

                reloaded = BotConfig.load().profiles["custom"]
                self.assertEqual(reloaded.calculator["exit_hm"], "15:15")
                self.assertEqual(reloaded.calculator["entry_before"], 5)
                self.assertEqual(reloaded.calculator["exit_after"], 5)
                self.assertNotIn("chave_invalida", reloaded.calculator)
                self.assertEqual(reloaded.exit_window.start_str, "15:10")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_profile_without_calculator_is_backward_compatible(self):
        prof = ShiftProfile.from_dict({
            "name": "6h_0745",
            "target_hours": 6,
            "entry_window": {"start": "07:25", "end": "08:05"},
            "lunch_start_window": {"start": "11:40", "end": "12:20"},
            "lunch_end_window": {"start": "13:20", "end": "13:40"},
            "exit_window": {"start": "15:15", "end": "15:45"},
        })
        self.assertEqual(prof.calculator, {})
        self.assertNotIn("calculator", prof.to_dict())


class TestStorageAndDuration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.state_mgr = StateManager(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_duration_calculation(self):
        intervals = [
            TimeInterval(start="2026-08-31T07:42:00", end="2026-08-31T11:45:00", issue_key="PROJ-1"),
            TimeInterval(start="2026-08-31T13:00:00", end="2026-08-31T17:42:00", issue_key="PROJ-2"),
        ]
        state = DailyState(intervals=intervals)
        total_sec = state.get_total_seconds()
        self.assertEqual(total_sec, 31500)  # 4h03m (14580s) + 4h42m (16920s) = 31500s = 8h45m

        by_issue = state.get_seconds_by_issue()
        self.assertEqual(by_issue.get("PROJ-1"), 14580)
        self.assertEqual(by_issue.get("PROJ-2"), 16920)


class TestEngineStateMachine(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.state_mgr = StateManager(base_dir=self.test_dir)
        self.config = BotConfig(active_profile="8h", notifications_enabled=False)
        self.config.jira.default_issue = "DEFAULT-1"
        self.mock_worklog_trigger = MagicMock(return_value=True)
        self.engine = BotEngine(
            config=self.config,
            state_manager=self.state_mgr,
            on_worklog_trigger=self.mock_worklog_trigger,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_day_flow_8h(self):
        # 1. Entrada as 07:42 (Unlock)
        t_entry = datetime(2026, 8, 31, 7, 42, 0)
        state = self.engine.handle_unlock(now=t_entry)
        self.assertEqual(state.status, "RUNNING")
        self.assertEqual(len(state.intervals), 1)

        # 2. Saida para almoco as 11:55 (Lock)
        t_lunch_start = datetime(2026, 8, 31, 11, 55, 0)
        state = self.engine.handle_lock(now=t_lunch_start)
        self.assertEqual(state.status, "PAUSED_LUNCH")

        # 3. Retorno do almoco as 13:05 (Unlock)
        t_lunch_end = datetime(2026, 8, 31, 13, 5, 0)
        state = self.engine.handle_unlock(now=t_lunch_end)
        self.assertEqual(state.status, "RUNNING")

        # 4. Fim de expediente as 17:42 (Lock)
        t_exit = datetime(2026, 8, 31, 17, 42, 0)
        state = self.engine.handle_lock(now=t_exit)
        self.assertEqual(state.status, "COMPLETED")

    def test_dynamic_comments_and_switch(self):
        # 1. Inicia o dia com descricao padrao
        t_entry = datetime(2026, 9, 2, 8, 0, 0)
        self.engine.handle_unlock(now=t_entry)
        self.engine.set_comment("Atividade inicial da manha")
        self.assertEqual(self.engine.state.get_issue_comment("DEFAULT-1"), "Atividade inicial da manha")

        # 2. Troca de ticket com nova descricao
        t_switch = datetime(2026, 9, 2, 10, 0, 0)
        self.engine.switch_ticket("CONSISABI-390", comment="Desenvolvimento de visoes mobile", now=t_switch)
        self.assertEqual(self.engine.state.target_issue, "CONSISABI-390")
        self.assertEqual(self.engine.state.get_issue_comment("CONSISABI-390"), "Desenvolvimento de visoes mobile")
        self.assertEqual(self.engine.state.get_issue_comment("DEFAULT-1"), "Atividade inicial da manha")

        # 3. Verifica lista de tickets trabalhados
        worked = self.engine.state.get_all_issues_worked()
        self.assertIn("DEFAULT-1", worked)
        self.assertIn("CONSISABI-390", worked)

    def test_shutdown_6h_logs_immediately(self):
        self.config.active_profile = "6h_0745"
        # 1. Entrada as 07:45
        self.engine.handle_unlock(now=datetime(2026, 10, 20, 7, 45, 0))
        # 2. Pausa almoco as 12:00 (4h15m)
        self.engine.handle_lock(now=datetime(2026, 10, 20, 12, 0, 0))
        # 3. Retorno almoco as 13:30
        self.engine.handle_unlock(now=datetime(2026, 10, 20, 13, 30, 0))
        # 4. Usuario desliga o PC direto as 15:15 (sem Win+L), completando 6h00m (21600s)
        state = self.engine.handle_shutdown(now=datetime(2026, 10, 20, 15, 15, 0))

        self.assertEqual(state.status, "COMPLETED")
        self.assertEqual(state.last_event, "COMPLETED_EXIT_SHUTDOWN")
        self.assertEqual(state.get_total_seconds(), 21600)
        self.assertTrue(state.is_logged)
        self.mock_worklog_trigger.assert_called_once()
        args = self.mock_worklog_trigger.call_args[0]
        self.assertEqual(args[0], "DEFAULT-1")
        self.assertEqual(args[1], 21600)

    def test_shutdown_6h_offline_queues_exact_6h(self):
        self.config.active_profile = "6h_0745"
        # Simula rede ja desconectada pelo Windows durante o desligamento
        self.mock_worklog_trigger.return_value = False

        self.engine.handle_unlock(now=datetime(2026, 10, 20, 7, 45, 0))
        self.engine.handle_lock(now=datetime(2026, 10, 20, 12, 0, 0))
        self.engine.handle_unlock(now=datetime(2026, 10, 20, 13, 30, 0))
        state = self.engine.handle_shutdown(now=datetime(2026, 10, 20, 15, 15, 0))

        self.assertEqual(state.status, "COMPLETED")
        self.assertEqual(state.get_total_seconds(), 21600)
        queue = self.state_mgr.load_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].issue_key, "DEFAULT-1")
        self.assertEqual(queue[0].time_spent_seconds, 21600)


class TestHistoricalWorklogs(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_update_worklog_comment(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        config = BotConfig(notifications_enabled=False)
        client = JiraClient(config.jira)
        res = client.update_worklog_comment("CONSISABI-390", "12345", "Nova descricao de teste")
        self.assertTrue(res)
        self.assertTrue(mock_urlopen.called)

    @patch("urllib.request.urlopen")
    def test_worklog_without_comment(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": "999"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        config = BotConfig(notifications_enabled=False)
        client = JiraClient(config.jira)
        res = client.submit_worklog("CONSISABI-427", 3600, "2026-09-02T08:00:00", no_comment=True)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("worklog_id"), "999")

        # Verifica se o payload enviado nao continha a chave 'comment'
        sent_req = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_req.data.decode("utf-8"))
        self.assertNotIn("comment", sent_body)

    def test_headers_contain_utf8_charset(self):
        config = BotConfig(notifications_enabled=False)
        client = JiraClient(config.jira)
        headers = client._build_headers("bearer")
        self.assertIn("charset=utf-8", headers.get("Content-Type", ""))

    def test_get_source_files_mtime(self):
        from daemon import get_source_files_mtime
        mtime = get_source_files_mtime()
        self.assertGreater(mtime, 0)

    def test_rollover_preserves_custom_comment(self):
        test_dir = Path(tempfile.mkdtemp())
        try:
            mgr = StateManager(base_dir=test_dir)
            old_state = DailyState(date_str="2026-09-01", target_issue="PROJ-999")
            old_state.intervals.append(TimeInterval(start="2026-09-01T08:00:00", end="2026-09-01T12:00:00", issue_key="PROJ-999"))
            old_state.set_issue_comment("PROJ-999", "Descricao customizada importante")
            mgr.save_state(old_state)

            new_state = mgr.load_state()
            queue = mgr.load_queue()
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0].comment, "Descricao customizada importante")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_transfer_hours_full(self):
        state = DailyState(target_issue="ORIGEM-1")
        state.intervals.append(TimeInterval(start="2026-09-03T08:00:00", end="2026-09-03T09:30:00", issue_key="ORIGEM-1"))
        state.set_issue_comment("ORIGEM-1", "Comentario da origem")

        transferred = state.transfer_hours("ORIGEM-1", "DESTINO-2")
        self.assertEqual(transferred, 5400)  # 1h30m = 5400s
        by_issue = state.get_seconds_by_issue()
        self.assertEqual(by_issue.get("DESTINO-2"), 5400)
        self.assertEqual(by_issue.get("ORIGEM-1", 0), 0)
        self.assertEqual(state.target_issue, "DESTINO-2")
        self.assertEqual(state.get_issue_comment("DESTINO-2"), "Comentario da origem")

    def test_transfer_hours_partial_split(self):
        state = DailyState(target_issue="ORIGEM-1")
        state.intervals.append(TimeInterval(start="2026-09-03T08:00:00", end="2026-09-03T10:00:00", issue_key="ORIGEM-1"))

        # Transfere 30 minutos (1800s) de 2h (7200s)
        transferred = state.transfer_hours("ORIGEM-1", "DESTINO-2", seconds=1800)
        self.assertEqual(transferred, 1800)
        self.assertEqual(len(state.intervals), 2)
        by_issue = state.get_seconds_by_issue()
        self.assertEqual(by_issue.get("ORIGEM-1"), 5400)  # 1h30m restou
        self.assertEqual(by_issue.get("DESTINO-2"), 1800)  # 30m transferido

    def test_parse_time_input(self):
        from cli import parse_time_input
        self.assertEqual(parse_time_input("01:30"), 5400)
        self.assertEqual(parse_time_input("45m"), 2700)
        self.assertEqual(parse_time_input("2h"), 7200)
        self.assertEqual(parse_time_input("1.5h"), 5400)
        self.assertIsNone(parse_time_input("invalido"))


class TestWebPanelAndShiftSchedule(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.state_mgr = StateManager(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_calculate_shift_schedule_full_day(self):
        from storage import calculate_shift_schedule
        # 07:45 as 12:00 (4h15m = 15300s) + 13:30 as 15:15 (1h45m = 6300s) = 6h00m (21600s)
        res = calculate_shift_schedule(
            date_str="2026-10-20",
            start_hm="07:45",
            lunch_start_hm="12:00",
            lunch_end_hm="13:30",
            end_hm="15:15",
            issue_key="CONSISABI-427",
            comment="Desenvolvimento BI",
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("total_seconds"), 21600)
        self.assertEqual(res.get("morning_seconds"), 15300)
        self.assertEqual(res.get("lunch_break_seconds"), 5400)
        self.assertEqual(res.get("afternoon_seconds"), 6300)
        self.assertEqual(res.get("status"), "COMPLETED")
        self.assertEqual(len(res.get("intervals", [])), 2)

    def test_apply_and_summarize_shift_schedule(self):
        state = DailyState(date_str="2026-10-20", target_issue="ATIVDIV-32")
        res = state.apply_shift_schedule(
            start_hm="08:00",
            lunch_start_hm="12:00",
            lunch_end_hm="13:30",
            end_hm="15:30",
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(state.get_total_seconds(), 21600)
        summary = state.get_shift_times_summary()
        self.assertEqual(summary["start_hm"], "08:00")
        self.assertEqual(summary["lunch_start_hm"], "12:00")
        self.assertEqual(summary["lunch_end_hm"], "13:30")
        self.assertEqual(summary["end_hm"], "15:30")

    def test_worklog_schedule_persistence_and_inference(self):
        # 1. Inferencia automatica para worklog de 6h iniciado as 07:45
        wl = {
            "id": "55501",
            "started": "2026-10-19T07:45:00.000-0300",
            "time_spent_seconds": 21600,
        }
        inferred = self.state_mgr.get_or_infer_worklog_schedule(wl, "12:00", "13:30")
        self.assertEqual(inferred["start_hm"], "07:45")
        self.assertEqual(inferred["lunch_start_hm"], "12:00")
        self.assertEqual(inferred["lunch_end_hm"], "13:30")
        self.assertEqual(inferred["end_hm"], "15:15")

        # 2. Persistencia explicita de horarios editados pelo usuario
        self.state_mgr.save_worklog_schedule("55501", {
            "start_hm": "07:50",
            "lunch_start_hm": "12:10",
            "lunch_end_hm": "13:40",
            "end_hm": "15:20",
        })
        saved = self.state_mgr.get_or_infer_worklog_schedule(wl)
        self.assertEqual(saved["start_hm"], "07:50")
        self.assertEqual(saved["lunch_start_hm"], "12:10")
        self.assertEqual(saved["lunch_end_hm"], "13:40")
        self.assertEqual(saved["end_hm"], "15:20")
        self.assertEqual(saved["is_saved"], "true")

    @patch("urllib.request.urlopen")
    def test_update_worklog_full(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"id": "777"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        config = BotConfig(notifications_enabled=False)
        client = JiraClient(config.jira)
        res = client.update_worklog_full(
            issue_key="CONSISABI-427",
            worklog_id="777",
            time_spent_seconds=21600,
            started_iso="2026-10-20T07:45:00",
            comment="Descricao e horario atualizados via Web",
        )
        self.assertTrue(res.get("success"))
        sent_req = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_req.data.decode("utf-8"))
        self.assertEqual(sent_body["timeSpentSeconds"], 21600)
        self.assertEqual(sent_body["comment"], "Descricao e horario atualizados via Web")
        self.assertIn("2026-10-20T07:45:00", sent_body["started"])

    def test_updater_isolation_and_folder_sync(self):
        """Testa se o updater copia apenas arquivos de codigo (.py/.bat) e preserva dados de usuario."""
        from updater import publish_clean_release, check_for_updates, perform_update, get_version_info
        import shutil

        info = get_version_info()
        self.assertIn("version", info)
        self.assertTrue(info["user_config_dir"].endswith(".jirabot"))

        release_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())
        mock_cfg_dir = Path(tempfile.mkdtemp())
        try:
            with patch("config.get_default_config_dir", return_value=mock_cfg_dir), \
                 patch("updater.get_default_config_dir", return_value=mock_cfg_dir):
                # 1. Publica release limpa a partir do projeto atual
                pub = publish_clean_release(str(release_dir))
                self.assertTrue(pub.get("success"))
                self.assertTrue((release_dir / "web_panel.py").exists())
                self.assertTrue((release_dir / "updater.py").exists())
                # Garante que nenhum arquivo sensivel ou de estado foi exportado
                self.assertFalse((release_dir / ".env").exists())
                self.assertFalse((release_dir / "config.json").exists())
                self.assertFalse((release_dir / "state.json").exists())

                # 2. Cria um arquivo pessoal simulado na pasta de destino e verifica que o updater nao toca nele
                (release_dir / "config.json").write_text('{"leak": true}', encoding="utf-8")
                chk = check_for_updates(str(release_dir))
                self.assertTrue(chk.get("success"))

                with patch("updater.APP_DIR", target_dir):
                    res = perform_update(str(release_dir))
                    self.assertTrue(res.get("success"))
                    self.assertTrue((target_dir / "web_panel.py").exists())
                    self.assertFalse((target_dir / "config.json").exists())
        finally:
            shutil.rmtree(release_dir, ignore_errors=True)
            shutil.rmtree(target_dir, ignore_errors=True)
            shutil.rmtree(mock_cfg_dir, ignore_errors=True)

    @patch("jira_client.JiraClient.get_user_worklogs_by_date_range")
    def test_build_weekly_payload(self, mock_range):
        """Testa a construcao do payload da Visualizacao Semanal com 7 dias (Seg a Dom)."""
        from web_panel import build_weekly_payload

        mock_range.return_value = [
            {
                "id": "9001",
                "issue_key": "CONSISABI-427",
                "summary": "Desenvolvimento BI",
                "started": "2026-10-19T07:45:00.000-0300",
                "date": "2026-10-19",
                "time_spent": "6h",
                "time_spent_seconds": 21600,
                "comment": "Modelagem dimensional",
            }
        ]
        payload = build_weekly_payload("2026-10-20")
        self.assertEqual(payload["monday"], "2026-10-19")
        self.assertEqual(payload["sunday"], "2026-10-25")
        self.assertEqual(len(payload["days"]), 7)
        monday_day = payload["days"][0]
        self.assertEqual(monday_day["date"], "2026-10-19")
        self.assertEqual(monday_day["total_seconds"], 21600)
        self.assertTrue(monday_day["is_logged"])
        self.assertEqual(len(monday_day["tickets"]), 1)

    def test_multi_ticket_batch_schedule_split(self):
        """Testa o calculo de multiplos tickets no mesmo dia (ex: Ticket 1 = 3h e Ticket 2 = 3h)."""
        from storage import calculate_shift_schedule

        # Ticket 1: 07:45 as 10:45 (sem pausa de almoco = 3h = 10800s)
        c1 = calculate_shift_schedule(
            date_str="2026-10-20",
            start_hm="07:45",
            lunch_start_hm="",
            lunch_end_hm="",
            end_hm="10:45",
            issue_key="CONSISABI-427",
        )
        self.assertTrue(c1.get("success"))
        self.assertEqual(c1.get("total_seconds"), 10800)

        # Ticket 2: 10:45 as 15:15 com pausa de almoco 12:00 as 13:30 (1h15m + 1h45m = 3h = 10800s)
        c2 = calculate_shift_schedule(
            date_str="2026-10-20",
            start_hm="10:45",
            lunch_start_hm="12:00",
            lunch_end_hm="13:30",
            end_hm="15:15",
            issue_key="ATIVDIV-32",
        )
        self.assertTrue(c2.get("success"))
        self.assertEqual(c2.get("total_seconds"), 10800)
        self.assertEqual(c1["total_seconds"] + c2["total_seconds"], 21600)


class TestAnalyticsAndRedesign(unittest.TestCase):
    def test_build_analytics_aggregation(self):
        from datetime import date
        from analytics import build_analytics, format_hm

        issues = {
            "PROJ-1": {
                "summary": "Tarefa 1",
                "issue_type": "Bug",
                "status": "Concluído",
                "status_category": "done",
                "completed_date": "2026-10-20",
                "completed_by_me": True,
            },
            "PROJ-2": {
                "summary": "Tarefa 2",
                "issue_type": "Melhoria",
                "status": "Em Andamento",
                "status_category": "indeterminate",
                "completed_date": "",
                "completed_by_me": False,
            },
            "PROJ-3": {
                "summary": "Tarefa 3",
                "issue_type": "Bug",
                "status": "Concluído",
                "status_category": "done",
                "completed_date": "2026-10-21",
                "completed_by_me": False,  # Finalizado por outra pessoa
            },
        }

        worklogs = [
            {"issue_key": "PROJ-1", "date": "2026-10-19", "time_spent_seconds": 7200, "comment": "Ajuste do bug"},
            {"issue_key": "PROJ-1", "date": "2026-10-20", "time_spent_seconds": 3600, "comment": ""},
            {"issue_key": "PROJ-2", "date": "2026-10-20", "time_spent_seconds": 10800, "comment": "Desenvolvimento"},
            {"issue_key": "PROJ-3", "date": "2026-10-21", "time_spent_seconds": 3600, "comment": ""},
        ]

        res = build_analytics(issues, worklogs, days=7, today=date(2026, 10, 21))
        self.assertTrue(res["available"])
        self.assertEqual(res["totals"]["seconds"], 25200)  # 7h = 25200s
        self.assertEqual(res["totals"]["worklogs"], 4)
        self.assertEqual(res["totals"]["tickets"], 3)

        # Tipos de ticket por tempo: Bug tem 14400s (4h), Melhoria tem 10800s (3h)
        self.assertEqual(res["by_type_time"][0]["type"], "Bug")
        self.assertEqual(res["by_type_time"][0]["seconds"], 14400)
        self.assertEqual(res["by_type_time"][1]["type"], "Melhoria")
        self.assertEqual(res["by_type_time"][1]["seconds"], 10800)

        # Tipos de ticket por lancamentos: Bug tem 3 lancamentos, Melhoria tem 1
        self.assertEqual(res["by_type_count"][0]["type"], "Bug")
        self.assertEqual(res["by_type_count"][0]["worklogs"], 3)

        # Descricao dos lancamentos: 2 com descricao, 2 sem descricao (50% cada)
        desc = res["description"]
        self.assertEqual(desc["worklogs_with"], 2)
        self.assertEqual(desc["worklogs_without"], 2)
        self.assertEqual(desc["worklogs_with_pct"], 50.0)
        self.assertEqual(desc["worklogs_without_pct"], 50.0)

        # Apenas PROJ-1 foi concluido pelo usuario (PROJ-3 foi finalizado por outro)
        comp = res["completion"]
        self.assertEqual(comp["total"], 1)
        self.assertEqual(comp["keys"], ["PROJ-1"])

        # Tempo medio por ticket: 25200 / 3 = 8400s (2h 20m)
        self.assertEqual(res["time_per_ticket"]["avg_seconds"], 8400)

        # Evolucao: 7 dias retornados
        self.assertEqual(len(res["evolution"]), 7)

    def test_web_panel_redesign_assets_injected(self):
        from web_panel import HTML_PAGE

        # Confirma que todos os marcadores foram substituidos e nao ha sobras
        self.assertNotIn("/*__THEME_CSS__*/", HTML_PAGE)
        self.assertNotIn("/*__EARLY_JS__*/", HTML_PAGE)
        self.assertNotIn("/*__UI_FX_JS__*/", HTML_PAGE)
        self.assertNotIn("/*__ANALYTICS_JS__*/", HTML_PAGE)
        self.assertNotIn("__LOGO_SVG__", HTML_PAGE)

        # Confirma a presenca dos novos elementos exigidos
        self.assertIn('id="hamburger-btn"', HTML_PAGE)
        self.assertIn('id="fx-toggle-btn"', HTML_PAGE)
        self.assertIn('id="tab-analytics"', HTML_PAGE)
        self.assertIn('id="an-start-date"', HTML_PAGE)
        self.assertIn('id="an-end-date"', HTML_PAGE)
        self.assertIn('class="brand-logo"', HTML_PAGE)
        self.assertIn('href="/favicon.svg"', HTML_PAGE)
        self.assertIn('data-tab="tab-settings"', HTML_PAGE)

    def test_build_analytics_single_day(self):
        from analytics import build_analytics

        issues = {
            "PROJ-1": {
                "summary": "Tarefa do dia",
                "issue_type": "Bug",
                "status": "Concluído",
                "status_category": "done",
                "completed_date": "2026-10-21",
                "completed_by_me": True,
            }
        }
        worklogs = [
            {"issue_key": "PROJ-1", "date": "2026-10-20", "time_spent_seconds": 3600, "comment": "Ontem"},
            {"issue_key": "PROJ-1", "date": "2026-10-21", "time_spent_seconds": 7200, "comment": "Hoje"},
        ]

        # Filtra apenas o dia 21/10/2026 (dia unitario)
        res = build_analytics(issues, worklogs, start_date="2026-10-21", end_date="2026-10-21")
        self.assertTrue(res["available"])
        self.assertEqual(res["period_days"], 1)
        self.assertEqual(res["start_date"], "2026-10-21")
        self.assertEqual(res["end_date"], "2026-10-21")
        self.assertEqual(res["totals"]["seconds"], 7200)  # Apenas as 2h do dia 21
        self.assertEqual(res["totals"]["worklogs"], 1)
        self.assertEqual(len(res["evolution"]), 1)
        self.assertEqual(res["completion"]["total"], 1)

    def test_build_analytics_custom_range_across_months(self):
        from analytics import build_analytics

        issues = {
            "PROJ-1": {
                "summary": "Tarefa longa",
                "issue_type": "Melhoria",
                "status": "Concluído",
                "status_category": "done",
                "completed_date": "2026-10-15",
                "completed_by_me": True,
            }
        }
        worklogs = [
            {"issue_key": "PROJ-1", "date": "2026-07-31", "time_spent_seconds": 3600, "comment": "Julho fora"},
            {"issue_key": "PROJ-1", "date": "2026-08-10", "time_spent_seconds": 7200, "comment": "Agosto dentro"},
            {"issue_key": "PROJ-1", "date": "2026-09-15", "time_spent_seconds": 10800, "comment": "Setembro dentro"},
            {"issue_key": "PROJ-1", "date": "2026-10-20", "time_spent_seconds": 14400, "comment": "Outubro dentro"},
            {"issue_key": "PROJ-1", "date": "2026-10-25", "time_spent_seconds": 3600, "comment": "Futuro fora"},
        ]

        # Intervalo livre de 01/08/2026 a 21/10/2026 (82 dias cruzando 3 meses)
        res = build_analytics(issues, worklogs, start_date="2026-08-01", end_date="2026-10-21")
        self.assertTrue(res["available"])
        self.assertEqual(res["period_days"], 82)
        self.assertEqual(res["start_date"], "2026-08-01")
        self.assertEqual(res["end_date"], "2026-10-21")
        # Deve somar Agosto (7200) + Setembro (10800) + Outubro (14400) = 32400s (9h)
        self.assertEqual(res["totals"]["seconds"], 32400)
        self.assertEqual(res["totals"]["worklogs"], 3)
        self.assertEqual(len(res["evolution"]), 82)

    def test_shift_profile_planned_exit_time(self):
        from config import ShiftProfile, TimeWindow
        from datetime import time

        # 1. Perfil padrao 6h_0745 com janela de 15:05 a 16:00 -> saida nominal 15:15
        p_6h = ShiftProfile(
            name="6h_0745",
            description="Turno 6h",
            target_hours=6.0,
            entry_window=TimeWindow("07:30", "08:15"),
            lunch_start_window=TimeWindow("11:30", "12:30"),
            lunch_end_window=TimeWindow("12:00", "13:30"),
            exit_window=TimeWindow("15:05", "16:00"),
        )
        self.assertEqual(p_6h.get_planned_exit_time(), time(15, 15))

        # 2. Perfil 8h padrao -> saida nominal 17:42
        p_8h = ShiftProfile(
            name="8h",
            description="Turno 8h",
            target_hours=8.0,
            entry_window=TimeWindow("07:15", "08:15"),
            lunch_start_window=TimeWindow("11:30", "12:30"),
            lunch_end_window=TimeWindow("12:55", "13:30"),
            exit_window=TimeWindow("17:25", "18:30"),
        )
        self.assertEqual(p_8h.get_planned_exit_time(), time(17, 42))

        # 3. Perfil personalizado com calculator persistido (ex: 16:45)
        p_custom = ShiftProfile(
            name="custom",
            description="Turno customizado",
            target_hours=7.0,
            entry_window=TimeWindow("08:00", "09:00"),
            lunch_start_window=TimeWindow("12:00", "13:00"),
            lunch_end_window=TimeWindow("13:00", "14:00"),
            exit_window=TimeWindow("16:30", "17:15"),
            calculator={"exit_hm": "16:45"},
        )
        self.assertEqual(p_custom.get_planned_exit_time(), time(16, 45))

    def test_bot_config_exit_warning_fields(self):
        from config import BotConfig

        cfg = BotConfig()
        # Valores padrao de fabrica
        self.assertTrue(cfg.exit_warning_enabled)
        self.assertEqual(cfg.exit_warning_minutes, 5)
        self.assertTrue(cfg.exit_warning_popup)

        # Serializacao e desserializacao
        cfg.exit_warning_enabled = False
        cfg.exit_warning_minutes = 15
        cfg.exit_warning_popup = False
        d = cfg.to_dict()
        self.assertFalse(d["exit_warning_enabled"])
        self.assertEqual(d["exit_warning_minutes"], 15)
        self.assertFalse(d["exit_warning_popup"])

        restored = BotConfig.from_dict(d)
        self.assertFalse(restored.exit_warning_enabled)
        self.assertEqual(restored.exit_warning_minutes, 15)
        self.assertFalse(restored.exit_warning_popup)

    def test_web_panel_alerts_payload_and_html(self):
        from web_panel import build_alerts_payload, HTML_PAGE

        payload = build_alerts_payload()
        self.assertIn("profile_name", payload)
        self.assertIn("planned_exit_hm", payload)
        self.assertIn("trigger_time_hm", payload)
        self.assertIn("warning_minutes", payload)
        self.assertIn("warning_enabled", payload)
        self.assertIn("warning_popup", payload)
        self.assertIn("fired_today", payload)

        # Confirma que a nova aba e seus controles estao no HTML
        self.assertIn('id="tab-alerts"', HTML_PAGE)
        self.assertIn('data-tab="tab-alerts"', HTML_PAGE)
        self.assertIn('id="cfg-alert-minutes"', HTML_PAGE)
        self.assertIn('id="cfg-alert-enabled"', HTML_PAGE)
        self.assertIn('id="cfg-alert-popup"', HTML_PAGE)
        self.assertIn('id="cfg-alert-toast"', HTML_PAGE)
        self.assertIn('setAlertMinutesQuick', HTML_PAGE)
        self.assertIn('testExitAlert', HTML_PAGE)
        self.assertIn('saveAlertConfig', HTML_PAGE)

    def test_engine_exit_warning_transition_timing(self):
        from engine import BotEngine
        from config import BotConfig, ShiftProfile, TimeWindow
        from storage import StateManager, DailyState
        from datetime import datetime, date, time
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            today = date.today()
            mgr = StateManager(base_dir=Path(tmpdir))
            st = DailyState(date_str=today.isoformat(), status="RUNNING")
            mgr.save_state(st)

            cfg = BotConfig()
            cfg.active_profile = "test_6h"
            cfg.profiles["test_6h"] = ShiftProfile(
                name="test_6h",
                description="Turno 6h teste",
                target_hours=6.0,
                entry_window=TimeWindow("07:30", "08:15"),
                lunch_start_window=TimeWindow("11:30", "12:30"),
                lunch_end_window=TimeWindow("12:00", "13:30"),
                exit_window=TimeWindow("15:05", "16:00"),
                calculator={"exit_hm": "15:15"},
            )
            cfg.exit_warning_enabled = True
            cfg.exit_warning_minutes = 5

            fired = []
            def _dummy_popup(sm, force=False):
                fired.append(True)

            engine = BotEngine(config=cfg, state_manager=mgr)
            import engine as engine_mod
            orig_popup = engine_mod.show_pre_exit_popup
            engine_mod.show_pre_exit_popup = _dummy_popup

            try:
                # 1. As 15:05 (antigo horario com bug: exit_window.start_time 15:10 - 5min = 15:05):
                # Com o calculo corrigido baseado na saida planejada 15:15, as 15:05 NAO deve disparar
                engine.check_scheduled_transitions(now=datetime.combine(today, time(15, 5, 0)))
                self.assertEqual(len(fired), 0)
                self.assertFalse(engine.state.prompted_exit_review)

                # 2. As 15:10 (exatos 5 minutos antes da saida planejada 15:15):
                # DEVE disparar o aviso
                engine.check_scheduled_transitions(now=datetime.combine(today, time(15, 10, 0)))
                self.assertEqual(len(fired), 1)
                self.assertTrue(engine.state.prompted_exit_review)
            finally:
                engine_mod.show_pre_exit_popup = orig_popup

    def test_show_pre_exit_popup_force_flag(self):
        from review_dialog import show_pre_exit_popup
        import sys
        from unittest.mock import patch, MagicMock

        with patch("review_dialog.BotConfig.load") as mock_cfg_load, \
             patch("review_dialog.send_notification") as mock_notify, \
             patch("review_dialog.subprocess.Popen") as mock_popen, \
             patch("review_dialog._bring_existing_popup_to_top", return_value=False):

            mock_cfg = MagicMock()
            mock_cfg.exit_warning_enabled = False
            mock_cfg.exit_warning_popup = False
            mock_cfg.notifications_enabled = False
            mock_cfg.get_current_profile.return_value.get_planned_exit_time.return_value.strftime.return_value = "15:15"
            mock_cfg_load.return_value = mock_cfg

            # 1. Sem force (comportamento diario normal): nao dispara subprocess nem popup
            show_pre_exit_popup(force=False)
            mock_popen.assert_not_called()

            # 2. Com force=True (disparo de teste explicito do usuario): dispara o subprocesso e o desktop WinSta0\Default
            show_pre_exit_popup(force=True)
            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args.kwargs
            self.assertIn("startupinfo", call_kwargs)
            si = call_kwargs["startupinfo"]
            if sys.platform == "win32":
                self.assertIsNotNone(si)
                self.assertEqual(si.lpDesktop, r"WinSta0\Default")


class TestReportReconciliationAndKeyCleaning(unittest.TestCase):
    def test_clean_jira_issue_key_patterns(self):
        from storage import clean_jira_issue_key

        self.assertEqual(clean_jira_issue_key("https://consisanet.atlassian.net/browse/NOTAON-5713"), "NOTAON-5713")
        self.assertEqual(clean_jira_issue_key("http://jira.internal/browse/ABC-1234?param=1#hash"), "ABC-1234")
        self.assertEqual(clean_jira_issue_key("  consisabi-427  "), "CONSISABI-427")
        self.assertEqual(clean_jira_issue_key("NOTAON-5713"), "NOTAON-5713")
        self.assertEqual(clean_jira_issue_key(""), "")
        self.assertEqual(clean_jira_issue_key(None), "")
        self.assertEqual(clean_jira_issue_key("invalid_key"), "INVALID_KEY")

    def test_day_summary_cleans_legacy_url_keys(self):
        from storage import DaySummary

        legacy_data = {
            "date_str": "2026-10-21",
            "total_seconds": 1151,
            "by_issue": {
                "https://consisanet.atlassian.net/browse/NOTAON-5713": 1151,
                "  CONSISABI-427  ": 3600,
            },
            "is_logged": True,
            "worklog_ids": ["123"],
            "completed_at": "2026-10-21T18:00:00",
        }
        summary = DaySummary.from_dict(legacy_data)
        self.assertIn("NOTAON-5713", summary.by_issue)
        self.assertIn("CONSISABI-427", summary.by_issue)
        self.assertNotIn("https://consisanet.atlassian.net/browse/NOTAON-5713", summary.by_issue)
        self.assertEqual(summary.by_issue["NOTAON-5713"], 1151)

    def test_build_report_payload_reconciles_from_jira(self):
        from datetime import date, timedelta
        from web_panel import build_report_payload

        test_dir = Path(tempfile.mkdtemp())
        try:
            today = date.today()
            d_prev = (today - timedelta(days=2)).isoformat()

            mock_worklogs = [
                {
                    "id": "9901",
                    "issue_key": "https://consisanet.atlassian.net/browse/NOTAON-5713",
                    "date": d_prev,
                    "time_spent_seconds": 21600,
                }
            ]

            with patch("config.get_default_config_dir", return_value=test_dir), \
                 patch("storage.get_default_config_dir", return_value=test_dir), \
                 patch("jira_client.JiraClient.get_user_worklogs_by_date_range", return_value=mock_worklogs):

                cfg = BotConfig(notifications_enabled=False)
                cfg.save()
                state_mgr = StateManager(base_dir=test_dir)
                self.assertEqual(len(state_mgr.load_history()), 0)

                payload = build_report_payload(days=7, fetch_jira=True)

                found_prev = next((r for r in payload["rows"] if r["date"] == d_prev), None)
                self.assertIsNotNone(found_prev)
                self.assertEqual(found_prev["total_seconds"], 21600)
                self.assertTrue(found_prev["is_logged"])
                self.assertEqual(len(found_prev["tickets"]), 1)
                self.assertEqual(found_prev["tickets"][0]["issue_key"], "NOTAON-5713")

                saved_history = state_mgr.load_history()
                self.assertEqual(len(saved_history), 1)
                self.assertEqual(saved_history[0].date_str, d_prev)
                self.assertIn("NOTAON-5713", saved_history[0].by_issue)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestThemeSelectorAndSeasonalThemes(unittest.TestCase):
    def test_theme_config_persistence(self):
        test_dir = Path(tempfile.mkdtemp())
        try:
            with patch("config.get_default_config_dir", return_value=test_dir):
                cfg = BotConfig(notifications_enabled=False)
                for theme in ["auto", "dark", "light", "halloween", "natal", "ano_novo", "pascoa"]:
                    cfg.theme = theme
                    cfg.save()
                    reloaded = BotConfig.load()
                    self.assertEqual(reloaded.theme, theme)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_theme_assets_and_badges(self):
        from web_assets import THEME_BADGES_HTML, THEME_CSS

        self.assertIn('badge-halloween', THEME_BADGES_HTML)
        self.assertIn('badge-natal', THEME_BADGES_HTML)
        self.assertIn('badge-ano_novo', THEME_BADGES_HTML)
        self.assertIn('badge-pascoa', THEME_BADGES_HTML)
        # Verifica que todas as declaracoes de tema existem no CSS
        self.assertIn('[data-theme="halloween"]', THEME_CSS)
        self.assertIn('[data-theme="natal"]', THEME_CSS)
        self.assertIn('[data-theme="ano_novo"]', THEME_CSS)
        self.assertIn('[data-theme="pascoa"]', THEME_CSS)
        self.assertIn('.theme-dropdown-wrap', THEME_CSS)
        self.assertIn('.theme-menu', THEME_CSS)

    def test_thematic_logos_and_lofi_scenes(self):
        from web_assets import (
            THEME_LOGOS_HTML,
            BRAND_TITLE_ICONS_HTML,
            LOFI_SCENES_HTML,
            THEME_CSS,
        )
        from web_panel import HTML_PAGE

        # 5 Logotipos completos
        self.assertIn('logo-default', THEME_LOGOS_HTML)
        self.assertIn('logo-halloween', THEME_LOGOS_HTML)
        self.assertIn('logo-natal', THEME_LOGOS_HTML)
        self.assertIn('logo-ano_novo', THEME_LOGOS_HTML)
        self.assertIn('logo-pascoa', THEME_LOGOS_HTML)

        # Icones de titulo
        self.assertIn('title-icon-halloween', BRAND_TITLE_ICONS_HTML)
        self.assertIn('title-icon-natal', BRAND_TITLE_ICONS_HTML)
        self.assertIn('title-icon-ano_novo', BRAND_TITLE_ICONS_HTML)
        self.assertIn('title-icon-pascoa', BRAND_TITLE_ICONS_HTML)

        # 5 Cenarios Lofi com animacoes SVG
        self.assertIn('scene-halloween', LOFI_SCENES_HTML)
        self.assertIn('scene-natal', LOFI_SCENES_HTML)
        self.assertIn('scene-ano_novo', LOFI_SCENES_HTML)
        self.assertIn('scene-pascoa', LOFI_SCENES_HTML)
        self.assertIn('scene-default', LOFI_SCENES_HTML)

        # Elementos especificos dos cenarios solicitados
        self.assertIn('lofi-scarecrow', LOFI_SCENES_HTML)
        self.assertIn('lofi-cat', LOFI_SCENES_HTML)
        self.assertIn('lofi-fireplace', LOFI_SCENES_HTML)
        self.assertIn('lofi-window-snow', LOFI_SCENES_HTML)
        self.assertIn('lofi-steam', LOFI_SCENES_HTML)

        # Presenca no HTML renderizado
        self.assertIn('sidebar-lofi-wrap', HTML_PAGE)
        self.assertIn('brand-title', HTML_PAGE)
        self.assertIn('brand-name', HTML_PAGE)
        self.assertIn('brand-title-icon', HTML_PAGE)
        # Protecao de layout: badges antigos nao vazam na marca
        self.assertNotIn('__THEME_BADGES__', HTML_PAGE)
        self.assertIn('.brand-theme-badge', THEME_CSS)
        self.assertIn('display: none !important', THEME_CSS)

        # Reprodutor de musica Lofi integrado aos temas com audio oficial Lofi Girl e YouTube
        self.assertIn('lofi-player', LOFI_SCENES_HTML)
        self.assertIn('lofi-track-title', LOFI_SCENES_HTML)
        self.assertIn('lofi-btn-play', LOFI_SCENES_HTML)
        self.assertIn('lofi-slider', LOFI_SCENES_HTML)
        self.assertIn('lofi-pill-vinyl', LOFI_SCENES_HTML)
        self.assertIn('lofi-pill-rain', LOFI_SCENES_HTML)
        self.assertIn('lofi-pill-fire', LOFI_SCENES_HTML)
        # Nomes limpos sem o sufixo "Real"
        self.assertIn('>Vinil</button>', LOFI_SCENES_HTML)
        self.assertIn('>Chuva</button>', LOFI_SCENES_HTML)
        self.assertIn('>Lareira</button>', LOFI_SCENES_HTML)
        self.assertNotIn('Chuva Real', LOFI_SCENES_HTML)
        self.assertNotIn('Lareira Real', LOFI_SCENES_HTML)
        self.assertIn('yt-player-music', LOFI_SCENES_HTML)
        self.assertIn('yt-player-vinyl', LOFI_SCENES_HTML)
        self.assertIn('yt-player-rain', LOFI_SCENES_HTML)
        self.assertIn('yt-player-fire', LOFI_SCENES_HTML)
        self.assertIn('.lofi-player', THEME_CSS)
        self.assertIn('.lofi-eq-bar', THEME_CSS)
        self.assertIn('.yt-audio-host', THEME_CSS)

        # Botao Lofi Girl posicionado no rodape lateral oposto ao perfil/status com avatar oficial
        self.assertIn('lofi-footer-btn', HTML_PAGE)
        self.assertIn('lofi-footer-link', HTML_PAGE)
        self.assertIn('lofi-footer-avatar', HTML_PAGE)
        self.assertIn('.lofi-footer-btn', THEME_CSS)
        self.assertIn('.lofi-footer-avatar', THEME_CSS)
        self.assertIn('.sidebar-footer-left', THEME_CSS)

        # Protecao do dropdown de temas com efeitos pausados
        self.assertIn('html.fx-paused .theme-menu', THEME_CSS)
        self.assertIn('visibility: visible !important', THEME_CSS)

        from web_assets import UI_FX_JS
        self.assertIn('LofiAudioEngine', UI_FX_JS)
        self.assertIn('initVinyl', UI_FX_JS)
        self.assertIn('syncVinyl', UI_FX_JS)
        self.assertIn('Lofi Girl', UI_FX_JS)
        self.assertIn('NIP3fNueJMA', UI_FX_JS)
        self.assertIn('UgHKb_7884o', UI_FX_JS)
        self.assertIn('V6V080RVeAE', UI_FX_JS)
        self.assertIn('XSXEaikz0Bc', UI_FX_JS)
        self.assertIn('0sfDth4lMLc', UI_FX_JS)
        self.assertIn('window.LofiPlayer', UI_FX_JS)


class TestJiraTicketsManagementAndDds(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.state_mgr = StateManager(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("urllib.request.urlopen")
    def test_get_my_assigned_tickets(self, mock_urlopen):
        import json
        mock_data = {
            "issues": [
                {
                    "key": "CONSISABI-418",
                    "fields": {
                        "summary": "Implementacao Regras BI",
                        "status": {"name": "Em Andamento"},
                        "priority": {"name": "Alta"},
                        "issuetype": {"name": "Tarefa"},
                        "customfield_11200": "https://consisa.sharepoint.com/:w:/r/dds.docx",
                        "customfield_12600": None,
                        "created": "2026-10-20T10:00:00.000-0300",
                        "updated": "2026-10-26T08:00:00.000-0300",
                    }
                },
                {
                    "key": "CONSISABI-442",
                    "fields": {
                        "summary": "Ajuste de relatorio",
                        "status": {"name": "Concluído"},
                        "priority": {"name": "Média"},
                        "issuetype": {"name": "Melhoria"},
                        "customfield_11200": None,
                        "customfield_12600": None,
                        "created": "2026-10-18T10:00:00.000-0300",
                        "updated": "2026-10-25T14:00:00.000-0300",
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)
        tickets = client.get_my_assigned_tickets(status_filter="all")
        self.assertEqual(len(tickets), 2)
        t1 = tickets[0]
        self.assertEqual(t1["key"], "CONSISABI-418")
        self.assertEqual(t1["summary"], "Implementacao Regras BI")
        self.assertEqual(t1["status"], "Em Andamento")
        self.assertEqual(t1["priority"], "Alta")
        self.assertTrue(t1["has_dds"])
        t2 = tickets[1]
        self.assertEqual(t2["key"], "CONSISABI-442")
        self.assertFalse(t2["has_dds"])

    @patch("urllib.request.urlopen")
    def test_get_ticket_dds_details(self, mock_urlopen):
        import json
        mock_data = {
            "key": "CONSISABI-418",
            "fields": {
                "summary": "Implementacao Regras BI",
                "status": {"name": "Em Andamento"},
                "priority": {"name": "Alta"},
                "issuetype": {"name": "Tarefa"},
                "created": "2026-10-20T10:00:00.000-0300",
                "updated": "2026-10-26T08:00:00.000-0300",
                "customfield_11200": "https://consisa.sharepoint.com/:w:/r/sites/DDS_418.docx",
                "customfield_12600": None,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Segue link DDS e Movidesk Ticket: 371517. Link: https://consisa.sharepoint.com/:w:/r/sites/DDS_Doc2.docx"}
                            ]
                        }
                    ]
                },
                "attachment": [
                    {
                        "id": "1001",
                        "filename": "especificacao.pdf",
                        "size": 2048,
                        "created": "2026-10-20T10:05:00.000-0300",
                        "content": "https://consisanet.atlassian.net/rest/api/2/attachment/content/1001"
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)
        details = client.get_ticket_dds_details("CONSISABI-418")
        self.assertEqual(details["key"], "CONSISABI-418")
        self.assertEqual(len(details["dds_links"]), 2)
        self.assertIn("embedview", details["dds_links"][0]["embed_url"])
        self.assertEqual(details["movidesk_ticket"], "371517")
        self.assertEqual(len(details["attachments"]), 1)
        self.assertEqual(details["attachments"][0]["name"], "especificacao.pdf")

    def test_web_markup_and_css_gestao_tickets(self):
        from web_panel import HTML_PAGE
        from web_assets import THEME_CSS

        # Aba de Tickets e Modal DDS presentes no HTML da SPA
        self.assertIn('tab-tickets', HTML_PAGE)
        self.assertIn('ticket-dds-modal', HTML_PAGE)
        self.assertIn('modal-dds-links-container', HTML_PAGE)
        self.assertIn('modal-ticket-description', HTML_PAGE)
        self.assertIn('modal-btn-start-ticket', HTML_PAGE)
        self.assertIn('loadMyTickets', HTML_PAGE)
        self.assertIn('openTicketDdsModal', HTML_PAGE)
        self.assertIn('startTicketFromCard', HTML_PAGE)
        self.assertIn('filterTicketsList', HTML_PAGE)

        # Recursos avancados: Leitor DDS nativo, Timeline e Imagens
        self.assertIn('subtab-btn-timeline', HTML_PAGE)
        self.assertIn('subtab-btn-images', HTML_PAGE)
        self.assertIn('subtab-btn-dds', HTML_PAGE)
        self.assertIn('modal-timeline-container', HTML_PAGE)
        self.assertIn('modal-images-grid', HTML_PAGE)
        self.assertIn('image-lightbox-modal', HTML_PAGE)
        self.assertIn('openImageLightbox', HTML_PAGE)
        self.assertIn('closeImageLightbox', HTML_PAGE)
        self.assertIn('copyDdsText', HTML_PAGE)
        self.assertIn('modal-dds-fullscreen-btn', HTML_PAGE)
        self.assertIn('switchModalSubtab', HTML_PAGE)

        # Recursos avancados: Menu lateral com categorias e dropdowns colapsaveis
        self.assertIn('nav-group-tickets', HTML_PAGE)
        self.assertIn('nav-group-jornada', HTML_PAGE)
        self.assertIn('nav-group-perfil', HTML_PAGE)
        self.assertIn('toggleNavGroup', HTML_PAGE)
        self.assertIn('initNavGroups', HTML_PAGE)

        # Regras CSS para os cards, badges, dropdowns, leitor nativo, timeline e galeria
        self.assertIn('.tickets-grid', THEME_CSS)
        self.assertIn('.ticket-card', THEME_CSS)
        self.assertIn('.badge-dds', THEME_CSS)
        self.assertIn('.badge-active-pulse', THEME_CSS)
        self.assertIn('.dds-link-card', THEME_CSS)
        self.assertIn('.nav-group-toggle', THEME_CSS)
        self.assertIn('.nav-group-items', THEME_CSS)
        self.assertIn('.modal-dialog.is-fullscreen', THEME_CSS)
        self.assertIn('.dds-viewer-container', THEME_CSS)
        self.assertIn('.movidesk-banner', THEME_CSS)
        self.assertIn('.dds-native-viewer', THEME_CSS)
        self.assertIn('.timeline-container', THEME_CSS)
        self.assertIn('.timeline-card', THEME_CSS)
        self.assertIn('.image-gallery-grid', THEME_CSS)

    def test_extrair_texto_docx(self):
        import io
        import zipfile
        from jira_client import extrair_texto_docx

        docx_buffer = io.BytesIO()
        with zipfile.ZipFile(docx_buffer, "w") as z:
            xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>
                    <w:p><w:r><w:t>DDS - Documento de Solução</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Regra de Negócio: Campo X deve ser calculado.</w:t></w:r></w:p>
                </w:body>
            </w:document>
            """
            z.writestr("word/document.xml", xml)
            z.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\nfakeimage")

        text, images = extrair_texto_docx(docx_buffer.getvalue())
        self.assertIn("DDS - Documento de Solução", text)
        self.assertIn("Regra de Negócio: Campo X deve ser calculado.", text)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["filename"], "image1.png")
        self.assertTrue(images[0]["data_url"].startswith("data:image/png;base64,"))

    @patch("urllib.request.urlopen")
    def test_comments_timeline_and_movidesk(self, mock_urlopen):
        import json
        mock_data = {
            "key": "CONSISABI-325",
            "fields": {
                "summary": "TICKET-379353 - Ajuste Balancete",
                "status": {"name": "Em Andamento"},
                "priority": {"name": "Média"},
                "issuetype": {"name": "Tarefa"},
                "created": "2026-01-07T10:00:00.000-0300",
                "updated": "2026-01-08T10:00:00.000-0300",
                "reporter": {"displayName": "Julio - Fortaleza"},
                "assignee": {"displayName": "Dev Jira"},
                "description": "Descrição da tarefa",
                "attachment": [
                    {
                        "id": "2001",
                        "filename": "screenshot.png",
                        "size": 5000,
                        "mimeType": "image/png",
                        "content": "https://consisanet.atlassian.net/rest/api/2/attachment/content/2001"
                    }
                ],
                "comment": {
                    "comments": [
                        {
                            "id": "501",
                            "author": {"displayName": "TI", "avatarUrls": {"48x48": "https://avatar.png"}},
                            "created": "2026-01-07T13:41:55.000-0300",
                            "body": "Julio - Fortaleza:\r\nsegue dds em anexo\r\n#MovideskAction#"
                        },
                        {
                            "id": "502",
                            "author": {"displayName": "Caio Dias", "avatarUrls": {}},
                            "created": "2026-01-19T15:56:15.000-0300",
                            "body": "Ajuste realizado conforme DDS."
                        }
                    ]
                }
            }
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)
        details = client.get_ticket_dds_details("CONSISABI-325")

        # Timeline
        self.assertEqual(len(details["comments_timeline"]), 2)
        c1 = details["comments_timeline"][0]
        self.assertTrue(c1["is_movidesk"])
        self.assertEqual(c1["movidesk_sender"], "Julio - Fortaleza")
        self.assertIn("segue dds em anexo", c1["body"])

        c2 = details["comments_timeline"][1]
        self.assertFalse(c2["is_movidesk"])
        self.assertEqual(c2["author"], "Caio Dias")

        # Imagens e proxy
        self.assertEqual(len(details["images"]), 1)
        self.assertEqual(details["images"][0]["name"], "screenshot.png")
        self.assertIn("/api/jira/attachment?url=", details["images"][0]["proxy_url"])

        # Movidesk info
        self.assertEqual(details["movidesk_info"]["ticket"], "379353")
        self.assertEqual(details["movidesk_info"]["solicitante"], "Julio - Fortaleza")

    def test_web_handler_start_ticket_endpoint(self):
        import io
        import json
        from web_panel import JiraBotWebHandler

        with patch("config.get_default_config_dir", return_value=self.test_dir), \
             patch("storage.get_default_config_dir", return_value=self.test_dir):

            cfg = BotConfig(notifications_enabled=False)
            cfg.save()

            req = MagicMock()
            handler = JiraBotWebHandler.__new__(JiraBotWebHandler)
            handler.request = req
            handler.client_address = ("127.0.0.1", 12345)
            handler.wfile = io.BytesIO()
            handler.path = "/api/jira/start-ticket"

            payload = {
                "issue_key": "CONSISABI-418",
                "comment": "Desenvolvimento DDS 418"
            }
            payload_bytes = json.dumps(payload).encode("utf-8")
            handler.rfile = io.BytesIO(payload_bytes)
            handler.headers = {"Content-Length": str(len(payload_bytes))}

            handler.send_response = MagicMock()
            handler.send_header = MagicMock()
            handler.end_headers = MagicMock()

            handler.do_POST()

            resp_bytes = handler.wfile.getvalue()
            self.assertTrue(len(resp_bytes) > 0)
            resp_data = json.loads(resp_bytes.decode("utf-8"))
            self.assertTrue(resp_data.get("success"))
            self.assertEqual(resp_data.get("active_ticket"), "CONSISABI-418")
            self.assertEqual(resp_data.get("active_comment"), "Desenvolvimento DDS 418")

    def test_estruturar_conteudo_dds_parsing(self):
        from jira_client import estruturar_conteudo_dds

        sample_dds = """
DDS – Documento de Detalhamento da Solicitação

Solicitação Nº
TICKET-380374

Dados do Solicitante
Nome do solicitante / Setor:
Luiz Henrique Gielow
Código / Empresa Cliente:
55550001 - CONSISA INFORMATICA LTDA.
Nome do contato na Empresa Cliente:
Luiz Henrique Gielow

Data:
Preenchido pelo Solicitante
Selecione o Tipo desta Solicitação:
CORREÇÃO (erros no sistema)
ALTERAÇÃO (alterações de legislação, melhorias de rotinas existentes)
X
IMPLEMENTAÇÃO (novas funcionalidades, atendimentos de novas legislações)

Sistema / Módulo:
Consisa BI
Opção (caminho da funcionalidade no sistema):
BI Mobile
Versão atual do sistema (código e data/hora):
Empresa / Filial:
Consisa Matriz

Especificação dos dados
(Período, Nº Nota, Empregado etc.):
Parâmetros gerais de teste.

Detalhar com clareza quais são as necessidades do cliente, não deixando margem para interpretação incorreta (Incluir evidencias – telas – sequência de passos). Para cada necessidade detalhar
- O que: Descreva a necessidade específica do cliente, explicando claramente o que é necessário ou o que está sendo solicitado.
- Quando/Como: Detalhe o momento e a forma como essa necessidade ocorre. Inclua um passo a passo que explique claramente o processo ou a situação em que a necessidade se manifesta. Use capturas de tela, sequência de passos e outros artefatos visuais para ilustrar as situações e facilitar a compreensão.
Disponibilizar versões MOBILES do CONSISA BI para os cenários atualmente existentes.
Trata-se de uma adaptação de layout das visões atuais para formato mobile, com impacto principalmente em tempo de desenvolvimento.

Resultado Esperado:
Por quê: Explique o motivo por trás da necessidade, descrevendo o impacto ou a importância que essa solicitação tem para o cliente. Em caso de obrigações legais, indicar a data limite para a situação envolvida.
Obs.: Para os casos de melhoria detalhar a forma que o cliente trabalha com esta informação ou falta dela. (Se controla por planilha, caso tenha embasamento legal, consultoria disponibilizar)
Facilitar a visualização de indicadores;
Apoiar a estratégia comercial de vendas de BI com acesso mobile;
Atender pedidos específicos de clientes no cenário comercial.

Preenchido pela Análise de Negócios
Nome: Jhonatan Reiss
Data: 15/01/2025
Adaptar as visões atuais do CONSISA BI para versões Mobiles, apresentando os principais indicativos de cada visão:
Gestão Comercial;
Gestão de Compras.
Resultado esperado:
Adaptar as visões atuais do CONSISA BI para versões Mobiles.

Revisão final
Categoria
Descrição
Revisão
Padrão de codificação
Todos os códigos incluídos apenas para fins de testes foram devidamente retirados?
Sim
Os valores gerados pelo sistema estão corretos de acordo com as regras estabelecidas?
Sim
Interface
A ordem de tabulação dos campos está correta?
Sim
A máscara do(s) campo(s) está de acordo com o tipo do campo?
Não aplicável
"""
        res = estruturar_conteudo_dds(sample_dds)
        self.assertTrue(res["has_structured_data"])
        self.assertEqual(res["tipo"], "IMPLEMENTAÇÃO")
        self.assertEqual(res["solicitacao"], "TICKET-380374")
        self.assertEqual(res["solicitante"], "Luiz Henrique Gielow")
        self.assertEqual(res["empresa"], "55550001 - CONSISA INFORMATICA LTDA.")
        self.assertEqual(res["sistema"], "Consisa BI")
        self.assertEqual(res["opcao"], "BI Mobile")
        self.assertEqual(res["empresa_filial"], "Consisa Matriz")
        self.assertIn("Disponibilizar versões MOBILES do CONSISA BI", res["necessidade_cliente"])
        self.assertNotIn("Detalhar com clareza quais são as necessidades", res["necessidade_cliente"])
        self.assertIn("Facilitar a visualização de indicadores;", res["resultado_esperado"])
        self.assertNotIn("Por quê: Explique o motivo", res["resultado_esperado"])
        self.assertEqual(res["analise_negocios"]["responsavel"], "Jhonatan Reiss")
        self.assertEqual(res["analise_negocios"]["data"], "15/01/2025")
        self.assertIn("Adaptar as visões atuais do CONSISA BI", res["analise_negocios"]["detalhamento"])
        self.assertTrue(len(res["checklist"]) >= 4)
        self.assertEqual(res["checklist"][0]["categoria"], "Padrão de codificação")
        self.assertEqual(res["checklist"][0]["resposta"], "Sim")
        self.assertEqual(res["checklist"][3]["categoria"], "Interface")
        self.assertEqual(res["checklist"][3]["resposta"], "Não aplicável")

    @patch("urllib.request.urlopen")
    def test_account_id_mention_resolution_and_timeline(self, mock_urlopen):
        import json

        def _mock_urlopen_router(req, *args, **kwargs):
            url = req.get_full_url() if hasattr(req, "get_full_url") else str(req)
            resp = MagicMock()
            resp.status = 200
            if "/rest/api/2/user?accountId=" in url:
                user_id = url.split("accountId=")[1]
                if "5cbf5ad212f0f60ffebf9bd3" in user_id:
                    resp.read.return_value = json.dumps({"displayName": "Jhonatan Reiss"}).encode("utf-8")
                elif "557058" in user_id:
                    resp.read.return_value = json.dumps({"displayName": "Roberto Zonta"}).encode("utf-8")
                else:
                    resp.read.return_value = json.dumps({"displayName": "Usuario Jira"}).encode("utf-8")
            elif "/rest/api/2/issue/TEST-1" in url:
                issue_data = {
                    "key": "TEST-1",
                    "fields": {
                        "summary": "Demanda de Teste Mencoes",
                        "status": {"name": "Em Andamento"},
                        "priority": {"name": "Alta"},
                        "issuetype": {"name": "Tarefa"},
                        "description": "Texto simples",
                        "attachment": [],
                        "comment": {
                            "comments": [
                                {
                                    "id": "1",
                                    "author": {"displayName": "TI"},
                                    "created": "2026-10-26T08:00:00.000-0300",
                                    "body": "Por favor [~accountid:5cbf5ad212f0f60ffebf9bd3] e [~accountid:557058:cc6f4eb2] avaliar dds."
                                }
                            ]
                        }
                    }
                }
                resp.read.return_value = json.dumps(issue_data).encode("utf-8")
            resp.__enter__.return_value = resp
            return resp

        mock_urlopen.side_effect = _mock_urlopen_router
        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)

        name1 = client.resolve_jira_account_id("5cbf5ad212f0f60ffebf9bd3")
        self.assertEqual(name1, "Jhonatan Reiss")
        name1_cached = client.resolve_jira_account_id("5cbf5ad212f0f60ffebf9bd3")
        self.assertEqual(name1_cached, "Jhonatan Reiss")

        details = client.get_ticket_dds_details("TEST-1")
        comments = details.get("comments_timeline", [])
        self.assertEqual(len(comments), 1)
        c = comments[0]
        self.assertIn("@Jhonatan Reiss", c["body"])
        self.assertIn("@Roberto Zonta", c["body"])
        self.assertNotIn("[~accountid:", c["body"])
        self.assertIn("Jhonatan Reiss", c["mentions"])
        self.assertIn("Roberto Zonta", c["mentions"])

    def test_web_markup_and_css_structured_dds(self):
        from web_panel import HTML_PAGE
        from web_assets import THEME_CSS

        self.assertIn('dds-structured-view', HTML_PAGE)
        self.assertIn('dds-raw-view', HTML_PAGE)
        self.assertIn('btn-toggle-dds-mode', HTML_PAGE)
        self.assertIn('dds-tipo-badge', HTML_PAGE)
        self.assertIn('dds-struct-meta-grid', HTML_PAGE)
        self.assertIn('dds-struct-necessidade', HTML_PAGE)
        self.assertIn('dds-struct-resultado', HTML_PAGE)
        self.assertIn('dds-struct-especificacao', HTML_PAGE)
        self.assertIn('dds-struct-analise', HTML_PAGE)
        self.assertIn('dds-card-checklist', HTML_PAGE)
        self.assertIn('dds-checklist-table', HTML_PAGE)
        self.assertIn('dds-checklist-tbody', HTML_PAGE)
        self.assertIn('toggleDdsViewMode', HTML_PAGE)
        self.assertIn('formatCommentBody', HTML_PAGE)

        self.assertIn('.dds-structured-container', THEME_CSS)
        self.assertIn('.dds-meta-grid', THEME_CSS)
        self.assertIn('.dds-meta-item', THEME_CSS)
        self.assertIn('.dds-section-card', THEME_CSS)
        self.assertIn('.dds-checklist-details', THEME_CSS)
        self.assertIn('.dds-checklist-summary', THEME_CSS)
        self.assertIn('.dds-checklist-table', THEME_CSS)
        self.assertIn('.mention-pill', THEME_CSS)

    @patch("urllib.request.urlopen")
    def test_parent_ticket_dds_inheritance(self, mock_urlopen):
        import json
        import urllib.parse

        def _mock_urlopen_parent_router(req, *args, **kwargs):
            raw_url = req.get_full_url() if hasattr(req, "get_full_url") else str(req)
            url = urllib.parse.unquote(raw_url)
            resp = MagicMock()
            resp.status = 200

            if "/rest/api/2/issue/CHILD-101" in url:
                child_data = {
                    "key": "CHILD-101",
                    "fields": {
                        "summary": "Implementar módulo sub-tarefa",
                        "status": {"name": "Em Andamento"},
                        "priority": {"name": "Média"},
                        "issuetype": {"name": "Desenvolvimento", "subtask": True},
                        "description": "Desenvolver conforme DDS pai",
                        "attachment": [],
                        "customfield_11200": None,
                        "customfield_12600": None,
                        "parent": {
                            "id": "1000",
                            "key": "PARENT-500",
                            "fields": {
                                "summary": "TICKET-99999 Demanda Principal com DDS",
                                "status": {"name": "Sprint Backlog"},
                                "priority": {"name": "Alta"},
                                "issuetype": {"name": "Solicitação", "subtask": False}
                            }
                        }
                    }
                }
                resp.read.return_value = json.dumps(child_data).encode("utf-8")

            elif "/rest/api/2/issue/PARENT-500" in url:
                parent_data = {
                    "key": "PARENT-500",
                    "fields": {
                        "summary": "TICKET-99999 Demanda Principal com DDS",
                        "status": {"name": "Sprint Backlog"},
                        "priority": {"name": "Alta"},
                        "issuetype": {"name": "Solicitação", "subtask": False},
                        "description": "Requisitos gerais",
                        "customfield_11200": "https://consisa.sharepoint.com/:w:/r/sites/DDS_Pai.docx",
                        "customfield_12600": None,
                        "attachment": [
                            {
                                "id": "901",
                                "filename": "especificacao_pai.pdf",
                                "size": 4096,
                                "created": "2026-10-20T10:00:00.000-0300",
                                "content": "https://consisanet.atlassian.net/rest/api/2/attachment/content/901"
                            }
                        ]
                    }
                }
                resp.read.return_value = json.dumps(parent_data).encode("utf-8")

            elif "/rest/api/2/search/jql" in url and "key in" not in url:
                search_data = {
                    "issues": [
                        {
                            "key": "CHILD-101",
                            "fields": {
                                "summary": "Implementar módulo sub-tarefa",
                                "status": {"name": "Em Andamento"},
                                "priority": {"name": "Média"},
                                "issuetype": {"name": "Desenvolvimento", "subtask": True},
                                "description": "Desenvolver conforme DDS pai",
                                "customfield_11200": None,
                                "customfield_12600": None,
                                "parent": {
                                    "key": "PARENT-500",
                                    "fields": {"summary": "TICKET-99999 Demanda Principal com DDS"}
                                }
                            }
                        }
                    ]
                }
                resp.read.return_value = json.dumps(search_data).encode("utf-8")

            elif "key in" in url:
                parent_search_data = {
                    "issues": [
                        {
                            "key": "PARENT-500",
                            "fields": {
                                "summary": "TICKET-99999 Demanda Principal com DDS",
                                "customfield_11200": "https://consisa.sharepoint.com/:w:/r/sites/DDS_Pai.docx",
                                "customfield_12600": None,
                                "description": "",
                                "attachment": []
                            }
                        }
                    ]
                }
                resp.read.return_value = json.dumps(parent_search_data).encode("utf-8")

            resp.__enter__.return_value = resp
            return resp

        mock_urlopen.side_effect = _mock_urlopen_parent_router
        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)

        # 1. Testa deteccao de subtarefa e heranca de status has_dds na listagem
        tickets = client.get_my_assigned_tickets()
        self.assertEqual(len(tickets), 1)
        t = tickets[0]
        self.assertEqual(t["key"], "CHILD-101")
        self.assertEqual(t["parent_key"], "PARENT-500")
        self.assertTrue(t["is_subtask"])
        self.assertTrue(t["has_dds"])
        self.assertTrue(t["dds_from_parent"])

        # 2. Testa heranca completa de DDS do ticket pai no get_ticket_dds_details
        details = client.get_ticket_dds_details("CHILD-101")
        self.assertEqual(details["key"], "CHILD-101")
        self.assertEqual(details["parent_key"], "PARENT-500")
        self.assertTrue(details["dds_inherited_from_parent"])
        self.assertTrue(len(details["dds_links"]) > 0)
        self.assertIn("DDS_Pai.docx", details["dds_links"][0]["url"])
        self.assertEqual(len(details["attachments"]), 1)
        self.assertEqual(details["attachments"][0]["name"], "especificacao_pai.pdf")
        self.assertEqual(details["movidesk_ticket"], "99999")

    def test_web_markup_parent_dds_inheritance(self):
        from web_panel import HTML_PAGE
        from web_assets import THEME_CSS

        self.assertIn('modal-ticket-parent-badge', HTML_PAGE)
        self.assertIn('dds-parent-inherited-alert', HTML_PAGE)
        self.assertIn('dds-parent-alert-key', HTML_PAGE)
        self.assertIn('dds-parent-alert-summary', HTML_PAGE)
        self.assertIn('dds-parent-alert-link', HTML_PAGE)
        self.assertIn('badge-parent', HTML_PAGE)
        self.assertIn('DDS NO PAI', HTML_PAGE)

        self.assertIn('.badge-parent', THEME_CSS)
        self.assertIn('.parent-info-banner', THEME_CSS)
        self.assertIn('.parent-link-pill', THEME_CSS)

    def test_web_markup_tree_hierarchy_view(self):
        from web_panel import HTML_PAGE
        from web_assets import THEME_CSS

        # Elementos HTML da arvore e alternador de modos
        self.assertIn('btn-view-tree', HTML_PAGE)
        self.assertIn('btn-view-grid', HTML_PAGE)
        self.assertIn('tickets-view-mode-toggle', HTML_PAGE)
        self.assertIn('tree-actions-bar', HTML_PAGE)
        self.assertIn('setTicketsViewMode', HTML_PAGE)
        self.assertIn('toggleTreeGroup', HTML_PAGE)
        self.assertIn('expandAllTreeGroups', HTML_PAGE)
        self.assertIn('collapseAllTreeGroups', HTML_PAGE)
        self.assertIn('renderTicketsTree', HTML_PAGE)
        self.assertIn('renderSingleTicketCard', HTML_PAGE)

        # Classes CSS da arvore
        self.assertIn('.tickets-tree-container', THEME_CSS)
        self.assertIn('.tree-parent-group', THEME_CSS)
        self.assertIn('.tree-parent-card', THEME_CSS)
        self.assertIn('.tree-parent-header', THEME_CSS)
        self.assertIn('.tree-parent-title', THEME_CSS)
        self.assertIn('.tree-chevron-btn', THEME_CSS)
        self.assertIn('.tree-children-container', THEME_CSS)
        self.assertIn('.tree-child-card', THEME_CSS)
        self.assertIn('.tree-child-title', THEME_CSS)
        self.assertIn('.tree-independent-section', THEME_CSS)

    def test_estruturar_conteudo_dds_full_sections(self):
        from jira_client import estruturar_conteudo_dds

        dds_sample = """
        DDS – Documento de Detalhamento da Solicitação
        Solicitação Nº
        TICKET-445566
        Dados do Solicitante
        Nome do solicitante / Setor:
        Carlos Eduardo / Comercial
        Código / Empresa Cliente:
        12345 - CONSISA INFORMATICA LTDA
        Nome do contato na Empresa Cliente:
        Carlos Eduardo
        Data:
        10/01/2025
        Selecione o Tipo desta Solicitação:
        CORREÇÃO (erros no sistema)
        [X] ALTERAÇÃO (alterações de legislação, melhorias de rotinas existentes)
        IMPLEMENTAÇÃO (novas funcionalidades)
        Sistema / Módulo:
        Consisa BI
        Opção (caminho da funcionalidade no sistema):
        Financeiro > DRE Gerencial
        Versão atual do sistema:
        2025.1.0
        Empresa / Filial:
        01 / 0001
        Detalhar com clareza quais são as necessidades do cliente:
        Ajustar o cálculo de deduções da receita bruta no relatório gerencial.
        Resultado Esperado:
        Cálculo apurado de acordo com a regra contábil da nova instrução normativa.

        Preenchido pelo Suporte:
        Nome: Lucas Suporte
        Data: 11/01/2025
        Testado na base de homologação com divergência confirmada no somatório.

        Preenchido pela Análise de Negócios
        Nome: Jhonatan Reiss
        Data: 12/01/2025
        Ajustar a formula do campo vlr_deducao no cubo DRE.

        Preenchido pelo Desenvolvimento (dados necessários para encaminhamento ao teste de implementação)
        Nome: Caio Desenvolvedor
        Data: 15/01/2025
        Alterada a procedure SP_BI_CALC_DEDUCAO e atualizada a unit uDREView.pas.

        Revisão final
        Padrão de codificação
        Todos os códigos incluídos apenas para fins de testes foram devidamente retirados?
        Sim
        Todas as variáveis foram devidamente inicializadas?
        Sim
        Interface
        A ordem de tabulação dos campos está correta?
        Sim

        Recomendações ao teste de implementação:
        Executar a consolidação do período 01/2025 e comparar com o extrato analítico da filial 01.

        Preenchido pelo Teste de Implementação
        Nome: Jhonatan Homologador
        Data: 18/01/2025
        Executados testes no ambiente de homologação com 3 cenários de deduções fiscais.

        Resultado (release ou divergência entre o esperado e o que o sistema está fazendo):
        1. Validação do cálculo de deduções aprovada sem divergências.
        2. Extrato analítico conferido com a contabilidade.
        3. Liberado para release de versão mensal.
        """

        res = estruturar_conteudo_dds(dds_sample)
        self.assertTrue(res["has_structured_data"])
        self.assertEqual(res["solicitacao"], "TICKET-445566")
        self.assertEqual(res["solicitante"], "Carlos Eduardo / Comercial")
        self.assertEqual(res["empresa"], "12345 - CONSISA INFORMATICA LTDA")
        self.assertEqual(res["tipo"], "ALTERAÇÃO")
        self.assertEqual(res["sistema"], "Consisa BI")
        self.assertEqual(res["opcao"], "Financeiro > DRE Gerencial")
        self.assertIn("Ajustar o cálculo", res["necessidade_cliente"])
        self.assertIn("Cálculo apurado", res["resultado_esperado"])

        # Valida Suporte
        self.assertEqual(res["suporte"]["responsavel"], "Lucas Suporte")
        self.assertEqual(res["suporte"]["data"], "11/01/2025")
        self.assertIn("Testado na base", res["suporte"]["detalhamento"])

        # Valida Analise de Negocios
        self.assertEqual(res["analise_negocios"]["responsavel"], "Jhonatan Reiss")
        self.assertEqual(res["analise_negocios"]["data"], "12/01/2025")

        # Valida Desenvolvimento (Caio)
        self.assertEqual(res["desenvolvimento"]["responsavel"], "Caio Desenvolvedor")
        self.assertEqual(res["desenvolvimento"]["data"], "15/01/2025")
        self.assertIn("SP_BI_CALC_DEDUCAO", res["desenvolvimento"]["detalhamento"])
        self.assertIn("Executar a consolidação", res["desenvolvimento"]["recomendacoes"])

        # Valida Checklist
        self.assertTrue(len(res["checklist"]) >= 3)

        # Valida Teste de Implementacao (Jhonatan)
        self.assertEqual(res["teste_implementacao"]["responsavel"], "Jhonatan Homologador")
        self.assertEqual(res["teste_implementacao"]["data"], "18/01/2025")
        self.assertIn("3 cenários de deduções", res["teste_implementacao"]["detalhamento"])

        # Valida Resultado da Homologacao
        self.assertEqual(res["resultado_homologacao"]["tipo"], "Release")
        self.assertIn("Liberado para release", res["resultado_homologacao"]["detalhamento"])

    def test_web_markup_dds_full_sections_and_sharepoint_embed(self):
        from web_panel import HTML_PAGE
        from web_assets import THEME_CSS

        # Sub-aba e painel de SharePoint Embed
        self.assertIn('subtab-btn-sharepoint', HTML_PAGE)
        self.assertIn('modal-view-sharepoint', HTML_PAGE)
        self.assertIn('modal-sharepoint-iframe', HTML_PAGE)
        self.assertIn('modal-sp-external-link', HTML_PAGE)
        self.assertIn('dds-sharepoint-callout-banner', HTML_PAGE)
        self.assertIn('reloadSharepointIframe', HTML_PAGE)
        self.assertIn('ensureSharepointIframeLoaded', HTML_PAGE)

        # Novos cards executivos na visao estruturada da DDS
        self.assertIn('dds-card-suporte', HTML_PAGE)
        self.assertIn('dds-struct-suporte', HTML_PAGE)
        self.assertIn('dds-card-desenvolvimento', HTML_PAGE)
        self.assertIn('dds-struct-dev', HTML_PAGE)
        self.assertIn('dds-struct-dev-rec', HTML_PAGE)
        self.assertIn('dds-card-teste', HTML_PAGE)
        self.assertIn('dds-struct-teste', HTML_PAGE)
        self.assertIn('dds-card-resultado-homologacao', HTML_PAGE)
        self.assertIn('dds-struct-resultado-homologacao', HTML_PAGE)

        # Classes CSS adicionadas
        self.assertIn('.dds-sp-callout-banner', THEME_CSS)
        self.assertIn('.sharepoint-embed-toolbar', THEME_CSS)
        self.assertIn('.sharepoint-embed-note', THEME_CSS)
        self.assertIn('.sharepoint-hub-container', THEME_CSS)
        self.assertIn('.sharepoint-reader-box', THEME_CSS)
        self.assertIn('.sharepoint-reader-content', THEME_CSS)

    def test_modal_no_horizontal_overflow_css(self):
        from web_assets import THEME_CSS
        # Garante que classes criticas do modal previnem overflow horizontal
        self.assertIn('.modal-body {', THEME_CSS)
        self.assertIn('overflow-x: hidden !important;', THEME_CSS)
        self.assertIn('.ticket-modal {', THEME_CSS)
        self.assertIn('.dds-view-container {', THEME_CSS)

    def test_subtask_dds_enrichment_logic(self):
        from jira_client import estruturar_conteudo_dds
        sample_raw = """
        DDS - Documento de Detalhamento da Solicitação
        Solicitação Nº 379353
        Nome do solicitante / Setor: Julio Schmidt
        Código / Empresa Cliente: 5550003 - Fortaleza
        Detalhar com clareza quais são as necessidades: Ajustar visão de BI no Balancete.
        Resultado Esperado: BI Saldo anterior correto.
        Preenchido pela Análise de Negócios
        Nome: Jhonatan Reiss
        Data: 07/01/2026
        Adaptar visões atuais do Consisa BI.
        """
        struct = estruturar_conteudo_dds(sample_raw)
        self.assertTrue(struct["has_structured_data"])
        self.assertEqual(struct["solicitacao"], "379353")
        self.assertEqual(struct["analise_negocios"]["responsavel"], "Jhonatan Reiss")
        # Sem preenchimento inicial no rascunho
        self.assertEqual(struct["desenvolvimento"]["detalhamento"], "")

        # Simula o enriquecimento por subtarefa
        dev_notes = ["d_calendario acumulado saldo anterior e saldo atual ajustado", "tabela calculada criada"]
        struct["desenvolvimento"]["detalhamento"] = "\n".join(dev_notes)
        struct["desenvolvimento"]["responsavel"] = "Caio Dias"
        struct["desenvolvimento"]["data"] = "19/01/2026"
        struct["teste_implementacao"]["detalhamento"] = "Testes de homologacao realizados"
        struct["teste_implementacao"]["responsavel"] = "Jhonatan Reiss"
        struct["resultado_homologacao"]["detalhamento"] = "1. Calculo ajustado\n2. Filtros validados\n3. Release liberado"

        self.assertEqual(struct["desenvolvimento"]["responsavel"], "Caio Dias")
        self.assertIn("tabela calculada", struct["desenvolvimento"]["detalhamento"])
        self.assertEqual(struct["teste_implementacao"]["responsavel"], "Jhonatan Reiss")
        self.assertIn("Release liberado", struct["resultado_homologacao"]["detalhamento"])

    def test_docx_consisa_table_extraction_logo_filter_and_inline_images(self):
        import io
        import zipfile
        from jira_client import extrair_documento_docx_completo

        docx_buf = io.BytesIO()
        with zipfile.ZipFile(docx_buf, "w") as zf:
            rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rIdLogo" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
                <Relationship Id="rIdDevImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image2.png"/>
                <Relationship Id="rIdTestImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image3.png"/>
            </Relationships>
            """
            doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                        xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                        xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                <w:body>
                    <w:tbl>
                        <w:tr>
                            <w:tc><w:p><w:r><w:drawing><a:graphic><a:graphicData><a:blip r:embed="rIdLogo"/></a:graphicData></a:graphic></w:drawing></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>DDS - Documento de Detalhamento da Solicitação</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Solicitação Nº</w:t></w:r></w:p><w:p><w:r><w:t>379353</w:t></w:r></w:p></w:tc>
                        </w:tr>
                    </w:tbl>
                    <w:tbl>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Especificação dos dados (Período, Nº Nota, Empregado etc.):</w:t></w:r></w:p><w:p><w:r><w:t>-</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc>
                                <w:p><w:r><w:t>Detalhar com clareza quais são as necessidades do cliente:</w:t></w:r></w:p>
                                <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Ajustar saldo anterior</w:t></w:r><w:r><w:t> na visão de Balancete.</w:t></w:r></w:p>
                            </w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Preenchido pela Análise de Sistemas</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Nome: Matheus Bellaver</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Data: //</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Criar view auxiliar para conferência contábil.</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Preenchido pelo Desenvolvimento (dados necessários para encaminhamento ao teste de implementação)</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Nome: Caio Dias</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Data: 19/01/2026</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc>
                                <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Medida DAX corrigida</w:t></w:r><w:r><w:t> conforme print abaixo:</w:t></w:r></w:p>
                                <w:p><w:r><w:drawing><a:graphic><a:graphicData><a:blip r:embed="rIdDevImg"/></a:graphicData></a:graphic></w:drawing></w:r></w:p>
                            </w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Preenchido pelo Teste de Implementação</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Nome: Jhonatan Reiss</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Data: 20/01/2026</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc>
                                <w:p><w:r><w:t>Conferido o resultado parcial na filial 01 e anexada evidência:</w:t></w:r></w:p>
                                <w:p><w:r><w:drawing><a:graphic><a:graphicData><a:blip r:embed="rIdTestImg"/></a:graphicData></a:graphic></w:drawing></w:r></w:p>
                            </w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc>
                                <w:p><w:r><w:t>Resultado (release ou divergência entre o esperado e o que o sistema está fazendo):</w:t></w:r></w:p>
                                <w:p><w:r><w:t>1. Saldo anterior conferido com razão contábil.</w:t></w:r></w:p>
                                <w:p><w:r><w:t>2. Aprovado para release.</w:t></w:r></w:p>
                            </w:tc>
                        </w:tr>
                    </w:tbl>
                </w:body>
            </w:document>
            """
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("word/document.xml", doc_xml)
            zf.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\nlogo_consisa")
            zf.writestr("word/media/image2.png", b"\x89PNG\r\n\x1a\nprint_caio_dev")
            zf.writestr("word/media/image3.png", b"\x89PNG\r\n\x1a\nprint_jhonatan_teste")

        parsed = extrair_documento_docx_completo(docx_buf.getvalue())
        emb = parsed["embedded_images"]
        # image1.png (logo do cabecalho Table 0 Row 0 Col 0) deve ser ignorado!
        self.assertEqual(len(emb), 2)
        self.assertEqual(emb[0]["filename"], "image2.png")
        self.assertEqual(emb[0]["section"], "Desenvolvimento")
        self.assertEqual(emb[1]["filename"], "image3.png")
        self.assertEqual(emb[1]["section"], "Teste de Implementação")

        sdds = parsed["structured_dds"]
        self.assertIsNotNone(sdds)
        self.assertTrue(sdds["has_structured_data"])
        self.assertEqual(sdds["solicitacao"], "379353")
        # Placeholder '-' e '//' devem ficar vazios
        self.assertEqual(sdds["especificacao_dados"], "")
        self.assertEqual(sdds["analise_sistemas"]["responsavel"], "Matheus Bellaver")
        self.assertEqual(sdds["analise_sistemas"]["data"], "")
        self.assertIn("Criar view auxiliar", sdds["analise_sistemas"]["detalhamento"])

        # Negrito e marcadores de imagem inline preservados
        self.assertIn("**Ajustar saldo anterior**", sdds["necessidade_cliente"])
        self.assertEqual(sdds["desenvolvimento"]["responsavel"], "Caio Dias")
        self.assertIn("**Medida DAX corrigida**", sdds["desenvolvimento"]["detalhamento"])
        self.assertIn("[[DOCX_IMG:docx-emb-1]]", sdds["desenvolvimento"]["detalhamento"])

        # Teste de implementacao nao pode truncar na palavra 'resultado' minuscula no meio da frase
        self.assertEqual(sdds["teste_implementacao"]["responsavel"], "Jhonatan Reiss")
        self.assertIn("anexada evidência", sdds["teste_implementacao"]["detalhamento"])
        self.assertIn("[[DOCX_IMG:docx-emb-2]]", sdds["teste_implementacao"]["detalhamento"])

        self.assertEqual(sdds["resultado_homologacao"]["tipo"], "Release")
        self.assertIn("Aprovado para release", sdds["resultado_homologacao"]["detalhamento"])
        self.assertIn("docx-render-table", parsed["document_html"])
        self.assertIn('data-docx-img-id="docx-emb-1"', parsed["document_html"])

    @patch("urllib.request.urlopen")
    def test_no_fake_homologacao_or_dev_leak_on_tickets_with_subtasks(self, mock_urlopen):
        import json

        mock_issue = {
            "key": "CONSISABI-380",
            "fields": {
                "summary": "Ajuste painel BI",
                "status": {"name": "Em Andamento"},
                "priority": {"name": "Normal"},
                "issuetype": {"name": "Solicitação"},
                "description": (
                    "DDS - Documento de Detalhamento da Solicitação\n"
                    "Solicitação Nº 390111\n"
                    "Especificação dos dados: -\n"
                    "Detalhar com clareza quais são as necessidades do cliente:\n"
                    "Criar filtro por regional.\n"
                    "Resultado Esperado:\n"
                    "Permitir análise regional.\n"
                    "Preenchido pela Análise de Sistemas\n"
                    "Nome: Matheus Bellaver\n"
                    "Data: //\n"
                    "Incluir dimensão d_regional.\n"
                ),
                "subtasks": [
                    {
                        "key": "CONSISABI-414",
                        "fields": {
                            "summary": "Subtarefa Desenvolvimento",
                            "status": {"name": "Concluído"},
                            "issuetype": {"name": "Desenvolvimento"},
                        },
                    },
                    {
                        "key": "CONSISABI-415",
                        "fields": {
                            "summary": "Subtarefa Testes",
                            "status": {"name": "Backlog"},
                            "issuetype": {"name": "Teste"},
                        },
                    },
                ],
                "attachment": [],
                "comment": {"comments": []},
            },
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_issue).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)
        details = client.get_ticket_dds_details("CONSISABI-380")
        sdds = details["structured_dds"]

        self.assertTrue(sdds["has_structured_data"])
        self.assertEqual(sdds["especificacao_dados"], "")
        self.assertEqual(sdds["analise_sistemas"]["responsavel"], "Matheus Bellaver")
        self.assertEqual(sdds["analise_sistemas"]["data"], "")
        # Garante ausencia absoluta de dados sinteticos / vazados de outros tickets
        self.assertEqual(sdds["desenvolvimento"]["detalhamento"], "")
        self.assertEqual(sdds["teste_implementacao"]["detalhamento"], "")
        self.assertEqual(sdds["resultado_homologacao"]["detalhamento"], "")
        self.assertNotIn("saldo anterior acumulado", json.dumps(details, ensure_ascii=False).lower())

    @patch("urllib.request.urlopen")
    def test_sharepoint_manager_encoding_and_manual_docx_override(self, mock_urlopen):
        import io
        import json
        import zipfile
        from sharepoint_client import SharePointManager, build_candidate_share_ids, encode_sharepoint_sharing_url

        sp_url = "https://consisasistemas.sharepoint.com/:w:/s/documentacao/IQD3R_iJ6S6z?e=zQejff"
        sid = encode_sharepoint_sharing_url(sp_url)
        self.assertTrue(sid.startswith("u!"))
        self.assertNotIn("=", sid)

        cands = build_candidate_share_ids(sp_url + "&action=embedview")
        self.assertTrue(len(cands) >= 2)
        self.assertEqual(cands[0], sid)

        sp_mgr = SharePointManager(base_dir=self.test_dir)
        st = sp_mgr.get_status()
        self.assertFalse(st["connected"])
        self.assertNotIn("access_token", json.dumps(st))

        # Cria .docx completo para testar importacao manual sobrepondo descricao/anexo
        docx_buf = io.BytesIO()
        with zipfile.ZipFile(docx_buf, "w") as zf:
            zf.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body>
                    <w:p><w:r><w:t>Solicitação Nº 379353</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Detalhar com clareza quais são as necessidades do cliente:</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Necessidade completa importada via DOCX.</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Preenchido pelo Desenvolvimento</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Nome: Caio Dias</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Data: 19/01/2026</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Implementação completa sincronizada.</w:t></w:r></w:p>
                  </w:body>
                </w:document>""",
            )
        save_res = sp_mgr.save_manual_docx("CONSISABI-325", "DDS-379353.docx", docx_buf.getvalue())
        self.assertTrue(save_res["success"])

        mock_issue = {
            "key": "CONSISABI-325",
            "fields": {
                "summary": "TICKET-379353 - Ajuste Balancete",
                "status": {"name": "Concluído"},
                "priority": {"name": "Normal"},
                "issuetype": {"name": "Solicitação"},
                "description": "Rascunho antigo",
                "customfield_12600": sp_url,
                "attachment": [],
                "comment": {"comments": []},
            },
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_issue).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = BotConfig(notifications_enabled=False)
        client = JiraClient(cfg.jira, self.state_mgr)
        details = client.get_ticket_dds_details("CONSISABI-325")
        self.assertEqual(details["dds_source"], "manual_docx")
        self.assertEqual(details["structured_dds"]["desenvolvimento"]["responsavel"], "Caio Dias")
        self.assertIn("Implementação completa sincronizada", details["structured_dds"]["desenvolvimento"]["detalhamento"])

    def test_web_rich_text_sharepoint_viewer_and_no_undefined_render_fn(self):
        from web_panel import HTML_PAGE
        from web_assets import THEME_CSS

        self.assertIn("formatDdsRichText", HTML_PAGE)
        self.assertIn("formatInlineRichSegments", HTML_PAGE)
        self.assertIn("sharepoint-doc-viewer", HTML_PAGE)
        self.assertIn("dds-card-analise-sistemas", HTML_PAGE)
        self.assertIn("dds-card-team-leader", HTML_PAGE)
        self.assertIn("startSharepointLogin", HTML_PAGE)
        self.assertIn("handleManualDocxUpload", HTML_PAGE)
        self.assertNotIn("renderDdsStructuredView(", HTML_PAGE)

        self.assertIn(".docx-visual-paper", THEME_CSS)
        self.assertIn(".docx-render-table", THEME_CSS)
        self.assertIn(".dds-inline-figure", THEME_CSS)
        self.assertIn(".sp-auth-panel", THEME_CSS)

    def test_single_table_consisa_docx_with_4col_checklist_and_correcao_keyword(self):
        import io
        import zipfile
        from jira_client import extrair_documento_docx_completo

        docx_buf = io.BytesIO()
        with zipfile.ZipFile(docx_buf, "w") as zf:
            zf.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body>
                    <w:tbl>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>DDS – Documento de Detalhamento da Solicitação</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Solicitação Nº</w:t></w:r></w:p><w:p><w:r><w:t>380000</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>Código / Empresa Cliente:</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Nome do contato na Empresa Cliente:</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Data:</w:t></w:r></w:p><w:p><w:r><w:t>09/03/2026</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>CORREÇÃO (erros no sistema)</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>ALTERAÇÃO (melhorias)</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>X</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>Detalhar com clareza quais são as necessidades do cliente, não deixando margem para interpretação incorreta. compreensão.</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc>
                          <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>-  O que:</w:t></w:r><w:r><w:t> Descreva a necessidade específica.</w:t></w:r></w:p>
                          <w:p><w:r><w:t>Como a correção paliativa já foi feita, precisamos reestruturar os filtros definitivamente.</w:t></w:r></w:p>
                        </w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>Preenchido pelo Team Leader</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Requisito</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Entendimento do Team Leader</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Cartão</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Pacote</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Fonte</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>Implementação</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc><w:p><w:r><w:t>Preenchido pelo Desenvolvimento</w:t></w:r></w:p></w:tc>
                      </w:tr>
                      <w:tr>
                        <w:tc>
                          <w:tbl>
                            <w:tr><w:tc><w:p><w:r><w:t>Revisão final</w:t></w:r></w:p></w:tc></w:tr>
                            <w:tr>
                              <w:tc><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Categoria</w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Descrição</w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Revisão</w:t></w:r></w:p></w:tc>
                            </w:tr>
                            <w:tr>
                              <w:tc><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Padrão de codificação</w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Todos os códigos de teste foram retirados?</w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Sim</w:t></w:r></w:p></w:tc>
                            </w:tr>
                            <w:tr>
                              <w:tc><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>SQL</w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t>Pergunta sem resposta preenchida?</w:t></w:r></w:p></w:tc>
                              <w:tc><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
                            </w:tr>
                          </w:tbl>
                        </w:tc>
                      </w:tr>
                    </w:tbl>
                  </w:body>
                </w:document>""",
            )

        parsed = extrair_documento_docx_completo(docx_buf.getvalue())
        sdds = parsed["structured_dds"]
        self.assertIsNotNone(sdds)
        self.assertEqual(sdds["solicitacao"], "380000")
        self.assertEqual(sdds["empresa"], "")
        self.assertEqual(sdds["contato"], "")
        self.assertEqual(sdds["data_solicitacao"], "09/03/2026")
        self.assertEqual(sdds["tipo"], "ALTERAÇÃO")
        self.assertIn("correção paliativa já foi feita", sdds["necessidade_cliente"])
        self.assertNotIn("Descreva a necessidade", sdds["necessidade_cliente"])
        self.assertEqual(sdds["team_leader"]["detalhamento"], "")
        self.assertEqual(len(sdds["checklist"]), 1)
        self.assertEqual(sdds["checklist"][0]["categoria"], "Padrão de codificação")
        self.assertEqual(sdds["checklist"][0]["pergunta"], "Todos os códigos de teste foram retirados?")
        self.assertEqual(sdds["checklist"][0]["resposta"], "Sim")

    def test_detect_and_import_from_downloads_by_key_and_pasted_text(self):
        import io
        import zipfile
        from pathlib import Path
        from sharepoint_client import SharePointManager

        sp_mgr = SharePointManager(base_dir=self.test_dir)

        # 1. Teste de Colar Texto da DDS
        paste_txt = (
            "DDS - Documento de Detalhamento da Solicitação\n"
            "Solicitação Nº 379353\n"
            "Nome do solicitante / Setor: Julio Schmidt / Consisanet\n"
            "Código / Empresa Cliente: 5550003/ Fortaleza\n"
            "Data: 07/01/2026\n"
            "CORREÇÃO (erros no sistema)\nX\n"
            "Detalhar com clareza quais são as necessidades do cliente:\n"
            "Ajustar visão do BI no BALANCETE quanto ao saldo anterior.\n"
            "Preenchido pelo Desenvolvimento\n"
            "Nome: Caio Dias\n"
            "Data: 19/01/2026\n"
            "Implementação com filtros ajustados no modelo tabular.\n"
        )
        res_paste = sp_mgr.save_pasted_text("CONSISABI-325", paste_txt)
        self.assertTrue(res_paste["success"])
        loaded_paste = sp_mgr.load_pasted_text("CONSISABI-325")
        self.assertEqual(loaded_paste, paste_txt.strip())

        # 2. Teste de Deteccao de Arquivo .docx em Downloads (mockando pasta)
        mock_dl = Path(self.test_dir) / "MockDownloads"
        mock_dl.mkdir(parents=True, exist_ok=True)
        docx_file = mock_dl / "DDS-379353.docx"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("word/document.xml", "<w:document><w:body/></w:document>")
        docx_file.write_bytes(buf.getvalue())

        with patch("os.environ.get", return_value=str(self.test_dir)):
            # Simula USERPROFILE\Downloads
            real_dl = Path(self.test_dir) / "Downloads"
            real_dl.mkdir(parents=True, exist_ok=True)
            real_target = real_dl / "DDS-379353.docx"
            real_target.write_bytes(buf.getvalue())

            det_res = sp_mgr.detect_and_import_from_downloads("CONSISABI-325", ticket_summary="TICKET-379353 - Ajuste Balancete")
            self.assertTrue(det_res.get("success"))
            self.assertEqual(det_res.get("filename"), "DDS-379353.docx")

    def test_ui_offline_toolbar_and_no_forced_sp_auth(self):
        from web_panel import HTML_PAGE

        self.assertIn("dds-offline-toolbar", HTML_PAGE)
        self.assertIn("detectDdsFromDownloads", HTML_PAGE)
        self.assertIn("openPasteDdsModal", HTML_PAGE)
        self.assertIn("modal-paste-dds", HTML_PAGE)
        self.assertIn("setupDdsDragAndDrop", HTML_PAGE)
        self.assertIn("/api/jira/dds/detect-download", HTML_PAGE)
        self.assertIn("/api/jira/dds/paste", HTML_PAGE)

    def test_sharepoint_login_profiles_and_client_ids(self):
        from unittest.mock import MagicMock
        from sharepoint_client import (
            SharePointManager,
            MS_GRAPH_CLI_CLIENT_ID,
            AZURE_CLI_CLIENT_ID,
            SHAREPOINT_SCOPES,
        )

        sp_mgr = SharePointManager(base_dir=self.test_dir)

        # 1. Perfil Graph CLI (Padrao / Recomendado)
        mock_app_graph = MagicMock()
        mock_app_graph.initiate_device_flow.return_value = {
            "user_code": "GRAPH123",
            "verification_uri": "https://microsoft.com/devicelogin",
        }
        with patch("msal.PublicClientApplication", return_value=mock_app_graph) as mock_pca:
            res_graph = sp_mgr.start_login(mode="device", profile="graph_cli")
            self.assertEqual(res_graph["mode"], "device")
            self.assertEqual(res_graph["user_code"], "GRAPH123")
            self.assertEqual(res_graph["client_id"], MS_GRAPH_CLI_CLIENT_ID)
            self.assertEqual(mock_pca.call_args[0][0], MS_GRAPH_CLI_CLIENT_ID)
            self.assertEqual(mock_pca.call_args[1]["authority"], "https://login.microsoftonline.com/organizations")
            mock_app_graph.initiate_device_flow.assert_called_with(scopes=SHAREPOINT_SCOPES)

        # 2. Perfil Azure CLI
        mock_app_az = MagicMock()
        mock_app_az.initiate_device_flow.return_value = {
            "user_code": "AZURE456",
            "verification_uri": "https://microsoft.com/devicelogin",
        }
        with patch("msal.PublicClientApplication", return_value=mock_app_az) as mock_pca:
            res_az = sp_mgr.start_login(mode="device", profile="azure_cli")
            self.assertEqual(res_az["user_code"], "AZURE456")
            self.assertEqual(res_az["client_id"], AZURE_CLI_CLIENT_ID)
            self.assertEqual(mock_pca.call_args[0][0], AZURE_CLI_CLIENT_ID)
            self.assertEqual(mock_pca.call_args[1]["authority"], "https://login.microsoftonline.com/organizations")

        # 3. Perfil Custom Client ID
        mock_app_custom = MagicMock()
        mock_app_custom.initiate_device_flow.return_value = {
            "user_code": "CUST789",
            "verification_uri": "https://microsoft.com/devicelogin",
        }
        custom_cid = "12345678-aaaa-bbbb-cccc-123456789abc"
        with patch("msal.PublicClientApplication", return_value=mock_app_custom) as mock_pca:
            res_custom = sp_mgr.start_login(mode="device", profile="custom", custom_client_id=custom_cid)
            self.assertEqual(res_custom["user_code"], "CUST789")
            self.assertEqual(res_custom["client_id"], custom_cid)
            self.assertEqual(mock_pca.call_args[0][0], custom_cid)
            self.assertEqual(mock_pca.call_args[1]["authority"], "https://login.microsoftonline.com/organizations")

    def test_ui_sharepoint_profiles_and_automatic_sync_controls(self):
        from web_panel import HTML_PAGE

        self.assertIn("sp_profile_radio", HTML_PAGE)
        self.assertIn("graph_cli", HTML_PAGE)
        self.assertIn("azure_cli", HTML_PAGE)
        self.assertIn("sp-custom-client-id-input", HTML_PAGE)
        self.assertIn("showSharepointConnectPanel", HTML_PAGE)
        self.assertIn("closeSharepointConnectPanel", HTML_PAGE)
        self.assertIn("triggerSharepointLoginFromProfile", HTML_PAGE)
        self.assertIn("getSelectedSpProfile", HTML_PAGE)

    def test_updater_sync_pip_dependencies_and_git_auto_restart(self):
        from unittest.mock import MagicMock
        from updater import sync_pip_dependencies, perform_update

        # 1. Teste de execucao do pip
        mock_proc_ok = MagicMock()
        mock_proc_ok.returncode = 0
        mock_proc_ok.stdout = "Successfully installed"
        mock_proc_ok.stderr = ""
        with patch("subprocess.run", return_value=mock_proc_ok) as mock_sub:
            ok, msg = sync_pip_dependencies()
            self.assertTrue(ok)
            self.assertIn("sincronizadas com sucesso", msg)

        # 2. Teste de perform_update em modo Git com sync_deps
        mock_status_ok = MagicMock()
        mock_status_ok.returncode = 0
        mock_status_ok.stdout = ""

        mock_git_ok = MagicMock()
        mock_git_ok.returncode = 0
        mock_git_ok.stdout = "Updating eed6b51..7beb37c\nFast-forward"
        mock_git_ok.stderr = ""

        with patch("subprocess.run", side_effect=[mock_status_ok, mock_git_ok, mock_proc_ok]):
            res = perform_update(update_source="", sync_deps=True)
            self.assertTrue(res.get("success"))
            self.assertTrue(res.get("requires_restart"))
            self.assertIn("Git", res.get("message"))
            self.assertIn("sincronizadas com sucesso", res.get("message"))


if __name__ == "__main__":
    unittest.main()



