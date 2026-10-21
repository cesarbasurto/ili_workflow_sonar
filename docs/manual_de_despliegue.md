# MANUAL DE DESPLIEGUE: Orquestador Airflow ETL (`ili-workflow`)

## TABLA DE CONTENIDO

1. OBJETIVO
2. TÉRMINOS Y/O CONCEPTOS
3. DESCRIPCIÓN DE LA SOLUCIÓN
4. COMPONENTES DEL SISTEMA
5. REQUISITOS DE HARDWARE Y SOFTWARE DEL SISTEMA
6. CONFIGURACIÓN DEL SISTEMA
7. PROCEDIMIENTO DE DESPLIEGUE
8. ERRORES TÉCNICOS MÁS COMUNES Y SU SOLUCIÓN
9. PRUEBAS DEL SISTEMA
10. MANTENIMIENTO Y SOPORTE
11. CONCLUSIONES

## 1. OBJETIVO

Proporcionar la guía para desplegar, configurar, verificar y mantener el Orquestador Airflow ETL (`ili-workflow`), plataforma construida sobre Apache Airflow 3 que ejecuta los ETL que transforman los datos del **modelo simplificado** al **modelo extendido LADM_COL** de los Objetos Territoriales Legales (OTL) contemplados en la consultoría, tanto en ambiente local de desarrollo como en un servidor de producción publicado detrás de Nginx.

## 2. TÉRMINOS Y/O CONCEPTOS

| Término | Definición |
|---|---|
| Orquestador Airflow ETL | Plataforma `ili-workflow` que centraliza el despliegue, la ejecución y el monitoreo de los ETL de todas las líneas temáticas. |
| Línea temática (OTL) | Categoría de Objeto Territorial Legal. Cada una tiene su propio ETL, con sus modelos INTERLIS y reglas de transformación. |
| ETL | Proceso de extracción, transformación y carga. Aquí, la conversión de un XTF del modelo simplificado a un XTF LADM_COL. |
| Apache Airflow | Motor de orquestación para programar, ejecutar y monitorear flujos de trabajo. Se usa la versión 3.3.0 con `CeleryExecutor`. |
| DAG | Flujo de trabajo de Airflow compuesto por tareas y sus dependencias. Cada ETL publica sus propios DAG. |
| Docker / Docker Compose | Plataforma de contenedores y herramienta que define y levanta todos los servicios del orquestador. |
| Submódulo Git | Repositorio independiente de un ETL incorporado al orquestador en `airflow/submodules/<etl>`. |
| INTERLIS / XTF | Lenguaje de modelado de datos geográficos (`.ili`) y su formato de transferencia de datos (`.xtf`). |
| ili2db / ili2pg | Herramienta Java que crea esquemas PostgreSQL desde modelos INTERLIS e importa, exporta y valida datos XTF. |
| LADM_COL | Perfil colombiano del modelo ISO 19152 (LADM). Es el modelo extendido de destino. |
| Modelo simplificado | Modelo INTERLIS de captura con el que se entregan los datos de entrada de cada OTL. |
| `process_id` | Identificador de cada ejecución. Define los esquemas `input_<process_id>` y `output_<process_id>` y la carpeta de salida. |
| PostGIS | Extensión espacial de PostgreSQL requerida por la base de datos de los ETL. |
| EPSG:9377 | Sistema de referencia MAGNA-SIRGAS 2018 / Origen Nacional, usado por defecto en los esquemas. |
| Fernet key | Clave con la que Airflow cifra las credenciales guardadas en su base de metadatos. |
| Proxy inverso / subpath | Publicación de Airflow mediante Nginx bajo una ruta, p. ej. `https://midominio.com/airflow`. |
| S3 | Almacenamiento de objetos donde se publica, comprimido, el XTF LADM_COL resultante. |

## 3. DESCRIPCIÓN DE LA SOLUCIÓN

El orquestador es la plataforma de ejecución común para los ETL de modelo simplificado → modelo extendio LADM_COL. **No contiene la lógica de cada transformación**: cada ETL vive en su propio repositorio Git (e.g: `af_ms_to_ladm_rhc`, `af_ms_to_ladm_nca` y `af_ms_to_ladm_zra`), se registra como submódulo y se enlaza a Airflow mediante el script `configure.sh` del propio ETL. Sus funciones principales son:

- **Gestión de ETL:** registro centralizado, alta, actualización y retiro de los ETL como submódulos con un único script (`update_submodules.sh`).
- **Integración con Airflow:** enlace automático de los DAG, modelos INTERLIS y scripts de cada ETL en las rutas que Airflow espera.
- **Configuración centralizada:** un solo archivo `.env` con la conexión a la base de datos, el almacenamiento S3, la URL pública y las claves de seguridad.
- **Librería de tareas reutilizables:** operaciones estándar de ili2db, ejecución de SQL, descarga de insumos, validaciones y publicación en S3, que todos los ETL comparten.
- **Ejecución y monitoreo:** programación, ejecución distribuida, reintentos y logs por tarea desde la interfaz de Airflow.

Ilustración 1. Arquitectura de despliegue en producción:

```text
Usuario ──HTTPS──► Nginx (/airflow) ──► airflow-apiserver (127.0.0.1:8080)
                                              │
      airflow-scheduler · airflow-dag-processor · airflow-triggerer
                                              │
               Redis 7.2 (cola Celery) · PostgreSQL 16 (metadatos de Airflow)
                                              │
                         airflow-worker (Java 21 + ili2pg)
                         │                                │
          PostgreSQL/PostGIS (BD de los ETL)       Bucket S3 (XTF LADM_COL .zip)
```

Flujo estándar de un DAG ETL, construido con las tareas que provee el orquestador (`utils/workflow_util.py` y `logic/models.py`):

| # | Tarea (`task_id`) | Qué hace |
|---|---|---|
| 1 | `validar_conexion_postgres` | Ejecuta `SELECT 1` contra la conexión de la BD de los ETL. |
| 2 | `download_xtf` | Descarga (http/https) o copia (ruta local en el worker) el XTF de entrada a `output/<etl>/<process_id>/<process_id>.xtf`. |
| 3 | `importar_esquema_modelo_simplificado` | Crea con ili2db el esquema `input_<process_id>` a partir del modelo simplificado. |
| 4 | `importar_datos_modelo_simplificado` | Carga el XTF de entrada en `input_<process_id>`. |
| 5 | `importar_esquema_modelo_ladm_col` | Crea el esquema `output_<process_id>` con el modelo extendido LADM_COL. |
| 6 | Tareas SQL del ETL (`ETL_TASKS`) | Transforman los datos de `input_*` a `output_*` (`SQLExecuteQueryOperator`), en el orden definido en el DAG del ETL. |
| 7 | `exportar_en_formato_xtf_datos_modelo_ladm_col` | Exporta y valida con ili2db el archivo `output_<process_id>.xtf`. |
| 8 | `publicar_en_s3_datos_zip_xtf_ladm_col` | Comprime el XTF y lo publica en S3 bajo `ili-workflow/<etl>/`. |

## 4. COMPONENTES DEL SISTEMA

Los servicios se definen en `airflow/compose.yml` (producción) y `airflow/compose.dev.yml` (local) y se organizan por capas:

| Capa | Componente | Tecnología | Función |
|---|---|---|---|
| Publicación | Nginx | Proxy inverso con TLS | Único acceso externo en producción; publica Airflow bajo el subpath. |
| Interfaz de usuario | `airflow-apiserver` | Airflow 3.3.0 (API server + UI web) | Visualización, ejecución manual y monitoreo de DAG; logs por tarea; API REST y Execution API (puerto 8080). |
| Seguridad | Auth manager de Airflow | `FabAuthManager` + JWT | Autenticación de usuarios y roles; tokens para la API. El administrador se crea en la inicialización. |
| Orquestación | `airflow-scheduler` | Airflow | Planifica las ejecuciones y resuelve dependencias entre tareas. |
| Orquestación | `airflow-dag-processor` | Airflow | Lee y procesa los DAG enlazados de cada ETL. |
| Orquestación | `airflow-triggerer` | Airflow | Gestiona tareas diferidas o basadas en eventos. |
| Ejecución | `airflow-worker` | Celery + Java 21 + ili2pg | Ejecuta las tareas (ili2db, SQL, S3). Puede escalarse horizontalmente. |
| Ejecución | `redis` | Redis 7.2 | Broker de mensajes de Celery para repartir tareas entre workers. |
| Datos | `postgres` | PostgreSQL 16 | Base de metadatos de Airflow: DAG, ejecuciones, usuarios y conexiones cifradas. No es la BD de los ETL. |
| Datos | BD de los ETL (externa) | PostgreSQL + PostGIS | Esquemas `input_*` y `output_*` de cada ejecución. |
| Datos | Bucket S3 (externo) | S3 | Publicación de los XTF LADM_COL resultantes. |
| Gestión de ETL | `update_submodules.sh` + `configure.sh` de cada ETL | Git (submódulos) | Registro, descarga, actualización, enlace y desregistro de los ETL. |
| Soporte | `airflow-init` | Airflow | Migra la base de metadatos, crea el administrador, valida recursos y ajusta permisos. Termina al finalizar. |
| Opcional | `flower` / `airflow-cli` | Celery Flower / CLI | Monitor de Celery (puerto 5555, `--profile flower`) y contenedor de depuración (`--profile debug`). |

## 5. REQUISITOS DE HARDWARE Y SOFTWARE DEL SISTEMA

| Recurso | Mínimo técnico (validado por `airflow-init`) | Recomendado para producción |
|---|---|---|
| CPU | 2 núcleos | x86_64, 4 núcleos / 8 hilos (Intel Xeon o AMD EPYC); 8 núcleos para ejecuciones concurrentes |
| Memoria RAM | 4 GB disponibles para Docker | 8 GB mínimo; 16 GB recomendado para XTF grandes o varias ejecuciones simultáneas |
| Disco | 10 GB libres | 50 GB o más en SSD (preferiblemente NVMe), sistema de archivos ext4 o XFS |
| Red | — | 1 Gbps; salida HTTPS hacia GitHub, registros de Docker y S3; acceso a la BD de los ETL |
| Arquitectura | `linux/amd64` | Servidor x86_64. En ARM (p. ej. Apple Silicon) funciona por emulación, más lento |

| Componente | Versión | Observación |
|---|---|---|
| Sistema operativo | Ubuntu Server 22.04 LTS o superior, Debian 12 o superior, RHEL 8 o superior | Con parches de seguridad al día. macOS o Windows con Docker Desktop solo para desarrollo. |
| Docker Engine | 24.0 o superior | |
| Docker Compose (plugin) | 2.21 o superior | Comando `docker compose`. |
| Git | 2.40 o superior | Con acceso a los repositorios de los ETL. |
| `wget`, `unzip`, `bash` | Versiones del sistema | Requeridos por los scripts de descarga y registro de ETL. |
| Apache Airflow | 3.3.0 | Incluido en la imagen (`apache/airflow:3.3.0`), con `apache-airflow-providers-postgres`, `boto3`, `requests` y `python-dotenv`. |
| Java (Eclipse Temurin JRE) | 21 | Incluido en la imagen. |
| ili2pg | 5.5.2 (principal) y 4.4.3 (legado) | Se descargan con `scripts/download_dependencies.sh`. |
| PostgreSQL (metadatos de Airflow) | 16 | Contenedor `postgres`. |
| Redis | 7.2-bookworm | Contenedor `redis`. |
| PostgreSQL + PostGIS (BD de los ETL) | PostGIS 3.x | Externa al despliegue. El usuario debe poder crear esquemas y las extensiones `postgis` y `uuid-ossp`, o estas deben existir. |
| Nginx | Versión estable | Solo producción, con certificado TLS. |
| Bucket S3 | — | Credenciales de escritura y ACL habilitadas (los objetos se publican como `public-read`). |

## 6. CONFIGURACIÓN DEL SISTEMA

Estructura del repositorio y propósito de cada elemento:

| Carpeta / archivo | Descripción |
|---|---|
| `airflow/.env` · `airflow/.env.example` | Variables de entorno del despliegue. `.env` contiene secretos y **no se versiona**. |
| `airflow/compose.yml` · `airflow/compose.dev.yml` | Servicios para producción y para desarrollo local. |
| `airflow/Dockerfile` · `airflow/requirements.txt` | Imagen personalizada (Airflow 3.3.0 + Java 21) y dependencias Python. |
| `airflow/config/` | Rutas de trabajo, rutas de los JAR de ili2pg y lectura de parámetros de BD. En `config/etl_config/<etl>` se enlaza el `config.py` de cada ETL. |
| `airflow/utils/` | Funciones reutilizables: ili2db, archivos y S3, tareas del flujo estándar y validadores de insumos y conexiones. |
| `airflow/logic/` | Tareas ili2db estándar (`models.py`) y, enlazados en `logic/<etl>`, los SQL y modelos INTERLIS de cada ETL. |
| `airflow/dags/` | DAG de cada ETL (`dags/<etl>/etl_dag.py`), enlazado por su `configure.sh`. |
| `airflow/libs/` | ili2pg descargado (`iliwrapper/bin`) y script `insert_ctm12_pg.sql` que registra EPSG:9377. |
| `airflow/submodules/` | Repositorios de los ETL (montados en solo lectura en los contenedores). |
| `airflow/output/` · `airflow/logs/` | Archivos generados por cada ejecución (`output/<etl>/<process_id>/`) y logs de Airflow (no versionados). |
| `airflow/update_submodules.sh` | Registro, actualización y desregistro de los ETL según la lista `SUBMODULOS`. |
| `scripts/download_dependencies.sh` | Descarga de ili2pg. |
| `docs/` | Documentación técnica detallada (variables, Nginx, PostgreSQL en Linux). |

Cada ETL sigue una estructura estándar (`config/etl_config/<etl>`, `dags/<etl>`, `logic/<etl>` y `output/<etl>`) que su `configure.sh` enlaza en las carpetas equivalentes del orquestador, de modo que las configuraciones de los distintos ETL no se mezclan. La estructura de los ETL entregados, las consideraciones para su despliegue y su ejecución se detallan en `docs/instructivo_despliegue_etl_otl.md`.

Variables de entorno (`airflow/.env`, creado a partir de `.env.example`). Docker Compose las carga en los contenedores y las usa para sustituir los valores `${...}` de los archivos `compose`. El detalle está en `docs/configuracion_variables_entorno.md`.

| Variable | Uso |
|---|---|
| `AIRFLOW_UID` | UID del usuario del servidor que ejecuta Docker (`id -u`). Evita problemas de permisos en `logs/`, `output/` y `dags/`. |
| `_AIRFLOW_WWW_USER_USERNAME` / `_AIRFLOW_WWW_USER_PASSWORD` | Usuario administrador creado en la inicialización. |
| `POSTGRES_CONN_ID` | Debe ser `terrainfo_etl`: es la conexión que Compose crea como `AIRFLOW_CONN_TERRAINFO_ETL`. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | BD de los ETL. Las usan tanto la conexión de Airflow (tareas SQL) como ili2db directamente. |
| `S3_AWS_REGION_NAME`, `S3_AWS_ACCESS_KEY_ID`, `S3_AWS_SECRET_ACCESS_KEY`, `S3_AWS_BUCKET_NAME` | Publicación del resultado en S3. |
| `AIRFLOW_PUBLIC_URL` | Esquema y dominio público, sin barra final (ej. `https://midominio.com`). |
| `AIRFLOW_PATH` | Subpath con barra inicial y sin barra final (ej. `/airflow`). Vacío para publicar en la raíz. |
| `FERNET_KEY` | Clave de cifrado de Airflow. Obligatoria en producción y **debe conservarse entre despliegues**. |
| `AIRFLOW__API_AUTH__JWT_SECRET` | Opcional, recomendado en producción: reemplaza el secreto JWT por defecto del compose. |

Generación de valores:

```bash
id -u                     # AIRFLOW_UID
openssl rand -hex 24      # contraseñas y secreto JWT
docker run --rm apache/airflow:3.3.0 python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # FERNET_KEY
```

Diferencias entre los archivos de Compose:

| Aspecto | `compose.yml` (producción) | `compose.dev.yml` (local) |
|---|---|---|
| Puerto del api-server | `127.0.0.1:8080` (solo vía Nginx) | `8080` en todas las interfaces |
| Subpath (`AIRFLOW__API__BASE_URL`) | `${AIRFLOW_PUBLIC_URL}${AIRFLOW_PATH}` | No aplica (raíz) |
| `FERNET_KEY` | Tomada del `.env` | Vacía |
| `host.docker.internal` | No definido: usar IP o DNS real de la BD | Mapeado al host (`host-gateway`) |

Registro de ETL: en `airflow/update_submodules.sh` se agrega una línea por ETL con el formato `nombre|URL|rama`; se pueden registrar tantos ETL como se requiera:

```bash
SUBMODULOS=(
    "af_ms_to_ladm_rhc|https://github.com/ceicol/af_ms_to_ladm_rhc.git|main"
    "af_ms_to_ladm_nca|https://github.com/ceicol/af_ms_to_ladm_nca.git|main"
    "af_ms_to_ladm_zra|https://github.com/ceicol/af_ms_to_ladm_zra.git|main"
)
```

Nginx (producción): el `location` debe coincidir con `AIRFLOW_PATH` y `proxy_pass` **no** debe terminar en `/`. Configuración completa en `docs/despliegue_usando_nginx_proxy_reverso.md`.

```nginx
location /airflow/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
location = /airflow { return 301 /airflow/; }
```

BD de los ETL: si PostgreSQL corre en el mismo servidor, debe escuchar en la interfaz de Docker (`listen_addresses`) y autorizar en `pg_hba.conf` solo las subredes de Docker (p. ej. `172.17.0.0/16`, `172.18.0.0/16`). Procedimiento en `docs/usar_host-docker-internal_linux.md`.

## 7. PROCEDIMIENTO DE DESPLIEGUE

Salvo que se indique lo contrario, los comandos se ejecutan en la carpeta `airflow/` del repositorio.

1. **Instalar los prerrequisitos** del servidor. Docker Engine y el plugin de Compose se instalan siguiendo la guía oficial de Docker para la distribución (`https://docs.docker.com/engine/install/`). Configurar además el acceso de Git a los repositorios de los ETL (token HTTPS o llave SSH).

   ```bash
   sudo apt update && sudo apt install -y git wget unzip
   sudo systemctl enable --now docker
   docker --version && docker compose version
   ```

2. **Clonar el repositorio.**

   ```bash
   git clone https://github.com/ceicol/ili-workflow.git
   cd ili-workflow
   ```

3. **Descargar ili2db** (desde la raíz del repositorio). Deja ili2pg 4.4.3 y 5.5.2 en `airflow/libs/iliwrapper/bin`.

   ```bash
   sh scripts/download_dependencies.sh
   ```

4. **Configurar variables de entorno** según la sección 6.

   ```bash
   cd airflow
   cp .env.example .env
   vi .env
   chmod 600 .env
   ```

5. **Registrar y enlazar los ETL.** Editar `SUBMODULOS` en `update_submodules.sh` y ejecutarlo. La lista `SUBMODULOS` es la fuente de verdad. Por cada ETL de la lista, el script registra el submódulo en `.gitmodules` (o actualiza su URL y rama), lo inicializa, lo deja en el último commit de la rama indicada (si hay cambios locales o commits sin publicar, los conserva y omite la actualización) y ejecuta el `configure.sh` del ETL, que crea los enlaces hacia Airflow. Los ETL registrados que ya no estén en la lista se desregistran (submódulo y enlaces), conservando su carpeta `output/<etl>`. Con `bash update_submodules.sh <repo>` se actualiza solo el ETL indicado. Debe terminar con `[OK] Proceso finalizado correctamente.` y dejar, por cada ETL, los enlaces `dags/<etl>`, `logic/<etl>` y `config/etl_config/<etl>` y la carpeta `output/<etl>`. No es necesario reiniciar los servicios: Airflow detecta el nuevo DAG en unos minutos. La estructura de cada ETL, su ejecución y la verificación de resultados se describen en `docs/instructivo_despliegue_etl_otl.md`.

   ```bash
   bash update_submodules.sh
   ```

6. **Construir e iniciar los servicios.**

   ```bash
   # Producción
   docker compose build
   docker compose up -d

   # Local
   docker compose -f compose.dev.yml up -d --build
   ```

7. **Validar la configuración sustituida** (producción).

   ```bash
   docker compose config | grep -E "BASE_URL|EXECUTION_API"
   docker compose ps
   ```

8. **Publicar en Nginx** (producción) y recargar.

   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

9. **Ingresar a Airflow** en `${AIRFLOW_PUBLIC_URL}${AIRFLOW_PATH}/` (producción) o `http://localhost:8080` (local) con el usuario administrador, y **activar (despausar) los DAG**: se crean pausados por defecto.

10. **Ejecutar las pruebas** de la sección 9.

## 8. ERRORES TÉCNICOS MÁS COMUNES Y SU SOLUCIÓN

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker: 'compose' is not a docker command` | Plugin de Docker Compose no instalado o Docker antiguo | Instalar Docker Engine y el plugin `docker-compose-plugin` desde el repositorio oficial de Docker; verificar con `docker compose version`. |
| Falla `git clone` o `update_submodules.sh` con error de autenticación o `Repository not found` | Sin credenciales para los repositorios privados de los ETL, URL mal escrita o sin salida a GitHub | Validar con `git ls-remote <url>`; configurar token HTTPS o llave SSH; corregir la URL en `SUBMODULOS`. |
| Los contenedores no inician: usuario `uid_del_usuario_del_servidor` inválido | `AIRFLOW_UID` quedó con el valor de ejemplo | Asignar el resultado de `id -u` en `.env` y repetir `docker compose up -d`. |
| `Fernet key must be 32 url-safe base64-encoded bytes` | `FERNET_KEY` vacía o con el texto de ejemplo en producción | Generar la clave (sección 6). Si ya existían credenciales cifradas, restaurar la clave original. |
| `bind: address already in use` en el puerto 8080 | Otro servicio usa el puerto | Identificarlo con `sudo lsof -i :8080`; liberarlo o cambiar el mapeo en el compose (p. ej. `127.0.0.1:8081:8080`) y ajustar `proxy_pass` en Nginx. |
| `airflow-init` muestra `WARNING!!!: Not enough memory/CPUS/Disk`, o contenedores reiniciando con `Killed` (OOM) | Recursos insuficientes para Docker | Revisar con `docker stats` y `free -h`; ampliar recursos según la sección 5. |
| `airflow-init` termina con error y los demás servicios no arrancan | Fallo en la migración de metadatos o variables inválidas | Revisar `docker compose logs airflow-init`, corregir y ejecutar `docker compose up -d` de nuevo. |
| Falla `docker compose build`: `"/dags": not found` | El `Dockerfile` copia `dags/`, que aún no existe | Ejecutar `update_submodules.sh` antes de construir; si aún no hay ETL, crear la carpeta con `mkdir -p dags`. |
| `Archivo JAR no encontrado: .../ili2pg-5.5.2.jar` | No se ejecutó `download_dependencies.sh`, o se ejecutó fuera de la raíz del repositorio | Ejecutarlo desde la raíz del repositorio y verificar `airflow/libs/iliwrapper/bin`. |
| `could not translate host name "host.docker.internal"` | En `compose.yml` (Linux) ese nombre no está definido | Usar en `DB_HOST` la IP o DNS de la BD, o agregar `extra_hosts: host.docker.internal:host-gateway` como en `compose.dev.yml`. |
| `Connection refused` o `no pg_hba.conf entry` hacia la BD de los ETL | PostgreSQL no escucha en la red de Docker, no autoriza su subred o un firewall bloquea el puerto | Ajustar `listen_addresses` y `pg_hba.conf` (`docs/usar_host-docker-internal_linux.md`), revisar el firewall y reiniciar PostgreSQL. |
| `The conn_id ... isn't defined` | `POSTGRES_CONN_ID` distinto de `terrainfo_etl` | Dejar `POSTGRES_CONN_ID=terrainfo_etl` (nombre ligado a `AIRFLOW_CONN_TERRAINFO_ETL`). |
| ili2db falla con `permission denied to create extension` | El usuario de BD no puede crear `postgis` / `uuid-ossp` | Crear las extensiones con un superusuario en la BD de los ETL o ampliar los privilegios del usuario. |
| Falla `exportar_en_formato_xtf_datos_modelo_ladm_col` | Los datos transformados no cumplen las restricciones del modelo LADM_COL (ili2db valida al exportar) | Revisar en el log de la tarea los errores de ili2db y corregir el SQL del ETL o los datos de entrada. |
| Falla la publicación en S3 (`AccessControlListNotSupported`, credenciales) | Bucket sin ACL habilitadas o credenciales/región incorrectas | Habilitar ACL en el bucket (Object Ownership) y validar las variables `S3_AWS_*`. Si el log muestra `exceptions must derive from BaseException`, la causa real está en la línea de error previa. |
| Página en blanco o 404 en `/airflow` | `BASE_URL` no aplicado, `proxy_pass` con `/` final o `location` distinto de `AIRFLOW_PATH` | Validar con `docker compose config`, recrear contenedores y alinear la configuración de Nginx. |
| La UI carga, pero todas las tareas fallan | `EXECUTION_API_SERVER_URL` sin el subpath | Verificar que use `${AIRFLOW_PATH}/execution/` y recrear contenedores. |
| El DAG del ETL no aparece | El ETL no quedó enlazado o tiene errores de importación | Confirmar el `[OK]` de `update_submodules.sh` y revisar `airflow dags list-import-errors` y `docker compose logs airflow-dag-processor`. Errores propios del ETL: sección 10 de `docs/instructivo_despliegue_etl_otl.md`. |
| `PermissionError` al escribir en `logs/` u `output/` | Archivos creados con otro UID | Corregir `AIRFLOW_UID` y ejecutar `sudo chown -R $(id -u):0 logs output`. |

Para diagnosticar cualquier caso: log de la tarea en la interfaz de Airflow y `docker compose logs -f <servicio>`.

## 9. PRUEBAS DEL SISTEMA

| # | Tipo | Prueba | Comando o acción | Resultado esperado |
|---|---|---|---|---|
| 1 | Integración | Submódulos ETL | `git submodule status` (raíz del repositorio) | Cada ETL con su commit, sin el prefijo `-` (no inicializado). |
| 2 | Integración | Estado de servicios | `docker compose ps` | Todos los servicios `running (healthy)`; `airflow-init` finalizado con código 0. |
| 3 | Integración | Salud de la API | `curl -f http://127.0.0.1:8080/airflow/api/v2/monitor/health` (local: `http://localhost:8080/api/v2/monitor/health`) | Respuesta JSON con `metadatabase` y `scheduler` en estado `healthy`. |
| 4 | Integración | Java e ili2db | `docker compose exec airflow-worker bash -c 'java -version && ls /opt/airflow/libs/iliwrapper/bin'` | Java 21 y carpetas `ili2pg-4.4.3` e `ili2pg-5.5.2`. |
| 5 | Integración | Conectividad a la BD de los ETL | `docker compose exec airflow-worker bash -c 'pg_isready -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$DB_USER"'` | `accepting connections`. |
| 6 | Funcional | Carga de DAG | `docker compose exec airflow-scheduler airflow dags list` y `airflow dags list-import-errors` | Los DAG de los ETL listados y sin errores de importación. |
| 7 | Funcional | Acceso web | Abrir `${AIRFLOW_PUBLIC_URL}${AIRFLOW_PATH}/` e iniciar sesión | Interfaz completa, sin errores 404 en la pestaña Red del navegador. |
| 8 | Funcional | Ejecución de extremo a extremo | Ejecutar el DAG de un ETL con un XTF de prueba (por defecto, `SIMPLIFIED_MODEL_EXAMPLE_XTF`) | Todas las tareas en `success`; en `output/<etl>/<process_id>/` quedan `<process_id>.xtf`, `output_<process_id>.xtf` y `.zip`; en la BD existen `input_<process_id>` y `output_<process_id>`; en S3 existe `ili-workflow/<etl>/output_<process_id>.zip`. |
| 9 | Seguridad | Exposición de puertos (producción) | `sudo ss -tlnp \| grep 8080` | Solo `127.0.0.1:8080`; el acceso externo es únicamente por Nginx (HTTPS). |
| 10 | Seguridad | Protección de secretos | `ls -l .env` y `git check-ignore -v .env` | Permisos `-rw-------` y archivo ignorado por Git. |
| 11 | Rendimiento | Consumo de recursos | `docker stats` durante la prueba 8 | Sin reinicios de contenedores ni memoria saturada de forma sostenida. |

## 10. MANTENIMIENTO Y SOPORTE

| Actividad | Frecuencia sugerida | Procedimiento |
|---|---|---|
| Respaldo de la BD de los ETL | Diaria | `pg_dump -h <host> -U <usuario> -Fc <bd> > etl_$(date +%F).dump`, almacenado fuera del servidor. |
| Respaldo de metadatos de Airflow | Diaria | `docker compose exec -T postgres pg_dump -U airflow airflow \| gzip > airflow_meta_$(date +%F).sql.gz` |
| Respaldo de configuración | En cada cambio | Copia segura de `.env` (en especial `FERNET_KEY`) y registro de los ETL y commits desplegados. |
| Prueba de restauración | Mensual | Restaurar un respaldo en un ambiente de pruebas y verificar su integridad. |
| Actualizar un ETL | Según publicación del ETL | `bash update_submodules.sh` (todos) o `bash update_submodules.sh <repo>` (uno). Si el submódulo tiene cambios locales o commits sin publicar, los conserva y omite la actualización (mensaje `WARN`). Airflow recarga los DAG sin reiniciar. |
| Registrar o retirar un ETL | Según necesidad | Añadir o quitar su línea en `SUBMODULOS` y ejecutar `bash update_submodules.sh`; seguir `docs/instructivo_despliegue_etl_otl.md`. |
| Actualizar el orquestador | Según publicación | Probar primero en ambiente local; luego `git pull`, `docker compose build` y `docker compose up -d`. |
| Actualizar ili2db | Según necesidad | Cambiar la versión en `scripts/download_dependencies.sh` **y** en `airflow/config/enums.py`, y volver a ejecutar la descarga. |
| Limpieza de ejecuciones | Mensual | Cada ejecución crea los esquemas `input_<process_id>` y `output_<process_id>` y una carpeta en `output/`. Eliminar los que ya no se requieran (`DROP SCHEMA ... CASCADE`). |
| Limpieza de logs y Docker | Semanal | Depurar `logs/` (p. ej. `find logs -type f -mtime +30 -delete`) e imágenes sin uso (`docker image prune`). |
| Monitoreo | Diaria | Estado de DAG y tareas en la UI, `docker compose ps`, `docker stats`, `df -h` y `docker compose logs -f <servicio>`. Flower opcional (`docker compose --profile flower up -d`, puerto 5555, sin exponer a Internet). |
| Seguridad | Trimestral | Rotar contraseñas y credenciales de BD y S3, definir el secreto JWT, mantener el api-server solo en `127.0.0.1` y revisar permisos de archivos. |
| Registro de cambios | En cada intervención | Documentar actualizaciones, incidencias y soluciones aplicadas. |

Soporte: las incidencias se registran en el repositorio `ceicol/ili-workflow` (o en el del ETL afectado), indicando DAG, `process_id`, tarea fallida, log de la tarea y versión (commit) desplegada. La documentación técnica de referencia está en la carpeta `docs/` del repositorio.

## 11. CONCLUSIONES

- El orquestador separa la plataforma de ejecución de la lógica de cada línea temática: incorporar o actualizar un ETL no requiere modificar el orquestador, solo registrarlo como submódulo.
- El despliegue se reduce a cuatro pasos: descargar ili2db, configurar `.env`, registrar los ETL y levantar Docker Compose; en producción se añade la publicación detrás de Nginx con subpath y HTTPS.
- La migración a Airflow 3 y la configuración centralizada en `.env` permiten pasar de desarrollo a producción sin modificar el código, cambiando solo variables de entorno y el archivo de Compose.
- La mayoría de los errores de despliegue se concentra en el `.env` (UID, `FERNET_KEY`, conexión a la BD y subpath); las pruebas de la sección 9 permiten confirmarlo antes de operar.
- Se recomienda mantener respaldos semanales con pruebas de restauración, limpiar periódicamente los esquemas de cada ejecución y rotar credenciales para asegurar la continuidad y seguridad del servicio.
