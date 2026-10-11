<p align="center">
  <img src="assets/banner.png" alt="ComfyUI Accelerated Downloader" width="100%">
</p>

<h1 align="center">⚡ ComfyUI Accelerated Downloader</h1>

<p align="center">
  <b>Turn a 30-minute model download into a 2-minute one.</b><br>
  <b>把 30 分鐘的模型下載變成 2 分鐘。</b><br>
  Deploying ComfyUI means pulling down <b>hundreds of GB</b> of models — and the
  official downloader is painfully slow. This accelerator fixes that.<br>
  部署 ComfyUI 需要下載數百 GB 的模型檔，官方下載器卻慢得令人絕望——本加速器就是為了解決這個問題而生。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/speed-~200_MB/s-22d3ee" alt="speed">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license">
  <img src="https://img.shields.io/badge/platform-Windows-38bdf8" alt="platform">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="python">
  <img src="https://img.shields.io/badge/deps-aria2_only-orange" alt="deps">
</p>

> 中文簡介：ComfyUI 部署需要下載大量模型檔，官方下載速度極慢，作者因此開發了這個加速器——aria2 16 路並發、雙鏡像競速、斷點續傳、批量下載、磁碟預檢與自動歸位，直接嵌入 ComfyUI。

---

## 🚀 Install 安裝

> ⚠️ **以系統管理員身分執行 PowerShell ／ Run PowerShell as Administrator**
>
> 在開始功能表搜尋 **PowerShell**，對其按右鍵 → 選 **「以系統管理員身分執行」**，再執行下列指令。
> 安裝程序需要系統權限（自動安裝 aria2、寫入 custom_nodes）。若跳過此步驟，安裝可能因權限不足而失敗。
>
> Search for **PowerShell** in the Start menu, right-click it → **"Run as administrator"**, then run the commands below. The installer needs system privileges (auto-installing aria2, writing to custom_nodes); skipping this step may cause permission errors.

```powershell
.\install.ps1                  # auto-detects D:\ComfyUI, installs aria2 if missing
                              # 自動偵測 D:\ComfyUI，缺 aria2 時自動安裝
.\install.ps1 -Root <path>     # or point it at your ComfyUI root / 或指定你的 ComfyUI 路徑
# restart ComfyUI / 重啟 ComfyUI 即可生效
```

Manual install 手動安裝：copy this folder to `<ComfyUI>\custom_nodes\ComfyUI_Accelerated_Downloader` and make sure `aria2c` is on PATH (`winget install aria2.aria2`).
手動安裝：把本資料夾複製到 `<ComfyUI>\custom_nodes\ComfyUI_Accelerated_Downloader`，並確認 `aria2c` 已加入 PATH（`winget install aria2.aria2`）。

## 📊 Why it's fast 為什麼快

<img src="assets/speed.svg" alt="Download speed comparison" width="100%">

- **16× multithreading** via aria2 ／ 透過 aria2 的 16 路多執行緒
- **Mirror racing** — every HF URL also gets an `hf-mirror.com` twin, aria2 uses the faster one ／ 每個 HF 連結同時競速原始源與 `hf-mirror.com` 鏡像，自動選快
- **Resume-safe** (`-c`) + **size-verified skip** of existing files ／ 斷點續傳 + 已存在檔案按大小比對跳過

## ✨ What you get 功能一覽

<img src="assets/features.svg" alt="Feature highlights" width="100%">

## 🧭 Usage 使用方式

**As a node 節點方式** — search 「加速模型下載」 (category `utils/下載加速`), feed it a manifest JSON path, done. Disk preflight runs first.
在節點清單搜尋「加速模型下載」（分類 `utils/下載加速`），輸入模型清單 JSON 路徑即可執行；磁碟空間會先預檢。

**As an API 介面方式** — async & pollable ／ 非同步且可輪詢進度：

| Endpoint 端點 | Purpose 用途 |
|---|---|
| `POST /api/accelerated-download/check` | preflight: per-drive need / free GB ／ 空間預檢：各磁碟需要 / 剩餘 GB |
| `POST /api/accelerated-download/start` | start a batch → `task_id` ／ 開始批量下載 → `task_id` |
| `GET  /api/accelerated-download/status?task_id=...` | poll progress ／ 查詢進度 |

**Manifest format 清單格式**

```json
{ "files": [ { "name": "sd_xl_base_1.0.safetensors",
               "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
               "directory": "checkpoints", "size_gb": 6.46 } ] }
```

`directory` = subfolder under `models/` ／ `models/` 底下的子資料夾。Also compatible with `comfyui_template_analysis.json` ／ 也相容 `comfyui_template_analysis.json`。

## 💬 FAQ 常見問題

<details>
<summary>Does it work for non-HuggingFace URLs? ／ 非 HuggingFace 的連結可以用嗎？</summary>
Yes — multithreading and resume still apply; only mirror racing is HF-specific.
可以——多執行緒與續傳依然生效，只有雙鏡像競速是 HF 限定。
</details>

<details>
<summary>Can it download gated / signed URLs? ／ 可以下載需要登入或一次性簽名的連結嗎？</summary>
No — aria2 can't authenticate. Resolve a valid direct URL first.
不行——aria2 無法鑑權，請先取得有效的直鏈。
</details>

<details>
<summary>Requirements? ／ 有什麼需求？</summary>
aria2 only (auto-installed), Windows PowerShell, ComfyUI.
只需要 aria2（自動安裝）、Windows PowerShell 與 ComfyUI。
</details>

## 📄 License 授權

MIT
