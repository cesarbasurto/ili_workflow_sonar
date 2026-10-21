# ili-workflow

Orquestador ETL en Apache Airflow para gestionar y transformar datos definidos en INTERLIS.

## Desarrolladores

1. Clona el repositorio en tu máquina local:

```shell
git clone https://github.com/ceicol/ili-workflow.git
```


2. Se descargan dependencias requeridas (ili2db):

```shell
cd ili-workflow/
sh scripts/download_dependencies.sh

```

3. Crear un archivo .env con las varibales que estan definidas en el archivo de ejemplo `.env.example`

```shell
cd airflow
cp .env.example .env
```


4. Registra tu submodulo del ETL a ejecutar:

```shell
vi update_submodules.sh

# Agrega el submódulo ETL de Airflow con el formato nombre|URL|rama.
SUBMODULOS=(
        "af_ms_to_ladm_nca|https://github.com/ceicol/af_ms_to_ladm_nca.git|main"
)

# Descarga o actualiza el submódulo y crea los enlaces hacia el ETL.
bash update_submodules.sh
```

5. Desplegamos airflow

```shell
cd airflow

# En producción
docker compose up -d

# En local
docker compose -f compose.dev.yml up -d
```