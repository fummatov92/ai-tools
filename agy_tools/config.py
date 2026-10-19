import os
from pathlib import Path

# ============================================================================
# CENTRALIZED CONFIG SERVICE (NestJS ConfigService Pattern in Python)
# ============================================================================

class ConfigService:
    """
    Centralized Configuration & Secrets Manager
    - Single Source of Truth: barcha muhit o'zgaruvchilari va sirlar faqat shu yerda jamlanadi.
    - Zero Hardcoding: kod ichida har qanday bot token, parol yoki shaxsiy IDlarni hardcode qilish qat'iyan taqiqlangan.
    - Strict Validation: zarur parametrlar (.env) mavjud bo'lmasa, soxta fallback bermasdan aniq xatolik qaytaradi.
    """
    def __init__(self):
        self._env = {}
        self._load_all_dotenvs()

    def _load_dotenv_file(self, filepath):
        p = Path(filepath).resolve()
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in self._env:
                                self._env[k] = v
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

    def _load_all_dotenvs(self):
        # 1. Custom env file ko'rsatilgan bo'lsa
        custom = os.getenv("AGY_ENV_FILE")
        if custom:
            self._load_dotenv_file(custom)

        # 2. Standart izlash yo'llari (cwd, repo root, .config/ai-tools, home)
        standard_paths = [
            Path.cwd() / ".env",
            Path(__file__).resolve().parent.parent / ".env",
            Path.home() / ".config" / "ai-tools" / ".env",
            Path.home() / ".env"
        ]
        for p in standard_paths:
            self._load_dotenv_file(p)

    def get(self, key, default=None):
        return os.getenv(key, self._env.get(key, default))

    def get_required(self, key):
        val = self.get(key)
        if val is None or val == "":
            raise ValueError(f"CRITICAL CONFIG ERROR: Majburiy muhit o'zgaruvchisi '{key}' .env faylida topilmadi!")
        return val

    def get_int(self, key, default=0):
        val = self.get(key)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_bot_token(self):
        """Telegram Bot Tokenini olish (Zero-Hardcode)."""
        return self.get_required("BOT_TOKEN")

    def get_default_chat_id(self, explicit_id=None):
        """Telegram Chat ID sini xavfsiz aniqlash (Hardcode taqiqlangan)."""
        if explicit_id:
            return str(explicit_id).strip()
        chat_id = self.get("DEFAULT_CHAT_ID")
        if not chat_id:
            allowed = self.get("ALLOWED_USER_IDS", "")
            if allowed:
                chat_id = allowed.split(",")[0].strip()
        if not chat_id:
            raise ValueError("CRITICAL CONFIG ERROR: 'DEFAULT_CHAT_ID' yoki 'ALLOWED_USER_IDS' .env faylida topilmadi!")
        return str(chat_id)


# Global Singleton Instance
config = ConfigService()


# ============================================================================
# AGY-TOOL GLOBAL CONFIGURATION VARIABLES (Derived from ConfigService)
# ============================================================================

HOME_DIR = config.get("HOME", os.path.expanduser("~"))

# 1. Path Jailing & Security
_raw_allowed = config.get("AGY_ALLOWED_DIRS", "")
if _raw_allowed:
    ALLOWED_DIRS = [os.path.realpath(os.path.expanduser(p.strip())) for p in _raw_allowed.split(",") if p.strip()]
else:
    ALLOWED_DIRS = [
        os.path.realpath(os.path.join(HOME_DIR, "Desktop")),
        os.path.realpath(os.path.join(HOME_DIR, ".local")),
        os.path.realpath(os.path.join(HOME_DIR, ".gemini")),
        os.path.realpath(os.path.join(HOME_DIR, "Downloads")),
    ]

# 2. Port Scanner Boundaries (sys module)
PORT_RANGE_START = config.get_int("AGY_PORT_RANGE_START", 15800)
PORT_RANGE_END = config.get_int("AGY_PORT_RANGE_END", 15900)

# 3. Logging & Auditing
LOG_DIR = os.path.realpath(os.path.expanduser(config.get("AGY_LOG_DIR", os.path.join(HOME_DIR, ".local/state/agy-tool"))))
MAX_LOG_SIZE_MB = config.get_int("AGY_MAX_LOG_SIZE_MB", 5)

# 4. Media & Multimodal Artifacts
TEMP_MEDIA_DIR = os.path.realpath(os.path.expanduser(config.get("AGY_TEMP_MEDIA_DIR", os.path.join(HOME_DIR, "Desktop/temp/media_artifacts"))))
TEMP_SUPER_MEDIA_DIR = os.path.realpath(os.path.expanduser(config.get("AGY_TEMP_SUPER_MEDIA_DIR", os.path.join(HOME_DIR, "Desktop/temp/super_media_artifacts"))))


# 6. Session Management
BRAIN_DIR = os.path.realpath(os.path.expanduser(config.get("AGY_BRAIN_DIR", os.path.join(HOME_DIR, ".gemini/antigravity-cli/brain"))))

# 7. Safe Probing Sandbox (doc module)
DEV_DB_SANDBOX_DIR = os.path.realpath(os.path.expanduser(config.get("AGY_DEV_DB_SANDBOX_DIR", os.path.join(HOME_DIR, "Desktop/temp/sandbox_db"))))
PROBE_SAFE_TABLES = [t.strip().lower() for t in config.get("AGY_PROBE_SAFE_TABLES", "branches,categories,roles,regions,districts,cities,tags,currencies,tariffs,status_types").split(",") if t.strip()]
API_IGNORE_PATTERNS = [p.strip().lower() for p in config.get("AGY_API_IGNORE_PATTERNS", "*payme*,*click*,*uzum*,*billing*,*webhook*,*sms*,*auth/login*,*checkout*").split(",") if p.strip()]
