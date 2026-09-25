#Requires -Version 5.1
<#
.SYNOPSIS
  一键启动实习平台本地开发环境（后端 8001 + 前端 5173）。

.DESCRIPTION
  - 若端口已被占用，会先尝试复用（健康则跳过启动）
  - 后端未就绪时前端代理会报 500 / 连不上，本脚本会等健康检查通过再开前端
  - 给学校演示：双击 start-dev.bat，或在 PowerShell 执行本脚本
#>
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$WebDir = Join-Path $Root "apps\web"
$ApiHost = "127.0.0.1"
$ApiPort = 8001
$WebPort = 5173
$HealthUrl = "http://${ApiHost}:${ApiPort}/api/v1/health"

function Test-PortListen([int]$Port) {
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-HttpOk([string]$Url, [int]$Seconds = 40) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

Write-Host ""
Write-Host "=== HUST OpenAtom intern-platform 开发启动 ===" -ForegroundColor Cyan
Write-Host "根目录: $Root"

if (-not (Test-Path $VenvPython)) {
  Write-Host "缺少虚拟环境: $VenvPython" -ForegroundColor Red
  Write-Host "请先: python -m venv .venv ; .\.venv\Scripts\pip install -e `".[dev]`""
  exit 1
}
if (-not (Test-Path (Join-Path $WebDir "package.json"))) {
  Write-Host "缺少前端目录: $WebDir" -ForegroundColor Red
  exit 1
}

# 后端
$needApi = $true
if (Test-PortListen $ApiPort) {
  if (Wait-HttpOk $HealthUrl 3) {
    Write-Host "[OK] 后端已在 :$ApiPort 运行" -ForegroundColor Green
    $needApi = $false
  } else {
    Write-Host "[!] 端口 $ApiPort 被占用但健康检查失败，请手动结束占用进程后重试" -ForegroundColor Yellow
    exit 1
  }
}

if ($needApi) {
  Write-Host "[..] 启动后端 uvicorn :$ApiPort ..."
  Start-Process -FilePath $VenvPython -ArgumentList @(
    "-m", "uvicorn", "apps.api.main:app",
    "--app-dir", ".",
    "--host", $ApiHost,
    "--port", "$ApiPort",
    "--reload"
  ) -WorkingDirectory $Root -WindowStyle Minimized
  if (-not (Wait-HttpOk $HealthUrl 45)) {
    Write-Host "[FAIL] 后端未在 45s 内就绪: $HealthUrl" -ForegroundColor Red
    Write-Host "请查看最小化的 uvicorn 窗口日志"
    exit 1
  }
  Write-Host "[OK] 后端就绪 $HealthUrl" -ForegroundColor Green
}

# 前端
$needWeb = $true
if (Test-PortListen $WebPort) {
  Write-Host "[OK] 前端已在 :$WebPort 运行" -ForegroundColor Green
  $needWeb = $false
}

if ($needWeb) {
  Write-Host "[..] 启动前端 Vite :$WebPort ..."
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if (-not $npm) {
    Write-Host "未找到 npm，请安装 Node.js" -ForegroundColor Red
    exit 1
  }
  Start-Process -FilePath "npm" -ArgumentList @(
    "run", "dev", "--", "--host", "127.0.0.1", "--port", "$WebPort", "--strictPort"
  ) -WorkingDirectory $WebDir -WindowStyle Minimized
  $webOk = Wait-HttpOk "http://127.0.0.1:${WebPort}/" 45
  if (-not $webOk) {
    Write-Host "[FAIL] 前端未在 45s 内就绪" -ForegroundColor Yellow
  } else {
    Write-Host "[OK] 前端就绪 http://127.0.0.1:${WebPort}/" -ForegroundColor Green
  }
}

Write-Host ""
Write-Host "打开: http://127.0.0.1:${WebPort}/" -ForegroundColor Cyan
Write-Host "API : http://127.0.0.1:${ApiPort}/docs"
Write-Host "演示账号密码: Demo@123456 （student@demo.hust.edu.cn）"
Write-Host "两个服务窗口已最小化；关掉窗口即停止对应服务。"
Write-Host ""
