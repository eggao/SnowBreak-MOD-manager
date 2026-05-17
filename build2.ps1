# Build script 2 - PAK Universal MOD Manager
# cx_Freeze 打包 → exe 在 dist\，依赖在 dist\lib\
$ErrorActionPreference = "Stop"

Write-Host "============================================"
Write-Host "  PAK Universal MOD Manager - 编译脚本 2"
Write-Host "  cx_Freeze 模式"
Write-Host "============================================"
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/6] 检查 Python..."
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  Python: $pythonVersion"
} catch {
    Write-Host "[错误] 未找到 Python，请确保 Python >= 3.10 已安装并加入 PATH。"
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host ""

Write-Host "[2/6] 安装 cx_Freeze..."
python -m ensurepip --upgrade *>$null
python -m pip install --upgrade pip -i https://pypi.org/simple/ *>$null
python -m pip install "cx-Freeze>=7.0" -i https://pypi.org/simple/ 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] cx_Freeze 安装失败。"
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host "  完成。"
Write-Host ""

Write-Host "[3/6] 清理旧产物..."
if (Test-Path "$PSScriptRoot\dist") {
    Remove-Item -Recurse -Force "$PSScriptRoot\dist" -ErrorAction SilentlyContinue
    Write-Host "  已删除旧 dist 目录。"
}
if (Test-Path "$PSScriptRoot\build_cx") {
    Remove-Item -Recurse -Force "$PSScriptRoot\build_cx" -ErrorAction SilentlyContinue
}
Remove-Item -Force "$PSScriptRoot\setup_cx.py" -ErrorAction SilentlyContinue
Write-Host "  完成。"
Write-Host ""

Write-Host "[4/6] 生成 cx_Freeze 配置..."
Write-Host "============================================"

$setupPy = @"
import os, sys
from cx_Freeze import setup, Executable

include_files = [
    ("icon.ico", "icon.ico"),
    ("qt.conf", "qt.conf"),
    ("License", "License"),
]

build_exe_options = {
    "packages": ["PyQt6", "PIL"],
    "includes": [
        "config", "i18n", "models", "mod_manager",
        "transfer_helpers", "ui", "utils", "workers",
    ],
    "include_files": include_files,
    "include_msvcr": True,
    "silent_level": 1,
}

setup(
    name="PAK Mod Manager",
    version="1.0.0",
    options={"build_exe": build_exe_options},
    executables=[Executable(
        "mod_manager.py",
        base="Win32GUI" if sys.platform == "win32" else None,
        icon="icon.ico",
        target_name="mod_manager.exe",
    )],
)
"@

Set-Content -Path "$PSScriptRoot\setup_cx.py" -Value $setupPy -Encoding UTF8
Write-Host "  配置:  setup_cx.py"
Write-Host ""

Write-Host "[5/6] 开始编译（首次编译可能需要较长时间）..."
Write-Host "============================================"
Write-Host ""

& python setup_cx.py build_exe

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[错误] 编译失败，请查看上方错误信息。"
    Read-Host "按任意键退出..."
    exit 1
}

Write-Host ""
Write-Host "[6/6] 迁移到 dist\..."
Write-Host "============================================"

$buildDirs = Get-ChildItem -Path "$PSScriptRoot\build" -Directory -Filter "exe.*" -ErrorAction SilentlyContinue
if (-not $buildDirs) {
    Write-Host "[错误] 未找到 cx_Freeze 编译输出 (build\exe.*)"
    Read-Host "按任意键退出..."
    exit 1
}
$buildOutputDir = $buildDirs[0].FullName
Write-Host "  源目录: $buildOutputDir"

if (-not (Test-Path "$PSScriptRoot\dist")) {
    New-Item -ItemType Directory -Path "$PSScriptRoot\dist" -Force *>$null
}

$items = Get-ChildItem -Path $buildOutputDir -Force
foreach ($item in $items) {
    $target = Join-Path "$PSScriptRoot\dist" $item.Name
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue
    }
}
foreach ($item in $items) {
    $target = Join-Path "$PSScriptRoot\dist" $item.Name
    Move-Item -Path $item.FullName -Destination $target -Force -ErrorAction SilentlyContinue
}

# 将 dist\ 根目录下多余的 dll/pyd 移入 lib\（保留 python*.dll）
$libDir = "$PSScriptRoot\dist\lib"
if (-not (Test-Path $libDir)) {
    New-Item -ItemType Directory -Path $libDir -Force *>$null
}
$extFiles = Get-ChildItem -Path "$PSScriptRoot\dist" -File | Where-Object {
    $_.Name -notmatch 'mod_manager\.exe$' -and
    $_.Name -notmatch '^python\d*\.dll$' -and
    $_.Extension -match '\.(dll|pyd|so)$'
}
foreach ($f in $extFiles) {
    Move-Item -Path $f.FullName -Destination "$libDir\" -Force -ErrorAction SilentlyContinue
    Write-Host "  → lib\$($f.Name)"
}

Write-Host "  exe:     dist\mod_manager.exe"
Write-Host "  运行时:  dist\lib\"

Remove-Item -Recurse -Force "$PSScriptRoot\build" -ErrorAction SilentlyContinue
Remove-Item -Force "$PSScriptRoot\setup_cx.py" -ErrorAction SilentlyContinue
Write-Host "  临时文件已清理"

$totalSize = 0
if (Test-Path "$PSScriptRoot\dist") {
    $totalSize = (Get-ChildItem -Recurse -File "$PSScriptRoot\dist" | Measure-Object -Property Length -Sum).Sum
}

Write-Host ""
Write-Host "============================================"
Write-Host "  编译完成！"
Write-Host ""
Write-Host "  总体积: $([math]::Round($totalSize / 1MB, 1)) MB"
Write-Host ""
Write-Host "  输出:"
Write-Host "    dist\mod_manager.exe         (主程序)"
Write-Host "    dist\lib\                    (运行时依赖)"
Write-Host "============================================"

Read-Host "按任意键退出..."
