import os
import sys
import re
import json
import sqlite3
import subprocess
import math
from typing import List, Dict, Any, Tuple
from agy_tools.utils import emit_progress, emit_result, safe_jail_path

def get_secure_describe():
    return {
        "name": "secure",
        "description": "Maxfiy ma'lumotlarni tozalash. scan=faqat hisobot, redact=tahrirlash. (.env dinamik flaglar va 60% maskalash bilan)",
        "commands": {
            "scan": "[DRY-RUN] Tahlil qilib scanning_docs/reports/ ga hisobot yozadi (sirlar 60% maskalangan ko'rinishda). Hech narsa o'zgartirilmaydi.",
            "redact": "[EXECUTE] Sirlarni o'zgartiradi va scanning_docs/backups/ ga zaxira yaratadi."
        }
    }

# === 60% MASKING & ENV SAFEGUARDS ===
ENV_KEY_KEYWORDS = {
    "SECRET", "PASSWORD", "PASS", "PASSWD", "PWD", "TOKEN", "KEY",
    "API_KEY", "APIKEY", "CREDENTIAL", "AUTH", "SALT", "HASH",
    "SIGNATURE", "PRIVATE", "CERT", "SIGNING", "WEBHOOK", "MASTER"
}

ENV_VALUE_BLACKLIST = {
    "true", "false", "null", "none", "undefined", "production", "development",
    "staging", "test", "testing", "localhost", "127.0.0.1", "0.0.0.0",
    "3000", "8080", "5000", "4000", "8000", "default", "standard", "root",
    "admin", "user", "guest", "postgres", "mysql", "redis", "mongodb", "sqlite"
}

def mask_secret_60pct(val: str) -> str:
    """
    Masks exactly ~60% of the secret with asterisks (*) in the middle,
    leaving visible hints at the start and end (e.g. jsjdj***kwjdi).
    """
    n = len(val)
    if n <= 4:
        return "*" * n
    mask_len = max(1, int(round(n * 0.6)))
    rem = n - mask_len
    left_len = rem // 2
    right_len = rem - left_len
    return val[:left_len] + ("*" * mask_len) + (val[n - right_len:] if right_len > 0 else "")

def calculate_shannon_entropy(s: str) -> float:
    """Calculates Shannon entropy to detect high-randomness secrets."""
    if not s:
        return 0.0
    prob = [float(s.count(c)) / len(s) for c in set(s)]
    return - sum([p * math.log(p) / math.log(2.0) for p in prob])

def is_valid_secret_candidate(key: str, val: str) -> bool:
    """Checks whether an env variable is a genuine sensitive secret."""
    key_upper = key.upper().strip()
    val_clean = val.strip().strip("'\"")

    if len(val_clean) < 6:
        return False
    if val_clean.lower() in ENV_VALUE_BLACKLIST:
        return False
    if val_clean.startswith("[REDACTED"):
        return False

    for kw in ENV_KEY_KEYWORDS:
        if kw in key_upper:
            return True

    if len(val_clean) >= 12 and calculate_shannon_entropy(val_clean) > 3.2:
        return True

    return False

def extract_dynamic_env_secrets(target_dir: str) -> List[Dict[str, Any]]:
    """
    Discovers all .env* files in target_dir, parses their key-values,
    and returns a list of sensitive secrets with their 60% masked hints.
    """
    abs_target = os.path.abspath(target_dir)
    env_files = []

    if os.path.isfile(abs_target):
        if os.path.basename(abs_target).startswith(".env"):
            env_files.append(abs_target)
    else:
        for root, dirs, files in os.walk(abs_target):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "dist", "build", ".venv", "venv", "scanning_docs"]]
            for f in files:
                if f.startswith(".env") and not f.endswith((".example", ".sample", ".template")):
                    env_files.append(os.path.join(root, f))
            rel = os.path.relpath(root, abs_target)
            if rel.count(os.sep) >= 2:
                dirs.clear()

    secrets = []
    seen_values = set()

    for env_path in env_files:
        try:
            with open(env_path, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" not in line:
                        continue

                    parts = line.split("=", 1)
                    key = parts[0].strip()
                    val = parts[1].strip().strip("'\"")

                    if is_valid_secret_candidate(key, val):
                        if val not in seen_values:
                            seen_values.add(val)
                            masked = mask_secret_60pct(val)
                            clean_key = re.sub(r"[^A-Za-z0-9_]", "_", key).upper()
                            secrets.append({
                                "key": clean_key,
                                "raw_value": val,
                                "masked_hint": masked,
                                "source_file": env_path,
                                "mask_token": f"[REDACTED_ENV_{clean_key}]"
                            })
        except Exception:
            continue

    return secrets

def build_dynamic_patterns(secrets: List[Dict[str, Any]]) -> List[Tuple[Any, str, int, str]]:
    """Builds compiled regex patterns from dynamic env secrets."""
    patterns = []
    sorted_secrets = sorted(secrets, key=lambda s: len(s["raw_value"]), reverse=True)
    for item in sorted_secrets:
        raw_val = item["raw_value"]
        pattern = re.compile(re.escape(raw_val))
        patterns.append((pattern, item["mask_token"], 100, item["key"]))
    return patterns

# === STATIC BASE PATTERNS ===
CLOUD_PATTERNS = [
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]+)\b"), "[REDACTED_OPENAI_KEY]", 99),
    (re.compile(r"\bhf_[A-Za-z0-9_-]+\b"), "[REDACTED_HF_TOKEN]", 99),
    (re.compile(r"\bAKIA[0-9A-Z]+\b"), "[REDACTED_AWS_ACCESS_KEY]", 99),
    (re.compile(r"\bAIzaSy[a-zA-Z0-9_-]{33}\b"), "[REDACTED_GOOGLE_API_KEY]", 99),
    (re.compile(r"\bAQ\.[a-zA-Z0-9_-]{30,80}\b"), "[REDACTED_GEMINI_OAUTH_TOKEN]", 99),
]
SOCIAL_PATTERNS = [
    (re.compile(r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35,}\b"), "[REDACTED_TELEGRAM_BOT_TOKEN]", 99),
    (re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b"), "[REDACTED_GITHUB_TOKEN]", 99),
    (re.compile(r"xox[baprs]-[0-9]+-[0-9]+(?:-[0-9]+)?-[a-zA-Z0-9]+"), "[REDACTED_SLACK_TOKEN]", 99),
    (re.compile(r"(?i)\b(?:sk|rk)_live_[a-zA-Z0-9_-]+\b"), "[REDACTED_STRIPE_KEY]", 99),
    (re.compile(r"\bSG\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"), "[REDACTED_SENDGRID_KEY]", 99),
]
DB_PATTERNS = [
    (re.compile(r"mongodb(?:\+srv)?:\/\/[^\s\"'<]+"), "[REDACTED_MONGODB_URL]", 99),
    (re.compile(r"postgres(?:ql)?:\/\/[^\s\"'<]+"), "[REDACTED_POSTGRES_URL]", 99),
    (re.compile(r"redis:\/\/[^\s\"'<]+"), "[REDACTED_REDIS_URL]", 99),
]
CRYPTO_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[^-]+-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]", 99),
    (re.compile(r"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT_TOKEN]", 99),
    (re.compile(r"\bP@ssw0rd_[a-zA-Z0-9_!@#$%^&*]+"), "[REDACTED_PASSWORD]", 99),
]
ALL_SPECIFIC_GROUPS = [CLOUD_PATTERNS, SOCIAL_PATTERNS, DB_PATTERNS, CRYPTO_PATTERNS]

QUOTED_KV_PATTERN = re.compile(
    r'''(?i)(["']?(?:password|passwd|pwd|db_pass|db_password|secret|token|api[_-]?key|access_token|private_key|auth_token)["']?\s*[:=]\s*(['"]))((?!\[REDACTED_)[^'\"\r\n]{1,150})(\2)'''
)
UNQUOTED_KV_PATTERN = re.compile(
    r'''(?i)(["']?(?:password|passwd|pwd|db_pass|db_password|secret|token|api[_-]?key|access_token|auth_token)["']?\s*[:=]\s*)(?!['"])(?!\[REDACTED_)([^\s'"#,\}]+)'''
)

IGNORED_DIRS = [
    "node_modules", ".git", "dist", "build", ".venv", "venv", "__pycache__",
    "scanning_docs", "vendor", ".next", ".angular", ".agents", "site-packages"
]

def get_backup_mode(): return os.environ.get("AGY_BACKUP_MODE", "sqlite").lower()

def check_workspace(path, dry_run=False):
    if dry_run: return True
    if os.environ.get("AGY_YES") == "1" or "-y" in sys.argv or "--yes" in sys.argv: return True
    if not sys.stdin.isatty() or "unittest" in sys.modules or "pytest" in sys.modules: return True
    print(f"\n⚠️  Workspace (Target Path): [{path}]")
    try:
        return input("Davom etasizmi? (Redact/O'zgartirish) [Y/n]: ").lower() in ['y', 'yes', '']
    except EOFError: return True

def setup_scanning_dirs(target_dir):
    base_dir = os.path.join(target_dir, "scanning_docs")
    reports_dir = os.path.join(base_dir, "reports")
    backups_dir = os.path.join(base_dir, "backups")
    try:
        for d in [base_dir, reports_dir, backups_dir]:
            if not os.path.exists(d): os.makedirs(d)
        gitignore_path = os.path.join(target_dir, ".gitignore")
        ignore_entry = "scanning_docs/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f: content = f.read()
            if ignore_entry not in content:
                with open(gitignore_path, "a") as f:
                    if content and not content.endswith("\n"): f.write("\n")
                    f.write(f"{ignore_entry}\n")
        else:
            with open(gitignore_path, "w") as f: f.write(f"{ignore_entry}\n")
        return reports_dir, backups_dir
    except Exception as e:
        print(f"\n❌ FATAL ERROR (Jildlar): scanning_docs papkasini yaratib bo'lmadi.\nSababi: {e}")
        sys.exit(1)

def redact_text_with_confidence(content: str, file_path: str, dynamic_patterns: list = None):
    """
    Applies secret redaction prioritizing dynamic .env secrets first,
    then specific patterns, then quoted/unquoted key-values.
    Returns: (redacted_content, changes)
    changes: [(file, line, confidence, raw_found, masked_hint, replaced_token, detail)]
    """
    changes = []
    dynamic_patterns = dynamic_patterns or []

    # 1. DYNAMIC ENV PATTERNS (Highest Priority, Confidence 100)
    for pat, mask, conf, key_name in dynamic_patterns:
        def repl_dyn(m, mk=mask, cf=conf, k=key_name):
            raw_matched = m.group(0)
            masked_hint = mask_secret_60pct(raw_matched)
            line_no = content.count('\n', 0, m.start()) + 1
            changes.append((file_path, line_no, cf, raw_matched, masked_hint, mk, f"Dynamic Env: {k}"))
            return mk
        content = pat.sub(repl_dyn, content)

    # 2. SPECIFIC KNOWN PATTERNS (Confidence 99)
    def repl_specific(match, mask, conf):
        raw_matched = match.group(0)
        masked_hint = mask_secret_60pct(raw_matched)
        line_no = content.count('\n', 0, match.start()) + 1
        changes.append((file_path, line_no, conf, raw_matched, masked_hint, mask, "Static Pattern"))
        return mask

    for group in ALL_SPECIFIC_GROUPS:
        for pattern, mask, conf in group:
            content = pattern.sub(lambda m, mk=mask, cf=conf: repl_specific(m, mk, cf), content)

    # 3. QUOTED KEY-VALUES (Confidence 95)
    def repl_quoted(match):
        raw_val = match.group(3)
        masked_hint = match.group(1) + mask_secret_60pct(raw_val) + match.group(4)
        repl = match.group(1) + "[REDACTED_PASSWORD]" + match.group(4)
        line_no = content.count('\n', 0, match.start()) + 1
        changes.append((file_path, line_no, 95, match.group(0), masked_hint, repl, "Quoted KV"))
        return repl
    content = QUOTED_KV_PATTERN.sub(repl_quoted, content)

    # 4. UNQUOTED KEY-VALUES (Confidence 90)
    def repl_unquoted(match):
        raw_val = match.group(2)
        masked_hint = match.group(1) + mask_secret_60pct(raw_val)
        repl = match.group(1) + "[REDACTED_PASSWORD]"
        line_no = content.count('\n', 0, match.start()) + 1
        changes.append((file_path, line_no, 90, match.group(0), masked_hint, repl, "Unquoted KV"))
        return repl
    content = UNQUOTED_KV_PATTERN.sub(repl_unquoted, content)

    return content, changes

def redact_text(content: str):
    """Backward-compatible helper for string redaction."""
    res, changes = redact_text_with_confidence(content, "")
    return res, len(changes)

def _process_directory(target_path, dry_run=False):
    target = safe_jail_path(target_path)
    if not check_workspace(target, dry_run=dry_run): sys.exit(0)

    mode = get_backup_mode()
    reports_dir, backups_dir = setup_scanning_dirs(
        target if os.path.isdir(target) else os.path.dirname(target)
    )

    ignored_exts = {
        '.zip', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mp3', '.db', '.sqlite', '.sqlite3', '.tar', '.gz',
        '.sql', '.schema', '.prisma', '.csv', '.lock', '.svg', '.pyc', '.bin'
    }
    ignored_names = {
        'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'requirements.txt', 
        'pipfile', 'pipfile.lock', 'poetry.lock', 'cargo.lock', 'composer.lock', 'composer.json', 
        'angular.json', 'nest-cli.json', 'tsconfig.json', 'jsconfig.json', 'vite.config.ts', 
        'vite.config.js', 'next.config.js', 'next.config.ts', 'webpack.config.js', 'rollup.config.js'
    }

    # 1. Load Dynamic .env secrets
    env_secrets = extract_dynamic_env_secrets(target)
    dynamic_patterns = build_dynamic_patterns(env_secrets)

    if os.path.isfile(target):
        all_targets = [target]
    else:
        cmd_count = ['find', target, '-type', 'd', '(']
        for i, d in enumerate(IGNORED_DIRS):
            if i > 0: cmd_count.append('-o')
            cmd_count.extend(['-name', d])
        cmd_count.extend([')', '-prune', '-o', '-type', 'f', '!', '-name', '.env*', '-print'])
        res_count = subprocess.run(cmd_count, stdout=subprocess.PIPE, text=True)
        all_targets = [p for p in res_count.stdout.strip().split('\n') if p]

    total_files = len(all_targets)

    # =========================================================================
    # 🚀 DRY-RUN REJIMI: Grep-Assisted ultra-tezkor tahlil va 60% maskalash
    # =========================================================================
    if dry_run:
        dynamic_grep_parts = [re.escape(s["raw_value"]) for s in env_secrets]
        dynamic_grep_str = ("|" + "|".join(dynamic_grep_parts)) if dynamic_grep_parts else ""

        combined_pattern = (
            r"\bsk-[A-Za-z0-9_-]+\b|\bhf_[A-Za-z0-9_-]+\b|\bAKIA[0-9A-Z]+\b|\bAIzaSy[a-zA-Z0-9_-]{33}\b|"
            r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35,}\b|\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b|"
            r"xox[baprs]-[0-9]+-[0-9]+(?:-[0-9]+)?-[a-zA-Z0-9]+|(?i)\b(?:sk|rk)_live_[a-zA-Z0-9_-]+\b|"
            r"\bSG\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b|mongodb(?:\+srv)?:\/\/[^\s\"'<]+|"
            r"postgres(?:ql)?:\/\/[^\s\"'<]+|redis:\/\/[^\s\"'<]+|-----BEGIN [A-Z ]+ PRIVATE KEY-----|"
            r"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|\bP@ssw0rd_[a-zA-Z0-9_!@#$%^&*]+|"
            r"""(?i)["']?(?:password|passwd|pwd|db_pass|db_password|secret|token|api[_-]?key|access_token|private_key|auth_token)["']?\s*[:=]\s*"""
            + dynamic_grep_str
        )

        grep_cmd = [
            "grep", "-rlIP", combined_pattern,
            "--exclude-dir=node_modules", "--exclude-dir=.git", "--exclude-dir=dist",
            "--exclude-dir=build", "--exclude-dir=.venv", "--exclude-dir=venv",
            "--exclude-dir=__pycache__", "--exclude-dir=scanning_docs",
            "--exclude-dir=vendor", "--exclude-dir=.next", "--exclude-dir=.angular",
            "--exclude=*.zip", "--exclude=*.pdf", "--exclude=*.png", "--exclude=*.jpg",
            "--exclude=*.db", "--exclude=*.pyc", "--exclude=package.json",
            "--exclude=package-lock.json", "--exclude=requirements.txt", "--exclude=.env*",
            target
        ]
        res_grep = subprocess.run(grep_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        candidate_files = [l for l in res_grep.stdout.strip().split("\n") if l]
        total_candidates = len(candidate_files)
        emit_progress("Pre-filter Done", 25, f"{total_candidates} ta nomzod fayl topildi")

        scan_report = []
        files_with_secrets_set = set()
        import time
        last_progress_time = time.time()

        for idx, fpath in enumerate(candidate_files, 1):
            basename = os.path.basename(fpath).lower()
            _, ext = os.path.splitext(basename)
            if ext in ignored_exts or basename in ignored_names: continue
            try:
                if os.path.getsize(fpath) > 1024 * 1024: continue
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            _, changes = redact_text_with_confidence(content, fpath, dynamic_patterns)
            if changes:
                files_with_secrets_set.add(fpath)
                for ch in changes:
                    # ch: (file, line, conf, raw_found, masked_hint, repl_token, detail)
                    scan_report.append({
                        "file": ch[0],
                        "line": ch[1],
                        "confidence": ch[2],
                        "source": ch[6],
                        # 60% masked hint: Never leaks raw secrets into reports!
                        "found": ch[4],
                        "would_replace_with": ch[5]
                    })

            now = time.time()
            if (now - last_progress_time >= 1.5) or idx == total_candidates:
                last_progress_time = now
                pct = 25 + int((idx / max(1, total_candidates)) * 70)
                emit_progress("Scanning Candidates", pct, f"[{idx}/{total_candidates}] Tahlil: {len(files_with_secrets_set)} ta faylda sir topildi")

        total_items = len(scan_report)
        redacted_files = len(files_with_secrets_set)

        if scan_report:
            try:
                report_path = os.path.join(reports_dir, "scan_report.json")
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "mode": "DRY-RUN (Scan only)",
                        "scanned_files": total_files,
                        "files_with_secrets": redacted_files,
                        "total_findings": total_items,
                        "dynamic_env_secrets_loaded": len(env_secrets),
                        "dynamic_env_keys": [s["key"] for s in env_secrets],
                        "findings": scan_report
                    }, f, indent=2)
                print(f"📋 Hisobot: {report_path}")
            except Exception as e:
                print(f"\n❌ FATAL ERROR (Hisobot yozish): {e}")
                sys.exit(1)

        return total_files, total_items, redacted_files

    # =========================================================================
    # 🛠 EXECUTE (REDACT) REJIMI: Zaxiralash va fayllarni niqoblash
    # =========================================================================
    valid_targets = []
    for fpath in all_targets:
        if "scanning_docs" in fpath: continue
        basename = os.path.basename(fpath).lower()
        _, ext = os.path.splitext(basename)
        if ext in ignored_exts or basename in ignored_names: continue
        try:
            if os.path.getsize(fpath) > 1024 * 1024: continue
        except OSError:
            continue
        valid_targets.append(fpath)

    pad_len = max(3, len(str(total_files)))
    chunk_size = 100
    db_conn = None
    json_changes = []
    total_items = 0; redacted_files = 0

    if mode == "sqlite":
        try:
            db_conn = sqlite3.connect(os.path.join(backups_dir, "backup.db"))
            db_conn.cursor().execute('''CREATE TABLE IF NOT EXISTS redactions
                (id INTEGER PRIMARY KEY, type TEXT, file TEXT, line INTEGER,
                 confidence INTEGER, original TEXT, replaced TEXT, detail TEXT)''')
        except sqlite3.Error as e:
            print(f"\n❌ FATAL ERROR (SQLite): Bazaga ulanib bo'lmadi.\nSababi: {e}")
            sys.exit(1)

    for i, fpath in enumerate(valid_targets):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f: content = f.read()
            new_content, changes = redact_text_with_confidence(content, fpath, dynamic_patterns)

            if changes:
                total_items += len(changes)
                redacted_files += 1

                if mode == "sqlite":
                    try:
                        # ch: (file, line, conf, raw_found, masked_hint, repl_token, detail)
                        db_records = [(ch[0], ch[1], ch[2], ch[3], ch[5], ch[6]) for ch in changes]
                        db_conn.cursor().executemany(
                            "INSERT INTO redactions (type, file, line, confidence, original, replaced, detail) VALUES ('redacted', ?, ?, ?, ?, ?, ?)", db_records)
                    except sqlite3.Error as e:
                        print(f"\n❌ FATAL ERROR (SQLite INSERT): Zaxiraga yozishda xatolik!\nFayl: {fpath}\nSababi: {e}")
                        sys.exit(1)
                else:
                    for ch in changes:
                        json_changes.append({"file": ch[0], "line": ch[1], "original_text": ch[3], "masked_hint": ch[4], "replaced_with": ch[5], "detail": ch[6]})

                try:
                    with open(fpath, "w", encoding="utf-8") as f: f.write(new_content)
                except PermissionError as e:
                    print(f"\n❌ FATAL ERROR (Ruxsat yo'q): Faylga yozib bo'lmadi!\nFayl: {fpath}\nSababi: {e}")
                    sys.exit(1)

        except PermissionError as e:
            print(f"\n❌ FATAL ERROR (Ruxsat yo'q): Faylni o'qib bo'lmadi!\nFayl: {fpath}\nSababi: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ FATAL ERROR (Kutilmagan xatolik): {fpath}\nSababi: {e}")
            sys.exit(1)

        if mode == "json":
            if (i + 1) % chunk_size == 0 or (i + 1) == len(valid_targets):
                if json_changes:
                    s = (i // chunk_size) * chunk_size + 1
                    e = min(i + 1, len(valid_targets))
                    chunk_name = f"{s:0{pad_len}d}-{e:0{pad_len}d}_backup.json"
                    try:
                        with open(os.path.join(backups_dir, chunk_name), "w") as f:
                            json.dump({"redacted_changes": json_changes}, f, indent=2)
                    except Exception as e:
                        print(f"\n❌ FATAL ERROR (JSON yozish): Chunk saqlab bo'lmadi.\nSababi: {e}")
                        sys.exit(1)
                    json_changes = []

    if mode == "sqlite":
        try:
            db_conn.commit(); db_conn.close()
        except sqlite3.Error as e:
            print(f"\n❌ FATAL ERROR (SQLite COMMIT): {e}")
            sys.exit(1)

    return total_files, total_items, redacted_files

def run_secure_scan(args):
    emit_progress("Scanning (Dry-Run)", 10, "Faqat hisobot, hech narsa o'zgartirilmaydi...")
    total_files, total_items, red_files = _process_directory(args.path, dry_run=True)
    emit_progress("Done", 100, f"Skanerlash yakunlandi. Topildi: {total_items} ta sir ({red_files} ta faylda)")
    emit_result({
        "mode": "DRY-RUN",
        "scanned_files": total_files,
        "files_with_secrets": red_files,
        "total_findings": total_items,
        "report": "scanning_docs/reports/scan_report.json"
    })

def run_secure_redact(args):
    dry_run = getattr(args, 'dry_run', False)
    if dry_run:
        return run_secure_scan(args)
    emit_progress("Redacting (Execute)", 10, "Sirlar qirqilib zaxira yozilmoqda...")
    total_files, total_items, red_files = _process_directory(args.path, dry_run=False)
    emit_progress("Done", 100, "Yakunlandi.")
    emit_result({
        "mode": "EXECUTE",
        "scanned_files": total_files,
        "redacted_files": red_files,
        "total_redacted": total_items,
        "backup": "scanning_docs/backups/"
    })
