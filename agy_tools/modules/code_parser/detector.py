import os
import sys
import json
import re
from typing import Dict, Any, List, Optional

def detect_framework(root_dir: str) -> Dict[str, Any]:
    """
    Detect tech stack, language, framework and entry points by reading
    project manifests and root directory structures.
    """
    abs_root = os.path.abspath(os.path.expanduser(root_dir))
    info: Dict[str, Any] = {
        "type": "Unknown",
        "language": "Unknown",
        "entry_points": [],
        "main": ""
    }

    if not os.path.isdir(abs_root):
        return info

    # 1. JavaScript / TypeScript (package.json)
    pkg_json_path = os.path.join(abs_root, "package.json")
    if os.path.isfile(pkg_json_path):
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    deps = {}
                    for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
                        sub_deps = data.get(dep_key, {})
                        if isinstance(sub_deps, dict):
                            deps.update(sub_deps)

                    has_ts = (
                        "typescript" in deps
                        or any(k.startswith("@types/") for k in deps)
                        or os.path.isfile(os.path.join(abs_root, "tsconfig.json"))
                    )
                    info["language"] = "TypeScript" if has_ts else "JavaScript"

                    if "@angular/core" in deps or "angular" in str(deps).lower():
                        info["type"] = "Angular"
                    elif "@nestjs/core" in deps:
                        info["type"] = "NestJS"
                    elif "next" in deps or "react" in deps:
                        info["type"] = "React / Next.js"
                    elif "express" in deps:
                        info["type"] = "Express"
                    elif "fastify" in deps:
                        info["type"] = "Fastify"
                    elif "koa" in deps:
                        info["type"] = "Koa"
                    else:
                        info["type"] = "Node.js"

                    main_field = data.get("main", "")
                    if main_field:
                        info["main"] = main_field
                        main_abs = os.path.join(abs_root, main_field)
                        if os.path.exists(main_abs):
                            info["entry_points"].append(os.path.abspath(main_abs))
                    return info
        except Exception:
            pass

    # 2. Python (requirements.txt, pyproject.toml, Pipfile, setup.py)
    python_manifests = ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]
    has_py_manifest = any(os.path.isfile(os.path.join(abs_root, m)) for m in python_manifests)
    if has_py_manifest:
        info["language"] = "Python"
        combined_text = ""
        for m in python_manifests:
            m_path = os.path.join(abs_root, m)
            if os.path.isfile(m_path):
                try:
                    with open(m_path, "r", encoding="utf-8", errors="ignore") as f:
                        combined_text += " " + f.read().lower()
                except Exception:
                    pass

        if "fastapi" in combined_text:
            info["type"] = "FastAPI"
        elif "django" in combined_text:
            info["type"] = "Django"
        elif "flask" in combined_text:
            info["type"] = "Flask"
        elif "tornado" in combined_text:
            info["type"] = "Tornado"
        elif "aiohttp" in combined_text:
            info["type"] = "aiohttp"
        else:
            info["type"] = "Python App"

        for candidate in ["main.py", "app.py", "manage.py", "wsgi.py"]:
            c_path = os.path.join(abs_root, candidate)
            if os.path.isfile(c_path):
                info["entry_points"].append(os.path.abspath(c_path))
                if not info["main"]:
                    info["main"] = candidate
        return info

    # 3. Go (go.mod)
    go_mod_path = os.path.join(abs_root, "go.mod")
    if os.path.isfile(go_mod_path):
        info["language"] = "Go"
        content = ""
        try:
            with open(go_mod_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
        except Exception:
            pass

        if "github.com/gin-gonic/gin" in content:
            info["type"] = "Gin"
        elif "github.com/gofiber/fiber" in content:
            info["type"] = "Fiber"
        elif "github.com/go-chi/chi" in content:
            info["type"] = "Chi"
        elif "github.com/labstack/echo" in content:
            info["type"] = "Echo"
        else:
            info["type"] = "Go App"

        main_go = os.path.join(abs_root, "main.go")
        if os.path.isfile(main_go):
            info["entry_points"].append(os.path.abspath(main_go))
            info["main"] = "main.go"
        return info

    # 4. PHP (composer.json or artisan)
    composer_path = os.path.join(abs_root, "composer.json")
    artisan_path = os.path.join(abs_root, "artisan")
    if os.path.isfile(composer_path) or os.path.isfile(artisan_path):
        info["language"] = "PHP"
        content = ""
        if os.path.isfile(composer_path):
            try:
                with open(composer_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
            except Exception:
                pass

        if os.path.isfile(artisan_path) or "laravel/framework" in content:
            info["type"] = "Laravel"
            if os.path.isfile(artisan_path):
                info["entry_points"].append(os.path.abspath(artisan_path))
                info["main"] = "artisan"
        elif "symfony/framework-bundle" in content:
            info["type"] = "Symfony"
        elif "slim/slim" in content:
            info["type"] = "Slim"
        else:
            info["type"] = "PHP App"
        return info

    # 5. C / C++ (CMakeLists.txt, Makefile, meson.build)
    c_manifests = ["CMakeLists.txt", "Makefile", "meson.build", "compile_commands.json"]
    if any(os.path.isfile(os.path.join(abs_root, m)) for m in c_manifests):
        info["language"] = "C/C++"
        info["type"] = "C/C++ App"
        for candidate in ["main.cpp", "main.c", "app.cpp", "app.c"]:
            c_path = os.path.join(abs_root, candidate)
            if os.path.isfile(c_path):
                info["entry_points"].append(os.path.abspath(c_path))
                info["main"] = candidate
        return info

    return info

