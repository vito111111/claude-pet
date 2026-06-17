# install_autostart.ps1 —— 把桌宠加入 Windows 开机自启(常驻)。
# 在「启动」文件夹(shell:startup)创建快捷方式，开机后用无窗口的 pythonw.exe
# 静默拉起 pet.py --resident。常驻后既跟随 Claude Code 会话状态，也随时可点击占卜
# (易经 / 诗经摇签)，不必打开 Claude Code 也能用。
#
# 用法：
#   安装：powershell -ExecutionPolicy Bypass -File install_autostart.ps1
#   卸载：powershell -ExecutionPolicy Bypass -File install_autostart.ps1 -Uninstall

param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'

$dir = $PSScriptRoot
if (-not $dir) { $dir = Split-Path -Parent $MyInvocation.MyCommand.Path }

$startup  = [Environment]::GetFolderPath('Startup')
$lnkPath  = Join-Path $startup 'Claude桌宠.lnk'

if ($Uninstall) {
    if (Test-Path $lnkPath) {
        Remove-Item $lnkPath -Force
        Write-Host "已移除开机自启：$lnkPath"
    } else {
        Write-Host "未发现自启快捷方式，无需移除。"
    }
    return
}

# 优先用无控制台窗口的 pythonw.exe
$pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pyw) { $pyw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $pyw) { throw "找不到 pythonw.exe / python.exe，请先安装 Python 3.9+ 并加入 PATH。" }

$target = Join-Path $dir 'pet.py'
if (-not (Test-Path $target)) { throw "找不到 $target" }

$shell = New-Object -ComObject WScript.Shell
$lnk   = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath       = $pyw
$lnk.Arguments        = '"' + $target + '" --resident'
$lnk.WorkingDirectory = $dir
$lnk.WindowStyle      = 7
$lnk.IconLocation     = "$pyw,0"
$lnk.Description       = 'Claude 桌宠 + 占卜(易经/诗经)'
$lnk.Save()

Write-Host "已安装开机自启 -> $lnkPath"
Write-Host "立即启动一次..."
& $pyw $target --resident
Write-Host "完成。下次开机将自动出现桌宠，可点击占卜。"
