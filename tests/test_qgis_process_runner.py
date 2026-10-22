import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from airflow.sdk import log as sdk_log
from logic import qgis_process_runner as runner


class FakeStdin:
    def __init__(self, error=None):
        self.payload = ""
        self.closed = False
        self.error = error

    def write(self, value):
        if self.error:
            raise self.error
        self.payload = value

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, lines=(), return_code=0, stdin=None):
        self.stdin = stdin if stdin is not None else FakeStdin()
        self.stdout = list(lines)
        self.return_code = return_code
        self.killed = False
        self.waited = False

    def kill(self):
        self.killed = True

    def wait(self):
        self.waited = True
        return self.return_code


class QgisProcessTests(unittest.TestCase):
    def test_validates_model_and_input_mapping_before_starting_process(self):
        invalid = (
            ("  ", {"inputs": {}}, ValueError),
            ("model:valid", [], TypeError),
            ("model:valid", {}, ValueError),
            ("model:valid", {"inputs": []}, TypeError),
            ("missing.model3", {"inputs": {}}, FileNotFoundError),
        )
        with patch.object(runner.subprocess, "Popen") as popen:
            for model, parameters, expected in invalid:
                with self.subTest(model=model, parameters=parameters):
                    with self.assertRaises(expected):
                        runner.run_qgis_model(model, parameters)
            popen.assert_not_called()

    @patch.object(runner, "_build_qgis_environment", return_value={"QT_QPA_PLATFORM": "offscreen"})
    @patch.object(runner.subprocess, "Popen")
    def test_success_sends_json_to_qgis_and_masks_named_secrets(self, popen, environment):
        process = FakeProcess(["first line\n", "\n", "second line\n"])
        popen.return_value = process
        parameters = {"inputs": {
            "PASSWORD": "secret-1", "service_token": "secret-2",
            "title": "Bogotá", "empty_secret": "",
        }, "ellipsoid": "WGS84"}

        with patch.object(sdk_log, "mask_secret") as mask:
            # The production module imports the function directly.
            with patch.object(runner, "mask_secret", mask):
                runner.run_qgis_model("model:parcel", parameters)

        self.assertEqual(json.loads(process.stdin.payload), parameters)
        self.assertTrue(process.stdin.closed)
        self.assertTrue(process.waited)
        self.assertFalse(process.killed)
        self.assertEqual(popen.call_args.args[0], [
            "qgis_process", "--verbose", "run", "model:parcel", "-",
        ])
        self.assertEqual(popen.call_args.kwargs["env"], environment.return_value)
        self.assertEqual(mask.call_count, 2)
        mask.assert_any_call("secret-1", name="PASSWORD")
        mask.assert_any_call("secret-2", name="service_token")

    @patch.object(runner, "_build_qgis_environment", return_value={})
    @patch.object(runner.subprocess, "Popen")
    def test_failure_reports_recent_output_without_losing_exit_code(self, popen, _):
        lines = [f"message {number}\n" for number in range(55)]
        process = FakeProcess(lines, return_code=7)
        popen.return_value = process

        with self.assertRaises(runner.QgisProcessError) as caught:
            runner.run_qgis_model("model:parcel", {"inputs": {}})

        message = str(caught.exception)
        self.assertIn("7", message)
        self.assertIn("message 54", message)
        self.assertNotIn("message 0\n", message)
        self.assertTrue(process.waited)

    @patch.object(runner, "_build_qgis_environment", return_value={})
    @patch.object(runner.subprocess, "Popen")
    def test_missing_pipes_and_write_failure_stop_subprocess(self, popen, _):
        for missing in ("stdin", "stdout"):
            process = FakeProcess()
            setattr(process, missing, None)
            popen.return_value = process
            with self.subTest(missing=missing):
                with self.assertRaises(runner.QgisProcessError):
                    runner.run_qgis_model("model:parcel", {"inputs": {}})
                self.assertTrue(process.killed)

        process = FakeProcess(stdin=FakeStdin(error=OSError("broken pipe")))
        popen.return_value = process
        with self.assertRaisesRegex(OSError, "broken pipe"):
            runner.run_qgis_model("model:parcel", {"inputs": {}})
        self.assertTrue(process.killed)
        self.assertTrue(process.waited)

    def test_model_path_and_display_name(self):
        with tempfile.TemporaryDirectory() as root:
            model = Path(root) / "parcel.model3"
            model.touch()
            runner._validate_model_reference(str(model))
            self.assertEqual(runner._model_display_name(str(model)), "parcel")
        self.assertEqual(runner._model_display_name("model:parcel"), "parcel")

    def test_environment_replaces_stale_runtime_and_preserves_qgis_profile(self):
        with tempfile.TemporaryDirectory() as root:
            runtime = str(Path(root) / "runtime")
            with patch.dict(os.environ, {
                "XDG_RUNTIME_DIR": "old-runtime",
                "QGIS_CUSTOM_CONFIG_PATH": "profile",
            }), patch.object(runner.tempfile, "mkdtemp", return_value=runtime):
                result = runner._build_qgis_environment()
        self.assertEqual(result["QT_QPA_PLATFORM"], "offscreen")
        self.assertEqual(result["XDG_RUNTIME_DIR"], runtime)
        self.assertEqual(result["QGIS_CUSTOM_CONFIG_PATH"], "profile")


if __name__ == "__main__":
    unittest.main()
