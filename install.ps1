# ============================================================
# install.ps1 — 將「加速下載」嵌入 ComfyUI
# 用法：在 comfyui_accelerated_downloader 資料夾內執行
#   .\install.ps1                    # 自動偵測 D:\ComfyUI
#   .\install.ps1 -Root D:\ComfyUI   # 指定安裝根目錄
# 作用：
#   1) 複製本節點到 <Root>\custom_nodes\ComfyUI_Accelerated_Downloader
#   2) 若無 aria2c 自動用 winget 安裝 aria2（多執行緒下載引擎）
#   3) 驗證檔案齊全
# ============================================================

param(
    [string]$Root = ""
)

$ErrorActionPreference = "Continue"

# ---- 定位 ComfyUI 根目錄 ----
if ([string]::IsNullOrWhiteSpace($Root)) {
    $candidates = @("D:\ComfyUI", "C:\ComfyUI", "$env:USERPROFILE\ComfyUI")
    foreach ($c in $candidates) {
        if ((Test-Path (Join-Path $c "main.py")) -and (Test-Path (Join-Path $c "custom_nodes"))) {
            $Root = $c
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($Root)) {
    Write-Host "[FAIL] 找不到 ComfyUI 根目錄，請用 -Root 指定（例如 .\install.ps1 -Root D:\ComfyUI）" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] ComfyUI 根目錄: $Root"

$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $Root "custom_nodes\ComfyUI_Accelerated_Downloader"

# ---- 複製節點 ----
if (Test-Path $dest) {
    Write-Host "[WARN] $dest 已存在，覆蓋更新..."
    Remove-Item $dest -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Get-ChildItem $src -Force | Where-Object { $_.Name -notin @("install.ps1", "README.md") } | ForEach-Object {
    Copy-Item $_.FullName $dest -Recurse -Force
}
Write-Host "[OK] 節點已複製到: $dest"

# ---- aria2 檢查/安裝 ----
$aria = Get-Command aria2c.exe -ErrorAction SilentlyContinue
if (-not $aria) {
    Write-Host "[INFO] 找不到 aria2c，嘗試用 winget 安裝 aria2..."
    $w = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($w) {
        winget install --id aria2.aria2 --accept-source-agreements --accept-package-agreements --silent | Out-Host
        $aria = Get-Command aria2c.exe -ErrorAction SilentlyContinue
    }
}
if ($aria) {
    Write-Host "[OK] aria2c: $($aria.Source)"
} else {
    Write-Host "[WARN] aria2 安裝未完成。請手動執行: winget install aria2.aria2 後重啟 ComfyUI" -ForegroundColor Yellow
}

# ---- 驗證 ----
$required = @("__init__.py", "nodes.py", "core.py")
$missing = $required | Where-Object { -not (Test-Path (Join-Path $dest $_)) }
if ($missing) {
    Write-Host "[FAIL] 複製不完整，缺少: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "[DONE] 部署完成。重啟 ComfyUI 後："
Write-Host "  - 節點：utils/下載加速 → 加速模型下載（批量）"
Write-Host "  - API：POST /api/accelerated-download/check（空間預檢）"
Write-Host "        POST /api/accelerated-download/start（開始批量下載）"
Write-Host "        GET  /api/accelerated-download/status?task_id=（查進度）"
