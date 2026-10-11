"""Accelerated model downloader core for ComfyUI.

Downloads models with aria2 multi-threaded mode (+ hf-mirror mirroring),
batch queue support, resume support and disk-space preflight.

Public API:
  - find_aria2()          -> path or None
  - mirror_urls(url)      -> [candidate urls]
  - check_disk_space(dir, size_gb) -> raises InsufficientDisk
  - download_manifest(manifest, report) -> downloads every entry, fills report
  - single_download(entry, report)    -> one entry

Manifest entry format (JSON array or object with "files"):
  {"name": "<filename>", "url": "<download url>", "directory": "<model subdir>",
   "size_gb": <optional expected size for skip/space check>}
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import urllib.parse

try:
    import folder_paths  # type: ignore
except ImportError:  # standalone / unit-test mode
    folder_paths = None

MODELS_DIR = "models"
HF_HOSTS = ("https://huggingface.co/", "http://huggingface.co/")
HF_MIRROR = "https://hf-mirror.com/"

# aria2 is the only real dependency; everything else is stdlib.
KNOWN_ARIA2 = [
    "aria2c",
    r"C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\aria2.aria2_Microsoft.Winget.Source_8wekyb3d8bbwe\aria2-1.37.0-win-64bit-build1\aria2c.exe",
]


class DownloadError(Exception):
    """Raised when a download fails or a preflight check fails."""


class InsufficientDisk(DownloadError):
    """Raised when the target drive lacks space for the planned downloads."""


def find_aria2() -> str | None:
    """Locate aria2c: PATH first, then well-known fallback paths."""
    for cand in KNOWN_ARIA2:
        if os.path.isabs(cand):
            if os.path.isfile(cand):
                return cand
            continue
        found = shutil.which(cand)
        if found:
            return found
    return None


def resolve_models_root() -> str:
    """Return the ComfyUI models root (folder_paths when embedded, else cwd/models)."""
    if folder_paths is not None:
        return folder_paths.models_dir
    return os.path.join(os.getcwd(), MODELS_DIR)


def mirror_urls(url: str) -> list[str]:
    """Return download candidates, fastest-first. For HF URLs we add the
    hf-mirror twin so aria2 can race both sources and pick the faster one.
    Non-HF URLs are returned unchanged (aria2 still multithreads them)."""
    candidates = [url]
    for host in HF_HOSTS:
        if url.startswith(host):
            candidates.append(HF_MIRROR + url[len(host):])
            break
    # de-dup, keep original first
    return list(dict.fromkeys(candidates))


def check_disk_space(target_dir: str, size_gb: float) -> float:
    """Raise InsufficientDisk when < size_gb will not fit on target_dir's drive.
    Returns free GB remaining after the download."""
    if size_gb <= 0:
        return float("inf")
    target_dir = target_dir or "."
    try:
        free = shutil.disk_usage(target_dir).free / (1024 ** 3)
    except OSError as exc:
        raise DownloadError(f"無法檢查磁碟空間: {target_dir}: {exc}") from exc
    if free < size_gb:
        raise InsufficientDisk(
            f"磁碟空間不足: 需要 {size_gb:.2f} GB，{target_dir} 所在磁碟僅剩 {free:.2f} GB。"
            f"請清理空間或改放其他磁碟。"
        )
    return free - size_gb


def _expected_target(entry: dict) -> tuple[str, str]:
    """Map a manifest entry to (absolute target dir, filename)."""
    name = entry.get("name") or entry.get("file_name")
    directory = entry.get("directory") or ""
    if not name:
        raise DownloadError(f"清單項目缺少 name/file_name: {entry}")
    root = resolve_models_root()
    target_dir = os.path.join(root, directory) if directory else root
    return target_dir, name


def _size_matches(path: str, size_gb: float | None, tolerance: float = 0.02) -> bool:
    """Existing file counts as downloaded when its size matches the expected one."""
    if size_gb is None:
        return os.path.getsize(path) > 0
    expected = size_gb * 1024 ** 3
    actual = os.path.getsize(path)
    return abs(actual - expected) <= expected * tolerance


def single_download(entry: dict, report: list, aria2: str | None = None,
                    skip_existing: bool = True, workers: int = 16) -> str:
    """Download one manifest entry; append a status line to `report`.
    Returns 'ok' | 'skipped' | 'failed'."""
    aria2 = aria2 or find_aria2()
    if not aria2:
        raise DownloadError("找不到 aria2c，請先安裝 aria2（winget install aria2.aria2）")

    target_dir, name = _expected_target(entry)
    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, name)
    size_gb = entry.get("size_gb")

    if skip_existing and os.path.isfile(dest) and _size_matches(dest, size_gb):
        report.append(f"[SKIP] {name} 已存在，跳過")
        return "skipped"

    size_for_check = size_gb or entry.get("size", 0) / (1024 ** 3)
    try:
        check_disk_space(target_dir, size_for_check)
    except InsufficientDisk as exc:
        report.append(f"[FAIL] {name}: {exc}")
        raise

    # resume via -c; race mirror candidates via aria2 URL list
    cmd = [aria2, "-x", str(workers), "-s", str(workers), "-c",
           "--dir", target_dir, "--out", name,
           "--continue=true", "--auto-file-renaming=false",
           "--max-tries=5", "--retry-wait=3"]
    cmd += mirror_urls(entry["url"])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        report.append(f"[FAIL] {name}: aria2 退出碼 {proc.returncode} ({' / '.join(tail)})")
        return "failed"
    report.append(f"[OK] {name} -> {dest}")
    return "ok"


def download_manifest(manifest: dict | list, report: list,
                      aria2: str | None = None, skip_existing: bool = True) -> dict:
    """Batch download. `manifest` is either a list of entries or
    {"files": [...], ...}. Preflights total disk usage upfront, then
    downloads serially. Returns a summary dict."""
    files = manifest.get("files") if isinstance(manifest, dict) else manifest
    if not isinstance(files, list) or not files:
        raise DownloadError("清單為空或格式不正確（需要 files 列表）")

    # group by target dir for per-drive space preflight
    total_by_dir: dict[str, float] = {}
    for entry in files:
        target_dir, _ = _expected_target(entry)
        total_by_dir[target_dir] = total_by_dir.get(target_dir, 0) + (entry.get("size_gb") or 0)

    for target_dir, size in total_by_dir.items():
        check_disk_space(target_dir, size)

    summary = {"ok": 0, "skipped": 0, "failed": 0}
    for entry in files:
        status = single_download(entry, report, aria2=aria2, skip_existing=skip_existing)
        summary[status] += 1
    return summary


# ---- async task tracking for the HTTP API --------------------------------
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


def start_task(manifest: dict | list) -> str:
    """Run a batch download in a background thread; returns a task id."""
    task_id = urllib.parse.quote(os.urandom(4).hex(), safe="")
    state = {"id": task_id, "status": "running", "report": [],
             "summary": {}, "error": None}
    with _tasks_lock:
        _tasks[task_id] = state

    def _run():
        try:
            state["summary"] = download_manifest(manifest, state["report"])
            state["status"] = "done"
        except InsufficientDisk as exc:
            state["status"] = "blocked"
            state["error"] = str(exc)
        except DownloadError as exc:
            state["status"] = "error"
            state["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 - surface any backend failure
            state["status"] = "error"
            state["error"] = f"{type(exc).__name__}: {exc}"

    threading.Thread(target=_run, daemon=True).start()
    return task_id


def get_task(task_id: str) -> dict | None:
    with _tasks_lock:
        return _tasks.get(task_id)


def load_manifest(path: str) -> dict | list:
    """Load a manifest JSON file (list or {"files": [...]})."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "files" not in data and "download_list" in data:
        # comfyui_template_analysis.json style: extract the list
        data = {"files": data["download_list"]}
    return data
