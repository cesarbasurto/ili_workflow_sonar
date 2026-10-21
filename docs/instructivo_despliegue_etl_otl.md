# INSTRUCTIVO: Despliegue y ejecución de los ETL de OTL en el Orquestador Airflow ETL (`ili-workflow`)

| Elemento | Valor |
|---|---|
| Aplica a | ETL de los OTLs y registrados como submódulos en `ili-workflow` |
| ETL de referencia | `af_ms_to_ladm_nca` (Nacimientos de agua) |
| Prerrequisito | Orquestador desplegado según `docs/manual_de_despliegue.md` |
| Notación | `<repo>`: submódulo del ETL (p. ej. `af_ms_to_ladm_nca`) · `<etl>`: nombre del ETL (p. ej. `ms_to_ladm_nca`) · `<process_id>`: identificador de una ejecución |

## 1. OBJETIVO Y ALCANCE

Explicar cómo desplegar y ejecutar en el orquestador los ETL entregados en la consultoría, cómo está compuesto cada uno y qué consideraciones deben tenerse en cuenta para su operación. Cada ETL transforma los datos de un Objeto Territorial Legal (OTL) desde su **modelo simplificado** al **modelo extendido LADM_COL**. Todos comparten la misma estructura, por lo que este instructivo aplica por igual a cada ETL entregado. El desarrollo de nuevos ETL no hace parte de su alcance.

## 2. ETL ENTREGADOS

Cada ETL es un producto independiente de la consultoría: tiene su propio repositorio Git, sus modelos INTERLIS, sus scripts de transformación y su versión. Se despliegan, actualizan y ejecutan de forma independiente, sin afectar a los demás.

| # | Submódulo (repositorio) | OTL | Rama |
|---|---|---|---|
| 1 | `af_ms_to_ladm_rhc` | Ronda hídrica | `main` |
| 2 | `af_ms_to_ladm_nca` | Nacimientos de agua | `main` |
| 3 | `af_ms_to_ladm_zra` | Zonas de recarga de acuíferos | `main` |

## 3. CÓMO SE INTEGRA UN ETL AL ORQUESTADOR

El orquestador aporta la plataforma de ejecución (Airflow, Java, ili2db, conexión a la base de datos y S3) y las tareas comunes; cada ETL aporta su configuración, su DAG, sus modelos y sus scripts SQL. Al registrar un ETL, su script `configure.sh` crea enlaces simbólicos desde el submódulo hacia las carpetas de Airflow. Cada carpeta lleva el nombre del ETL, de modo que las configuraciones de los distintos ETL no se mezclan:

| En el submódulo | En el orquestador (`airflow/`) | Tipo | Ruta en los contenedores |
|---|---|---|---|
| `config/etl_config/<etl>/` | `config/etl_config/<etl>` | Enlace simbólico | `/opt/airflow/config/etl_config/<etl>` |
| `dags/<etl>/` | `dags/<etl>` | Enlace simbólico | `/opt/airflow/dags/<etl>` |
| `logic/<etl>/` | `logic/<etl>` | Enlace simbólico | `/opt/airflow/logic/<etl>` |
| `output/<etl>/` | `output/<etl>` | Carpeta real, no versionada | `/opt/airflow/output/<etl>` |

Ejemplo con NCA:

```text
airflow/
├── config/etl_config/ms_to_ladm_nca -> ../../submodules/af_ms_to_ladm_nca/config/etl_config/ms_to_ladm_nca
├── dags/ms_to_ladm_nca              -> ../submodules/af_ms_to_ladm_nca/dags/ms_to_ladm_nca
├── logic/ms_to_ladm_nca             -> ../submodules/af_ms_to_ladm_nca/logic/ms_to_ladm_nca
└── output/ms_to_ladm_nca/           (archivos de cada ejecución)
```

Los enlaces son relativos, por lo que funcionan igual en el servidor y dentro de los contenedores. La carpeta `airflow/submodules` se monta **en solo lectura**: los ETL nunca escriben en su propia carpeta y todo lo que genera una ejecución queda en `output/<etl>/<process_id>/`.

## 4. ESTRUCTURA DE UN ETL

```text
<repo>/
├── configure.sh                       # Crea los enlaces en el orquestador
├── README.md                          # Descripción del ETL
├── config/etl_config/<etl>/config.py  # Variables del ETL
├── dags/<etl>/etl_dag.py              # DAG: tareas y orden de ejecución
├── logic/<etl>/
│   ├── sql/NNN_<paso>.sql             # Scripts de transformación
│   └── resources/models/
│       ├── SIMPLIFICADO/              # Modelo simplificado (.ili) y sus dependencias
│       └── LADM_COL/                  # Modelo extendido, núcleo LADM_COL y dependencias
└── output/<etl>/                      # Marca la carpeta de salida (su contenido no se versiona)
```

| Componente | Qué contiene | Rol en la ejecución |
|---|---|---|
| `configure.sh` | Script de enlace estándar | Lo ejecuta `update_submodules.sh` cada vez que registra o actualiza el ETL. Exige que existan `dags/`, `logic/` y `config/etl_config/`. |
| `config.py` | Identificación del ETL, modelos, XTF de ejemplo y lista de SQL | Parametriza el DAG. |
| `etl_dag.py` | DAG de Airflow (`dag_id` = nombre del ETL) | Define las tareas, los parámetros de ejecución y el orden en que se ejecutan los SQL. |
| `sql/` | Scripts SQL numerados (`000`, `010`, `020`…) | Cada script resuelve una parte específica de la transformación del modelo simplificado al LADM_COL. |
| `resources/models/` | Archivos `.ili` en `SIMPLIFICADO` y `LADM_COL` | ili2db crea con ellos los esquemas de la base de datos y valida la exportación. Cada carpeta incluye también los modelos que importa (p. ej. `ISO19107_PLANAS`, núcleo LADM_COL). |
| `output/<etl>/` | Carpeta vacía (`.gitkeep`) | Indica al orquestador que cree la carpeta de salida del ETL. |

Variables de `config.py`:

| Variable | Descripción | Valor en NCA |
|---|---|---|
| `DAG_DESCRIPTION` | Descripción del ETL, visible en Airflow | `ETL que transforma los datos del modelo simplificado al modelo extendido LADM_COL del OTL de nacimientos de agua.` |
| `ETL_NAME` | Nombre del ETL; coincide con las carpetas `<etl>` del repositorio y con el `dag_id` | `ms_to_ladm_nca` |
| `ETL_VERSION` | Versión del ETL | `0.1` |
| `ETL_TAGS` | Etiquetas para filtrar el DAG en Airflow | `ms_to_ladm_nca`, `0.1`, `ETL`, `LADM_COL`, `OTL`, `Nacimientos de agua` |
| `SIMPLIFIED_MODEL_NAME` | Nombre (`MODEL`) del modelo simplificado en INTERLIS | `MS_NacimientosAgua_V0_1` |
| `LADM_COL_MODEL_NAME` | Nombre (`MODEL`) del modelo extendido LADM_COL | `LADM_COL_v_1_0_0_Ext_NCA` |
| `SIMPLIFIED_MODEL_EXAMPLE_XTF` | URL pública de un conjunto de datos de prueba; es el valor por defecto con el que se ejecuta el ETL | `https://terrainfo.nyc3.cdn.digitaloceanspaces.com/OTLS/ms_nca.xtf` |
| `ETL_TASKS` | Lista de tuplas `(tarea, archivo SQL)` con los SQL que transforman los datos de forma atomizada | 10 tareas (`000` a `090`) |

Tareas del DAG, en orden de ejecución. Las tareas 1 a 5, 7 y 8 son comunes a todos los ETL; la 6 corresponde a los SQL propios de cada uno:

| # | Tarea (`task_id`) | Qué hace |
|---|---|---|
| 1 | `validar_conexion_postgres` | Verifica la conexión con la base de datos de los ETL. |
| 2 | `download_xtf` | Descarga o copia el XTF de entrada en `output/<etl>/<process_id>/<process_id>.xtf`. |
| 3 | `importar_esquema_modelo_simplificado` | Crea el esquema `input_<process_id>` con el modelo simplificado. |
| 4 | `importar_datos_modelo_simplificado` | Importa el XTF en `input_<process_id>`, validándolo contra el modelo simplificado. |
| 5 | `importar_esquema_modelo_ladm_col` | Crea el esquema `output_<process_id>` con el modelo extendido LADM_COL. |
| 6 | Tareas SQL de `ETL_TASKS` | Transforman los datos de `input_*` a `output_*`. Solo pueden ejecutarse después de crear los esquemas e importar los datos del modelo simplificado. |
| 7 | `exportar_en_formato_xtf_datos_modelo_ladm_col` | Exporta `output_<process_id>.xtf` y lo valida contra el modelo LADM_COL. |
| 8 | `publicar_en_s3_datos_zip_xtf_ladm_col` | Comprime el XTF y lo publica en S3 en `ili-workflow/<etl>/`. |

Las tareas `inicio` y `fin` solo marcan el comienzo y el final del flujo.

Scripts SQL de NCA, como ejemplo de cómo se descompone la transformación:

| Tarea | Transformación |
|---|---|
| `preparar_estructura_etl` (`000`) | Extensiones `postgis` y `uuid-ossp`, sistema EPSG:9377, dataset y basket del modelo LADM_COL y columnas auxiliares de cruce. |
| `migrar_interesados` (`010`) | Autoridades ambientales → `NCA_Interesado`. |
| `migrar_fuentes_administrativas` (`020`) | Datos de fuente de cada nacimiento → `NCA_FuenteAdministrativa`. |
| `migrar_unidad_administrativa` (`030`) | Nacimientos de agua → `NCA_UAB_NacimientoAgua`. |
| `migrar_unidad_espacial` (`040`) | Geometría de los nacimientos → `NCA_UE_NacimientoAgua`. |
| `diligenciar_relacion_entre_unidad_administrativa_y_espacial` (`050`) | Relación unidad espacial – unidad administrativa (`COL_UEBaUnit`). |
| `crear_estructura_col_area_valor` (`060`) | Área de cada unidad espacial (`COL_AreaValor`). |
| `crear_agrupacion_interesados` (`070`) | Agrupación de autoridades cuando hay más de un interesado. |
| `crear_responsabilidades` (`080`) | Responsabilidades de la autoridad ambiental sobre cada nacimiento (`NCA_Responsabilidad`). |
| `diligenciar_relacion_col_rrrfuente` (`090`) | Relación entre cada responsabilidad y su fuente administrativa (`COL_RRRFuente`). |

El orden de los SQL está definido en el DAG y responde a la integridad referencial del modelo LADM_COL (primero interesados y fuentes, luego unidades, relaciones y, por último, responsabilidades y sus fuentes), por lo que no debe alterarse.

## 5. CONSIDERACIONES PARA EL DESPLIEGUE Y LA OPERACIÓN

| Aspecto | Consideración |
|---|---|
| Acceso a los repositorios | Los repositorios de los ETL son privados: el servidor necesita credenciales de Git con acceso de lectura (token HTTPS o llave SSH). |
| Base de datos de los ETL | El script `000` de cada ETL crea, si no existen, las extensiones `postgis` y `uuid-ossp`. El usuario de `DB_USER` debe tener privilegios para crearlas, o un administrador debe crearlas antes. |
| Independencia de los ETL | Cada ETL usa carpetas con su propio nombre. No se deben crear manualmente carpetas con ese nombre en `dags/`, `logic/` o `config/etl_config/`: `configure.sh` las movería a `airflow/.configure_backups/`. |
| Submódulos de solo lectura | No se deben editar archivos dentro de `airflow/submodules/<repo>`. Si hay cambios locales o commits sin publicar, `update_submodules.sh` no actualiza ni desregistra ese ETL, para no perderlos. Los ajustes se publican como una nueva versión en su repositorio. |
| Reinicio de servicios | Registrar o actualizar un ETL no requiere reiniciar Airflow; el DAG aparece en unos minutos y **queda pausado** hasta activarlo. |
| `process_id` | Identifica cada ejecución y forma parte del nombre de los esquemas: solo minúsculas, números y guion bajo (p. ej. `nca_20261020_01`). No debe reutilizarse. Si se omite, Airflow propone uno aleatorio. |
| XTF de entrada | Debe corresponder al modelo simplificado del ETL (`SIMPLIFIED_MODEL_NAME`) y su nombre debe terminar en `.xtf`. Puede ser una URL accesible desde el worker o un archivo dentro de una ruta visible por los contenedores, por ejemplo `airflow/output/<etl>/insumos/`, que en el contenedor es `/opt/airflow/output/<etl>/insumos/`. |
| Validación de datos | ili2db valida dos veces: al importar el XTF (contra el modelo simplificado) y al exportar el resultado (contra el modelo LADM_COL). Si la exportación termina en `success`, el XTF generado es conforme al modelo extendido. |
| Ejecuciones simultáneas | Pueden ejecutarse varios ETL, o varias veces el mismo ETL, al mismo tiempo, siempre con `process_id` distintos. Cada ejecución consume recursos del worker y de la base de datos. |
| Crecimiento del almacenamiento | Cada ejecución crea dos esquemas en la base de datos y una carpeta en `output/<etl>/`. Deben depurarse periódicamente (sección 10 del manual de despliegue). |
| Publicación en S3 | El resultado se publica como objeto de lectura pública. Las variables `S3_AWS_*` deben estar configuradas en el `.env` del orquestador. |

## 6. PROCEDIMIENTO DE DESPLIEGUE DE LOS ETL

Los comandos se ejecutan en la carpeta `airflow/` del orquestador, salvo que se indique lo contrario.

1. **Verificar los prerrequisitos.** El orquestador debe estar en funcionamiento (`docker compose ps`) y el servidor debe tener acceso a los repositorios:

   ```bash
   git ls-remote https://github.com/ceicol/af_ms_to_ladm_nca.git
   ```

2. **Registrar los ETL** en `update_submodules.sh`, una línea por ETL con el formato `nombre|URL|rama`. Se pueden registrar tantos ETL como se requiera. La lista `SUBMODULOS` es la fuente de verdad: el script registra los ETL nuevos, actualiza los existentes y desregistra los que se retiren de ella:

   ```bash
   SUBMODULOS=(
       "af_ms_to_ladm_rhc|https://github.com/ceicol/af_ms_to_ladm_rhc.git|main"
       "af_ms_to_ladm_nca|https://github.com/ceicol/af_ms_to_ladm_nca.git|main"
       "af_ms_to_ladm_zra|https://github.com/ceicol/af_ms_to_ladm_zra.git|main"
   )
   ```

3. **Descargar y enlazar los ETL.** Por cada ETL de la lista, el script registra el submódulo (si es nuevo), descarga la última versión de la rama indicada y ejecuta su `configure.sh`. Los ETL registrados que ya no estén en la lista se desregistran:

   ```bash
   bash update_submodules.sh
   ```

   Resultado esperado por cada ETL (ejemplo con NCA):

   ```text
   [INFO] Procesando submódulo: af_ms_to_ladm_nca
   [INFO] Enlace creado: dags/ms_to_ladm_nca -> ../submodules/af_ms_to_ladm_nca/dags/ms_to_ladm_nca
   [INFO] Enlace creado: logic/ms_to_ladm_nca -> ../submodules/af_ms_to_ladm_nca/logic/ms_to_ladm_nca
   [INFO] Enlace creado: config/etl_config/ms_to_ladm_nca -> ../../submodules/af_ms_to_ladm_nca/config/etl_config/ms_to_ladm_nca
   [INFO] Directorio de salida preparado: output/ms_to_ladm_nca
   [OK] Submódulo 'af_ms_to_ladm_nca' actualizado y enlazado correctamente.
   ...
   [INFO] Resumen: registrados=3, actualizados=0, desregistrados=0, omitidos=0.
   [OK] Proceso finalizado correctamente.
   ```

4. **Verificar los submódulos y enlaces:**

   ```bash
   git submodule status                         # cada ETL con su commit y sin prefijo "-"
   ls -l dags logic config/etl_config output    # un enlace o carpeta por ETL
   ```

5. **Verificar que Airflow cargó los DAG.** Si un DAG no aparece después de unos minutos, reiniciar el procesador de DAG con `docker compose restart airflow-dag-processor`.

   ```bash
   docker compose exec airflow-scheduler airflow dags list
   docker compose exec airflow-scheduler airflow dags list-import-errors
   ```

## 7. EJECUCIÓN DE UN ETL

Desde la interfaz web de Airflow:

1. Ingresar a Airflow y abrir **Dags**. Filtrar por la etiqueta `OTL` o por el nombre del ETL.
2. Abrir el DAG (`ms_to_ladm_<sigla>`) y **activarlo** con el interruptor (los DAG se crean pausados).
3. Pulsar **Trigger** y diligenciar los parámetros:

   | Parámetro | Valor por defecto | Descripción |
   |---|---|---|
   | `process_id` | Identificador aleatorio | Identificador de la ejecución (ver sección 5). |
   | `xtf_path` | `SIMPLIFIED_MODEL_EXAMPLE_XTF` del ETL | URL o ruta en el contenedor del XTF del modelo simplificado. |

4. Confirmar la ejecución y seguir su avance en las vistas **Grid** o **Graph**. Cada tarea muestra su log, donde se registran los comandos de ili2db y los mensajes de error.

Con los valores por defecto, el ETL se ejecuta con su conjunto de datos de prueba: es la forma recomendada de validar un ETL recién desplegado.

Desde la línea de comandos:

```bash
docker compose exec airflow-scheduler airflow dags unpause ms_to_ladm_nca
docker compose exec airflow-scheduler airflow dags trigger ms_to_ladm_nca \
  --conf '{"process_id": "nca_20261020_01", "xtf_path": "https://<servidor>/<ruta>/<archivo>.xtf"}'
```

Con un archivo local en lugar de una URL:

```bash
mkdir -p output/ms_to_ladm_nca/insumos
cp /ruta/origen/datos_nca.xtf output/ms_to_ladm_nca/insumos/
# xtf_path = /opt/airflow/output/ms_to_ladm_nca/insumos/datos_nca.xtf
```

## 8. VERIFICACIÓN DE RESULTADOS

| Verificación | Resultado esperado |
|---|---|
| Estado de las tareas | Todas en `success`, desde `inicio` hasta `fin`. |
| Carpeta `output/<etl>/<process_id>/` | `<process_id>.xtf` (entrada), `output_<process_id>.xtf` (resultado LADM_COL) y `output_<process_id>.zip`. |
| Base de datos de los ETL | Esquemas `input_<process_id>` (datos de entrada) y `output_<process_id>` (datos transformados al modelo LADM_COL). |
| Bucket S3 | Objeto `ili-workflow/<etl>/output_<process_id>.zip`, accesible en `https://<bucket>.s3.<region>.amazonaws.com/ili-workflow/<etl>/output_<process_id>.zip`. |

Consulta de control sobre los datos transformados (ejemplo con NCA):

```sql
SELECT 'nca_uab_nacimientoagua' AS tabla, count(*) FROM output_<process_id>.nca_uab_nacimientoagua
UNION ALL
SELECT 'nca_ue_nacimientoagua', count(*) FROM output_<process_id>.nca_ue_nacimientoagua
UNION ALL
SELECT 'nca_interesado', count(*) FROM output_<process_id>.nca_interesado;
```

## 9. ACTUALIZACIÓN Y RETIRO DE UN ETL

| Operación | Procedimiento |
|---|---|
| Actualizar a una nueva versión | Cuando se publique una nueva versión en la rama registrada, ejecutar `bash update_submodules.sh` para actualizar todos los ETL, o `bash update_submodules.sh <repo>` para actualizar solo uno (p. ej. `bash update_submodules.sh af_ms_to_ladm_nca`). El script descarga la rama, deja el submódulo en su último commit e indica el cambio (`Submódulo actualizado de <commit> a <commit>`). Si el submódulo tiene cambios locales o commits sin publicar, los conserva y omite la actualización (mensaje `WARN`). No requiere reiniciar servicios; la nueva versión se refleja en la etiqueta `ETL_VERSION` del DAG. |
| Cambiar la rama o la URL de un ETL | Modificar su línea en `SUBMODULOS` y ejecutar `bash update_submodules.sh`. El script actualiza `.gitmodules` y cambia el submódulo a la nueva rama. |
| Retirar un ETL | Quitar su línea de `SUBMODULOS` y ejecutar `bash update_submodules.sh`. El script desregistra el ETL: elimina sus enlaces `dags/<etl>`, `logic/<etl>` y `config/etl_config/<etl>`, su entrada en `.gitmodules`, la carpeta `airflow/submodules/<repo>` y su repositorio en `.git/modules`. La carpeta `output/<etl>`, con los resultados de ejecuciones anteriores, se conserva. Si se desea borrar también su historial en Airflow: `airflow dags delete <etl>`. |
| Revisar qué cambió | Al final de cada ejecución el script muestra un resumen (`registrados`, `actualizados`, `desregistrados`, `omitidos`). Los cambios de submódulos quedan en el índice de Git del orquestador (`git status` desde la raíz del repositorio). |

## 10. ERRORES FRECUENTES

| Síntoma | Causa probable | Solución |
|---|---|---|
| `update_submodules.sh` falla con error de autenticación o `Repository not found` | El servidor no tiene acceso al repositorio privado o la URL es incorrecta | Validar con `git ls-remote <url>`, configurar las credenciales y revisar la línea en `SUBMODULOS`. |
| `WARN El submódulo tiene cambios locales sin confirmar` | Se modificaron archivos dentro de `airflow/submodules/<repo>` | Si los cambios no se requieren, descartarlos (`git -C submodules/<repo> checkout -- .`) y repetir `update_submodules.sh`; los ajustes al ETL se publican en su repositorio. |
| `WARN El submódulo tiene commits que no están en el repositorio remoto` | Se hicieron commits dentro de `airflow/submodules/<repo>` sin publicarlos | Publicarlos en el repositorio del ETL o, si no se requieren, descartarlos (`git -C submodules/<repo> reset --hard origin/<rama>`) y repetir `update_submodules.sh`. |
| `La ruta 'airflow/submodules/<repo>' existe y no es un submódulo` | Existe una carpeta con el nombre del submódulo que no fue creada por el script | Mover o eliminar la carpeta y repetir `update_submodules.sh`. |
| `WARN Se respaldó la ruta existente en .configure_backups/...` | Existía una carpeta real con el nombre del ETL | Revisar el respaldo en `airflow/.configure_backups/` y eliminarlo si no se requiere. |
| El DAG no aparece o figura en `airflow dags list-import-errors` | El ETL no quedó enlazado o la versión publicada tiene un error | Confirmar el `[OK]` del script y los enlaces (paso 4 de la sección 6); reportar el error de importación al responsable del ETL. |
| Falla `download_xtf` (`The URL does not point to a .xtf file`, `Local file not found`, 404) | La URL no termina en `.xtf`, no es accesible desde el worker o la ruta local no es visible en el contenedor | Corregir `xtf_path`; para archivos locales usar una ruta bajo `/opt/airflow/output/`. |
| Falla `importar_datos_modelo_simplificado` | El XTF no corresponde al modelo simplificado del ETL o tiene errores de validación | Revisar el log de la tarea y corregir el XTF de entrada. |
| Falla `preparar_estructura_etl` con `permission denied to create extension` | El usuario de base de datos no puede crear `postgis` o `uuid-ossp` | Crear las extensiones con un superusuario o ampliar los privilegios del usuario. |
| Falla `preparar_estructura_etl` con `duplicate key value violates unique constraint` | Se reutilizó un `process_id` | Ejecutar con un `process_id` nuevo o eliminar antes los esquemas `input_` y `output_` de esa ejecución. |
| `syntax error at or near "-"` en una tarea SQL | `process_id` con guiones u otros caracteres no válidos | Usar solo minúsculas, números y guion bajo. |
| Falla `exportar_en_formato_xtf_datos_modelo_ladm_col` | Los datos transformados no cumplen alguna restricción del modelo LADM_COL | Revisar en el log los errores de validación de ili2db; normalmente provienen de datos de entrada incompletos o inconsistentes. |
| Fallan la conexión a la base de datos o la publicación en S3 | Configuración del orquestador | Ver la sección 8 del manual de despliegue. |