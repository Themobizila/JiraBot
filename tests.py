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
        try:
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


if __name__ == "__main__":
    unittest.main()



