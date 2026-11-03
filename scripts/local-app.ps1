param([ValidateSet('setup','start','stop','status')][string]$Action='start',[switch]$NoBrowser)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONUTF8='1'
$python=Join-Path $root '.venv\Scripts\python.exe'

function Find-Uv {
    $command=Get-Command uv -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($candidate in @("$env:USERPROFILE\.local\bin\uv.exe","$env:LOCALAPPDATA\Microsoft\WinGet\Links\uv.exe")) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
}
function Install-Requirement([string]$id) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install Microsoft App Installer (WinGet), or follow the manual setup in README.md.' }
    & winget install --id $id --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installation of $id did not complete. Follow the manual setup in README.md." }
    $env:Path=[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')
}

if ($Action -eq 'setup') {
    if (Test-Path -LiteralPath $python) {
        & $python local_app.py status --quiet
        if ($LASTEXITCODE -eq 0) { throw 'Stop the local app before running Setup.cmd.' }
        if ($LASTEXITCODE -ne 1) { throw 'Another local control command is running. Wait, then run Setup.cmd again.' }
    }
    $uv=Find-Uv
    if (-not $uv) { Install-Requirement 'astral-sh.uv';$uv=Find-Uv }
    if (-not $uv) { throw 'uv could not be found. Restart this window and run Setup.cmd again.' }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Install-Requirement 'OpenJS.NodeJS.LTS' }
    Write-Host 'Installing the locked Python environment (first setup can take several minutes)...'
    & $uv sync --frozen --no-dev
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Your existing .env and data were kept.' }
    & $python local_app.py setup
} else {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run Setup.cmd first.' }
    if ($Action -eq 'start' -and $NoBrowser) { & $python local_app.py start --no-browser }
    else { & $python local_app.py $Action }
}
exit $LASTEXITCODE
