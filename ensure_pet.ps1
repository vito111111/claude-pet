# ensure_pet.ps1 —— 保证桌面宠物渲染器(pet.py --resident)正在运行且未僵死。
# 由 Claude Code 的 SessionStart hook 调用：每次打开 Claude Code 都确保宠物出现。
#
# 判活逻辑用「心跳文件」而非「进程是否存在」：pet.py 每 ~500ms 刷新
# ~/.claude/pet_status/.heartbeat 的时间戳。若心跳新鲜(<6s)说明渲染器正常，直接退出；
# 否则杀掉所有 pet.py 进程(含持有单例端口却无窗口的僵死实例)并重新拉起。

$ErrorActionPreference = 'SilentlyContinue'

# 脚本所在目录(可移植：不写死用户路径)
$dir = $PSScriptRoot
if (-not $dir) { $dir = Split-Path -Parent $MyInvocation.MyCommand.Path }

# 优先用无控制台的 pythonw.exe；找不到则回退 python.exe
$pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pyw) { $pyw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $pyw) { $pyw = 'pythonw.exe' }   # 交给 PATH 解析
$hb   = Join-Path $env:USERPROFILE '.claude\pet_status\.heartbeat'

$fresh = $false
if (Test-Path $hb) {
    try {
        $t   = [double]((Get-Content $hb -Raw).Trim())
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
        if (($now - $t) -lt 6) { $fresh = $true }
    } catch {}
}

if ($fresh) { return }   # 渲染器活着且在刷新，无需动作

# 心跳过期或不存在 -> 清掉所有(可能僵死的) pet.py 进程
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pet.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Start-Sleep -Milliseconds 400   # 让旧实例释放单例端口 50573

Start-Process -FilePath $pyw -ArgumentList 'pet.py', '--resident' `
    -WorkingDirectory $dir -WindowStyle Hidden
