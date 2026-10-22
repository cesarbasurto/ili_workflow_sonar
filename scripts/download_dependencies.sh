#!/bin/bash

# Note: the version of ili2db and ilivalidator must be the same as the one used in the source code
# airflow/config/enums.py


LEGACY_ILI2DB_VERSION="4.4.3"
ILI2DB_VERSION="5.5.2"

# Target directory
ILI2DB_DEST_DIR="airflow/libs/iliwrapper/bin"

# Elimina las librerías existentes para hacer una descarga limpia
rm -rf "$ILI2DB_DEST_DIR/*"

# Create the target directory if it doesn't exist
mkdir -p "$ILI2DB_DEST_DIR"

# Download legacy ili2pg
echo "Downloading legacy ili2pg..."
wget --https-only https://downloads.interlis.ch/ili2pg/ili2pg-${LEGACY_ILI2DB_VERSION}.zip -P "$ILI2DB_DEST_DIR"

# Download ili2pg
echo "Downloading ili2pg..."
wget --https-only https://downloads.interlis.ch/ili2pg/ili2pg-${ILI2DB_VERSION}.zip -P "$ILI2DB_DEST_DIR"


# Unzip files into the target directory
echo "Unzipping files..."
unzip -o "$ILI2DB_DEST_DIR/ili2pg-${LEGACY_ILI2DB_VERSION}.zip" -d "$ILI2DB_DEST_DIR/ili2pg-${LEGACY_ILI2DB_VERSION}"
unzip -o "$ILI2DB_DEST_DIR/ili2pg-${ILI2DB_VERSION}.zip" -d "$ILI2DB_DEST_DIR/ili2pg-${ILI2DB_VERSION}"

# Clean up downloaded ZIP files
echo "Cleaning up downloaded files..."
rm "$ILI2DB_DEST_DIR/ili2pg-${LEGACY_ILI2DB_VERSION}.zip"
rm "$ILI2DB_DEST_DIR/ili2pg-${ILI2DB_VERSION}.zip"

echo "Process completed."