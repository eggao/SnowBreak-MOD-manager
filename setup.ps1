# Setup script - PAK Universal MOD Manager
$ErrorActionPreference = "Stop"

Write-Host "============================================"
Write-Host "  PAK Universal MOD Manager - 环境安装"
Write-Host "============================================"
Write-Host ""
Write-Host "此脚本会安装项目所需的所有依赖。"
Write-Host "相当于: pip install -e `".[dev]`""
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/3] 检查 Python..."
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  Python: $pythonVersion"
} catch {
    Write-Host "[错误] 未找到 Python，请确保 Python >= 3.10 已安装并加入 PATH。"
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host ""

Write-Host "[2/3] 安装项目运行时依赖..."
python -m pip install --upgrade pip
python -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 依赖安装失败。"
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host ""

Write-Host "[3/3] 安装编译工具 PyInstaller..."
python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 编译工具安装失败。"
    Read-Host "按任意键退出..."
    exit 1
}
Write-Host ""

Write-Host "============================================"
Write-Host "  环境安装完成！"
Write-Host ""
Write-Host "  现在可以:"
Write-Host "    - 直接运行: python mod_manager.py"
Write-Host "    - 或: pak-mod-manager"
Write-Host "    - 编译打包: .\build.ps1"
Write-Host "============================================"

Read-Host "按任意键退出..."
