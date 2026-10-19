import os
import sys
import re
import gzip
import sqlite3
import struct
import json
import shutil
import subprocess
from pathlib import Path
from agy_tools.utils import emit_result, emit_progress

def _format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def get_db_describe():
    return {
        "name": "db",
        "description": "Multi-engine ma'lumotlar bazasi va zaxira (backup) fayllarini tekshirish (Postgres, MySQL, SQLite, MongoDB, Redis).",
        "commands": {
            "inspect": "DB backup yoki jonli faylni tahlil qilish (jadvallar, yozuvlar, hajm)",
            "tables": "DB ichidagi barcha jadvallar va ularning strukturasini ko'rish",
            "dump": "Jonli ma'lumotlar bazasidan SQL dump yaratish",
            "query": "SQLite yoki SQL dump fayl ustida SQL so'rovlarini bajarish"
        }
    }

def open_sql_stream(file_path: str):
    """Opens plain SQL or gzipped SQL as a text stream."""
    if file_path.endswith('.gz'):
        return gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore')
    return open(file_path, 'r', encoding='utf-8', errors='ignore')

def _normalize_db_type(db_type: str) -> str:
    if not db_type:
        return "auto"
    t = db_type.lower().strip()
    if t in ["postgres", "postgresql", "psql", "pgsql"]:
        return "postgres"
    if t in ["mysql", "mariadb"]:
        return "mysql"
    if t in ["sqlite", "sqlite3"]:
        return "sqlite"
    if t in ["mongo", "mongodb", "bson"]:
        return "mongodb"
    if t in ["redis", "rdb"]:
        return "redis"
    return "auto"

def detect_db_type(path: str, explicit_type: str = "auto") -> str:
    norm = _normalize_db_type(explicit_type)
    if norm != "auto":
        return norm

    # Directory check (e.g. mongodump directory)
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith('.bson') or f.endswith('.metadata.json'):
                    return "mongodb"
        return "unknown"

    # File checks
    ext = path.lower()
    if ext.endswith(('.sqlite', '.db', '.sqlite3')):
        return "sqlite"
    if ext.endswith('.rdb'):
        return "redis"
    if ext.endswith(('.bson', '.metadata.json')):
        return "mongodb"

    # Magic bytes check for binary formats
    try:
        with open(path, 'rb') as f:
            header = f.read(32)
            if header.startswith(b'SQLite format 3\x00'):
                return "sqlite"
            if header.startswith(b'REDIS'):
                return "redis"
            if header.startswith(b'PGDMP'):
                return "postgres"
    except Exception:
        pass

    # SQL / GZ peek
    if ext.endswith(('.sql', '.sql.gz', '.dump')):
        try:
            with open_sql_stream(path) as f:
                lines = []
                for _ in range(100):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
                content = "".join(lines).lower()
                if "postgresql database dump" in content or "copy " in content:
                    return "postgres"
                if "mysql dump" in content or "engine=" in content or "mariadb" in content:
                    return "mysql"
        except Exception:
            pass
        return "sql_generic"

    return "unknown"

# ============================================================================
# 1. SQLITE HANDLER
# ============================================================================
def inspect_sqlite(file_path: str, format_type: str = "table") -> dict:
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_list = [row[0] for row in cursor.fetchall()]
    
    table_stats = []
    total_rows = 0
    
    for t in tables_list:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM \"{t}\";")
            count = cursor.fetchone()[0]
        except Exception:
            count = 0
        total_rows += count
        
        cursor.execute(f"PRAGMA table_info(\"{t}\");")
        cols = [{"name": c[1], "type": c[2] or "TEXT", "pk": bool(c[5])} for c in cursor.fetchall()]
        table_stats.append({
            "name": t,
            "rows": count,
            "columns_count": len(cols),
            "columns": cols
        })
        
    conn.close()
    file_size = os.path.getsize(file_path)
    return {
        "file_name": os.path.basename(file_path),
        "db_type": "SQLite (.db)",
        "file_size": _format_size(file_size),
        "file_size_bytes": file_size,
        "tables_count": len(table_stats),
        "total_rows": total_rows,
        "tables": table_stats
    }

def dump_sqlite(file_path: str, out_file: str = None) -> dict:
    if not os.path.exists(file_path):
        emit_result(None, success=False, error=f"Fayl topilmadi: {file_path}")
        return
    conn = sqlite3.connect(file_path)
    if not out_file:
        base, _ = os.path.splitext(file_path)
        out_file = f"{base}_dump.sql"
    
    with open(out_file, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")
    conn.close()
    
    size = os.path.getsize(out_file)
    msg = f"✅ SQLite bazasi muvaffaqiyatli SQL ga dump qilindi: `{out_file}` ({_format_size(size)})"
    emit_result({"dump_file": out_file, "size": size}, success=True)

def query_sqlite(file_path: str, query: str, format_type: str = "table") -> dict:
    if not os.path.exists(file_path):
        emit_result(None, success=False, error=f"Fayl topilmadi: {file_path}")
        return
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
    except Exception as e:
        conn.close()
        emit_result(None, success=False, error=f"SQL Query xatosi: {str(e)}")
        return
    conn.close()

    res = {
        "query": query,
        "columns": cols,
        "row_count": len(rows),
        "rows": rows[:50]
    }
    if format_type == "json":
        emit_result(res, success=True)
        return
    
    # Mobile Card formatting for query results
    out = [f"🔍 **SQL Query Natijasi:** `{query}`"]
    out.append(f"• 📊 **Qatorlar soni:** `{len(rows)}` ta")
    out.append(f"• 🏷️ **Ustunlar:** {', '.join([f'`{c}`' for c in cols])}\n")
    out.append("📋 **Qatorlar (Top 10):**")
    for idx, r in enumerate(rows[:10], 1):
        vals = ", ".join([f"{c}={r[i]}" for i, c in enumerate(cols[:4])])
        out.append(f"{idx}. {vals}")
    if len(rows) > 10:
        out.append(f"... va yana `{len(rows) - 10}` ta qator mavjud.")
    emit_result("\n".join(out), success=True)

# ============================================================================
# 2. POSTGRESQL & MYSQL STREAM PARSER
# ============================================================================
def inspect_sql_stream_dump(file_path: str, db_flavor: str = "generic", max_tables: int = 100) -> dict:
    file_size = os.path.getsize(file_path)
    is_gzipped = file_path.endswith('.gz')
    
    tables = {}
    current_table = None
    in_copy = False
    copy_table = None
    in_insert_table = None
    
    re_create_table = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:`|"|\[)?([a-zA-Z0-9_\.]+)(?:`|"|\])?\s*\(', re.IGNORECASE)
    re_insert_into = re.compile(r'INSERT\s+INTO\s+(?:`|"|\[)?([a-zA-Z0-9_\.]+)(?:`|"|\])?', re.IGNORECASE)
    re_copy_start = re.compile(r'COPY\s+([a-zA-Z0-9_\.]+)\s*\(?.*?\)?\s+FROM\s+stdin;', re.IGNORECASE)
    
    line_count = 0
    with open_sql_stream(file_path) as f:
        for line in f:
            line_count += 1
            l_strip = line.strip()
            
            # COPY block parsing (PostgreSQL dumps)
            if in_copy:
                if l_strip == '\\.' or l_strip.startswith('\\.'):
                    in_copy = False
                    copy_table = None
                else:
                    if copy_table in tables:
                        tables[copy_table]["rows"] += 1
                continue
                
            match_copy = re_copy_start.match(l_strip)
            if match_copy:
                copy_table = match_copy.group(1).replace('"', '').replace('`', '').split('.')[-1]
                in_copy = True
                if copy_table not in tables:
                    tables[copy_table] = {"name": copy_table, "rows": 0, "columns": []}
                continue
                
            # CREATE TABLE parsing
            match_create = re_create_table.search(line)
            if match_create:
                raw_tbl = match_create.group(1).replace('"', '').replace('`', '').split('.')[-1]
                current_table = raw_tbl
                if current_table not in tables:
                    tables[current_table] = {"name": current_table, "rows": 0, "columns": []}
                continue
                
            # Columns within CREATE TABLE
            if current_table:
                if l_strip.startswith(')') or l_strip.endswith(');'):
                    current_table = None
                else:
                    col_match = re.match(r'^\s*[`"\[]?([a-zA-Z0-9_]+)[`"\]]?\s+([a-zA-Z0-9_\(\)]+)', line)
                    if col_match:
                        col_name = col_match.group(1)
                        col_type = col_match.group(2)
                        if col_name.upper() not in {'PRIMARY', 'KEY', 'CONSTRAINT', 'FOREIGN', 'UNIQUE', 'CHECK'}:
                            tables[current_table]["columns"].append({"name": col_name, "type": col_type})
                continue
                
            # INSERT INTO parsing (including multi-line batches)
            match_insert = re_insert_into.search(line)
            if match_insert:
                in_insert_table = match_insert.group(1).replace('"', '').replace('`', '').split('.')[-1]
                if in_insert_table not in tables:
                    tables[in_insert_table] = {"name": in_insert_table, "rows": 0, "columns": []}

            if in_insert_table:
                val_count = len(re.findall(r'\([^\(\)]+\)', line))
                if val_count > 0:
                    tables[in_insert_table]["rows"] += val_count
                if l_strip.endswith(';'):
                    in_insert_table = None

    table_list = list(tables.values())
    total_rows = sum(t["rows"] for t in table_list)
    table_list.sort(key=lambda x: x["rows"], reverse=True)
    
    flavor_name = "PostgreSQL" if db_flavor == "postgres" else ("MySQL / MariaDB" if db_flavor == "mysql" else "SQL Dump")
    if is_gzipped:
        flavor_name += " (Gzipped .sql.gz)"
    else:
        flavor_name += " (.sql)"
        
    return {
        "file_name": os.path.basename(file_path),
        "db_type": flavor_name,
        "file_size": _format_size(file_size),
        "file_size_bytes": file_size,
        "scanned_lines": line_count,
        "tables_count": len(table_list),
        "total_rows": total_rows,
        "tables": table_list[:max_tables]
    }

def inspect_postgres_binary(file_path: str, max_tables: int = 100) -> dict:
    """Parses PostgreSQL Custom Binary Dump (-Fc) via pg_restore Table of Contents."""
    file_size = os.path.getsize(file_path)
    pg_restore_bin = shutil.which("pg_restore") or "/usr/bin/pg_restore"
    
    tables = {}
    if os.path.exists(pg_restore_bin):
        try:
            res = subprocess.run([pg_restore_bin, "-l", file_path], capture_output=True, text=True, timeout=10)
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                # Line format: 123; 1259 16384 TABLE public users fayzillo
                parts = line.split(";")
                if len(parts) > 1:
                    info = parts[1].strip().split()
                    if len(info) >= 4 and info[2] in ["TABLE", "TABLE DATA", "VIEW", "MATERIALIZED VIEW"]:
                        tbl_name = info[4] if len(info) > 4 else info[3]
                        schema = info[3] if len(info) > 4 else "public"
                        if tbl_name not in tables:
                            tables[tbl_name] = {"name": tbl_name, "schema": schema, "rows": 0, "columns": []}
        except Exception:
            pass

    table_list = list(tables.values())
    return {
        "file_name": os.path.basename(file_path),
        "db_type": "PostgreSQL Custom Binary Dump (-Fc)",
        "file_size": _format_size(file_size),
        "file_size_bytes": file_size,
        "tables_count": len(table_list),
        "total_rows": sum(t["rows"] for t in table_list),
        "tables": table_list[:max_tables]
    }

# ============================================================================
# 3. MONGODB HANDLER (BSON & DUMP DIRECTORIES)
# ============================================================================
def inspect_bson_file(file_path: str) -> dict:
    """Fast 0-token BSON document counter by reading 4-byte LE sizes and seeking."""
    file_size = os.path.getsize(file_path)
    doc_count = 0
    with open(file_path, "rb") as f:
        while True:
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                break
            doc_size = struct.unpack("<i", size_bytes)[0]
            if doc_size < 5:
                break
            f.seek(doc_size - 4, os.SEEK_CUR)
            doc_count += 1
            
    col_name = os.path.splitext(os.path.basename(file_path))[0]
    # Check if companion metadata.json exists
    meta_path = os.path.join(os.path.dirname(file_path), f"{col_name}.metadata.json")
    indexes = []
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
                for idx in mdata.get("indexes", []):
                    idx_keys = ",".join(idx.get("key", {}).keys())
                    indexes.append(f"{idx.get('name', 'idx')}({idx_keys})")
        except Exception:
            pass

    return {
        "name": col_name,
        "rows": doc_count,
        "indexes": indexes,
        "file_size": _format_size(file_size),
        "columns": [{"name": "_id", "type": "ObjectId"}] + ([{"name": "indexes", "type": "; ".join(indexes[:3])}] if indexes else [])
    }

def inspect_mongodb(path: str, format_type: str = "table", max_tables: int = 100) -> dict:
    collections = []
    total_size = 0
    
    if os.path.isfile(path):
        c = inspect_bson_file(path)
        collections.append(c)
        total_size = os.path.getsize(path)
        base_name = os.path.basename(path)
    else:
        # Directory scan (mongodump folder)
        base_name = os.path.basename(os.path.abspath(path))
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith('.bson'):
                    fpath = os.path.join(root, f)
                    total_size += os.path.getsize(fpath)
                    collections.append(inspect_bson_file(fpath))

    total_docs = sum(c["rows"] for c in collections)
    collections.sort(key=lambda x: x["rows"], reverse=True)
    return {
        "file_name": base_name,
        "db_type": "MongoDB Dump (BSON)",
        "file_size": _format_size(total_size),
        "file_size_bytes": total_size,
        "tables_count": len(collections),
        "total_rows": total_docs,
        "tables": collections[:max_tables]
    }

# ============================================================================
# 4. REDIS HANDLER (RDB BINARY DUMP)
# ============================================================================
def _read_rdb_length(f):
    b = f.read(1)
    if not b:
        return None, False
    first = b[0]
    enc_type = (first & 0xC0) >> 6
    if enc_type == 0:
        return (first & 0x3F), False
    elif enc_type == 1:
        next_b = f.read(1)
        if not next_b:
            return None, False
        return (((first & 0x3F) << 8) | next_b[0]), False
    elif enc_type == 2:
        val = f.read(4)
        if len(val) < 4:
            return None, False
        return struct.unpack('>I', val)[0], False
    else:
        return (first & 0x3F), True

def _read_rdb_string(f):
    length, is_special = _read_rdb_length(f)
    if length is None:
        return None
    if is_special:
        if length == 0:
            b = f.read(1)
            return str(b[0]) if b else ""
        elif length == 1:
            b = f.read(2)
            return str(struct.unpack('<h', b)[0]) if len(b) == 2 else ""
        elif length == 2:
            b = f.read(4)
            return str(struct.unpack('<i', b)[0]) if len(b) == 4 else ""
        elif length == 3:
            clen, _ = _read_rdb_length(f)
            ulen, _ = _read_rdb_length(f)
            f.read(clen)
            return "<lzf_compressed>"
        return ""
    else:
        return f.read(length).decode('utf-8', errors='ignore')

def inspect_redis_rdb(file_path: str, format_type: str = "table") -> dict:
    file_size = os.path.getsize(file_path)
    aux = {}
    dbs = {}
    current_db = 0
    version = "Unknown"

    with open(file_path, 'rb') as f:
        magic = f.read(9)
        if magic.startswith(b'REDIS'):
            version = magic[5:].decode('ascii', errors='ignore')

        while True:
            b = f.read(1)
            if not b:
                break
            op = b[0]
            if op == 0xFA:  # AUX metadata
                k = _read_rdb_string(f)
                v = _read_rdb_string(f)
                if k:
                    aux[k] = v
            elif op == 0xFE:  # SELECTDB
                db_num, _ = _read_rdb_length(f)
                current_db = db_num
            elif op == 0xFB:  # RESIZEDB (keys count)
                db_size, _ = _read_rdb_length(f)
                exp_size, _ = _read_rdb_length(f)
                dbs[current_db] = {'name': f"db{current_db}", 'rows': db_size, 'expires': exp_size, 'columns': [{'name': 'keys', 'type': str(db_size)}, {'name': 'expires', 'type': str(exp_size)}]}
            elif op == 0xFF:  # EOF
                break

    db_list = list(dbs.values())
    total_keys = sum(d['rows'] for d in db_list)
    
    meta_info = []
    if "redis-ver" in aux:
        meta_info.append(f"v{aux['redis-ver']}")
    if "used-mem" in aux:
        try:
            meta_info.append(f"Mem: {_format_size(int(aux['used-mem']))}")
        except Exception:
            pass

    return {
        "file_name": os.path.basename(file_path),
        "db_type": f"Redis RDB Dump ({', '.join(meta_info) or version})",
        "file_size": _format_size(file_size),
        "file_size_bytes": file_size,
        "tables_count": len(db_list),
        "total_rows": total_keys,
        "tables": db_list
    }

# ============================================================================
# MAIN ENTRY POINTS
# ============================================================================
def inspect_db_file(file_path: str, db_type: str = "auto", format_type: str = "table", max_tables: int = 50):
    emit_progress("Inspect DB", 20, f"Baza zaxirasi tahlil qilinmoqda: {os.path.basename(file_path)}")
    
    if not os.path.exists(file_path):
        emit_result(None, success=False, error=f"Fayl topilmadi: {file_path}")
        return
        
    resolved_type = detect_db_type(file_path, explicit_type=db_type)
    
    if resolved_type == "sqlite":
        data = inspect_sqlite(file_path, format_type)
    elif resolved_type == "mongodb":
        data = inspect_mongodb(file_path, format_type, max_tables)
    elif resolved_type == "redis":
        data = inspect_redis_rdb(file_path, format_type)
    elif resolved_type == "postgres":
        if os.path.isfile(file_path) and not file_path.endswith(('.sql', '.sql.gz')):
            data = inspect_postgres_binary(file_path, max_tables)
        else:
            data = inspect_sql_stream_dump(file_path, db_flavor="postgres", max_tables=max_tables)
    elif resolved_type == "mysql":
        data = inspect_sql_stream_dump(file_path, db_flavor="mysql", max_tables=max_tables)
    else:
        # Default fallback stream parser
        data = inspect_sql_stream_dump(file_path, db_flavor="generic", max_tables=max_tables)

    emit_progress("Inspect DB", 90, "Formatlash yakunlanmoqda")
    
    if format_type == "json":
        emit_result(data, success=True)
        return
        
    # Mobile Card format
    out = []
    out.append(f"📦 **DB Backup Tahlili: `{data['file_name']}`**")
    out.append(f"• 🏷️ **Turi:** {data['db_type']}")
    out.append(f"• 💾 **Hajmi:** `{data['file_size']}`")
    if 'scanned_lines' in data:
        out.append(f"• 📑 **Qatorlar soni:** `{data['scanned_lines']:,}` qator")
    out.append(f"• 🗄️ **Jadvallar / Kolleksiyalar soni:** `{data['tables_count']}` ta")
    out.append(f"• 📊 **Taxminiy yozuvlar (Rows/Keys/Docs):** `{data['total_rows']:,}` ta\n")
    
    unit_title = "Kolleksiyalar / Jadvallar" if resolved_type == "mongodb" else ("Keyspaces / DBs" if resolved_type == "redis" else "Asosiy Jadvallar (Top Tables)")
    out.append(f"📋 **{unit_title}:**")
    
    for idx, t in enumerate(data['tables'][:15], 1):
        cols_summary = ", ".join([f"`{c['name']}`" for c in t.get('columns', [])[:4]])
        if len(t.get('columns', [])) > 4:
            cols_summary += f" (+{len(t['columns']) - 4})"
        out.append(f"{idx}. 🗂️ **`{t['name']}`**: `{t['rows']:,}` qator/element | Ustunlar: {cols_summary or '(N/A)'}")
        
    if len(data['tables']) > 15:
        out.append(f"\n... va yana `{len(data['tables']) - 15}` ta boshqa modellar/jadvallar mavjud.")
        
    result_text = "\n".join(out)
    emit_result(result_text, success=True)

def list_tables(file_path: str, db_type: str = "auto", format_type: str = "table"):
    inspect_db_file(file_path, db_type=db_type, format_type=format_type, max_tables=250)

def run_db_query(file_path: str, query: str, db_type: str = "auto", format_type: str = "table"):
    resolved_type = detect_db_type(file_path, explicit_type=db_type)
    if resolved_type == "sqlite":
        query_sqlite(file_path, query, format_type=format_type)
    else:
        emit_result(None, success=False, error=f"To'g'ridan-to'g'ri 'query' buyrug'i hozirda SQLite bazalari uchun faol. Katta SQL ({resolved_type}) damplar ustida so'rov bajarish uchun avval uni live bazaga yoki SQLite ga import qilish tavsiya etiladi.")

def run_db_dump(file_path: str, out_file: str = None, db_type: str = "auto"):
    resolved_type = detect_db_type(file_path, explicit_type=db_type)
    if resolved_type == "sqlite":
        dump_sqlite(file_path, out_file=out_file)
    else:
        emit_result(None, success=False, error=f"Dump buyrug'i SQLite (.db) fayllarini .sql ga aylantirish uchun mo'ljallangan. Ushbu fayl turi: {resolved_type}")
