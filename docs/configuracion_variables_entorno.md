## Variables de entorno

La configuración del despliegue se realiza mediante un archivo `.env`. El repositorio incluye el archivo `.env.example` como referencia de las variables que deben configurarse en cada ambiente.

Para crear la configuración local o de producción:

```bash
cp .env.example .env
```

> **Importante:** el archivo `.env` puede contener credenciales y secretos y, por lo tanto, **no debe almacenarse en el repositorio Git**.

### Archivo `.env.example`

```dotenv
# Airflow
AIRFLOW_UID=1000
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=cambiar_esta_contraseña

# DB PostgreSQL
POSTGRES_CONN_ID=terrainfo_etl
DB_HOST=host.docker.internal
DB_NAME=etl
DB_USER=postgres
DB_PASSWORD=cambiar_esta_contraseña
DB_PORT=5432

# S3 Storage
S3_AWS_REGION_NAME=
S3_AWS_ACCESS_KEY_ID=
S3_AWS_SECRET_ACCESS_KEY=
S3_AWS_BUCKET_NAME=

# Despliegue
AIRFLOW_PUBLIC_URL=https://midominio.com
AIRFLOW_PATH=/airflow

# Seguridad
FERNET_KEY=
```

### Descripción de las variables

| Variable | Descripción | Ejemplo |
|---|---|---|
| `AIRFLOW_UID` | UID del usuario del sistema que ejecutará los contenedores de Airflow. Permite mantener correctamente los permisos de los archivos y volúmenes compartidos. | `1000` |
| `_AIRFLOW_WWW_USER_USERNAME` | Nombre del usuario administrador que puede crearse durante la inicialización de Airflow. | `admin` |
| `_AIRFLOW_WWW_USER_PASSWORD` | Contraseña inicial del usuario administrador. En producción debe reemplazarse por una contraseña segura. | `contraseña_segura` |
| `POSTGRES_CONN_ID` | Identificador de la conexión PostgreSQL utilizada por los DAG y procesos ETL. | `terrainfo_etl` |
| `DB_HOST` | Host donde se encuentra PostgreSQL. | `host.docker.internal` |
| `DB_NAME` | Nombre de la base de datos. | `etl` |
| `DB_USER` | Usuario de conexión a PostgreSQL. | `postgres` |
| `DB_PASSWORD` | Contraseña del usuario PostgreSQL. Debe mantenerse como secreto. | — |
| `DB_PORT` | Puerto utilizado por PostgreSQL. | `5432` |
| `S3_AWS_REGION_NAME` | Región donde se encuentra el almacenamiento S3. | `us-east-1` |
| `S3_AWS_ACCESS_KEY_ID` | Access Key utilizada para acceder al almacenamiento S3. | — |
| `S3_AWS_SECRET_ACCESS_KEY` | Secret Access Key utilizada para acceder al almacenamiento S3. Debe mantenerse como secreto. | — |
| `S3_AWS_BUCKET_NAME` | Nombre del bucket S3 utilizado por la aplicación. | — |
| `AIRFLOW_PUBLIC_URL` | Esquema y dominio público por el que se accede a Airflow, **sin** barra final. | `https://midominio.com` |
| `AIRFLOW_PATH` | Subpath bajo el que Nginx publica Airflow, con barra inicial y **sin** barra final. Dejar vacío para publicar en la raíz. | `/airflow` |
| `FERNET_KEY` | Clave utilizada por Airflow para cifrar información sensible almacenada en su base de datos. Debe configurarse en producción y conservarse entre despliegues. | — |

Con la configuración:

```dotenv
AIRFLOW_PUBLIC_URL=https://midominio.com
AIRFLOW_PATH=/airflow
```

la URL pública de Airflow será:

```text
https://midominio.com/airflow
```

### Configuración de `AIRFLOW_UID`

`AIRFLOW_UID` identifica el usuario del sistema anfitrión con el que se ejecutarán los contenedores de Airflow. Su objetivo principal es evitar problemas de permisos sobre directorios montados como volúmenes, por ejemplo:

```text
dags/
logs/
plugins/
config/
```

En servidores **Linux**, obtener el UID del usuario que ejecutará Docker mediante:

```bash
id -u
```

Por ejemplo:

```bash
$ id -u
1000
```

El archivo `.env` debe entonces contener:

```dotenv
AIRFLOW_UID=1000
```

También puede generarse automáticamente:

```bash
echo "AIRFLOW_UID=$(id -u)"
```

> El valor no debe generarse aleatoriamente. Debe corresponder al UID del usuario del servidor que administra los archivos y volúmenes utilizados por Airflow.

### Usuario administrador de Airflow

Las siguientes variables definen las credenciales utilizadas durante la creación inicial del usuario administrador:

```dotenv
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=cambiar_esta_contraseña
```

En producción se debe sustituir `cambiar_esta_contraseña` por una contraseña segura.

Puede generarse una contraseña aleatoria, por ejemplo, utilizando OpenSSL:

```bash
openssl rand -hex 24
```

Ejemplo de resultado:

```text
c27b8ac10df39b273436dd7398c5fa769c547e60fc9baf82
```

Y posteriormente:

```dotenv
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=c27b8ac10df39b273436dd7398c5fa769c547e60fc9baf82
```

> Las variables `_AIRFLOW_WWW_USER_*` están orientadas principalmente a la inicialización del ambiente. Una vez creado el administrador, la gestión de usuarios debe realizarse utilizando los mecanismos de autenticación y administración correspondientes a la versión de Airflow instalada.

### Configuración de `FERNET_KEY`

Airflow utiliza `FERNET_KEY` para cifrar información sensible almacenada en su base de datos, especialmente credenciales de conexiones.

En producción debe generarse una clave segura.

Ejecutar:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Se obtendrá un valor similar a:

```text
M8u9rTCK5_wP8fZXVNVmxQ0Bhf2qD3kI0F7VzPHjYqE=
```

Registrar el resultado en `.env`:

```dotenv
FERNET_KEY=M8u9rTCK5_wP8fZXVNVmxQ0Bhf2qD3kI0F7VzPHjYqE=
```

Y pasarlo a Airflow desde `docker-compose.yml`:

```yaml
environment:
  AIRFLOW__CORE__FERNET_KEY: ${FERNET_KEY}
```

> **No generar una nueva `FERNET_KEY` en cada despliegue.** La misma clave debe conservarse durante el ciclo de vida del ambiente. Cambiarla directamente puede impedir que Airflow descifre credenciales previamente almacenadas.

### Configuración para producción

Antes de desplegar en producción se deben revisar, como mínimo, las siguientes variables:

```dotenv
AIRFLOW_UID=<uid_del_usuario_del_servidor>

_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=<contraseña_segura>

DB_PASSWORD=<contraseña_segura>

S3_AWS_REGION_NAME=<region>
S3_AWS_ACCESS_KEY_ID=<access_key>
S3_AWS_SECRET_ACCESS_KEY=<secret_key>
S3_AWS_BUCKET_NAME=<bucket>

AIRFLOW_PUBLIC_URL=https://midominio.com
AIRFLOW_PATH=/airflow

FERNET_KEY=<fernet_key_generada>
```

Las siguientes variables deben considerarse **secretos**:

```text
_AIRFLOW_WWW_USER_PASSWORD
DB_PASSWORD
S3_AWS_ACCESS_KEY_ID
S3_AWS_SECRET_ACCESS_KEY
FERNET_KEY
```

No deben almacenarse con sus valores reales en `.env.example`, archivos versionados, imágenes Docker ni documentación pública.
