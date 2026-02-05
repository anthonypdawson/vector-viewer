Write-Host "Installing Vector Inspector..."

# Ensure Python exists
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is required but not installed."
    exit 1
}

python -m pip install --upgrade pip
python -m pip install --upgrade vector-inspector

Write-Host "Creating desktop shortcut..."

$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut("$env:USERPROFILE\Desktop\Vector Inspector.lnk")
$Shortcut.TargetPath = "vector-inspector"
$Shortcut.Save()

Write-Host "Launching Vector Inspector..."
Start-Process vector-inspector