# ⚡ ComfyUI Accelerated Downloader

**Turn a 30-minute ComfyUI model download into a 2-minute one.**

Real-world result from the project's reference machine (HF direct):
**~200 MB/s sustained** with 16-way multithreading + automatic mirror racing,
**zero failed downloads** across a 100-file / 732 GB batch.

> 中文簡介：ComfyUI 部署需要下載大量模型檔，官方下載速度極慢，作者因此開發了這個加速器——內建 aria2 16 路並發、HF/hf-mirror 雙鏡像自動競速、斷點續傳、批量下載、磁碟空間預檢與自動歸位，安裝後直接嵌入 ComfyUI，缺模型時不再走官方慢速下載。

---

## The problem — and why I built this

**Deploying ComfyUI means downloading a huge amount of model files.** Checkpoints,
VAEs, text encoders, LoRAs, controlnets — each easily 6–30+ GB, and a complete
template suite needs **hundreds of GB** just to get started.

**The official downloader is painfully slow**: single-connection, no
multithreading, no mirror fallback, no resume. A single 6 GB checkpoint can
take **hours**; a full deployment takes days — downloads frequently die at 90%,
and you only find out the disk is full halfway through a 30 GB fetch.

**That's exactly why I wrote this.** An accelerator that lives inside ComfyUI
and turns those huge downloads into a fast, reliable, safe batch operation —
instead of babysitting the official downloader all day.

| | Official single-thread download | **This tool** |
|---|---|---|
| Speed | ~0.4–0.6 MB/s | **190–230 MB/s** (aria2 16× + mirror racing) |
| Interrupted download | ❌ restart from zero | ✅ resume anywhere (`-c`) |
| Batch download | ❌ manual, one by one | ✅ one manifest → full queue |
| Disk-space preflight | ❌ discover mid-download | ✅ checked *before* it starts |
| Already-downloaded files | ❌ re-download | ✅ size-verified skip |
| File placement | ❌ manual moves | ✅ auto-placed in the right model folder |

## Features

- **16× multithreaded downloads** — powered by aria2 (`-x16 -s16 -c`)
- **Automatic mirror racing** — every HuggingFace URL gets an `hf-mirror.com`
  twin; aria2 races both sources and uses whichever is faster
- **Resume-safe** — interrupted transfers continue, never restart from zero
- **Batch downloads** — feed a manifest JSON with N files; a reliable queue
  processes them all, one status line per file
- **Disk-space preflight** — the batch **refuses to start** with a clear
  message when the target drive cannot fit it (per-drive check)
- **Auto-placement** — files land in `models/<subfolder>` automatically and
  respect ComfyUI `extra_model_paths.yaml` (e.g. an E-drive model mapping)
- **Skip existing** — files already present (size-verified) are never re-downloaded
- **Embedded in ComfyUI** — available as a custom node **and** as an async HTTP API
- **Zero Python dependencies** — Python stdlib + aria2 only

## Install (Windows)

```powershell
# from the unpacked folder
.\install.ps1                 # auto-detects D:\ComfyUI; installs aria2 if missing
.\install.ps1 -Root <path>    # or point it at your ComfyUI root
# restart ComfyUI
```

Manual: copy this folder to `<ComfyUI>\custom_nodes\ComfyUI_Accelerated_Downloader`
and make sure `aria2c` is on PATH (`winget install aria2.aria2`).

## Usage

### 1. As a ComfyUI node

Search **「加速模型下載」** (category `utils/下載加速`) → node
`AcceleratedModelDownloader`. Enter the path to a manifest JSON and run.
Disk preflight runs first — if space is insufficient the node returns a clear
message instead of starting a doomed download.

### 2. As an HTTP API (async, pollable)

| Endpoint | Purpose |
|---|---|
| `POST /api/accelerated-download/check` | preflight: per-drive need / free GB |
| `POST /api/accelerated-download/start` | start a batch in background → `task_id` |
| `GET  /api/accelerated-download/status?task_id=...` | poll progress (`running` / `done` / `blocked` / `error`) |

Insufficient disk → `check` returns `blocked`; a `start`ed task ends `blocked`
with the reason. Preflight always happens before any download.

## Manifest format

```json
{
  "files": [
    {
      "name": "sd_xl_base_1.0.safetensors",
      "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
      "directory": "checkpoints",
      "size_gb": 6.46
    }
  ]
}
```

- `directory` = subfolder under `models/` (checkpoints, diffusion_models, vae,
  text_encoders, controlnet, loras, …)
- `size_gb` enables skip-verification and disk preflight — fill it in
- Also compatible with `comfyui_template_analysis.json` (its `download_list`
  is read automatically)

## FAQ

**Does it work for non-HuggingFace URLs?**
Yes — multithreading and resume still apply; only mirror racing is HF-specific.

**Can it download gated / one-time-signed URLs?**
No. aria2 cannot authenticate, so resolve a valid, accessible direct URL first.

**What are the requirements?**
aria2 only (the installer fetches it automatically), Windows PowerShell,
ComfyUI with custom-node support.

## License

[MIT](LICENSE)
