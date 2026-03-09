@echo off
chcp 65001 >nul
echo ====================================
echo HuggingFace 离线模型配置工具
echo ====================================
echo.

echo [1/3] 设置用户环境变量...
powershell -Command "[System.Environment]::SetEnvironmentVariable('HF_HUB_OFFLINE', '1', 'User')"
if %errorlevel% equ 0 (
    echo ✅ HF_HUB_OFFLINE=1 已设置（用户级别）
) else (
    echo ❌ 设置失败
    exit /b 1
)
echo.

echo [2/3] 设置国内镜像（可选，加速下载）...
powershell -Command "[System.Environment]::SetEnvironmentVariable('HF_ENDPOINT', 'https://hf-mirror.com', 'User')"
if %errorlevel% equ 0 (
    echo ✅ HF_ENDPOINT=https://hf-mirror.com 已设置
) else (
    echo ⚠️  镜像设置失败（可跳过）
)
echo.

echo [3/3] 验证环境变量...
powershell -Command "Write-Host '当前用户环境变量:' -ForegroundColor Cyan; [System.Environment]::GetEnvironmentVariable('HF_HUB_OFFLINE', 'User') | Write-Host"
echo.

echo ====================================
echo ✅ 配置完成！
echo ====================================
echo.
echo ⚠️  重要提示：
echo   1. 需要重启 PowerShell 才能生效
echo   2. 关闭所有 PowerShell 窗口后重新打开
echo   3. 运行以下命令验证：
echo      echo $env:HF_HUB_OFFLINE
echo.
echo 📖 详细文档：OFFLINE_MODEL_COMPLETE_GUIDE.md
echo.
pause
