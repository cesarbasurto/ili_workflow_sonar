## Publicación de Airflow detrás de Nginx (proxy inverso con subpath)

Airflow 3 se ejecuta en Docker y se publica a través de Nginx bajo un subpath configurable. La URL pública se define mediante variables de entorno, de modo que el dominio o la ruta pueden cambiarse sin modificar el `docker-compose.yaml`.

| Acceso | URL |
|---|---|
| Público (vía Nginx) | `${AIRFLOW_PUBLIC_URL}${AIRFLOW_PATH}/` (ej. `https://midominio.com/airflow/`) |
| Directo al contenedor (solo diagnóstico) | `http://127.0.0.1:8080${AIRFLOW_PATH}/` |

### Por qué se requiere esta configuración

Nginx reenvía las peticiones conservando el prefijo del subpath. Por defecto Airflow asume que se sirve desde la raíz (`/`), por lo que sin configuración adicional responde 404 o la interfaz web (una SPA en React) intenta cargar sus recursos (`/static/...`, `/api/v2/...`) sin el prefijo, y esas rutas no llegan a Airflow. Por eso hay que indicarle a Airflow su URL base y ajustar la URL interna de la Execution API.

### 1. Variables de entorno (`.env`)

Docker Compose lee automáticamente el archivo `.env` ubicado en la misma carpeta que `docker-compose.yaml` y sustituye las referencias `${VARIABLE}`.

| Variable | Descripción | Ejemplo |
|---|---|---|
| `AIRFLOW_PUBLIC_URL` | Esquema y dominio público por el que se accede a Airflow, **sin** barra final | `https://midominio.com` |
| `AIRFLOW_PATH` | Subpath bajo el que Nginx publica Airflow, con barra inicial y **sin** barra final. Dejar vacío para publicar en la raíz | `/airflow` |

Ejemplo de `.env`:

```dotenv
AIRFLOW_PUBLIC_URL=https://midominio.com
AIRFLOW_PATH=/airflow
```

> El archivo `.env` no se versiona (está en `.gitignore`). El repositorio incluye un `.env.example` con los valores de referencia: copiarlo con `cp .env.example .env` y ajustar los valores.

### 2. Configuración en `docker-compose.yaml`

En la sección común de entorno (`x-airflow-common` → `environment`):

```yaml
# URL pública con la que se accede a Airflow (en Airflow 3 está en [api], no en [webserver])
AIRFLOW__API__BASE_URL: '${AIRFLOW_PUBLIC_URL}${AIRFLOW_PATH}'

# La Execution API también queda montada bajo el subpath; si no se ajusta, las tareas fallan
AIRFLOW__CORE__EXECUTION_API_SERVER_URL: 'http://airflow-apiserver:8080${AIRFLOW_PATH}/execution/'
```

`AIRFLOW_PUBLIC_URL` solo afecta la URL base de la interfaz. `AIRFLOW_PATH` afecta tanto la interfaz como la Execution API, por eso se define una sola vez y ambas variables la reutilizan.

Se recomienda exponer el puerto del api-server solo en la interfaz local, para que el único acceso externo sea a través de Nginx:

```yaml
services:
  airflow-apiserver:
    ports:
      - "127.0.0.1:8080:8080"
```

### 3. Configuración de Nginx

Nginx **no** lee el archivo `.env`. El `location` debe coincidir manualmente con el valor de `AIRFLOW_PATH` (en este ejemplo, `/airflow`):

```nginx
server {
    server_name midominio.com;   # debe coincidir con AIRFLOW_PUBLIC_URL

    location /airflow/ {                    # debe coincidir con AIRFLOW_PATH
        proxy_pass http://127.0.0.1:8080;   # SIN barra final: conserva el prefijo del subpath
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Redirige el subpath sin barra final
    location = /airflow {
        return 301 /airflow/;
    }
}
```

**Importante:** `proxy_pass` no debe terminar en `/`. Con `http://127.0.0.1:8080/` Nginx eliminaría el prefijo del subpath antes de reenviar la petición, lo cual es incompatible con el `BASE_URL` configurado.

### 4. Aplicar los cambios

```bash
# Ver el compose con las variables ya sustituidas (validación previa)
docker compose config | grep -E "BASE_URL|EXECUTION_API"

# Recrear los contenedores para tomar las nuevas variables
docker compose up -d

# Validar y recargar Nginx
sudo nginx -t && sudo systemctl reload nginx
```

Luego abrir `${AIRFLOW_PUBLIC_URL}${AIRFLOW_PATH}/` en el navegador y ejecutar un DAG de prueba para confirmar que las tareas corren correctamente.

### Cambiar la URL pública

| Cambio | Qué actualizar |
|---|---|
| Solo el dominio | `AIRFLOW_PUBLIC_URL` en `.env`, y `server_name` y certificado TLS en Nginx |
| Solo el subpath | `AIRFLOW_PATH` en `.env`, y los dos bloques `location` en Nginx |
| Paso de HTTP a HTTPS | Esquema en `AIRFLOW_PUBLIC_URL` y configuración TLS en Nginx |

Después de cualquier cambio, repetir los pasos de la sección 4.

### Solución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| Página en blanco o 404 en recursos | Airflow no tomó `BASE_URL` | Revisar `.env`, validar con `docker compose config` y recrear contenedores |
| 404 en el subpath | `proxy_pass` con barra final, o `location` distinto de `AIRFLOW_PATH` | Quitar la `/` final de `proxy_pass` y alinear el `location` |
| La UI carga pero las tareas fallan | `EXECUTION_API_SERVER_URL` sin el subpath | Verificar que use `${AIRFLOW_PATH}/execution/` |
| Variables vacías en `docker compose config` | `.env` ausente o en otra carpeta | Ubicar `.env` junto a `docker-compose.yaml` |
| `:8080/` ya no responde en la raíz | Comportamiento esperado | Usar `:8080${AIRFLOW_PATH}/` o acceder por Nginx |

Para diagnosticar, revisar la pestaña **Red** de las herramientas de desarrollador del navegador (F12) y los logs del api-server:

```bash
docker compose logs -f airflow-apiserver
```

