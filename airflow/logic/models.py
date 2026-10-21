import os

from airflow.providers.standard.operators.python import PythonOperator

from config.general_config import BASE_LOGIC_DIR, OUTPUT_DIR
from config.ili2db_config import Ili2DbConfiguration
from config.enums import Ili2dbJarPath
from utils.interlis_utils import (
    import_schema,
    import_data,
    exportar_xtf
)

# ============================================================================
# Operaciones de ili2db para importar el modelo simplificado
# ============================================================================

def import_schema_ms(process_id:str, etl_name: str, simplified_model_name: str):
    ili2db_config = Ili2DbConfiguration()

    ili2db_config.PROCESS_ID = process_id
    ili2db_config.ILI2DB_JAR_PATH = Ili2dbJarPath.LATEST.value
    ili2db_config.MODEL_DIR = os.path.join(BASE_LOGIC_DIR, etl_name, 'resources', 'models', 'SIMPLIFICADO')
    ili2db_config.MODEL_NAME = simplified_model_name
    ili2db_config.SCHEMA_NAME = 'input_{}'.format(process_id)

    import_schema(ili2db_config)

def importar_data_ms(process_id:str, etl_name: str, simplified_model_name: str):

    ili2db_config = Ili2DbConfiguration()

    ili2db_config.PROCESS_ID = process_id
    ili2db_config.ILI2DB_JAR_PATH = Ili2dbJarPath.LATEST.value
    ili2db_config.MODEL_DIR = os.path.join(BASE_LOGIC_DIR, etl_name, 'resources', 'models', 'SIMPLIFICADO')
    ili2db_config.MODEL_NAME = simplified_model_name
    ili2db_config.SCHEMA_NAME = 'input_{}'.format(process_id)
    ili2db_config.XTF_PATH = os.path.join(OUTPUT_DIR, etl_name, process_id, f'{process_id}.xtf')

    import_data(ili2db_config)

# =====================================================================
# Operaciones de ili2db para el modelo Extendido LADM_COL
# =====================================================================

def import_schema_ladm(process_id:str, etl_name: str, ladm_col_model_name: str):
    ili2db_config = Ili2DbConfiguration()

    ili2db_config.PROCESS_ID = process_id
    ili2db_config.ILI2DB_JAR_PATH = Ili2dbJarPath.LATEST.value
    ili2db_config.MODEL_DIR = os.path.join(BASE_LOGIC_DIR, etl_name, 'resources', 'models', 'LADM_COL')
    ili2db_config.MODEL_NAME = ladm_col_model_name
    ili2db_config.SCHEMA_NAME = 'output_{}'.format(process_id)

    import_schema(ili2db_config)

def export_xtf_ladm(process_id:str, etl_name: str, ladm_col_model_name: str):
    ili2db_config = Ili2DbConfiguration()

    ili2db_config.PROCESS_ID = process_id
    ili2db_config.XTF_PATH = os.path.join(OUTPUT_DIR, etl_name, process_id, 'output_{}.xtf'.format(ili2db_config.PROCESS_ID))
    ili2db_config.ILI2DB_JAR_PATH = Ili2dbJarPath.LATEST.value
    ili2db_config.MODEL_DIR = os.path.join(BASE_LOGIC_DIR, etl_name, 'resources', 'models', 'LADM_COL')
    ili2db_config.MODEL_NAME = ladm_col_model_name
    ili2db_config.SCHEMA_NAME = 'output_{}'.format(process_id)

    exportar_xtf(ili2db_config)

# ==================================================
# TASK ILI2DB MODELO SIMPLIFICADO
# ==================================================

def import_schema_ms_task(process_id:str, etl_name: str, simplified_model_name: str):
    return PythonOperator(
        task_id='importar_esquema_modelo_simplificado',
        python_callable=import_schema_ms,
        op_kwargs={
            "process_id": process_id,
            "etl_name": etl_name,
            "simplified_model_name": simplified_model_name,
        },
    )

def import_data_ms_task(process_id:str, etl_name: str, simplified_model_name: str):
    return PythonOperator(
        task_id='importar_datos_modelo_simplificado',
        python_callable=importar_data_ms,
        op_kwargs={
            "process_id": process_id,
            "etl_name": etl_name,
            "simplified_model_name": simplified_model_name,
        },
    )

# ==================================================
# TASK ILI2DB EXTENDIDO LADM_COL
# ==================================================

def import_schema_ladm_task(process_id:str, etl_name: str, ladm_col_model_name: str):
    return PythonOperator(
        task_id='importar_esquema_modelo_ladm_col',
        python_callable=import_schema_ladm,
        op_kwargs={
            "process_id": process_id,
            "etl_name": etl_name,
            "ladm_col_model_name": ladm_col_model_name,
        },
    )

def export_xtf_ladm_task(process_id:str, etl_name: str, ladm_col_model_name: str):
    return PythonOperator(
        task_id='exportar_en_formato_xtf_datos_modelo_ladm_col',
        python_callable=export_xtf_ladm,
        op_kwargs={
            "process_id": process_id,
            "etl_name": etl_name,
            "ladm_col_model_name": ladm_col_model_name,
        },
    )
