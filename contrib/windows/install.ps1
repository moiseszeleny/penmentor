# penmentor on Windows: a venv for it, the xournal++ plugin, and its keys started with Windows.
# From the checkout:   powershell -ExecutionPolicy Bypass -File contrib\windows\install.ps1
# Re-running it is safe (it updates everything and restarts the keys). Remove the keys again with:
#   contrib\windows\install.ps1 -Uninstall
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
# the venv lives with penmentor's other files, not in the checkout: 500 MB and 11 000 files that a checkout in
# OneDrive (the Desktop, Documents) would upload and slow down
$venv = Join-Path $env:LOCALAPPDATA 'penmentor\venv'
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'penmentor keys.lnk'

function Stop-Keys {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*penmentor*--daemon*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
}

if ($Uninstall) {
    if (Test-Path $startup) { Remove-Item $startup }
    Stop-Keys
    Write-Host 'penmentor keys removed from startup and stopped.'
    Write-Host "Its Python environment is still in $venv (delete the folder to remove it)."
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
Stop-Keys  # an older one, with the keys and the Python it started with
Start-Sleep -Milliseconds 500
# started by Explorer, through the shortcut: not a child of this terminal, so closing it (or the app that opened it)
# doesn't take the keys down with it
Start-Process explorer.exe -ArgumentList "`"$startup`""

Write-Host ''
Write-Host 'Done. Ctrl+Alt+Shift+A asks (menu), Ctrl+Alt+Shift+M checks for mistakes, Ctrl+Alt+Shift+S checks the solution.'
Write-Host 'Restart xournal++ once so it loads the plugin. You also need one agent logged in: claude, codex or agy.'
$old = Join-Path $repo '.venv'
if (Test-Path $old) { Write-Host "An older environment is still in $old : penmentor no longer uses it, you can delete that folder." }
& $py -m penmentor --selftest
