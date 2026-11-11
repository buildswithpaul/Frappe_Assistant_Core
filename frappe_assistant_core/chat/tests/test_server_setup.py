# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The server-setup check reads gunicorn's real flags and warns when FACO cannot be carried."""

from unittest.mock import MagicMock, patch

import frappe

from frappe_assistant_core.chat import server_setup
from frappe_assistant_core.chat.api.settings.registration import run_diagnostics
from frappe_assistant_core.chat.server_setup import (
    DEFAULT_EXPECTED_CHATTERS,
    RECOMMENDED_FIX,
    assess,
    get_server_setup,
    parse_gunicorn_cmdline,
    read_web_server_config,
)
from frappe_assistant_core.patches.v3_3.seed_expected_concurrent_chatters import execute as seed_patch
from frappe_assistant_core.tests.base_test import BaseAssistantTest


class TestParseGunicornCmdline(BaseAssistantTest):
    def test_parses_bench_style_cmdline(self):
        argv = "gunicorn -b 127.0.0.1:8000 -w 4 -t 120 frappe.app:application --preload".split()
        parsed = parse_gunicorn_cmdline(argv)
        self.assertEqual(parsed["worker_class"], "sync")
        self.assertEqual(parsed["workers"], 4)
        self.assertEqual(parsed["threads"], 1)
        self.assertEqual(parsed["timeout"], 120)

    def test_parses_docker_style_cmdline(self):
        argv = (
            "/home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/env/bin/gunicorn "
            "--chdir=/home/frappe/frappe-bench/sites --bind=0.0.0.0:8000 --threads=4 --workers=2 "
            "--worker-class=gthread --worker-tmp-dir=/dev/shm --timeout=120 "
            "--graceful-timeout=30 frappe.app:application --preload"
        ).split()
        parsed = parse_gunicorn_cmdline(argv)
        self.assertEqual(parsed["worker_class"], "gthread")
        self.assertEqual(parsed["workers"], 2)
        self.assertEqual(parsed["threads"], 4)
        self.assertEqual(parsed["timeout"], 120)

    def test_space_separated_long_options(self):
        argv = "gunicorn --workers 3 --threads 2 --worker-class gthread --timeout 90".split()
        parsed = parse_gunicorn_cmdline(argv)
        self.assertEqual((parsed["workers"], parsed["threads"], parsed["timeout"]), (3, 2, 90))
        self.assertEqual(parsed["worker_class"], "gthread")

    def test_short_worker_class(self):
        parsed = parse_gunicorn_cmdline("gunicorn -k gevent -w 2".split())
        self.assertEqual(parsed["worker_class"], "gevent")

    def test_gunicorn_defaults_apply(self):
        parsed = parse_gunicorn_cmdline(["gunicorn", "frappe.app:application"])
        self.assertEqual(
            (parsed["worker_class"], parsed["workers"], parsed["threads"], parsed["timeout"]),
            ("sync", 1, 1, 30),
        )

    def test_threads_with_sync_is_gthread(self):
        parsed = parse_gunicorn_cmdline("gunicorn -w 2 --threads 4".split())
        self.assertEqual(parsed["worker_class"], "gthread")

    def test_attached_short_forms(self):
        parsed = parse_gunicorn_cmdline("gunicorn -w4 -k=gthread -t120 --threads 2".split())
        self.assertEqual(
            (parsed["workers"], parsed["worker_class"], parsed["timeout"], parsed["threads"]),
            (4, "gthread", 120, 2),
        )

    def test_env_args_apply_under_the_cli_flags(self):
        # Production: GUNICORN_CMD_ARGS is set in the gunicorn master's environment; gunicorn
        # applies it over a config file and under the command line.
        parsed = parse_gunicorn_cmdline(
            "gunicorn -w 2 frappe.app:application".split(),
            env_args="--workers 8 --threads=4 -k gthread",
        )
        self.assertEqual((parsed["workers"], parsed["threads"]), (2, 4))
        self.assertEqual(parsed["worker_class"], "gthread")

    def test_config_file_makes_missing_values_unknown_not_default(self):
        parsed = parse_gunicorn_cmdline("gunicorn -c gunicorn.conf.py -w 4".split())
        self.assertEqual(parsed["workers"], 4)
        self.assertIsNone(parsed["threads"])
        self.assertIsNone(parsed["worker_class"])
        parsed = parse_gunicorn_cmdline("gunicorn --config=g.py".split())
        self.assertIsNone(parsed["workers"])

    def test_config_flag_in_env_args_counts(self):
        parsed = parse_gunicorn_cmdline(["gunicorn"], env_args="--config g.py")
        self.assertIsNone(parsed["worker_class"])

    def test_not_gunicorn_returns_none(self):
        self.assertIsNone(parse_gunicorn_cmdline(["python", "-m", "frappe.utils.bench_helper", "serve"]))
        self.assertIsNone(parse_gunicorn_cmdline(["werkzeug", "-w", "4"]))
        self.assertIsNone(parse_gunicorn_cmdline([]))


class TestAssess(BaseAssistantTest):
    def _config(self, worker_class, workers, threads):
        return {
            "worker_class": worker_class,
            "workers": workers,
            "threads": threads,
            "timeout": 120,
            "source": "gunicorn",
        }

    def test_sync_warns_with_fix(self):
        result = assess(self._config("sync", 16, 1), 10)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["fix"], RECOMMENDED_FIX)
        self.assertIn("sync workers", result["reasons"][0])

    def test_too_few_slots_warns(self):
        result = assess(self._config("gthread", 2, 4), 10)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["slots"], 8)
        self.assertEqual(result["required_slots"], 20)
        self.assertEqual(result["fix"], RECOMMENDED_FIX)

    def test_enough_slots_ok(self):
        result = assess(self._config("gthread", 4, 8), 10)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["slots"], 32)
        self.assertEqual(result["reasons"], [])
        self.assertIsNone(result["fix"])

    def test_async_workers_get_no_false_warning(self):
        for worker_class in ("gevent", "eventlet", "uvicorn.workers.UvicornWorker"):
            result = assess(self._config(worker_class, 1, 1), 10)
            self.assertEqual(result["status"], "ok", worker_class)
            self.assertEqual(result["reasons"], [])
            self.assertIsNone(result["fix"])

    def test_config_file_with_unread_values_is_unknown(self):
        result = assess(self._config(None, 4, None), 10)
        self.assertEqual(result["status"], "unknown")

    def test_unknown_source_is_unknown_not_ok(self):
        config = {
            "worker_class": None,
            "workers": None,
            "threads": None,
            "timeout": None,
            "source": "unknown",
        }
        result = assess(config, 10)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["slots"])
        self.assertEqual(result["required_slots"], 20)

    def test_conf_fallback_cannot_judge_the_class(self):
        config = {"worker_class": None, "workers": 4, "threads": None, "timeout": 120, "source": "conf"}
        self.assertEqual(assess(config, 10)["status"], "unknown")


class TestReadAndEndpoints(BaseAssistantTest):
    def setUp(self):
        super().setUp()
        # nosemgrep: frappe-setuser — test bootstrap; runs in an isolated transaction
        frappe.set_user("Administrator")

    def _patch_master(self, argv, env=None):
        # Production reads the gunicorn master's real cmdline via its parent pid; the test supplies
        # the argv a bench-managed master shows, because no gunicorn master exists under run-tests.
        process = MagicMock()
        process.cmdline.return_value = argv
        process.environ.return_value = env or {}
        return patch.object(server_setup.psutil, "Process", return_value=process)

    def test_reads_master_cmdline(self):
        with self._patch_master("gunicorn -w 2 --threads 4 -k gthread".split()):
            config = read_web_server_config()
        self.assertEqual(config["source"], "gunicorn")
        self.assertEqual((config["workers"], config["threads"]), (2, 4))

    def test_reads_gunicorn_cmd_args_from_master_environment(self):
        with self._patch_master(
            ["gunicorn", "frappe.app:application"],
            env={"GUNICORN_CMD_ARGS": "--workers=4 --threads=8 --worker-class=gthread"},
        ):
            result = get_server_setup()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["slots"], 32)

    def test_unreadable_environment_still_reads_cmdline(self):
        process = MagicMock()
        process.cmdline.return_value = "gunicorn -w 2".split()
        process.environ.side_effect = server_setup.psutil.AccessDenied()
        with patch.object(server_setup.psutil, "Process", return_value=process):
            config = read_web_server_config()
        self.assertEqual(config["workers"], 2)

    def test_falls_back_to_site_config(self):
        with self._patch_master(["python", "serve"]), patch.object(
            server_setup.frappe, "conf", frappe._dict(gunicorn_workers=6, http_timeout=90)
        ):
            config = read_web_server_config()
        self.assertEqual(config["source"], "conf")
        self.assertEqual((config["workers"], config["timeout"]), (6, 90))
        self.assertIsNone(config["worker_class"])

    def test_unknown_when_nothing_readable(self):
        with patch.object(server_setup.psutil, "Process", side_effect=OSError), patch.object(
            server_setup.frappe, "conf", frappe._dict()
        ):
            self.assertEqual(read_web_server_config()["source"], "unknown")

    def test_get_server_setup_merges_config_and_assessment(self):
        with self._patch_master("gunicorn -w 4 -t 120".split()):
            result = get_server_setup()
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["workers"], 4)
        self.assertEqual(result["worker_class"], "sync")

    def test_expected_chatters_comes_from_settings(self):
        frappe.db.set_single_value("FAC Chat Settings", "expected_concurrent_chatters", 50)
        with self._patch_master("gunicorn -w 4 --threads 8".split()):
            result = get_server_setup()
        self.assertEqual(result["required_slots"], 100)
        self.assertEqual(result["status"], "warning")

    def test_run_diagnostics_includes_server_setup_without_client(self):
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=None
        ), self._patch_master("gunicorn -w 4 -t 120".split()):
            result = run_diagnostics()
        self.assertEqual(result["status"], "no_client")
        self.assertEqual(result["server_setup"]["status"], "warning")

    def test_run_diagnostics_includes_server_setup_with_client(self):
        client = MagicMock()
        client.diagnose_registration.return_value = {"status": "ok", "bound_host": "x"}
        with patch(
            "frappe_assistant_core.chat.fac_cloud_client.get_fac_cloud_client", return_value=client
        ), self._patch_master("gunicorn -w 4 --threads 8".split()):
            result = run_diagnostics()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["server_setup"]["status"], "ok")


class TestSeedPatch(BaseAssistantTest):
    def test_patch_seeds_10_and_keeps_custom(self):
        # A site upgrading from 3.2 has a FAC Chat Settings row without the field, which reads 0
        # (Int type default), not the schema default.
        frappe.db.set_single_value("FAC Chat Settings", "expected_concurrent_chatters", 0)
        seed_patch()
        self.assertEqual(
            int(frappe.db.get_single_value("FAC Chat Settings", "expected_concurrent_chatters")),
            DEFAULT_EXPECTED_CHATTERS,
        )
        frappe.db.set_single_value("FAC Chat Settings", "expected_concurrent_chatters", 40)
        seed_patch()
        self.assertEqual(
            int(frappe.db.get_single_value("FAC Chat Settings", "expected_concurrent_chatters")), 40
        )
