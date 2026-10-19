import os
import sys
import json
from pathlib import Path
from agy_tools.utils import emit_progress, emit_result, safe_jail_path
from agy_tools.config import config

try:
    import requests
except ImportError:
    requests = None
import urllib.request
import urllib.parse
import urllib.error

def get_sender_describe():
    return {
        "name": "sender",
        "description": "JarvisOS Telegram xabar, hujjat, rasm va jonli status (Live Message) yuborish vositasi.",
        "commands": {
            "msg": "Telegram chatga to'g'ridan-to'g'ri matnli xabar jo'natish (HTML yoki Markdown)",
            "doc": "Fayl yoki hujjatni Telegramga to'g'ridan-to'g'ri jo'natish",
            "photo": "Rasmni Telegram chatga rasm sifatida jo'natish",
            "live": "Mavjud jonli xabarni (Live Message ID) real-vaqtda tahrirlash/yangilash"
        }
    }

def run_send_msg(args):
    text = getattr(args, "text", None) or getattr(args, "message", None)
    if not text:
        return emit_result(None, success=False, error="Xabar matni berilmadi.")
    
    try:
        token = config.get_bot_token()
        chat_id = config.get_default_chat_id(getattr(args, "chat_id", None))
    except Exception as ce:
        return emit_result(None, success=False, error=str(ce))

    parse_mode = getattr(args, "parse_mode", "HTML")

    emit_progress("Sending Message", 30, f"Chat {chat_id} ga xabar yuborilmoqda...")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if parse_mode and parse_mode != "None":
        payload["parse_mode"] = parse_mode

    try:
        if requests:
            res = requests.post(url, json=payload, timeout=20)
            res_json = res.json()
        else:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                res_json = json.loads(r.read().decode("utf-8"))

        if res_json.get("ok"):
            msg_id = res_json.get("result", {}).get("message_id")
            emit_progress("Done", 100, f"Xabar muvaffaqiyatli yetkazildi (ID: {msg_id})")
            return emit_result({
                "message_id": msg_id,
                "chat_id": chat_id,
                "status": "SENT"
            }, success=True)
        else:
            err = res_json.get("description", "Noma'lum Telegram xatosi")
            return emit_result(None, success=False, error=f"Telegram xatosi: {err}")
    except Exception as e:
        return emit_result(None, success=False, error=f"Ulanish xatosi: {str(e)}")

def run_send_doc(args):
    file_path = getattr(args, "file", None) or getattr(args, "path", None)
    if not file_path or not os.path.exists(file_path):
        return emit_result(None, success=False, error=f"Fayl topilmadi: {file_path}")

    try:
        token = config.get_bot_token()
        chat_id = config.get_default_chat_id(getattr(args, "chat_id", None))
    except Exception as ce:
        return emit_result(None, success=False, error=str(ce))

    caption = getattr(args, "caption", "") or ""

    emit_progress("Sending Document", 30, f"Fayl ({os.path.basename(file_path)}) chat {chat_id} ga yuklanmoqda...")

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    try:
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            if requests:
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption
                files = {"document": (filename, f)}
                res = requests.post(url, data=data, files=files, timeout=60)
                res_json = res.json()
            else:
                import mimetypes
                import uuid
                boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
                body = bytearray()

                def add_field(name, val):
                    body.extend(f"--{boundary}\r\n".encode("utf-8"))
                    body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
                    body.extend(f"{val}\r\n".encode("utf-8"))

                add_field("chat_id", chat_id)
                if caption:
                    add_field("caption", caption)

                mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode("utf-8"))
                body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
                body.extend(f.read())
                body.extend(b"\r\n")
                body.extend(f"--{boundary}--\r\n".encode("utf-8"))

                req = urllib.request.Request(
                    url,
                    data=bytes(body),
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    res_json = json.loads(r.read().decode("utf-8"))

        if res_json.get("ok"):
            msg_id = res_json.get("result", {}).get("message_id")
            emit_progress("Done", 100, f"Hujjat muvaffaqiyatli yuborildi (ID: {msg_id})")
            return emit_result({
                "message_id": msg_id,
                "chat_id": chat_id,
                "file": file_path,
                "filename": filename,
                "status": "SENT"
            }, success=True)
        else:
            err = res_json.get("description", "Noma'lum Telegram xatosi")
            return emit_result(None, success=False, error=f"Telegram xatosi: {err}")
    except Exception as e:
        return emit_result(None, success=False, error=f"Hujjat yuborishda xatolik: {str(e)}")

def run_send_photo(args):
    photo_path = getattr(args, "file", None) or getattr(args, "path", None)
    if not photo_path or not os.path.exists(photo_path):
        return emit_result(None, success=False, error=f"Rasm topilmadi: {photo_path}")

    try:
        token = config.get_bot_token()
        chat_id = config.get_default_chat_id(getattr(args, "chat_id", None))
    except Exception as ce:
        return emit_result(None, success=False, error=str(ce))

    caption = getattr(args, "caption", "") or ""

    emit_progress("Sending Photo", 30, f"Rasm chat {chat_id} ga yuborilmoqda...")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    try:
        with open(photo_path, "rb") as f:
            if requests:
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption
                files = {"photo": (os.path.basename(photo_path), f)}
                res = requests.post(url, data=data, files=files, timeout=60)
                res_json = res.json()
            else:
                return emit_result(None, success=False, error="requests kutubxonasi mavjud emas.")

        if res_json.get("ok"):
            msg_id = res_json.get("result", {}).get("message_id")
            emit_progress("Done", 100, f"Rasm muvaffaqiyatli yetkazildi (ID: {msg_id})")
            return emit_result({
                "message_id": msg_id,
                "chat_id": chat_id,
                "photo": photo_path,
                "status": "SENT"
            }, success=True)
        else:
            err = res_json.get("description", "Telegram xatosi")
            return emit_result(None, success=False, error=f"Telegram xatosi: {err}")
    except Exception as e:
        return emit_result(None, success=False, error=f"Rasm yuborishda xatolik: {str(e)}")

def run_send_live(args):
    message_id = getattr(args, "message_id", None)
    text = getattr(args, "text", "")
    if not message_id or not text:
        return emit_result(None, success=False, error="message_id va text berilishi shart.")

    try:
        token = config.get_bot_token()
        chat_id = config.get_default_chat_id(getattr(args, "chat_id", None))
    except Exception as ce:
        return emit_result(None, success=False, error=str(ce))

    url = f"https://api.telegram.org/bot{token}/editMessageText"

    payload = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        if requests:
            res = requests.post(url, json=payload, timeout=15)
            res_json = res.json()
        else:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                res_json = json.loads(r.read().decode("utf-8"))

        if res_json.get("ok"):
            return emit_result({
                "chat_id": chat_id,
                "message_id": message_id,
                "status": "UPDATED"
            }, success=True)
        else:
            desc = res_json.get("description", "")
            if "can't parse entities" in desc or "markdown" in desc.lower():
                payload.pop("parse_mode", None)
                if requests:
                    retry_res = requests.post(url, json=payload, timeout=15)
                    retry_json = retry_res.json()
                else:
                    data_bytes = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        retry_json = json.loads(r.read().decode("utf-8"))

                if retry_json.get("ok"):
                    return emit_result({
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "status": "UPDATED_PLAIN"
                    }, success=True)
            return emit_result(None, success=False, error=f"Live message update xatosi: {desc}")
    except Exception as e:
        return emit_result(None, success=False, error=f"Live message ulanish xatosi: {str(e)}")
