import os
import subprocess
from typing import List, Optional, Set

DEFAULT_IGNORED_DIRS = [
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".agents", ".angular", "vendor", "venv", ".venv", ".cache",
    ".idea", ".vscode", "coverage", ".turbo"
]

DEFAULT_IGNORED_EXTS = {
    ".min.js", ".bundle.js", ".d.ts", ".map", ".pyc"
}

def _normalize_extensions(extensions: Optional[List[str]]) -> Optional[Set[str]]:
    if not extensions:
        return None
    normalized = set()
    for ext in extensions:
        ext_clean = ext.strip().lower()
        if not ext_clean.startswith("."):
            ext_clean = "." + ext_clean
        normalized.add(ext_clean)
    return normalized

def _is_file_ignored(filepath: str, ignored_exts: Set[str]) -> bool:
    fname = os.path.basename(filepath).lower()
    for ie in ignored_exts:
        if fname.endswith(ie):
            return True
    return False

def _find_via_subprocess(
    abs_root: str,
    normalized_exts: Optional[Set[str]],
    max_files: int,
    ignored_dirs: List[str],
    ignored_exts: Set[str]
) -> Optional[List[str]]:
    """Runs high-performance Linux find command with directory pruning."""
    try:
        # Build prune clause for ignored directories
        prune_parts = []
        for i, idir in enumerate(ignored_dirs):
            if i > 0:
                prune_parts.append("-o")
            prune_parts.extend(["-name", idir])

        cmd = ["find", abs_root, "-type", "d", "(", *prune_parts, ")", "-prune", "-o", "-type", "f"]

        if normalized_exts:
            ext_parts = []
            for i, ext in enumerate(normalized_exts):
                if i > 0:
                    ext_parts.append("-o")
                ext_parts.extend(["-name", f"*{ext}"])
            cmd.extend(["(", *ext_parts, ")"])

        cmd.append("-print")

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False
        )
        if proc.returncode != 0:
            return None

        results = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            abs_path = os.path.abspath(line)
            if not _is_file_ignored(abs_path, ignored_exts):
                results.append(abs_path)
                if len(results) >= max_files:
                    break
        return results
    except Exception:
        return None

def _find_via_walk(
    abs_root: str,
    normalized_exts: Optional[Set[str]],
    max_files: int,
    ignored_dirs_set: Set[str],
    ignored_exts: Set[str]
) -> List[str]:
    """Fallback directory walker using pure Python os.walk."""
    results = []
    for root, dirs, files in os.walk(abs_root, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if d not in ignored_dirs_set and not d.startswith(".git")]
        for file in files:
            abs_path = os.path.abspath(os.path.join(root, file))
            if _is_file_ignored(abs_path, ignored_exts):
                continue

            if normalized_exts is not None:
                _, ext = os.path.splitext(file.lower())
                if ext not in normalized_exts:
                    continue

            results.append(abs_path)
            if len(results) >= max_files:
                return results
    return results

def find_files(
    root_dir: str,
    extensions: Optional[List[str]] = None,
    max_files: int = 5000,
    ignored_dirs: Optional[List[str]] = None
) -> List[str]:
    """
    High-performance file discovery returning absolute paths.
    Uses Linux find with pruning where available, with graceful fallback to os.walk.
    """
    abs_root = os.path.abspath(os.path.expanduser(root_dir))
    norm_exts = _normalize_extensions(extensions)
    active_ignored_dirs = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS

    if os.path.isfile(abs_root):
        if _is_file_ignored(abs_root, DEFAULT_IGNORED_EXTS):
            return []
        if norm_exts is not None:
            _, ext = os.path.splitext(abs_root.lower())
            if ext not in norm_exts:
                return []
        return [abs_root]

    if not os.path.isdir(abs_root):
        return []

    # Attempt fast find via subprocess
    sub_results = _find_via_subprocess(
        abs_root, norm_exts, max_files, active_ignored_dirs, DEFAULT_IGNORED_EXTS
    )
    if sub_results is not None:
        return sub_results

    # Fallback to pure Python os.walk
    ignored_dirs_set = set(active_ignored_dirs)
    return _find_via_walk(
        abs_root, norm_exts, max_files, ignored_dirs_set, DEFAULT_IGNORED_EXTS
    )
