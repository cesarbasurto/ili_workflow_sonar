#!/usr/bin/env bash
# =============================================================================
# update_submodules.sh
#
# Sincroniza los ETL registrados como submódulos Git en airflow/submodules con
# la lista SUBMODULOS:
#
#   - ETL nuevo en la lista      -> se registra, se descarga y se enlaza.
#   - ETL que ya está registrado -> se actualiza a la última versión de su rama
#                                   y se vuelven a validar sus enlaces.
#   - ETL retirado de la lista   -> se desregistra: se eliminan el submódulo,
#                                   su entrada en .gitmodules, su repositorio
#                                   en .git/modules y sus enlaces en Airflow.
#                                   La carpeta output/<etl> se conserva.
#
# Un ETL con cambios locales o commits sin publicar no se actualiza ni se
# desregistra, para no perder esos cambios.
#
# Uso:
#   bash update_submodules.sh                  Sincroniza todos los ETL.
#   bash update_submodules.sh <nombre> [...]   Actualiza solo los ETL indicados
#                                              (no desregistra ningún ETL).
# =============================================================================
set -Eeuo pipefail
IFS=$'\n\t'

# Formato: nombre|URL|rama
SUBMODULOS=(
)

# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
log() {
    local nivel="$1"
    shift

    if [[ "$nivel" == "WARN" || "$nivel" == "ERROR" ]]; then
        printf '[%s] %s\n' "$nivel" "$*" >&2
    else
        printf '[%s] %s\n' "$nivel" "$*"
    fi
}

fallar() {
    local mensaje="$1"

    log "ERROR" "$mensaje"
    exit 1
}

trap 'log "ERROR" "Falló el comando en la línea $LINENO: $BASH_COMMAND"' ERR
trap 'codigo_salida=$?; if [[ "$codigo_salida" -ne 0 ]]; then log "ERROR" "Proceso finalizado con errores (código $codigo_salida)."; fi' EXIT

es_submodulo_inicializado() {
    local ruta_submodulo="$1"

    [[ -e "$ruta_submodulo/.git" ]]
}

tiene_cambios_locales() {
    local ruta_submodulo="$1"

    ! git -C "$ruta_submodulo" diff --quiet || \
        ! git -C "$ruta_submodulo" diff --cached --quiet
}

tiene_commits_sin_publicar() {
    local ruta_submodulo="$1"
    local commits

    commits="$(git -C "$ruta_submodulo" log --branches --not --remotes --oneline -1 2>/dev/null || true)"
    [[ -n "$commits" ]]
}

# Devuelve el nombre con el que el submódulo está registrado en .gitmodules.
nombre_modulo_por_ruta() {
    local ruta_buscada="$1"
    local clave
    local ruta

    [[ -f "$ARCHIVO_GITMODULES" ]] || return 1

    while IFS=' ' read -r clave ruta; do
        if [[ "$ruta" == "$ruta_buscada" ]]; then
            clave="${clave#submodule.}"
            printf '%s\n' "${clave%.path}"
            return 0
        fi
    done < <(git config --file "$ARCHIVO_GITMODULES" --get-regexp '^submodule\..*\.path$' 2>/dev/null || true)

    return 1
}

# Registra en el índice de Git los cambios de .gitmodules.
registrar_gitmodules() {
    if [[ -f "$ARCHIVO_GITMODULES" ]]; then
        git add --force -- "$ARCHIVO_GITMODULES"
    fi
}

esta_en_lista() {
    local buscado="$1"
    shift
    local elemento

    for elemento in "$@"; do
        [[ "$elemento" == "$buscado" ]] && return 0
    done

    return 1
}

# Elimina los enlaces de Airflow que apuntan al submódulo indicado.
eliminar_enlaces_submodulo() {
    local nombre_submodulo="$1"
    local directorio
    local enlace
    local destino

    shopt -s nullglob
    for directorio in "${DIRECTORIOS_ENLACES[@]}"; do
        for enlace in "$directorio"/*; do
            [[ -L "$enlace" ]] || continue
            destino="$(readlink "$enlace")"

            if [[ "$destino" == *"submodules/$nombre_submodulo/"* ]]; then
                rm -f -- "$enlace"
                log "INFO" "Enlace eliminado: ${enlace#"$DIRECTORIO_AIRFLOW"/}"

                if [[ "$directorio" == "$DIRECTORIO_AIRFLOW/dags" && -d "$DIRECTORIO_AIRFLOW/output/${enlace##*/}" ]]; then
                    log "INFO" "Se conserva la carpeta de salida: output/${enlace##*/}"
                fi
            fi
        done
    done
    shopt -u nullglob
}

# Elimina enlaces hacia submódulos que ya no existen (enlaces rotos).
limpiar_enlaces_rotos() {
    local directorio
    local enlace
    local destino

    shopt -s nullglob
    for directorio in "${DIRECTORIOS_ENLACES[@]}"; do
        for enlace in "$directorio"/*; do
            [[ -L "$enlace" && ! -e "$enlace" ]] || continue
            destino="$(readlink "$enlace")"

            if [[ "$destino" == *"submodules/"* ]]; then
                rm -f -- "$enlace"
                log "INFO" "Enlace roto eliminado: ${enlace#"$DIRECTORIO_AIRFLOW"/} -> $destino"
            fi
        done
    done
    shopt -u nullglob
}

# -----------------------------------------------------------------------------
# Desregistro de un submódulo
# -----------------------------------------------------------------------------
desregistrar_submodulo() {
    local nombre_modulo="$1"
    local ruta_relativa="$2"
    local ruta_absoluta="$RAIZ_REPOSITORIO/$ruta_relativa"
    local nombre_submodulo="${ruta_relativa##*/}"

    log "INFO" "Desregistrando submódulo retirado de la lista: $nombre_submodulo"

    if es_submodulo_inicializado "$ruta_absoluta"; then
        if tiene_cambios_locales "$ruta_absoluta"; then
            log "WARN" "El submódulo '$nombre_submodulo' tiene cambios locales sin confirmar. No se desregistra para conservarlos."
            TOTAL_OMITIDOS=$((TOTAL_OMITIDOS + 1))
            return 0
        fi

        if tiene_commits_sin_publicar "$ruta_absoluta"; then
            log "WARN" "El submódulo '$nombre_submodulo' tiene commits que no están en el repositorio remoto. No se desregistra para conservarlos."
            TOTAL_OMITIDOS=$((TOTAL_OMITIDOS + 1))
            return 0
        fi
    fi

    if git ls-files --error-unmatch -- "$ruta_relativa" >/dev/null 2>&1; then
        # git rm exige que .gitmodules no tenga cambios sin registrar en el índice.
        registrar_gitmodules
        git submodule deinit --quiet --force -- "$ruta_relativa"
        git rm --quiet --force -- "$ruta_relativa"
    else
        git config --file "$ARCHIVO_GITMODULES" --remove-section "submodule.$nombre_modulo" 2>/dev/null || true
        git config --remove-section "submodule.$nombre_modulo" 2>/dev/null || true
        rm -rf -- "$ruta_absoluta"
    fi

    if [[ -d "$DIRECTORIO_GIT/modules/$nombre_modulo" ]]; then
        rm -rf -- "${DIRECTORIO_GIT:?}/modules/$nombre_modulo"
    fi

    if [[ -d "$ruta_absoluta" ]]; then
        rmdir -- "$ruta_absoluta" 2>/dev/null || true
    fi

    eliminar_enlaces_submodulo "$nombre_submodulo"

    TOTAL_DESREGISTRADOS=$((TOTAL_DESREGISTRADOS + 1))
    log "OK" "Submódulo '$nombre_submodulo' desregistrado correctamente."
}

# -----------------------------------------------------------------------------
# Registro y actualización de un submódulo
# -----------------------------------------------------------------------------
procesar_submodulo() {
    local nombre_submodulo="$1"
    local url_submodulo="$2"
    local rama_submodulo="$3"
    local ruta_relativa="$DIRECTORIO_SUBMODULOS_RELATIVO/$nombre_submodulo"
    local ruta_absoluta="$RAIZ_REPOSITORIO/$ruta_relativa"
    local script_configuracion="$ruta_absoluta/configure.sh"
    local nombre_modulo=""
    local url_actual=""
    local rama_registrada=""
    local commit_anterior=""
    local commit_nuevo=""
    local actualizacion_omitida="false"

    log "INFO" "Procesando submódulo: $nombre_submodulo"
    log "INFO" "Ruta: $ruta_relativa"
    log "INFO" "Repositorio: $url_submodulo"
    log "INFO" "Rama esperada: $rama_submodulo"

    if nombre_modulo="$(nombre_modulo_por_ruta "$ruta_relativa")"; then
        log "INFO" "La entrada del submódulo ya está registrada en .gitmodules."

        url_actual="$(git config --file "$ARCHIVO_GITMODULES" --get "submodule.$nombre_modulo.url" 2>/dev/null || true)"
        if [[ "$url_actual" != "$url_submodulo" ]]; then
            log "INFO" "Actualizando la URL registrada del submódulo."
            git config --file "$ARCHIVO_GITMODULES" "submodule.$nombre_modulo.url" "$url_submodulo"
        fi

        rama_registrada="$(git config --file "$ARCHIVO_GITMODULES" --get "submodule.$nombre_modulo.branch" 2>/dev/null || true)"
        if [[ "$rama_registrada" != "$rama_submodulo" ]]; then
            log "INFO" "Actualizando la rama registrada a '$rama_submodulo'."
            git config --file "$ARCHIVO_GITMODULES" "submodule.$nombre_modulo.branch" "$rama_submodulo"
        fi

        registrar_gitmodules
        git submodule sync --quiet -- "$ruta_relativa"
    else
        if [[ -d "$ruta_absoluta" ]] && ! es_submodulo_inicializado "$ruta_absoluta" && \
            [[ -n "$(ls -A "$ruta_absoluta" 2>/dev/null)" ]]; then
            fallar "La ruta '$ruta_relativa' existe y no es un submódulo. Muévala o elimínela y repita el proceso."
        fi

        log "INFO" "Registrando y descargando el submódulo."
        git submodule add --force -b "$rama_submodulo" "$url_submodulo" "$ruta_relativa"
        TOTAL_REGISTRADOS=$((TOTAL_REGISTRADOS + 1))
    fi

    if ! es_submodulo_inicializado "$ruta_absoluta"; then
        log "INFO" "Inicializando el submódulo."
        if ! git submodule update --init --recursive -- "$ruta_relativa"; then
            es_submodulo_inicializado "$ruta_absoluta" || \
                fallar "No fue posible descargar el submódulo '$nombre_submodulo'. Verifique la URL y el acceso al repositorio."

            log "WARN" "No fue posible obtener el commit registrado; se descarga la última versión de '$rama_submodulo'."
            git -C "$ruta_absoluta" fetch --quiet origin \
                "+refs/heads/$rama_submodulo:refs/remotes/origin/$rama_submodulo"
            git -C "$ruta_absoluta" checkout --quiet --force -B "$rama_submodulo" "origin/$rama_submodulo"
        fi
    fi

    commit_anterior="$(git -C "$ruta_absoluta" rev-parse --short HEAD)"

    log "INFO" "Descargando cambios de origin/$rama_submodulo."
    git -C "$ruta_absoluta" fetch --quiet origin \
        "+refs/heads/$rama_submodulo:refs/remotes/origin/$rama_submodulo"

    if tiene_cambios_locales "$ruta_absoluta"; then
        log "WARN" "El submódulo tiene cambios locales sin confirmar. Se omite la actualización para conservarlos."
        actualizacion_omitida="true"
        TOTAL_OMITIDOS=$((TOTAL_OMITIDOS + 1))
    elif tiene_commits_sin_publicar "$ruta_absoluta"; then
        log "WARN" "El submódulo tiene commits que no están en el repositorio remoto. Se omite la actualización para conservarlos."
        actualizacion_omitida="true"
        TOTAL_OMITIDOS=$((TOTAL_OMITIDOS + 1))
    else
        git -C "$ruta_absoluta" checkout --quiet -B "$rama_submodulo" "origin/$rama_submodulo"
        git -C "$ruta_absoluta" branch --quiet --set-upstream-to="origin/$rama_submodulo" "$rama_submodulo"
        git -C "$ruta_absoluta" submodule update --init --recursive --quiet

        commit_nuevo="$(git -C "$ruta_absoluta" rev-parse --short HEAD)"

        if [[ "$commit_anterior" == "$commit_nuevo" ]]; then
            log "INFO" "Sin cambios: el submódulo está en la última versión de '$rama_submodulo' ($commit_nuevo)."
        else
            log "INFO" "Submódulo actualizado de $commit_anterior a $commit_nuevo."
            TOTAL_ACTUALIZADOS=$((TOTAL_ACTUALIZADOS + 1))
        fi

        # Registra en el orquestador el commit desplegado del submódulo.
        git add -- "$ruta_relativa"
    fi

    [[ -f "$script_configuracion" ]] || \
        fallar "No se encontró el archivo configure.sh en '$ruta_relativa'."

    log "INFO" "Creando los enlaces de Airflow mediante configure.sh."
    AIRFLOW_ROOT="$DIRECTORIO_AIRFLOW" bash "$script_configuracion"

    if [[ "$actualizacion_omitida" == "true" ]]; then
        log "WARN" "Submódulo '$nombre_submodulo' enlazado, pero sin actualizar."
    else
        log "OK" "Submódulo '$nombre_submodulo' actualizado y enlazado correctamente."
    fi
}

# -----------------------------------------------------------------------------
# Validaciones
# -----------------------------------------------------------------------------
log "INFO" "Iniciando sincronización de submódulos..."

command -v git >/dev/null 2>&1 || fallar "El comando 'git' no está disponible."
command -v bash >/dev/null 2>&1 || fallar "El comando 'bash' no está disponible."

DIRECTORIO_SCRIPT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if ! RAIZ_REPOSITORIO="$(git -C "$DIRECTORIO_SCRIPT" rev-parse --show-toplevel 2>/dev/null)"; then
    fallar "No fue posible determinar la raíz del repositorio Git."
fi

DIRECTORIO_GIT="$(git -C "$RAIZ_REPOSITORIO" rev-parse --absolute-git-dir)"
DIRECTORIO_AIRFLOW="$RAIZ_REPOSITORIO/airflow"
DIRECTORIO_SUBMODULOS_RELATIVO="airflow/submodules"
DIRECTORIO_SUBMODULOS="$RAIZ_REPOSITORIO/$DIRECTORIO_SUBMODULOS_RELATIVO"
ARCHIVO_GITMODULES="$RAIZ_REPOSITORIO/.gitmodules"
DIRECTORIOS_ENLACES=(
    "$DIRECTORIO_AIRFLOW/dags"
    "$DIRECTORIO_AIRFLOW/logic"
    "$DIRECTORIO_AIRFLOW/config/etl_config"
)

[[ -d "$DIRECTORIO_AIRFLOW" ]] || fallar "No existe el directorio '$DIRECTORIO_AIRFLOW'."
mkdir -p "$DIRECTORIO_SUBMODULOS"
cd "$RAIZ_REPOSITORIO"

NOMBRES=()
URLS=()
RAMAS=()

for registro_submodulo in ${SUBMODULOS[@]+"${SUBMODULOS[@]}"}; do
    IFS='|' read -r nombre_submodulo url_submodulo rama_submodulo <<< "$registro_submodulo"

    [[ -n "$nombre_submodulo" && -n "$url_submodulo" && -n "$rama_submodulo" ]] || \
        fallar "La definición de submódulo no es válida: '$registro_submodulo'."

    [[ "$nombre_submodulo" != */* ]] || \
        fallar "El nombre del submódulo no puede contener '/': '$nombre_submodulo'."

    if esta_en_lista "$nombre_submodulo" ${NOMBRES[@]+"${NOMBRES[@]}"}; then
        fallar "El submódulo '$nombre_submodulo' está repetido en SUBMODULOS."
    fi

    NOMBRES+=("$nombre_submodulo")
    URLS+=("$url_submodulo")
    RAMAS+=("$rama_submodulo")
done

FILTRO=("$@")
for nombre_filtro in ${FILTRO[@]+"${FILTRO[@]}"}; do
    esta_en_lista "$nombre_filtro" ${NOMBRES[@]+"${NOMBRES[@]}"} || \
        fallar "El submódulo '$nombre_filtro' no está definido en SUBMODULOS."
done

TOTAL_REGISTRADOS=0
TOTAL_ACTUALIZADOS=0
TOTAL_DESREGISTRADOS=0
TOTAL_OMITIDOS=0

log "INFO" "Validaciones completadas correctamente."
log "INFO" "Raíz del repositorio: $RAIZ_REPOSITORIO"
log "INFO" "Directorio de submódulos: $DIRECTORIO_SUBMODULOS"
log "INFO" "Submódulos definidos en SUBMODULOS: ${#NOMBRES[@]}"

# -----------------------------------------------------------------------------
# 1. Desregistro de los submódulos retirados de SUBMODULOS
# -----------------------------------------------------------------------------
if [[ "${#FILTRO[@]}" -eq 0 ]]; then
    RETIRADOS_NOMBRE_MODULO=()
    RETIRADOS_RUTA=()

    if [[ -f "$ARCHIVO_GITMODULES" ]]; then
        while IFS=' ' read -r clave_modulo ruta_modulo; do
            [[ "$ruta_modulo" == "$DIRECTORIO_SUBMODULOS_RELATIVO/"* ]] || continue

            if ! esta_en_lista "${ruta_modulo##*/}" ${NOMBRES[@]+"${NOMBRES[@]}"}; then
                clave_modulo="${clave_modulo#submodule.}"
                RETIRADOS_NOMBRE_MODULO+=("${clave_modulo%.path}")
                RETIRADOS_RUTA+=("$ruta_modulo")
            fi
        done < <(git config --file "$ARCHIVO_GITMODULES" --get-regexp '^submodule\..*\.path$' 2>/dev/null || true)
    fi

    if [[ "${#RETIRADOS_RUTA[@]}" -gt 0 ]]; then
        log "WARN" "Submódulos registrados que ya no están en SUBMODULOS: ${#RETIRADOS_RUTA[@]}"

        for indice in "${!RETIRADOS_RUTA[@]}"; do
            desregistrar_submodulo "${RETIRADOS_NOMBRE_MODULO[$indice]}" "${RETIRADOS_RUTA[$indice]}"
        done
    fi
else
    log "INFO" "Se procesarán solo los submódulos indicados; no se desregistrará ningún submódulo."
fi

# -----------------------------------------------------------------------------
# 2. Registro y actualización de los submódulos de SUBMODULOS
# -----------------------------------------------------------------------------
for indice in ${NOMBRES[@]+"${!NOMBRES[@]}"}; do
    if [[ "${#FILTRO[@]}" -gt 0 ]] && ! esta_en_lista "${NOMBRES[$indice]}" "${FILTRO[@]}"; then
        continue
    fi

    procesar_submodulo "${NOMBRES[$indice]}" "${URLS[$indice]}" "${RAMAS[$indice]}"
done

# -----------------------------------------------------------------------------
# 3. Limpieza de enlaces rotos y resumen
# -----------------------------------------------------------------------------
limpiar_enlaces_rotos

log "INFO" "Resumen: registrados=$TOTAL_REGISTRADOS, actualizados=$TOTAL_ACTUALIZADOS, desregistrados=$TOTAL_DESREGISTRADOS, omitidos=$TOTAL_OMITIDOS."

if [[ "$TOTAL_OMITIDOS" -gt 0 ]]; then
    log "WARN" "Hay submódulos omitidos por cambios locales o commits sin publicar; revise los mensajes WARN anteriores."
fi

if [[ "$TOTAL_REGISTRADOS" -gt 0 || "$TOTAL_ACTUALIZADOS" -gt 0 || "$TOTAL_DESREGISTRADOS" -gt 0 ]]; then
    log "INFO" "Los cambios de submódulos quedaron en el índice de Git del orquestador (git status)."
fi

log "OK" "Proceso finalizado correctamente."
