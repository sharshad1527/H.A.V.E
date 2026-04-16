#!/bin/bash

echo "========================================================"
echo "       H.A.V.E. Pro Editor - Linux Installer"
echo "========================================================"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH. Please install Python 3.10+"
    exit 1
fi

# Create Virtual Environment
echo "[1/4] Creating Python Virtual Environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate venv and install requirements
echo "[2/4] Activating venv and installing requirements..."
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Create Desktop Shortcut
echo "[3/4] Creating .desktop file..."

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${APP_DIR}/venv/bin/python"
DESKTOP_FILE="have_pro_editor.desktop"

# Attempt to convert svg to png for the desktop icon
# Although many linux environments support svg directly in .desktop files,
# providing a fallback PNG if conversion is possible can be helpful.
ICON_PATH="${APP_DIR}/icons/HAVE_Pro_Logo.svg"
if [ -f "$ICON_PATH" ]; then
    # We can try to use PySide6 to convert if we want, but .desktop natively supports svg
    echo "Icon found."
else
    echo "[WARNING] icons/HAVE_Pro_Logo.svg not found."
    ICON_PATH=""
fi

cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=HAVE Pro Editor
Comment=H.A.V.E. Pro Editor
StartupWMClass=HAVE Pro Editor
Exec=${VENV_PYTHON} ${APP_DIR}/main_gui.py
Icon=${ICON_PATH}
Path=${APP_DIR}
Terminal=false
Categories=AudioVideo;Video;
EOF

echo "[4/4] Installing Desktop Shortcut..."

# Install to ~/.local/share/applications/
mkdir -p "$HOME/.local/share/applications"
cp "$DESKTOP_FILE" "$HOME/.local/share/applications/"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null

# Copy to Desktop if it exists
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_DIR/"
    chmod +x "$DESKTOP_DIR/$DESKTOP_FILE"
fi

rm "$DESKTOP_FILE"

echo "========================================================"
echo "Installation Complete!"
echo "You can now launch 'HAVE Pro Editor' from your application menu or Desktop."
echo "========================================================"
