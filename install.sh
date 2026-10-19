#!/usr/bin/env bash
# ==========================================================
# ai-tools Universal Installer & Dependency Checker
# ==========================================================
set -e

INSTALL_DIR="$HOME/.local/bin"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 ai-tools (v2.0) o'rnatilmoqda..."

mkdir -p "$INSTALL_DIR"
mkdir -p "$HOME/.local/state/agy-tool"

# 1. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Xatolik: Python 3 topilmadi! Iltimos, python3 o'rnating."
    exit 1
fi

# 2. Check & Install Python Dependencies
if [ -f "$SOURCE_DIR/requirements.txt" ]; then
    echo "📦 Python bog'liqliklarini tekshirish..."
    if command -v pip3 &> /dev/null; then
        pip3 install -q -r "$SOURCE_DIR/requirements.txt" 2>/dev/null || pip install -q -r "$SOURCE_DIR/requirements.txt" 2>/dev/null || echo "⚠️ Eslatma: pip orqali o'rnatishda xatolik bo'ldi. Qo'lda 'pip install -r requirements.txt' qiling."
    fi
fi

# 3. Create .env if not exists
if [ ! -f "$SOURCE_DIR/.env" ] && [ -f "$SOURCE_DIR/.env.example" ]; then
    cp "$SOURCE_DIR/.env.example" "$SOURCE_DIR/.env"
    echo "📄 .env shabloni nusxalandi ($SOURCE_DIR/.env)"
fi

# 4. Make CLI executables
chmod +x "$SOURCE_DIR/bin/agy-tool"
chmod +x "$SOURCE_DIR/bin/ai-tool" 2>/dev/null || true

# 5. Create launcher in ~/.local/bin
cat << LAUNCHER_EOF > "$INSTALL_DIR/ai-tool"
#!/usr/bin/env bash
TOOL_ENTRY="$SOURCE_DIR/bin/ai-tool"
if [ ! -f "\$TOOL_ENTRY" ]; then
  TOOL_ENTRY="$SOURCE_DIR/bin/agy-tool"
fi

if [ -f "\$TOOL_ENTRY" ]; then
  exec "\$TOOL_ENTRY" "\$@"
else
  echo "{\"success\": false, \"error\": \"ai-tool executable topilmadi: \$TOOL_ENTRY\"}" >&2
  exit 1
fi
LAUNCHER_EOF

chmod +x "$INSTALL_DIR/ai-tool"
ln -sf "$INSTALL_DIR/ai-tool" "$INSTALL_DIR/agy-tool"

# 6. Check System CLI Dependencies
echo ""
echo "🔍 Tizim yordamchi vositalari (External CLI Tools) tekshiruvi:"

check_tool() {
    local cmd=$1
    local pkg=$2
    local module=$3
    if command -v "$cmd" &> /dev/null; then
        echo "  ✅ $cmd: o'rnatilgan (Modul: $module)"
    else
        echo "  ⚠️  $cmd: topilmadi! (Kerakli modul: $module | O'rnatish: apt install $pkg)"
    fi
}

check_tool "ffmpeg" "ffmpeg" "media, super-media"
check_tool "ffprobe" "ffmpeg" "media, super-media"
check_tool "tesseract" "tesseract-ocr" "media (OCR)"
check_tool "rclone" "rclone" "drive (Google Drive 5TB)"
check_tool "sqlite3" "sqlite3" "db, secure"
check_tool "node" "nodejs" "debug, bot"

echo ""
echo "✅ O'rnatish muvaffaqiyatli yakunlandi!"
echo "📍 Buyruqlar: $INSTALL_DIR/ai-tool va $INSTALL_DIR/agy-tool"
echo "🧪 Tekshirish: ai-tool --describe"
