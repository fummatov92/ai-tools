import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path
from agy_tools.utils import emit_progress, emit_result, safe_jail_path

DEFAULT_REMOTE = os.environ.get("GDRIVE_REMOTE", "gdrive")
DEFAULT_RCLONE_BIN = os.path.expanduser("~/.local/bin/rclone")


def find_rclone_bin() -> str:
    """Finds available rclone binary path."""
    if os.path.exists(DEFAULT_RCLONE_BIN) and os.access(DEFAULT_RCLONE_BIN, os.X_OK):
        return DEFAULT_RCLONE_BIN
    found = shutil.which("rclone")
    if found:
        return found
    for cand in ["/usr/local/bin/rclone", "/usr/bin/rclone"]:
        if os.path.exists(cand) and os.access(cand, os.X_OK):
            return cand
    return ""


def get_rclone_config_path() -> str:
    """Returns path to rclone configuration file."""
    custom_conf = os.environ.get("RCLONE_CONFIG")
    if custom_conf and os.path.exists(custom_conf):
        return custom_conf
    home = os.path.expanduser("~")
    return os.path.join(home, ".config", "rclone", "rclone.conf")


def format_bytes(size_bytes: int) -> str:
    """Formats raw bytes to human-readable string."""
    if size_bytes is None or size_bytes < 0:
        return "N/A"
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"


def get_drive_describe():
    """Returns module capabilities schema for --describe flag."""
    return {
        "name": "drive",
        "description": "Google Drive 0-Token Avtomatizatsiya va Fayl Boshqaruvi Moduli (rclone & cloud sync dvigateli).",
        "commands": {
            "status": "Google Drive ulanish holati, kvotasi va konfiguratsiyasini tekshirish",
            "setup": "Google Drive masofaviy diskini (remote) Service Account yoki OAuth orqali sozlash",
            "ls": "Google Drive papkasidagi fayl va jildlar ro'yxatini olish (JSON/table)",
            "upload": "Lokal fayl yoki papkani Google Drive ga yuklash (avtomatik chunking va retry)",
            "download": "Google Drive dan fayl yoki papkani lokal serverga yuklab olish",
            "sync": "Lokal jild va Google Drive orasida bir tomonlama yoki ikki tomonlama sinxronizatsiya",
            "mkdir": "Google Drive da yangi papka yaratish",
            "quota": "Google Drive xotira hajmi, bandligi va erkin qoldiqni hisoblash",
            "link": "Google Drive dagi fayl uchun ochiq/ulashish havolasini (shareable link) olish",
            "delete": "Google Drive dan faylni o'chirish"
        }
    }


def run_drive_status(args):
    """Checks Google Drive configuration and live connection status."""
    emit_progress("Checking Drive", 20, "Rclone vositasi va sozlamalar tekshirilmoqda...")
    rclone_bin = find_rclone_bin()
    conf_path = get_rclone_config_path()
    remote = getattr(args, "remote", None) or DEFAULT_REMOTE

    result = {
        "rclone_installed": bool(rclone_bin),
        "rclone_bin": rclone_bin or None,
        "rclone_version": None,
        "config_exists": os.path.exists(conf_path),
        "config_path": conf_path,
        "remote_name": remote,
        "remote_configured": False,
        "connection_live": False,
        "quota": None,
        "details": ""
    }

    if not rclone_bin:
        result["details"] = "rclone binar fayli topilmadi. O'rnatish lozim."
        return emit_result(result, success=False, error="rclone topilmadi.")

    # Get version
    try:
        ver_res = subprocess.run([rclone_bin, "version"], capture_output=True, text=True, timeout=5)
        if ver_res.returncode == 0:
            first_line = ver_res.stdout.split("\n")[0]
            result["rclone_version"] = first_line.replace("rclone ", "").strip()
    except Exception:
        pass

    # Check remotes
    try:
        rem_res = subprocess.run([rclone_bin, "listremotes"], capture_output=True, text=True, timeout=5)
        remotes = [r.strip().rstrip(":") for r in rem_res.stdout.split("\n") if r.strip()]
        result["configured_remotes"] = remotes
        if remote in remotes:
            result["remote_configured"] = True
    except Exception as e:
        result["details"] = f"Remoteni tekshirishda xatolik: {e}"

    if not result["remote_configured"]:
        result["details"] = (
            f"'{remote}' nomli Google Drive masofaviy diski hali sozlanmagan. "
            f"Sozlash uchun: agy-tool drive setup --service-account <path_to_json> yoki rclone config"
        )
        return emit_result(result, success=True)

    # Test live connection via 'about'
    emit_progress("Testing Connection", 60, f"'{remote}:' bilan jonli aloqa tekshirilmoqda...")
    try:
        about_cmd = [rclone_bin, "about", f"{remote}:", "--json"]
        about_res = subprocess.run(about_cmd, capture_output=True, text=True, timeout=15)
        if about_res.returncode == 0:
            result["connection_live"] = True
            try:
                raw_quota = json.loads(about_res.stdout)
                total = raw_quota.get("total", 0)
                used = raw_quota.get("used", 0)
                free = raw_quota.get("free", 0)
                trash = raw_quota.get("trashed", 0)
                used_pct = round((used / total * 100), 2) if total and total > 0 else 0
                result["quota"] = {
                    "total_bytes": total,
                    "used_bytes": used,
                    "free_bytes": free,
                    "trash_bytes": trash,
                    "total_formatted": format_bytes(total),
                    "used_formatted": format_bytes(used),
                    "free_formatted": format_bytes(free),
                    "trash_formatted": format_bytes(trash),
                    "used_pct": f"{used_pct}%"
                }
                result["details"] = "Google Drive ga ulanish muvaffaqiyatli o'rnatildi."
            except Exception:
                result["details"] = "Google Drive ulandi, ammo kvota ma'lumoti o'qilmadi."
        else:
            result["connection_live"] = False
            result["details"] = f"Aloqa xatosi: {about_res.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        result["connection_live"] = False
        result["details"] = "Google Drive API timeout (15s). Tarmoqni tekshiring."
    except Exception as e:
        result["connection_live"] = False
        result["details"] = f"Ulanishda kutilmagan xatolik: {e}"

    emit_progress("Done", 100, "Google Drive status tekshiruvi yakunlandi.")
    return emit_result(result, success=True)


def run_drive_setup(args):
    """Sets up or updates Google Drive remote using Service Account or OAuth."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi tizimda topilmadi.")

    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    sa_path = getattr(args, "service_account", None)
    folder_id = getattr(args, "folder_id", None)
    token = getattr(args, "token", None)
    code = getattr(args, "code", None)
    client_id = getattr(args, "client_id", None)
    client_secret = getattr(args, "client_secret", None)
    oauth_json = getattr(args, "oauth_json", None)

    # Check default oauth json if not explicitly passed
    default_oauth_json = os.environ.get("GDRIVE_OAUTH_JSON", os.path.expanduser("~/.config/ai-tools/gdrive_oauth_client.json"))
    if not oauth_json and os.path.exists(default_oauth_json):
        oauth_json = default_oauth_json

    if oauth_json and os.path.exists(oauth_json):
        try:
            with open(oauth_json, "r", encoding="utf-8") as of:
                odata = json.load(of)
                inst = odata.get("installed") or odata.get("web") or {}
                if not client_id:
                    client_id = inst.get("client_id")
                if not client_secret:
                    client_secret = inst.get("client_secret")
        except Exception:
            pass

    # Handle authorization code exchange if provided
    if code:
        emit_progress("Exchanging Code", 30, "Google OAuth avtorizatsiya kodi tokenga almashtirilmoqda...")
        import urllib.request
        import urllib.parse
        clean_code = code.strip()
        if "code=" in clean_code:
            try:
                parsed = urllib.parse.urlparse(clean_code)
                qs = urllib.parse.parse_qs(parsed.query)
                clean_code = qs.get("code", [clean_code])[0]
            except Exception:
                pass

        if not client_id or not client_secret:
            return emit_result(None, success=False, error="OAuth Client ID yoki Secret topilmadi. --oauth-json yoki --client-id ko'rsating.")

        post_data = urllib.parse.urlencode({
            "code": clean_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "http://localhost",
            "grant_type": "authorization_code"
        }).encode("utf-8")
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=post_data, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                token_resp = json.loads(resp.read().decode("utf-8"))
                token = json.dumps(token_resp)
        except Exception as te:
            return emit_result(None, success=False, error=f"Google OAuth tokenni olishda xatolik: {te}")

    emit_progress("Setting Up Drive", 40, f"'{remote}' Google Drive konfiguratsiyasi yaratilmoqda...")

    cmd = [rclone_bin, "config", "create", remote, "drive", "scope=drive"]

    if sa_path:
        abs_sa = os.path.realpath(os.path.abspath(os.path.expanduser(sa_path)))
        if not os.path.exists(abs_sa):
            return emit_result(None, success=False, error=f"Service account fayli topilmadi: {sa_path}")
        try:
            with open(abs_sa, "r", encoding="utf-8") as sf:
                json.load(sf)
        except Exception as se:
            return emit_result(None, success=False, error=f"Noto'g'ri JSON formati: {se}")
        cmd.append(f"service_account_file={abs_sa}")

    if client_id:
        cmd.append(f"client_id={client_id}")
    if client_secret:
        cmd.append(f"client_secret={client_secret}")

    if folder_id:
        cmd.append(f"root_folder_id={folder_id}")

    if token:
        cmd.append(f"token={token}")

    if not sa_path and not token:
        return emit_result(
            None,
            success=False,
            error="Autentifikatsiya ma'lumotlari berilmadi. --service-account <path_to_json>, --token <json> yoki --code <code> ko'rsating."
        )

    try:
        import configparser
        conf_path = get_rclone_config_path()
        os.makedirs(os.path.dirname(conf_path), exist_ok=True)
        cp = configparser.ConfigParser()
        if os.path.exists(conf_path):
            cp.read(conf_path)
        if not cp.has_section(remote):
            cp.add_section(remote)
        cp.set(remote, "type", "drive")
        cp.set(remote, "scope", "drive")
        if sa_path:
            cp.set(remote, "service_account_file", abs_sa)
            if cp.has_option(remote, "token"):
                cp.remove_option(remote, "token")
        if client_id:
            cp.set(remote, "client_id", client_id)
        if client_secret:
            cp.set(remote, "client_secret", client_secret)
        if folder_id:
            cp.set(remote, "root_folder_id", folder_id)
        if token:
            cp.set(remote, "token", token)
            if cp.has_option(remote, "service_account_file"):
                cp.remove_option(remote, "service_account_file")
        with open(conf_path, "w") as f:
            cp.write(f)

        emit_progress("Verifying Connection", 70, "Yangi konfiguratsiya orqali Drive tekshirilmoqda...")
        test_res = subprocess.run([rclone_bin, "lsf", f"{remote}:", "--max-depth", "1"], capture_output=True, text=True, timeout=15)
        if test_res.returncode == 0:
            data = {
                "remote": remote,
                "status": "configured_and_verified",
                "service_account": sa_path or None,
                "folder_id": folder_id or None,
                "details": f"'{remote}' Google Drive muvaffaqiyatli sozlandi va ulandi!"
            }
            emit_progress("Done", 100, "Google Drive tayyor.")
            return emit_result(data, success=True)
        else:
            data = {
                "remote": remote,
                "status": "configured_unverified",
                "details": f"Konfiguratsiya saqlandi, ammo tekshiruvda ogohlantirish: {test_res.stderr.strip()[:150]}"
            }
            return emit_result(data, success=True)
    except Exception as e:
        return emit_result(None, success=False, error=f"Setup jarayonida xatolik: {e}")


def run_drive_ls(args):
    """Lists files and directories in Google Drive remote path."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi topilmadi.")

    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    raw_path = getattr(args, "path", "") or ""
    remote_target = f"{remote}:{raw_path.lstrip('/')}"
    max_items = getattr(args, "max", 50) or 50

    emit_progress("Listing Files", 30, f"'{remote_target}' jildi o'rganilmoqda...")

    cmd = [rclone_bin, "lsjson", remote_target]
    if getattr(args, "recursive", False):
        cmd.append("-R")
    else:
        cmd.extend(["--max-depth", "1"])

    if getattr(args, "dirs_only", False):
        cmd.append("--dirs-only")
    elif getattr(args, "files_only", False):
        cmd.append("--files-only")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            return emit_result(None, success=False, error=f"Ro'yxat olishda xatolik: {res.stderr.strip()[:200]}")

        raw_items = json.loads(res.stdout or "[]")
        items = []
        total_size = 0

        for item in raw_items[:max_items]:
            is_dir = item.get("IsDir", False)
            size = item.get("Size", 0)
            if not is_dir and size > 0:
                total_size += size

            items.append({
                "name": item.get("Name"),
                "path": item.get("Path"),
                "is_dir": is_dir,
                "size_bytes": size,
                "size_formatted": format_bytes(size) if not is_dir else "DIR",
                "mime_type": item.get("MimeType", ""),
                "mod_time": item.get("ModTime", ""),
                "id": item.get("ID", "")
            })

        data = {
            "remote_target": remote_target,
            "count": len(items),
            "total_listed": len(raw_items),
            "total_size_formatted": format_bytes(total_size),
            "items": items
        }
        emit_progress("Done", 100, f"{len(items)} ta element topildi.")
        return emit_result(data, success=True)
    except Exception as e:
        return emit_result(None, success=False, error=f"Drive ro'yxatida xatolik: {e}")


def run_drive_upload(args):
    """Uploads local file or directory to Google Drive."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi topilmadi.")

    local_path = getattr(args, "local_path", None)
    if not local_path:
        return emit_result(None, success=False, error="Yuklanuvchi lokal fayl yoki jild manzili berilmadi.")

    safe_local = safe_jail_path(local_path)
    if not os.path.exists(safe_local):
        return emit_result(None, success=False, error=f"Lokal fayl topilmadi: {local_path}")

    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    raw_remote_path = getattr(args, "remote_path", "") or ""
    remote_target = f"{remote}:{raw_remote_path.lstrip('/')}"

    is_dir = os.path.isdir(safe_local)
    size_bytes = sum(os.path.getsize(os.path.join(dirpath, f)) for dirpath, _, filenames in os.walk(safe_local) for f in filenames) if is_dir else os.path.getsize(safe_local)

    emit_progress("Uploading to Drive", 25, f"{os.path.basename(safe_local)} ({format_bytes(size_bytes)}) yuklanmoqda...")

    start_time = time.time()
    if is_dir:
        cmd = [rclone_bin, "copy", safe_local, remote_target, "--stats", "1s"]
    else:
        # If target has trailing slash or is empty, copy into directory
        if remote_target.endswith("/") or raw_remote_path == "":
            cmd = [rclone_bin, "copy", safe_local, remote_target]
        else:
            cmd = [rclone_bin, "copyto", safe_local, remote_target]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = round(time.time() - start_time, 2)
        if res.returncode != 0:
            return emit_result(None, success=False, error=f"Yuklashda xato: {res.stderr.strip()[:200]}")

        emit_progress("Complete", 100, "Muvaffaqiyatli yuklandi.")
        data = {
            "status": "uploaded",
            "source": safe_local,
            "destination": remote_target,
            "is_dir": is_dir,
            "size_bytes": size_bytes,
            "size_formatted": format_bytes(size_bytes),
            "duration_seconds": duration
        }
        return emit_result(data, success=True)
    except subprocess.TimeoutExpired:
        return emit_result(None, success=False, error="Yuklash jarayoni 300 soniyadan oshib ketdi (timeout).")
    except Exception as e:
        return emit_result(None, success=False, error=f"Yuklashda xatolik: {e}")


def run_drive_download(args):
    """Downloads file or directory from Google Drive to local destination."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi topilmadi.")

    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    raw_remote_path = getattr(args, "remote_path", "") or ""
    remote_target = f"{remote}:{raw_remote_path.lstrip('/')}"

    local_path = getattr(args, "local_path", None)
    if not local_path:
        local_path = os.path.join(os.getcwd(), os.path.basename(raw_remote_path) or "drive_download")

    safe_local = safe_jail_path(local_path)
    emit_progress("Downloading from Drive", 25, f"{remote_target} -> {safe_local} yuklab olinmoqda...")

    start_time = time.time()
    cmd = [rclone_bin, "copy", remote_target, safe_local]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = round(time.time() - start_time, 2)
        if res.returncode != 0:
            return emit_result(None, success=False, error=f"Yuklab olishda xato: {res.stderr.strip()[:200]}")

        emit_progress("Complete", 100, "Muvaffaqiyatli yuklab olindi.")
        data = {
            "status": "downloaded",
            "source": remote_target,
            "destination": safe_local,
            "duration_seconds": duration
        }
        return emit_result(data, success=True)
    except Exception as e:
        return emit_result(None, success=False, error=f"Yuklab olishda xatolik: {e}")


def run_drive_sync(args):
    """Synchronizes local directory and Google Drive."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi topilmadi.")

    local_dir = safe_jail_path(getattr(args, "local_dir", "."))
    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    raw_remote = getattr(args, "remote_path", "") or ""
    remote_target = f"{remote}:{raw_remote.lstrip('/')}"
    direction = getattr(args, "direction", "up")  # up: local -> remote, down: remote -> local

    src = local_dir if direction == "up" else remote_target
    dst = remote_target if direction == "up" else local_dir

    emit_progress("Syncing Drive", 20, f"Sinxronizatsiya boshlandi: {src} -> {dst}")
    cmd = [rclone_bin, "sync", src, dst]
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")

    start_time = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        duration = round(time.time() - start_time, 2)
        if res.returncode != 0:
            return emit_result(None, success=False, error=f"Sync xatosi: {res.stderr.strip()[:200]}")

        emit_progress("Complete", 100, "Sinxronizatsiya yakunlandi.")
        data = {
            "status": "synced",
            "source": src,
            "destination": dst,
            "dry_run": getattr(args, "dry_run", False),
            "duration_seconds": duration
        }
        return emit_result(data, success=True)
    except Exception as e:
        return emit_result(None, success=False, error=f"Sync jarayonida xatolik: {e}")


def run_drive_mkdir(args):
    """Creates a directory in Google Drive."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi topilmadi.")

    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    raw_path = getattr(args, "path", None)
    if not raw_path:
        return emit_result(None, success=False, error="Yaratiluvchi jild nomi/yo'li berilmadi.")

    remote_target = f"{remote}:{raw_path.lstrip('/')}"
    emit_progress("Creating Directory", 40, f"'{remote_target}' yaratilmoqda...")

    try:
        res = subprocess.run([rclone_bin, "mkdir", remote_target], capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            return emit_result(None, success=False, error=f"Papka yaratishda xato: {res.stderr.strip()[:200]}")
        emit_progress("Done", 100, "Jild yaratildi.")
        return emit_result({"status": "created", "path": remote_target}, success=True)
    except Exception as e:
        return emit_result(None, success=False, error=f"Papka yaratishda xatolik: {e}")


def run_drive_quota(args):
    """Retrieves Google Drive storage quota and usage stats."""
    return run_drive_status(args)


def run_drive_link(args):
    """Generates public/shareable web link for a file on Google Drive."""
    rclone_bin = find_rclone_bin()
    if not rclone_bin:
        return emit_result(None, success=False, error="rclone vositasi topilmadi.")

    remote = getattr(args, "remote", None) or DEFAULT_REMOTE
    raw_path = getattr(args, "path", None)
    if not raw_path:
        return emit_result(None, success=False, error="Havola olinishi kerak bo'lgan fayl yo'li berilmadi.")

    remote_target = f"{remote}:{raw_path.lstrip('/')}"
    emit_progress("Generating Link", 50, f"'{remote_target}' uchun havola so'ralmoqda...")

    try:
        res = subprocess.run([rclone_bin, "link", remote_target], capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return emit_result(None, success=False, error=f"Havola olishda xato: {res.stderr.strip()[:200]}")
        link_url = res.stdout.strip()
        emit_progress("Done", 100, "Havola olindi.")
        return emit_result({"path": remote_target, "link": link_url}, success=True)
    except Exception as e:
        return emit_result(None, success=False, error=f"Havola generatsiyasida xatolik: {e}")
