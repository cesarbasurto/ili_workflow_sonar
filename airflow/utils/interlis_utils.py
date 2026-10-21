import os
import subprocess
import logging

from config.general_config import EPSG_SCRIPT
from config.ili2db_config import DbConfiguration, Ili2DbConfiguration


def exportar_xtf(ili2db_config:Ili2DbConfiguration):
    """
    Exporta datos del esquema 'ladm' a XTF utilizando la configuración dinámica.
    """

    """
    Importar un modelo de datos a una base de datos postgres
    """
    db_config = DbConfiguration()

    logging.info(f"Iniciando exportar_datos_ladm para {ili2db_config.MODEL_NAME}...")
    logging.info(f"Exportando datos del esquema {ili2db_config.SCHEMA_NAME} a XTF...")

    output_dir = os.path.dirname(ili2db_config.XTF_PATH)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    command = [
        "java",
        "-jar",
        ili2db_config.ILI2DB_JAR_PATH,
        "--dbhost", db_config.DB_HOST,
        "--dbport", str(db_config.DB_PORT),
        "--dbusr", db_config.DB_USER,
        "--dbpwd", db_config.DB_PASSWORD,
        "--dbdatabase", db_config.DB_NAME,
        "--dbschema", ili2db_config.SCHEMA_NAME,
        "--export",
        "--exportTid",
        "--strokeArcs",
        "--modeldir", ili2db_config.MODEL_DIR,
        "--models", ili2db_config.MODEL_NAME,
        # "--iliMetaAttrs",    "NULL",# si es NULL, parámetro no soportado en ili2db 4.4.3
        ili2db_config.XTF_PATH
    ]


    if ili2db_config.DISABLE_VALIDATION:
        command.append('--disableValidation')

    logging.info("Ejecutando exportación a XTF:")
    logging.info(" ".join(command))


    try: 
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"Exportación a XTF completada exitosamente: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error exportando XTF: {e.stderr}")
        raise RuntimeError(f"Error exportando XTF: {e.stderr}")
    except Exception as e:
        logging.error(f"Error en exportar_datos_ladm: {e}")
        raise RuntimeError(f"Error exportando XTF: {e}")
    finally:
        logging.debug("STDOUT:\n", result.stdout)
        logging.debug("STDERR:\n", result.stderr)

def import_schema(ili2db_config:Ili2DbConfiguration):
    """
    Importar un modelo de datos a una base de datos postgres
    """
    db_config = DbConfiguration()
    
    logging.info(f"Iniciando importar_esquema_ladm para {ili2db_config.MODEL_NAME}...")
    logging.info(f"Importando esquema {ili2db_config.SCHEMA_NAME}...")
    
    if not os.path.exists(ili2db_config.ILI2DB_JAR_PATH):
        logging.error("❌ importar_esquema_ladm falló. JAR no encontrado.")
        raise FileNotFoundError(f"Archivo JAR no encontrado: {ili2db_config.ILI2DB_JAR_PATH}")
    
    command = [
        "java",
        "-jar",
        ili2db_config.ILI2DB_JAR_PATH,
        "--schemaimport", "--setupPgExt",
        "--dbhost", db_config.DB_HOST,
        "--dbport", str(db_config.DB_PORT),
        "--dbusr", db_config.DB_USER,
        "--dbpwd", db_config.DB_PASSWORD,
        "--dbdatabase", db_config.DB_NAME,
        "--dbschema", ili2db_config.SCHEMA_NAME,
        "--coalesceCatalogueRef", "--createNumChecks", "--createUnique",
        "--createFk", "--createFkIdx", "--coalesceMultiSurface",
        "--coalesceMultiLine", "--coalesceMultiPoint", "--coalesceArray",
        "--beautifyEnumDispName", "--createGeomIdx", "--createMetaInfo",
        "--expandMultilingual", "--createTypeConstraint",
        "--createEnumTabs", "--createTidCol", "--smart2Inheritance",
        "--strokeArcs", 
        "--defaultSrsAuth", "EPSG",
        "--defaultSrsCode", "9377",
        "--preScript", EPSG_SCRIPT,
        # "--postScript", "NULL",  # si es NULL, parámetro no soportado en ili2db 4.4.3
        "--modeldir", ili2db_config.MODEL_DIR,
        "--models", ili2db_config.MODEL_NAME,
        # "--iliMetaAttrs", "NULL", # si es NULL, parámetro no soportado en ili2db 4.4.3
    ]

    if ili2db_config.USE_BASKETS == True:
        command.append("--createBasketCol")

    logging.info("Ejecutando import schema:")
    logging.info(" ".join(command))

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"Creación del esquema de la base de datos completada: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error al crear el esquema de la base de datos: {e.stderr}")
        raise RuntimeError(f"Error al crear el esquema de la base de datos: {e.stderr}")
    except Exception as e:
        logging.error(f"Error al crear el esquema de la base de datos: {e}")
        raise RuntimeError(f"Error al crear el esquema de la base de datos: {e}")
    finally:
        logging.debug("STDOUT:\n", result.stdout)
        logging.debug("STDERR:\n", result.stderr)

def import_data(ili2db_config:Ili2DbConfiguration):
    """
    Importar un conjunto de datos a su modelo en interlis a una base de datos postgres
    """
    db_config = DbConfiguration()
    
    logging.info(f"Iniciando importar_esquema_ladm para {ili2db_config.MODEL_NAME}...")
    logging.info(f"Importando esquema {ili2db_config.SCHEMA_NAME}...")
    
    if not os.path.exists(ili2db_config.ILI2DB_JAR_PATH):
        logging.error("❌ importar_esquema_ladm falló. JAR no encontrado.")
        raise FileNotFoundError(f"Archivo JAR no encontrado: {ili2db_config.ILI2DB_JAR_PATH}")
    
    command = [
        "java",
        "-jar",
        ili2db_config.ILI2DB_JAR_PATH,
        "--update",
        "--dbhost", db_config.DB_HOST,
        "--dbport", str(db_config.DB_PORT),
        "--dbusr", db_config.DB_USER,
        "--dbpwd", db_config.DB_PASSWORD,
        "--dbdatabase", db_config.DB_NAME,
        "--dbschema", ili2db_config.SCHEMA_NAME,
        "--importTid",
        "--importBid",
        "--dataset", "Baseset",
        "--modeldir", ili2db_config.MODEL_DIR,
        ili2db_config.XTF_PATH
    ]

    logging.info("Ejecutando import data:")
    logging.info(" ".join(command))

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info(f"Importación del XTF completada exitosamente: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error importando el XTF: {e.stderr}")
        raise RuntimeError(f"Error importando el XTF: {e.stderr}")
    except Exception as e:
        logging.error(f"Error importando el XTF: {e}")
        raise RuntimeError(f"Error importando el XTF: {e}")
    finally:
        logging.debug("STDOUT:\n", result.stdout)
        logging.debug("STDERR:\n", result.stderr)
