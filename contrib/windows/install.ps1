# penmentor on Windows: a venv for it, the xournal++ plugin, and its keys started with Windows.
# From the checkout:   powershell -ExecutionPolicy Bypass -File contrib\windows\install.ps1
# Re-running it is safe. Remove the keys again with:   contrib\windows\install.ps1 -Uninstall
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$venv = Join-Path $repo '.venv'
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'penmentor keys.lnk'

if ($Uninstall) {
    if (Test-Path $startup) { Remove-Item $startup }
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*penmentor*--daemon*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId }
    Write-Host 'penmentor keys removed from startup and stopped.'
    return
}

if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    Write-Host "Creating $venv"
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $venv } else { & python -m venv $venv }
}
$py = Join-Path $venv 'Scripts\python.exe'
$pyw = Join-Path $venv 'Scripts\pythonw.exe'
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -e $repo
& $py -m penmentor --install-plugin

# the keys, at every login (a shortcut in the Startup folder), and now
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($startup)
$lnk.TargetPath = $pyw
$lnk.Arguments = '-m penmentor --daemon'
$lnk.WorkingDirectory = $repo
$lnk.Description = 'penmentor: the keys that start it'
$lnk.Save()
Start-Process -FilePath $pyw -ArgumentList '-m', 'penmentor', '--daemon' -WorkingDirectory $repo

Write-Host ''
Write-Host 'Done. Ctrl+Alt+Shift+A asks (menu), Ctrl+Alt+Shift+M checks for mistakes, Ctrl+Alt+Shift+S checks the solution.'
Write-Host 'Restart xournal++ once so it loads the plugin. You also need one agent logged in: claude, codex or agy.'
& $py -m penmentor --selftest
