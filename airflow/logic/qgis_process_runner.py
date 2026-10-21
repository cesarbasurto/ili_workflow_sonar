from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from airflow.sdk.log import mask_secret


LOGGER = logging.getLogger(__name__)

SENSITIVE_PARAMETER_NAMES = {
    "password",
    "etl_password",
    "token",
    "secret",
    "api_key",
    "private_key",
}


class QgisProcessError(RuntimeError):
    """Error producido durante la ejecución de qgis_process."""


def run_qgis_model(
    model: str | Path,
    parameters: Mapping[str, Any],
) -> None:
    """
    Ejecuta un modelo QGIS mediante qgis_process.

    Args:
        model:
            Identificador del modelo, por ejemplo:
            ``model:Polygon_to_Surveying``

            También puede ser la ruta absoluta a un archivo:
            ``/opt/airflow/qgis-models/model.model3``

        parameters:
            Objeto con el formato JSON esperado por qgis_process.

            Debe contener al menos:

            {
                "inputs": {
                    "PARAMETER_NAME": "value"
                }
            }

            También puede incluir:
            - ellipsoid
            - distance_units
            - area_units

    Raises:
        ValueError:
            Si los parámetros no son válidos.

        FileNotFoundError:
            Si se suministra una ruta de modelo que no existe.

        QgisProcessError:
            Si qgis_process termina con error.
    """

    model_reference = str(model).strip()

    if not model_reference:
        raise ValueError(
            "El identificador o ruta del modelo no puede estar vacío."
        )

    if not isinstance(parameters, Mapping):
        raise TypeError(
            "parameters debe ser un diccionario o Mapping."
        )

    if "inputs" not in parameters:
        raise ValueError(
            "parameters debe contener la clave 'inputs'."
        )

    inputs = parameters["inputs"]

    if not isinstance(inputs, Mapping):
        raise TypeError(
            "parameters['inputs'] debe ser un diccionario."
        )

    _validate_model_reference(model_reference)
    _register_secrets_for_masking(inputs)

    environment = _build_qgis_environment()

    command = [
        "qgis_process",
        "--verbose",
        "run",
        model_reference,
        "-",
    ]

    LOGGER.info(
        "Iniciando modelo QGIS: %s",
        model_reference,
    )

    LOGGER.info(
        "Parámetros de entrada: %s",
        ", ".join(sorted(inputs.keys())),
    )

    LOGGER.info(
        "Configuración espacial: ellipsoid=%s, "
        "distance_units=%s, area_units=%s",
        parameters.get("ellipsoid", "default"),
        parameters.get("distance_units", "default"),
        parameters.get("area_units", "default"),
    )

    started_at = time.monotonic()

    process = subprocess.Popen(
        command,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    if process.stdin is None:
        process.kill()
        raise QgisProcessError(
            "No fue posible abrir stdin para qgis_process."
        )

    if process.stdout is None:
        process.kill()
        raise QgisProcessError(
            "No fue posible abrir stdout para qgis_process."
        )

    recent_output: list[str] = []

    try:
        payload = json.dumps(
            parameters,
            ensure_ascii=False,
            default=str,
        )

        process.stdin.write(payload)
        process.stdin.close()

        for output_line in process.stdout:
            clean_line = output_line.rstrip()

            if not clean_line:
                continue

            LOGGER.info(
                "[QGIS][%s] %s",
                _model_display_name(model_reference),
                clean_line,
            )

            recent_output.append(clean_line)

            # Conservamos solamente las últimas líneas para el
            # mensaje de error.
            if len(recent_output) > 50:
                recent_output.pop(0)

        return_code = process.wait()

    except Exception:
        process.kill()
        process.wait()
        raise

    elapsed_seconds = time.monotonic() - started_at

    if return_code != 0:
        output_tail = "\n".join(recent_output[-20:])

        raise QgisProcessError(
            f"El modelo QGIS terminó con error.\n"
            f"Modelo: {model_reference}\n"
            f"Código de salida: {return_code}\n"
            f"Duración: {elapsed_seconds:.2f} segundos\n"
            f"Últimos mensajes:\n{output_tail}"
        )

    LOGGER.info(
        "Modelo QGIS finalizado correctamente: %s",
        model_reference,
    )

    LOGGER.info(
        "Duración total: %.2f segundos",
        elapsed_seconds,
    )


def _validate_model_reference(
    model_reference: str,
) -> None:
    """
    Verifica la existencia del modelo cuando se recibe una ruta.
    """

    is_model_identifier = ":" in model_reference
    is_probable_path = (
        "/" in model_reference
        or "\\" in model_reference
        or model_reference.endswith(".model3")
    )

    if is_model_identifier and not is_probable_path:
        return

    model_path = Path(model_reference)

    if not model_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el modelo QGIS: {model_path}"
        )


def _build_qgis_environment() -> dict[str, str]:
    """
    Construye un entorno aislado para ejecutar QGIS sin interfaz gráfica.
    """

    environment = os.environ.copy()

    environment["QT_QPA_PLATFORM"] = "offscreen"

    # No reutilizar XDG_RUNTIME_DIR definido por Docker,
    # porque puede haber sido creado por root.
    runtime_directory = Path(
        f"/tmp/qgis-runtime-{os.getuid()}-{os.getpid()}"
    )

    # El directorio se crea directamente con permisos 0700
    # por el mismo usuario que ejecuta la tarea.
    runtime_directory.mkdir(
        parents=False,
        exist_ok=True,
        mode=0o700,
    )

    environment["XDG_RUNTIME_DIR"] = str(runtime_directory)

    # Útil si el perfil o plugins QGIS están montados en otra ruta.
    qgis_custom_config = os.getenv(
        "QGIS_CUSTOM_CONFIG_PATH"
    )

    if qgis_custom_config:
        environment["QGIS_CUSTOM_CONFIG_PATH"] = (
            qgis_custom_config
        )

    return environment


def _register_secrets_for_masking(
    parameters: Mapping[str, Any],
) -> None:
    """
    Registra secretos para que Airflow los oculte en los logs.
    """

    for parameter_name, parameter_value in parameters.items():
        normalized_name = parameter_name.lower()

        if (
            normalized_name in SENSITIVE_PARAMETER_NAMES
            or normalized_name.endswith("_password")
            or normalized_name.endswith("_secret")
            or normalized_name.endswith("_token")
        ):
            if parameter_value not in (None, ""):
                mask_secret(
                    parameter_value,
                    name=parameter_name,
                )


def _model_display_name(
    model_reference: str,
) -> str:
    """
    Devuelve un nombre corto para prefijar los logs.
    """

    if model_reference.startswith("model:"):
        return model_reference.removeprefix("model:")

    return Path(model_reference).stem