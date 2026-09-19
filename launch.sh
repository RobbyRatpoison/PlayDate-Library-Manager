#!/usr/bin/env bash
# PlayDate — single entry point for Linux and macOS.
# Run this directly or pin it to your dock/taskbar.
# On first run (or when the venv is missing), setup runs automatically.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$DIR/.venv/bin/python"
OS="$(uname)"

# ── Register/update desktop integration (self-healing if folder moves) ─────────

if [ "$OS" = "Linux" ]; then
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/playdate.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PlayDate
Comment=Your personal Steam library manager
Exec=$DIR/launch.sh
Icon=$DIR/static/img/favicon.png
Terminal=false
Categories=Game;
StartupWMClass=playdate
EOF
    chmod +x "$DESKTOP_DIR/playdate.desktop"
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

elif [ "$OS" = "Darwin" ]; then
    APP="$HOME/Applications/PlayDate.app"
    mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
    cat > "$APP/Contents/MacOS/PlayDate" << EOF
#!/usr/bin/env bash
exec "$DIR/launch.sh"
EOF
    chmod +x "$APP/Contents/MacOS/PlayDate"
    if [ ! -f "$APP/Contents/Info.plist" ]; then
        cat > "$APP/Contents/Info.plist" << 'PLISTEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>CFBundleName</key>        <string>PlayDate</string>
    <key>CFBundleDisplayName</key> <string>PlayDate</string>
    <key>CFBundleIdentifier</key>  <string>com.playdate.app</string>
    <key>CFBundleVersion</key>     <string>1.0</string>
    <key>CFBundleExecutable</key>  <string>PlayDate</string>
    <key>CFBundlePackageType</key> <string>APPL</string>
    <key>CFBundleIconFile</key>    <string>favicon</string>
    <key>LSUIElement</key>         <false/>
</dict></plist>
PLISTEOF
    fi
    [ -f "$DIR/static/img/favicon.png" ] && \
        cp "$DIR/static/img/favicon.png" "$APP/Contents/Resources/favicon.png" 2>/dev/null || true
    mdimport "$APP" 2>/dev/null || true
fi

# ── macOS: find a Python that PlayDate can actually use ────────────────────────
# Apple's bundled python3 is too old, and on a fresh Mac just *running* it pops
# up a multi-GB Xcode Command Line Tools install. So on macOS we look for a
# suitable Python ourselves and, if there isn't one, explain what to install.
# (Linux is untouched: it needs the distro's python3 to match python3-gi.)

PLAYDATE_MIN_PY_MINOR=10   # keep in sync with requirements.txt

_py_ok() {  # $1 = python executable; needs >= 3.MIN, tkinter, venv, ensurepip
    [ -x "$1" ] || return 1
    "$1" - "$PLAYDATE_MIN_PY_MINOR" >/dev/null 2>&1 <<'PYCHECK'
import sys
if sys.version_info < (3, int(sys.argv[1])):
    sys.exit(1)
import tkinter, venv, ensurepip
PYCHECK
}

find_mac_python() {
    local v c
    local -a candidates=()
    for v in 3.14 3.13 3.12 3.11 3.10; do
        candidates+=(
            "/Library/Frameworks/Python.framework/Versions/$v/bin/python3"
            "/opt/homebrew/bin/python$v"
            "/usr/local/bin/python$v"
        )
        c="$(command -v "python$v" 2>/dev/null)" && candidates+=("$c")
    done
    c="$(command -v python3 2>/dev/null)" && candidates+=("$c")
    for c in "${candidates[@]}"; do
        # /usr/bin/python3 is Apple's stub: only safe to run once the Command
        # Line Tools are installed, otherwise it triggers the big download.
        if [ "$c" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then
            continue
        fi
        if _py_ok "$c"; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

mac_python_missing() {
    local msg="PlayDate needs Python 3.$PLAYDATE_MIN_PY_MINOR or newer, with tkinter included."
    if [ -t 1 ]; then
        echo "$msg"
        if command -v brew >/dev/null 2>&1; then
            printf "Install it now with Homebrew (python@3.12 + python-tk@3.12)? [y/N] "
            read -r reply
            if [ "$reply" = "y" ] || [ "$reply" = "Y" ]; then
                if brew install python@3.12 python-tk@3.12; then
                    return 0   # caller re-runs the search
                fi
                echo "The Homebrew install failed."
            fi
        fi
        echo "Download the macOS installer from https://www.python.org/downloads/macos/"
        echo "(it includes tkinter) and install it."
        command -v open >/dev/null 2>&1 && open "https://www.python.org/downloads/macos/"
        # Wait here so the user doesn't have to relaunch after installing.
        while true; do
            printf "Press Enter once it's installed to continue, or type q to quit: "
            read -r reply || return 1
            [ "$reply" = "q" ] || [ "$reply" = "Q" ] && return 1
            if [ -n "$(find_mac_python)" ]; then
                return 0   # caller re-runs the search
            fi
            echo "Still no suitable Python found (3.$PLAYDATE_MIN_PY_MINOR+ with tkinter)."
        done
    else
        # Launched from PlayDate.app / Finder: there is no terminal to print to.
        command -v osascript >/dev/null 2>&1 && osascript -e \
            "display dialog \"$msg Install it from python.org, then open PlayDate again.\" buttons {\"OK\"} with title \"PlayDate\"" \
            >/dev/null 2>&1
        command -v open >/dev/null 2>&1 && open "https://www.python.org/downloads/macos/"
    fi
    return 1
}

# ── Run setup if venv is missing ───────────────────────────────────────────────

if [ ! -f "$VENV_PYTHON" ]; then
    SETUP_PYTHON="python3"
    if [ "$OS" = "Darwin" ]; then
        SETUP_PYTHON="$(find_mac_python)"
        if [ -z "$SETUP_PYTHON" ]; then
            mac_python_missing && SETUP_PYTHON="$(find_mac_python)"
        fi
        if [ -z "$SETUP_PYTHON" ]; then
            echo "Setup cannot continue without a suitable Python. Re-run launch.sh after installing one."
            exit 1
        fi
    fi
    PLAYDATE_LAUNCH_PENDING=1 "$SETUP_PYTHON" "$DIR/install.py"
    if [ ! -f "$VENV_PYTHON" ]; then
        echo "Setup did not complete. Re-run launch.sh to try again."
        exit 1
    fi
fi

# ── Launch ─────────────────────────────────────────────────────────────────────

exec "$VENV_PYTHON" "$DIR/main.py" "$@"
