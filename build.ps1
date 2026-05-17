# Build script - PAK Universal MOD Manager
# PyInstaller --onedir 模式 → 展平到 dist\，保留 _internal\
$ErrorActionPreference = "Stop"

Write-Host "============================================"
Write-Host "  PAK Universal MOD Manager - 编译脚本"
Write-Host "  PyInstaller 模式"
Write-Host "============================================"
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/5] 检查 Python..."
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  Python: $pythonVersion"
} catch {
    Write-Host "[错误] 未找到 Python，请确保 Python >= 3.10 已安装并加入 PATH。"
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host ""

Write-Host "[2/5] 安装依赖..."
python -m ensurepip --upgrade *>$null
python -m pip install --upgrade pip -i https://pypi.org/simple/ *>$null
python -m pip install -e ".[dev]" -i https://pypi.org/simple/ 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] 依赖安装可能有异常，继续尝试编译..."
}
Write-Host "  完成。"
Write-Host ""

Write-Host "[3/5] 清理旧产物..."
if (Test-Path "$PSScriptRoot\dist") {
    Remove-Item -Recurse -Force "$PSScriptRoot\dist" -ErrorAction SilentlyContinue
    Write-Host "  已删除旧 dist 目录。"
}
if (Test-Path "$PSScriptRoot\build_temp") {
    Remove-Item -Recurse -Force "$PSScriptRoot\build_temp" -ErrorAction SilentlyContinue
}
if (Test-Path "$PSScriptRoot\mod_manager.spec") {
    Remove-Item -Force "$PSScriptRoot\mod_manager.spec" -ErrorAction SilentlyContinue
}
Write-Host "  完成。"
Write-Host ""

Write-Host "[4/5] 开始编译（首次编译可能需要较长时间）..."
Write-Host "============================================"
Write-Host ""

$pyiArgs = @(
    "--onedir",
    "--name", "mod_manager",
    "--icon=$PSScriptRoot\icon.ico",
    "--noconsole",
    "--version-file=$PSScriptRoot\version_info.txt",
    # "--runtime-tmpdir", "PAKModMgr",
    "--add-data=$PSScriptRoot\icon.ico;.",
    "--add-data=$PSScriptRoot\qt.conf;.",
    "--add-data=$PSScriptRoot\License;.",
    "--noupx",
    "--clean",
    "--workpath=$PSScriptRoot\build_temp",
    "--distpath=$PSScriptRoot\dist",
    "$PSScriptRoot\mod_manager.py"
)

& python -m PyInstaller @pyiArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[错误] 编译失败，请查看上方错误信息。"
    Read-Host "按任意键退出..."
    exit 1
}

Write-Host ""
Write-Host "[5/5] 展平到 dist\..."
Write-Host "============================================"

$srcDir = "$PSScriptRoot\dist\mod_manager"
$dstDir = "$PSScriptRoot\dist"

if (-not (Test-Path "$srcDir\mod_manager.exe")) {
    Write-Host "[错误] 未找到编译输出: $srcDir\mod_manager.exe"
    Read-Host "按任意键退出..."
    exit 1
}

Start-Sleep -Milliseconds 500

$items = Get-ChildItem -Path $srcDir -Force
foreach ($item in $items) {
    $target = Join-Path $dstDir $item.Name
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue
    }
}
foreach ($item in $items) {
    $target = Join-Path $dstDir $item.Name
    Move-Item -Path $item.FullName -Destination $target -Force -ErrorAction SilentlyContinue
}

Remove-Item -Recurse -Force $srcDir -ErrorAction SilentlyContinue
Write-Host "  exe:     dist\mod_manager.exe"
Write-Host "  运行时:  dist\_internal\"

# 修改 PE 头 TimeDateStamp 以改变文件哈希（绕过签名检测）
$exePath = "$dstDir\mod_manager.exe"
try {
    $bytes = [IO.File]::ReadAllBytes($exePath)
    $e_lfanew = [BitConverter]::ToInt32($bytes, 0x3C)
    $tsOff = $e_lfanew + 8
    $newTs = [BitConverter]::GetBytes((Get-Date -UFormat '%s') -as [uint32])
    [Array]::Copy($newTs, 0, $bytes, $tsOff, 4)
    # 清零 PE CheckSum 进一步打破签名
    $chkOff = $e_lfanew + 88
    $zero = [BitConverter]::GetBytes([uint32]0)
    [Array]::Copy($zero, 0, $bytes, $chkOff, 4)
    [IO.File]::WriteAllBytes($exePath, $bytes)
    Write-Host "  已随机化 PE 签名"
} catch {
    Write-Host "  [警告] PE 签名修改失败: $($_.Exception.Message)"
}

Remove-Item -Recurse -Force "$PSScriptRoot\build_temp" -ErrorAction SilentlyContinue
Remove-Item -Force "$PSScriptRoot\mod_manager.spec" -ErrorAction SilentlyContinue

$totalSize = 0
if (Test-Path $dstDir) {
    $totalSize = (Get-ChildItem -Recurse -File $dstDir | Measure-Object -Property Length -Sum).Sum
}

Write-Host ""
Write-Host "============================================"
Write-Host "  编译完成！"
Write-Host ""
Write-Host "  总体积: $([math]::Round($totalSize / 1MB, 1)) MB"
Write-Host ""
Write-Host "  输出:"
Write-Host "    dist\mod_manager.exe         (主程序)"
Write-Host "    dist\_internal\              (运行时依赖)"
Write-Host "============================================"

Read-Host "按任意键退出..."
