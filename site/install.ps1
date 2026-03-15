Write-Host "Installing Vector Inspector..."

$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $pyCmd) { $pyCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pyCmd) {
    Write-Error "Python is required but not installed."
    exit 1
}
$python = $pyCmd.Path

try {
    & $python -m pip install --upgrade pip
    & $python -m pip install --upgrade vector-inspector
}
catch {
    Write-Error "Failed to install package: $_"
    exit 1
}

Write-Host "Creating desktop shortcut..."
$cmd = Get-Command vector-inspector -ErrorAction SilentlyContinue
$exe = if ($cmd) { $cmd.Path } else { $null }

$desktop = [Environment]::GetFolderPath("Desktop")
if (-not $exe) {
    Write-Host "Could not locate vector-inspector executable. Skipping shortcut creation."
}
else {
    $WScriptShell = New-Object -ComObject WScript.Shell
    $lnkPath = Join-Path $desktop "Vector Inspector.lnk"
    $Shortcut = $WScriptShell.CreateShortcut($lnkPath)
    $Shortcut.TargetPath = $exe
    $Shortcut.WorkingDirectory = Split-Path $exe
    $Shortcut.IconLocation = $exe
    $Shortcut.Save()
    Write-Host "Shortcut created at $lnkPath."
}

Write-Host "Launching Vector Inspector..."
if ($exe) {
    Start-Process -FilePath $exe
}
else {
    Start-Process -FilePath "vector-inspector" -ErrorAction SilentlyContinue
}