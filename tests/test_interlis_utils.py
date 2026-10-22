import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.ili2db_config import Ili2DbConfiguration
from utils import interlis_utils


class InterlisProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.jar = self.root / "ili2db.jar"
        self.jar.touch()
        self.config = Ili2DbConfiguration()
        self.config.ILI2DB_JAR_PATH = str(self.jar)
        self.config.MODEL_DIR = str(self.root / "models")
        self.config.MODEL_NAME = "Modelo"
        self.config.SCHEMA_NAME = "test_schema"
        self.config.XTF_PATH = str(self.root / "output" / "data.xtf")
        self.db_env = patch.dict(os.environ, {
            "DB_HOST": "localhost", "DB_PORT": "5432", "DB_USER": "tester",
            "DB_PASSWORD": "test-password", "DB_NAME": "testdb",
        })
        self.db_env.start()
        self.addCleanup(self.db_env.stop)

    @patch("utils.interlis_utils.subprocess.run")
    def test_export_creates_output_directory_and_passes_model_options(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "ok", "")
        self.config.DISABLE_VALIDATION = True

        interlis_utils.exportar_xtf(self.config)

        self.assertTrue(Path(self.config.XTF_PATH).parent.is_dir())
        command = run.call_args.args[0]
        self.assertEqual(command[0:3], ["java", "-jar", str(self.jar)])
        self.assertEqual(command[command.index("--dbschema") + 1], "test_schema")
        self.assertEqual(command[command.index("--models") + 1], "Modelo")
        self.assertIn("--disableValidation", command)
        self.assertEqual(command[-2], self.config.XTF_PATH)
        self.assertTrue(run.call_args.kwargs["check"])

    @patch("utils.interlis_utils.subprocess.run")
    def test_export_wraps_process_failure(self, run):
        run.side_effect = subprocess.CalledProcessError(1, ["java"], stderr="invalid model")

        with self.assertRaisesRegex(RuntimeError, "invalid model"):
            interlis_utils.exportar_xtf(self.config)

    @patch("utils.interlis_utils.subprocess.run")
    def test_schema_import_uses_basket_option_only_when_requested(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        interlis_utils.import_schema(self.config)
        self.assertIn("--createBasketCol", run.call_args.args[0])

        self.config.USE_BASKETS = False
        interlis_utils.import_schema(self.config)
        self.assertNotIn("--createBasketCol", run.call_args.args[0])
        self.assertIn("--schemaimport", run.call_args.args[0])

    @patch("utils.interlis_utils.subprocess.run")
    def test_schema_import_requires_jar(self, run):
        self.jar.unlink()
        with self.assertRaises(FileNotFoundError):
            interlis_utils.import_schema(self.config)
        run.assert_not_called()

    @patch("utils.interlis_utils.subprocess.run")
    def test_schema_import_reports_java_failure(self, run):
        run.side_effect = subprocess.CalledProcessError(2, ["java"], stderr="bad schema")
        with self.assertRaisesRegex(RuntimeError, "bad schema"):
            interlis_utils.import_schema(self.config)

    @patch("utils.interlis_utils.subprocess.run")
    def test_data_import_uses_xtf_and_reports_failure(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        interlis_utils.import_data(self.config)
        command = run.call_args.args[0]
        self.assertIn("--update", command)
        self.assertEqual(command[-1], self.config.XTF_PATH)

        run.side_effect = subprocess.CalledProcessError(3, ["java"], stderr="bad XTF")
        with self.assertRaisesRegex(RuntimeError, "bad XTF"):
            interlis_utils.import_data(self.config)

    @patch("utils.interlis_utils.subprocess.run")
    def test_data_import_requires_jar(self, run):
        self.jar.unlink()
        with self.assertRaises(FileNotFoundError):
            interlis_utils.import_data(self.config)
        run.assert_not_called()

    @patch("utils.interlis_utils.subprocess.run", side_effect=OSError("java unavailable"))
    def test_process_launch_errors_are_reported_for_each_operation(self, run):
        for operation in (
            interlis_utils.exportar_xtf,
            interlis_utils.import_schema,
            interlis_utils.import_data,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(RuntimeError, "java unavailable"):
                    operation(self.config)
        self.assertEqual(run.call_count, 3)


if __name__ == "__main__":
    unittest.main()
