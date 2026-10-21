# Despliegues de docker compose


La solución de despliegue de Apache Airflow mediante Docker se encuentra disponible en dos variantes, diseñadas para atender diferentes necesidades de procesamiento. La primera variante incorpora **Java 21** y está orientada a la ejecución de procesos que utilizan **ili2db** para la lectura, transformación, validación y gestión de modelos y datos **INTERLIS**. La segunda variante incorpora un entorno de **QGIS** junto con las dependencias necesarias para ejecutar algoritmos de **QGIS Processing** y **GRASS GIS**, y se encuentra optimizada para realizar operaciones de geoprocesamiento de bajo nivel directamente desde los DAG de Airflow. Ambas variantes mantienen la misma arquitectura base de Airflow, diferenciándose principalmente por las herramientas y dependencias adicionales incluidas para soportar cada tipo de flujo de procesamiento.

Si solo requeremos Airflow con soporte de java 21 pudemos usar [Dockerfile](Dockerfile)
Si deseamos que Airflow soporte QGIS, GRASS y GDAL debemos usar [Dockerfile.airflow-qgis-grass](Dockerfile.airflow-qgis-grass)

### Reconstruir la imagen de QGIS - Airflow - Java - GDAL - GRASS

```
docker build \
  --no-cache \
  --platform=linux/amd64 \
  -f Dockerfile.airflow-qgis-grass \
  -t airflow-qgis:3.3.0-qgis3.44-grass-java21 \
  .
```

### Validar la nueva imagen

```
docker run --rm \
  --platform=linux/amd64 \
  airflow-qgis:3.3.0-qgis3.44-grass-java21 \
  bash -lc '
    set -eux

    echo "=== GRASS ==="
    grass --version

    echo "=== Plugin ==="
    qgis_process plugins

    echo "=== Algoritmo ==="
    qgis_process help grass:v.clean

    echo "=== Identificador ==="
    qgis_process list | grep -F "grass:v.clean"
  '
```