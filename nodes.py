"""ComfyUI nodes for accelerated model downloads.

Exposes one node, AcceleratedModelDownloader, plus three HTTP endpoints:

  POST /api/accelerated-download/check   preflight disk space
  POST /api/accelerated-download/start   start a batch download (async)
  GET  /api/accelerated-download/status  poll task progress

A manifest is a JSON file with either a plain list of entries or
{"files": [...]} (also accepts comfyui_template_analysis.json directly,
extracting its download_list). Entry fields:
  name, url, directory, size_gb
"""
from __future__ import annotations

import json

from . import core

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


class AcceleratedModelDownloader:
    """Batch-download missing models with aria2 multithreading + mirror racing.

    Feed it a manifest JSON path; it preflights disk space, skips files that
    already exist, downloads everything with resume support, and reports.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "manifest_path": ("STRING", {"default": "", "placeholder": "模型清單 JSON 路徑"}),
                "auto_skip_existing": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    FUNCTION = "run"
    CATEGORY = "utils/下載加速"

    def run(self, manifest_path: str, auto_skip_existing: bool = True) -> tuple[str]:
        if not manifest_path or not manifest_path.strip():
            return ("請填寫模型清單 JSON 路徑（files 列表或含 download_list 的分析報告）。",)
        if not core.find_aria2():
            return ("找不到 aria2c。請先安裝：winget install aria2.aria2，然後重啟 ComfyUI。",)
        try:
            manifest = core.load_manifest(manifest_path.strip())
        except (OSError, ValueError) as exc:
            return (f"讀取清單失敗: {exc}",)
        report: list[str] = []
        try:
            summary = core.download_manifest(manifest, report, skip_existing=auto_skip_existing)
        except core.InsufficientDisk as exc:
            return (f"[空間不足] {exc}\n請先清理磁碟或調整清單後再執行。",)
        except core.DownloadError as exc:
            return (f"[失敗] {exc}",)
        head = f"下載完成：成功 {summary['ok']} / 跳過 {summary['skipped']} / 失敗 {summary['failed']}"
        return ("\n".join([head] + report),)


NODE_CLASS_MAPPINGS["AcceleratedModelDownloader"] = AcceleratedModelDownloader
NODE_DISPLAY_NAME_MAPPINGS["AcceleratedModelDownloader"] = "加速模型下載（批量）"


# ---- HTTP endpoints -------------------------------------------------------
def _register_routes() -> None:
    try:
        from server import PromptServer  # type: ignore
        from aiohttp import web
    except ImportError:
        return  # endpoints optional when running outside the ComfyUI server

    routes = PromptServer.instance.routes

    @routes.post("/api/accelerated-download/check")
    async def check_space(request):
        try:
            body = await request.json()
            manifest = core.load_manifest(body.get("manifest_path", "")) if body.get("manifest_path") else body.get("files", [])
            files = manifest["files"] if isinstance(manifest, dict) else manifest
            if not isinstance(files, list):
                return web.json_response({"ok": False, "error": "清單格式不正確"}, status=400)
            need = sum((f.get("size_gb") or 0) for f in files)
            by_dir: dict[str, float] = {}
            for f in files:
                target = core._expected_target(f)[0]
                by_dir[target] = by_dir.get(target, 0) + (f.get("size_gb") or 0)
            result = {"ok": True, "need_gb": round(need, 2), "dirs": []}
            for target_dir, size in by_dir.items():
                try:
                    remaining = core.check_disk_space(target_dir, size)
                    result["dirs"].append({"dir": target_dir, "need_gb": round(size, 2),
                                           "free_gb": round(remaining + size, 2)})
                except core.InsufficientDisk as exc:
                    result.update({"ok": False, "blocked": str(exc)})
            return web.json_response(result)
        except Exception as exc:  # noqa: BLE001
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.post("/api/accelerated-download/start")
    async def start_download(request):
        try:
            body = await request.json()
            manifest = core.load_manifest(body.get("manifest_path", "")) if body.get("manifest_path") else body.get("files", [])
            task_id = core.start_task(manifest)
            return web.json_response({"ok": True, "task_id": task_id})
        except Exception as exc:  # noqa: BLE001
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.get("/api/accelerated-download/status")
    async def task_status(request):
        task_id = request.query.get("task_id", "")
        state = core.get_task(task_id)
        if state is None:
            return web.json_response({"ok": False, "error": "找不到任務"}, status=404)
        return web.json_response({"ok": True, "status": state["status"],
                                  "report": state["report"], "summary": state["summary"],
                                  "error": state["error"]})


_register_routes()
