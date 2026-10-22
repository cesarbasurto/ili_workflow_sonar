import sys
import types
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow"))


def _module(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


# Airflow is a runtime dependency; these unit tests exercise our task wiring
# without installing or starting the scheduler.
_module("airflow")
sdk = _module("airflow.sdk")
sdk.Connection = type("Connection", (), {})
sdk_log = _module("airflow.sdk.log")
sdk_log.mask_secret = lambda value, name=None: None
_module("airflow.providers")
_module("airflow.providers.standard")
_module("airflow.providers.standard.operators")
standard_python = _module("airflow.providers.standard.operators.python")
_module("airflow.providers.common")
_module("airflow.providers.common.sql")
_module("airflow.providers.common.sql.operators")
common_sql = _module("airflow.providers.common.sql.operators.sql")


class OperatorStub:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


standard_python.PythonOperator = OperatorStub
common_sql.SQLExecuteQueryOperator = OperatorStub
