#!/bin/bash
set -eo pipefail

# Convert relative path to absolute based on current working directory
to_abs_path() {
    local p="$1"
    if [[ -n "$p" ]]; then
        readlink -m "$p"
    fi
}

# Capture user environment overrides before sourcing build_common
USER_DIST_DIR="$(to_abs_path "${DIST_DIR:-}")"
USER_SERVER_PATH="$(to_abs_path "${SERVER_PATH:-}")"
USER_OUTPUT_DIR="$(to_abs_path "${OUTPUT_DIR:-}")"
USER_VERSION="${VERSION:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$SCRIPT_DIR"
# Sourcing build_common provides WORK_DIR, OUTPUT_DIR, VERSION
. build_common
cd "$ROOT_DIR"

DIST_DIR="${USER_DIST_DIR:-$WORK_DIR/build-linux-x86_64/dist}"
SERVER_PATH="${USER_SERVER_PATH:-$WORK_DIR/build-server/server/scrcpy-server}"
OUTPUT_DIR="${USER_OUTPUT_DIR:-$OUTPUT_DIR}"
RAW_VERSION="${USER_VERSION:-$VERSION}"

# Check for required tools
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "ERROR: 'dpkg-deb' is required but not found in PATH." >&2
    exit 1
fi

# Validate required input files
missing_files=()
missing_server=false
missing_client=false

if [[ ! -f "$SERVER_PATH" ]]; then
    missing_files+=("$SERVER_PATH")
    missing_server=true
fi

if [[ ! -f "$DIST_DIR/scrcpy" ]]; then
    missing_files+=("$DIST_DIR/scrcpy")
    missing_client=true
fi

if [[ ! -f "$DIST_DIR/adb" ]]; then
    missing_files+=("$DIST_DIR/adb")
    missing_client=true
fi

if [[ ${#missing_files[@]} -gt 0 ]]; then
    echo "ERROR: Missing required input file(s):" >&2
    for f in "${missing_files[@]}"; do
        echo "  - $f" >&2
    done
    echo "" >&2
    echo "Please build the required components first:" >&2
    if [[ "$missing_server" = true ]]; then
        echo "  - Run 'release/build_server.sh' to build scrcpy-server" >&2
    fi
    if [[ "$missing_client" = true ]]; then
        echo "  - Run 'release/build_linux.sh x86_64' to build scrcpy and adb" >&2
    fi
    exit 1
fi

# Normalize version for Debian package (must start with digit, no underscores, valid chars)
if [[ -z "$RAW_VERSION" ]]; then
    RAW_VERSION="0.0.0"
fi
PKG_VERSION="${RAW_VERSION#[vV]}"
PKG_VERSION="${PKG_VERSION//_/.}"
PKG_VERSION="${PKG_VERSION//[^a-zA-Z0-9.+~-]/.}"
if [[ ! "$PKG_VERSION" =~ ^[0-9] ]]; then
    PKG_VERSION="0.0+${PKG_VERSION}"
fi

# Get maintainer from git config or fallback
GIT_NAME="$(git config user.name 2>/dev/null || true)"
GIT_EMAIL="$(git config user.email 2>/dev/null || true)"
if [[ -n "$GIT_NAME" && -n "$GIT_EMAIL" ]]; then
    MAINTAINER="$GIT_NAME <$GIT_EMAIL>"
elif [[ -n "$GIT_NAME" ]]; then
    MAINTAINER="$GIT_NAME <unknown@localhost>"
elif [[ -n "$GIT_EMAIL" ]]; then
    MAINTAINER="Scrcpy Maintainer <$GIT_EMAIL>"
else
    MAINTAINER="Scrcpy Maintainer <scrcpy@localhost>"
fi

# Prepare staging area
STAGE_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

# 1. /opt/scrcpy-gui/
OPT_DIR="$STAGE_DIR/opt/scrcpy-gui"
mkdir -p "$OPT_DIR"
cp -a "$DIST_DIR"/. "$OPT_DIR/"
cp "$SERVER_PATH" "$OPT_DIR/scrcpy-server"
cp -a "$ROOT_DIR/gui/scrcpy_gui" "$OPT_DIR/"
find "$OPT_DIR/scrcpy_gui" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$OPT_DIR/scrcpy_gui" -type f -name "*.pyc" -delete 2>/dev/null || true

# 2. /usr/bin wrappers
mkdir -p "$STAGE_DIR/usr/bin"
cat <<'EOF' > "$STAGE_DIR/usr/bin/scrcpy-gui"
#!/bin/sh
export SCRCPY_SERVER_PATH=/opt/scrcpy-gui/scrcpy-server
export SCRCPY_BIN=/opt/scrcpy-gui/scrcpy
export ADB=/opt/scrcpy-gui/adb
export PYTHONPATH=/opt/scrcpy-gui${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m scrcpy_gui "$@"
EOF

cat <<'EOF' > "$STAGE_DIR/usr/bin/scrcpy"
#!/bin/sh
export SCRCPY_SERVER_PATH=/opt/scrcpy-gui/scrcpy-server
export ADB=/opt/scrcpy-gui/adb
exec /opt/scrcpy-gui/scrcpy "$@"
EOF

# 3. .desktop file
mkdir -p "$STAGE_DIR/usr/share/applications"
cat <<'EOF' > "$STAGE_DIR/usr/share/applications/scrcpy-gui.desktop"
[Desktop Entry]
Type=Application
Name=Scrcpy GUI
Name[vi]=Hiển thị màn hình Android
Comment=Display and control Android devices
Comment[vi]=Hiển thị và điều khiển thiết bị Android
Exec=scrcpy-gui
Icon=scrcpy-gui
Terminal=false
Categories=Utility;
EOF

# 4. Icon
ICON_DEST="$STAGE_DIR/usr/share/icons/hicolor/256x256/apps/scrcpy-gui.png"
mkdir -p "$(dirname "$ICON_DEST")"
if [[ -f "$ROOT_DIR/app/data/scrcpy.png" ]]; then
    cp "$ROOT_DIR/app/data/scrcpy.png" "$ICON_DEST"
elif [[ -f "$DIST_DIR/scrcpy.png" ]]; then
    cp "$DIST_DIR/scrcpy.png" "$ICON_DEST"
else
    echo "ERROR: Icon file 'scrcpy.png' not found in '$ROOT_DIR/app/data' or '$DIST_DIR'." >&2
    exit 1
fi

# 5. DEBIAN/control
mkdir -p "$STAGE_DIR/DEBIAN"
cat <<EOF > "$STAGE_DIR/DEBIAN/control"
Package: scrcpy-gui
Version: $PKG_VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: $MAINTAINER
Depends: python3 (>= 3.10), python3-tk
Recommends: va-driver-all
Conflicts: scrcpy
Replaces: scrcpy
Description: GUI and statically linked scrcpy for Android screen mirroring
 Display and control Android devices connected via USB or Wi-Fi.
 Includes scrcpy client, scrcpy-server, adb, and graphical launcher.
EOF

# 6. Set file permissions:
# Directories: 0755
# Files: 0644
# Binaries and wrappers: 0755
find "$STAGE_DIR" -type d -exec chmod 0755 {} +
find "$STAGE_DIR" -type f -exec chmod 0644 {} +

chmod 0755 "$STAGE_DIR/usr/bin/scrcpy"
chmod 0755 "$STAGE_DIR/usr/bin/scrcpy-gui"
chmod 0755 "$OPT_DIR/scrcpy"
chmod 0755 "$OPT_DIR/adb"

# 7. Build deb package
mkdir -p "$OUTPUT_DIR"
DEB_NAME="scrcpy-gui_${PKG_VERSION}_amd64.deb"
DEB_PATH="$OUTPUT_DIR/$DEB_NAME"

rm -f "$DEB_PATH"
dpkg-deb --root-owner-group --build "$STAGE_DIR" "$DEB_PATH"

echo "Generated '$DEB_PATH'"
