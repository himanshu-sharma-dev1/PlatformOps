#!/bin/bash
set -e

SERVICE_PATH=$(pwd)
REQUIREMENTS_FILE="$SERVICE_PATH/requirements.txt"

echo " Service path: $SERVICE_PATH"
echo " Looking for requirements at: $REQUIREMENTS_FILE"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "⚠No requirements.txt found in $SERVICE_PATH"
    exit 0
fi

echo " Checking requirements for service: $(basename "$SERVICE_PATH")"

echo " Checking currently installed packages..."
INSTALLED_PACKAGES=$(pip freeze | cut -d '=' -f 1)

echo " Comparing with $REQUIREMENTS_FILE..."

TO_INSTALL=$(grep -vE '^\s*#|^\s*--' "$REQUIREMENTS_FILE" | sed 's/#.*//' | while read line; do
    # Skip empty lines
    pkg=$(echo "$line" | awk -F'==' '{print $1}' | xargs)
    if [ -z "$pkg" ]; then
        continue
    fi
    if ! echo "$INSTALLED_PACKAGES" | grep -qx "$pkg"; then
        echo "$line"
    fi
done)

if [ -z "$TO_INSTALL" ]; then
    echo " All packages already installed. Nothing to install."
else
    echo "️ Installing missing packages:"
    echo "$TO_INSTALL"
    echo "$TO_INSTALL" | xargs pip install
fi

echo " Done."