from __future__ import annotations

import email.utils
import io
import ast
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import heightmap_limits, osm_access, osm_fetch
from backend.tf3_converter_core import _load_lua_table, _normalize_mod_descriptor


class HeightmapLimitTests(unittest.TestCase):
    def test_pixel_limit_boundaries_without_allocating_grid(self):
        self.assertEqual(
            heightmap_limits.validate_heightmap_pixels(
                heightmap_limits.MAX_HEIGHTMAP_PIXELS
            ),
            6145,
        )
        for pixels in (6146, 16385):
            with self.subTest(pixels=pixels), self.assertRaisesRegex(
                ValueError, "6145"
            ):
                heightmap_limits.validate_heightmap_pixels(pixels)

    def test_api_uses_same_pixel_limit(self):
        studio_root = Path(__file__).resolve().parents[1]
        api_tree = ast.parse(
            (studio_root / "backend" / "api.py").read_text(encoding="utf-8")
        )
        studio_api = next(
            node
            for node in api_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "StudioApi"
        )
        method = next(
            node
            for node in studio_api.body
            if isinstance(node, ast.FunctionDef) and node.name == "download_heightmap"
        )
        namespace = {"HL": heightmap_limits, "Path": Path}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "<api-test>", "exec"), namespace)
        api_type = type("StudioApiTestHarness", (), {"download_heightmap": namespace["download_heightmap"]})
        api = api_type()
        api.work = Path(tempfile.gettempdir())
        api.state = {"target_game": "tf3"}
        api._job = lambda *args, **kwargs: {"ok": True}

        rejected = api.download_heightmap({}, "huge", output_pixels=6146)
        self.assertFalse(rejected["ok"])
        self.assertIn("6145", rejected["error"])
        accepted = api.download_heightmap({}, "huge", output_pixels=6145)
        self.assertTrue(accepted["ok"])


class OSMCooldownTests(unittest.TestCase):
    def setUp(self):
        with osm_access._LOCK:
            osm_access._LAST_REQUEST.clear()
            osm_access._COOLDOWN_UNTIL.clear()

    def tearDown(self):
        with osm_access._LOCK:
            osm_access._LAST_REQUEST.clear()
            osm_access._COOLDOWN_UNTIL.clear()

    def test_429_response_sets_seconds_cooldown_and_waits(self):
        url = "https://overpass-api.de/api/interpreter"
        request = urllib.request.Request(url)
        error = urllib.error.HTTPError(
            url, 429, "Too many requests", {"Retry-After": "3"}, io.BytesIO()
        )
        now = [100.0]
        with (
            patch.object(osm_fetch.urllib.request, "urlopen", side_effect=error),
            patch.object(osm_access.time, "monotonic", side_effect=lambda: now[0]),
            patch.object(
                osm_access.time,
                "sleep",
                side_effect=lambda delay: now.__setitem__(0, now[0] + delay),
            ),
        ):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                osm_fetch._open_url(request, timeout=1)
            raised.exception.close()
            self.assertEqual(osm_access._COOLDOWN_UNTIL["overpass-api.de"], 103.0)
            osm_access.wait_for_request_slot(url)

        self.assertGreaterEqual(now[0], 103.0)

    def test_retry_after_http_date_is_supported(self):
        url = "https://nominatim.openstreetmap.org/search"
        wall_now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        retry_at = wall_now.timestamp() + 20
        retry_datetime = datetime.fromtimestamp(retry_at, timezone.utc)
        retry_headers = (
            email.utils.format_datetime(retry_datetime, usegmt=True),
            retry_datetime.strftime("%a %b %d %H:%M:%S %Y"),
        )
        with (
            patch.object(osm_access.time, "time", return_value=wall_now.timestamp()),
            patch.object(osm_access.time, "monotonic", return_value=50.0),
        ):
            for retry_header in retry_headers:
                osm_access.note_host_cooldown(url, retry_header)
        self.assertEqual(
            osm_access._COOLDOWN_UNTIL["nominatim.openstreetmap.org"], 70.0
        )


class OSMDownloadValidationTests(unittest.TestCase):
    def test_invalid_replacement_preserves_destination(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size=-1):
                body, self.body = self.body, b""
                return body

        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "map.osm"
            original = b"<osm version='0.6'>" + b"valid" * 100
            dest.write_bytes(original)
            invalid = b"not OSM XML " + b"x" * 500
            with (
                patch.object(osm_fetch, "wait_for_request_slot"),
                patch.object(
                    osm_fetch.urllib.request,
                    "urlopen",
                    return_value=Response(invalid),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "OSM XML"):
                    osm_fetch._download_to(
                        "https://overpass-api.de/api/interpreter",
                        dest,
                        b"query",
                        timeout=1,
                    )

            self.assertEqual(dest.read_bytes(), original)
            self.assertFalse(dest.with_name(dest.name + ".part").exists())


class ConverterCallbackTests(unittest.TestCase):
    def test_inline_callback_is_warned_and_not_written_as_filename(self):
        parsed = _load_lua_table(
            """
            function data()
              return {
                name = "Legacy",
                runFn = function() print("inline") end,
              }
            end
            """
        )
        descriptor = _normalize_mod_descriptor(parsed)
        self.assertIsNone(descriptor.run_script)
        self.assertNotIn("runScript", descriptor.as_mod_json())
        self.assertEqual(len(descriptor.warnings), 1)
        self.assertIn("inline run callback", descriptor.warnings[0])

    def test_filename_callback_reference_is_preserved(self):
        descriptor = _normalize_mod_descriptor(
            {"runScript": {"fileName": "scripts/run.lua"}}
        )
        self.assertEqual(descriptor.run_script, "scripts/run.lua")
        self.assertEqual(
            descriptor.as_mod_json()["runScript"],
            {"fileName": "scripts/run.lua"},
        )
        self.assertEqual(descriptor.warnings, [])


class StudioApiExposureTests(unittest.TestCase):
    def test_window_reference_is_private_but_dialog_operations_remain_available(self):
        studio_root = Path(__file__).resolve().parents[1]
        api_tree = ast.parse(
            (studio_root / "backend" / "api.py").read_text(encoding="utf-8")
        )
        main_tree = ast.parse(
            (studio_root / "main.py").read_text(encoding="utf-8")
        )
        studio_api = next(
            node
            for node in api_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "StudioApi"
        )
        self_references = [
            node.attr
            for node in ast.walk(studio_api)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ]
        self.assertNotIn("window", self_references)
        self.assertIn("_window", self_references)
        main_assignments = [
            node
            for node in ast.walk(main_tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "api"
                and target.attr == "_window"
                for target in node.targets
            )
        ]
        self.assertEqual(len(main_assignments), 1)

        dialog = next(
            node
            for node in studio_api.body
            if isinstance(node, ast.FunctionDef) and node.name == "_dialog"
        )
        fake_webview = SimpleNamespace(
            FileDialog=SimpleNamespace(FOLDER=2, OPEN=1)
        )
        dialog_namespace = {"webview": fake_webview}
        exec(
            compile(ast.Module(body=[dialog], type_ignores=[]), "<dialog-test>", "exec"),
            dialog_namespace,
        )
        calls = []

        class FakeWindow:
            def create_file_dialog(self, kind, **kwargs):
                calls.append((kind, kwargs))
                return ["selected"]

        api = SimpleNamespace(
            _window=FakeWindow(),
            work=Path(tempfile.gettempdir()),
        )
        self.assertEqual(dialog_namespace["_dialog"](api, folder=True), ["selected"])
        self.assertEqual(calls, [(2, {"directory": str(api.work)})])


if __name__ == "__main__":
    unittest.main()
