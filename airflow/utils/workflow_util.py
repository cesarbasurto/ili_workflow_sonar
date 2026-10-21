from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.providers.standard.operators.python import PythonOperator

from utils.file_utils import download_or_copy_xtf, upload_to_s3_xtf_ladm


def create_sql_task(postgres_conn_id: str, task_id: str, sql_file: str) -> SQLExecuteQueryOperator:
    """Construye una tarea SQL con la conexión PostgreSQL indicada."""
    return SQLExecuteQueryOperator(
        task_id=task_id,
        conn_id=postgres_conn_id,
        sql=sql_file,
    )


def create_etl_tasks(postgres_conn_id: str, etl_tasks: str) -> dict[str, SQLExecuteQueryOperator]:
    """Construye las tareas SQL en el contexto del DAG activo, indexadas por task_id."""
    return {
        task_id: create_sql_task(postgres_conn_id, task_id, sql_file)
        for task_id, sql_file in etl_tasks
    }


def check_db_connection_task(postgres_conn_id: str) -> SQLExecuteQueryOperator:
    return SQLExecuteQueryOperator(
        task_id="validar_conexion_postgres",
        conn_id=postgres_conn_id,
        sql="SELECT 1;",
        doc_md="""Validando conexión a la base de datos..."""
    )


def download_xtf_task(process_id:str, url_xtf:str, etl_name: str) -> PythonOperator:
    return PythonOperator(
        task_id='download_xtf',
        python_callable=download_or_copy_xtf,
        op_kwargs={"process_id": process_id, "source": url_xtf, "etl_name": etl_name},
    )

def publish_s3_xtf_ladm_task(process_id:str, etl_name: str) -> PythonOperator:
    return PythonOperator(
        task_id='publicar_en_s3_datos_zip_xtf_ladm_col',
        python_callable=upload_to_s3_xtf_ladm,
        op_kwargs={"process_id": process_id, "etl_name": etl_name},
    )