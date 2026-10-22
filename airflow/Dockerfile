# Apache Airflow 3.3.0
FROM apache/airflow:3.3.0

# ---------------------------------------------------------------------
# Dependencias del sistema
# ---------------------------------------------------------------------
USER root

# Agregamos el repositorio oficial de Eclipse Adoptium
# e instalamos Temurin JRE 21 junto con GDAL.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        gpg \
        wget \
    && wget --max-redirect=0 -qO- \
        https://packages.adoptium.net/artifactory/api/gpg/key/public \
        | gpg --dearmor --batch --yes \
        -o /usr/share/keyrings/adoptium.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] \
        https://packages.adoptium.net/artifactory/deb \
        $(. /etc/os-release && echo "${VERSION_CODENAME}") main" \
        > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        python3-gdal \
        temurin-21-jre \
    && JAVA_REAL_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" \
    && ln -s "${JAVA_REAL_HOME}" /opt/java-21 \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Ruta estable, independiente de amd64 o arm64
ENV JAVA_HOME=/opt/java-21
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Verificamos Java durante la construcción
RUN java -version

# ---------------------------------------------------------------------
# Dependencias Python
# ---------------------------------------------------------------------
USER airflow

COPY requirements.txt /tmp/requirements.txt

# Fijamos la versión de Airflow para evitar que una dependencia
# actualice o degrade accidentalmente Apache Airflow.
# Se usa el pip de la imagen base (sin --upgrade pip, que no es reproducible),
# solo wheels (sin ejecutar scripts de setup) y el archivo de constraints
# de la imagen para fijar las versiones resueltas.
RUN pip install --no-cache-dir --only-binary :all: \
        "apache-airflow==${AIRFLOW_VERSION}" \
        -r /tmp/requirements.txt \
        --constraint "${HOME}/constraints.txt"

# ---------------------------------------------------------------------
# Código de la aplicación
# ---------------------------------------------------------------------
WORKDIR /app

COPY --chown=airflow:root dags/ /app/dags/
COPY --chown=airflow:root utils/ /app/utils/
