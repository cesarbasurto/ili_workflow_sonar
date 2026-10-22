import os
import tempfile
from pathlib import Path

def build_qgis_environment() -> dict[str, str]:
    """
    Construye un entorno aislado para ejecutar QGIS sin interfaz gráfica.
    """

    environment = os.environ.copy()

    environment["QT_QPA_PLATFORM"] = "offscreen"

    # No reutilizar XDG_RUNTIME_DIR definido por Docker,
    # porque puede haber sido creado por root.
    # mkdtemp crea de forma atómica un directorio con nombre aleatorio
    # y permisos 0700, propiedad del usuario que ejecuta la tarea.
    runtime_directory = Path(
        tempfile.mkdtemp(prefix="qgis-runtime-")
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

