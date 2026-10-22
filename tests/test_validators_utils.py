import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from utils import validators_utils as validators


class ValidatorTests(unittest.TestCase):
    def test_input_file_must_exist_be_regular_and_readable(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "input.xtf"
            with self.assertRaises(FileNotFoundError):
                validators.input_file_validator(str(path))
            with self.assertRaises(ValueError):
                validators.input_file_validator(root)

            path.write_text("xtf data")
            with patch.object(validators.os, "access", return_value=False):
                with self.assertRaises(PermissionError):
                    validators.input_file_validator(str(path))
            validators.input_file_validator(str(path))

    @patch.object(validators, "_build_qgis_environment", return_value={"QGIS": "test"})
    @patch.object(validators.subprocess, "run")
    def test_qgis_model_checks_version_help_and_required_parameters(self, run, environment):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "QGIS 3.44", ""),
            subprocess.CompletedProcess([], 0, "INPUT and OUTPUT", ""),
        ]
        validators.qgis_model_validator("model:parcel", ["input", "output"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0], ["qgis_process", "help", "model:parcel"])
        self.assertEqual(run.call_args.kwargs["env"], environment.return_value)

    @patch.object(validators, "_build_qgis_environment", return_value={})
    @patch.object(validators.subprocess, "run")
    def test_qgis_model_reports_unavailable_binary_or_missing_model(self, run, _):
        run.return_value = subprocess.CompletedProcess([], 1, "", "qgis missing")
        with self.assertRaisesRegex(RuntimeError, "qgis missing"):
            validators.qgis_model_validator("model:parcel")

        run.side_effect = [
            subprocess.CompletedProcess([], 0, "QGIS 3.44", ""),
            subprocess.CompletedProcess([], 2, "", "model missing"),
        ]
        with self.assertRaisesRegex(RuntimeError, "model missing"):
            validators.qgis_model_validator("model:parcel")

    @patch.object(validators, "_build_qgis_environment", return_value={})
    @patch.object(validators.subprocess, "run")
    def test_qgis_model_detects_missing_parameters(self, run, _):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "QGIS 3.44", ""),
            subprocess.CompletedProcess([], 0, "INPUT", ""),
        ]
        with self.assertRaisesRegex(RuntimeError, "OUTPUT"):
            validators.qgis_model_validator("model:parcel", ["INPUT", "OUTPUT"])

    def test_connection_validator_lists_missing_fields(self):
        connection = SimpleNamespace(
            conn_id="postgres", host="localhost", schema="db", port=5432,
            login="user", password="password",
        )
        validators.etl_connection_validator(connection)

        connection.port = None
        connection.password = ""
        with self.assertRaises(ValueError) as caught:
            validators.etl_connection_validator(connection)
        self.assertIn("password", str(caught.exception))
        self.assertIn("port", str(caught.exception))
        self.assertIn("postgres", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
