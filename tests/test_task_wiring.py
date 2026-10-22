import os
import unittest
from unittest.mock import patch

from logic import models
from utils import workflow_util


class EtlTaskWiringTests(unittest.TestCase):
    def test_interlis_operations_build_expected_schema_and_paths(self):
        operations = (
            (models.import_schema_ms, "import_schema", "input_42", "SIMPLIFICADO"),
            (models.importar_data_ms, "import_data", "input_42", "SIMPLIFICADO"),
            (models.import_schema_ladm, "import_schema", "output_42", "LADM_COL"),
            (models.export_xtf_ladm, "exportar_xtf", "output_42", "LADM_COL"),
        )
        for operation, target, schema, model_dir in operations:
            with self.subTest(operation=operation.__name__):
                with patch.object(models, target) as invoked:
                    operation("42", "etl", "ParcelModel")
                config = invoked.call_args.args[0]
                self.assertEqual(config.PROCESS_ID, "42")
                self.assertEqual(config.SCHEMA_NAME, schema)
                self.assertEqual(config.MODEL_NAME, "ParcelModel")
                self.assertEqual(config.ILI2DB_JAR_PATH, models.Ili2dbJarPath.LATEST.value)
                self.assertTrue(config.MODEL_DIR.endswith(os.path.join("etl", "resources", "models", model_dir)))
                if operation is models.importar_data_ms:
                    self.assertTrue(config.XTF_PATH.endswith(os.path.join("etl", "42", "42.xtf")))
                if operation is models.export_xtf_ladm:
                    self.assertTrue(config.XTF_PATH.endswith(os.path.join("etl", "42", "output_42.xtf")))

    def test_interlis_task_factories_bind_matching_callable_and_arguments(self):
        factories = (
            (models.import_schema_ms_task, models.import_schema_ms, "simplified_model_name"),
            (models.import_data_ms_task, models.importar_data_ms, "simplified_model_name"),
            (models.import_schema_ladm_task, models.import_schema_ladm, "ladm_col_model_name"),
            (models.export_xtf_ladm_task, models.export_xtf_ladm, "ladm_col_model_name"),
        )
        for factory, callable_, model_parameter in factories:
            with self.subTest(factory=factory.__name__):
                task = factory("42", "etl", "ParcelModel")
                self.assertIs(task.python_callable, callable_)
                self.assertEqual(task.op_kwargs, {
                    "process_id": "42", "etl_name": "etl", model_parameter: "ParcelModel",
                })
                self.assertTrue(task.task_id)

    def test_sql_task_builders_keep_connection_and_sql_file(self):
        task = workflow_util.create_sql_task("postgres", "load", "load.sql")
        self.assertEqual((task.task_id, task.conn_id, task.sql), ("load", "postgres", "load.sql"))

        tasks = workflow_util.create_etl_tasks("postgres", [
            ("first", "first.sql"), ("second", "second.sql"),
        ])
        self.assertEqual(set(tasks), {"first", "second"})
        self.assertEqual(tasks["second"].sql, "second.sql")

        check = workflow_util.check_db_connection_task("postgres")
        self.assertEqual(check.sql, "SELECT 1;")
        self.assertEqual(check.conn_id, "postgres")

    def test_file_transfer_tasks_bind_inputs_to_expected_functions(self):
        download = workflow_util.download_xtf_task("42", "https://example.test/file.xtf", "etl")
        self.assertIs(download.python_callable, workflow_util.download_or_copy_xtf)
        self.assertEqual(download.op_kwargs, {
            "process_id": "42", "source": "https://example.test/file.xtf", "etl_name": "etl",
        })

        publish = workflow_util.publish_s3_xtf_ladm_task("42", "etl")
        self.assertIs(publish.python_callable, workflow_util.upload_to_s3_xtf_ladm)
        self.assertEqual(publish.op_kwargs, {"process_id": "42", "etl_name": "etl"})


if __name__ == "__main__":
    unittest.main()
