import os
from pathlib import Path
import logging

import subprocess
from airflow.sdk import Connection

from logic.qgis_process_runner import _build_qgis_environment

LOGGER = logging.getLogger(__name__)


def input_file_validator(file_path: str) -> None:

    input_file = Path(file_path)

    if not input_file.exists():
        raise FileNotFoundError(
            "No se encontró el archivo dentro del worker: "
            f"{input_file}"
        )

    if not input_file.is_file():
        raise ValueError(
            f"La ruta no corresponde a un archivo: {input_file}"
        )

    if not os.access(input_file, os.R_OK):
        raise PermissionError(
            f"El worker no tiene permisos de lectura sobre: {input_file}"
        )

    LOGGER.info("Archivo disponible: %s", input_file)


def qgis_model_validator(qgis_model_id: str, expected_parameters: list=None) -> None:
        environment = _build_qgis_environment()

        version_result = subprocess.run(
            ["qgis_process", "--version"],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )

        if version_result.returncode != 0:
            raise RuntimeError(
                "No fue posible ejecutar qgis_process.\n"
                f"STDOUT:\n{version_result.stdout}\n"
                f"STDERR:\n{version_result.stderr}"
            )

        LOGGER.info(
            "Versión de QGIS:\n%s",
            version_result.stdout.strip(),
        )

        model_result = subprocess.run(
            [
                "qgis_process",
                "help",
                qgis_model_id,
            ],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )

        if model_result.returncode != 0:
            raise RuntimeError(
                f"QGIS no encontró el modelo {qgis_model_id}.\n"
                "Verifica que el modelo esté instalado en el perfil "
                "QGIS del worker o utiliza la ruta absoluta al .model3.\n\n"
                f"STDOUT:\n{model_result.stdout}\n"
                f"STDERR:\n{model_result.stderr}"
            )

        LOGGER.info(
            "Modelo QGIS encontrado: %s",
            qgis_model_id,
        )

        # Comprueba que los parámetros principales aparezcan en la ayuda.
        if expected_parameters:
            model_help = (
                model_result.stdout
                + "\n"
                + model_result.stderr
            ).lower()

            missing_parameters = [
                parameter
                for parameter in expected_parameters
                if parameter.lower() not in model_help
            ]

            if missing_parameters:
                raise RuntimeError(
                    "El modelo fue encontrado, pero no aparecen estos "
                    f"parámetros en su definición: {missing_parameters}"
                )


def etl_connection_validator(connection:Connection):
        """
        Se valida que el objeto de conexión tenga los parámetros requeridos
        para poder ejecutar el ETL a postgres.
        """
        database = connection.schema
        hostname = connection.host
        port = connection.port
        username = connection.login
        password = connection.password

        required_values = {
            "hostname": hostname,
            "database": database,
            "username": username,
            "password": password,
            "port": port,
        }

        missing_values = [
            name
            for name, value in required_values.items()
            if value in (None, "")
        ]

        if missing_values:
            raise ValueError(
                f"La conexión {connection.conn_id} no tiene definidos: "
                + ", ".join(missing_values)
            )