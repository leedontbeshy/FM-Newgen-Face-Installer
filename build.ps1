param(
    [string]$Python = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
    [string]$OutputDirectory = 'dist'
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $releaseRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputDirectory))
    $workspaceRoot = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if (-not $releaseRoot.StartsWith($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build output must be inside this workspace.'
    }
    $releaseFolder = Join-Path $releaseRoot 'FMNewgenFaceInstaller'
    & $Python -m PyInstaller --noconfirm --distpath $releaseRoot FMNewgenFaceInstaller.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $releaseFolder 'README.md')
    foreach ($notice in @('LICENSE', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CODE_OF_CONDUCT.md')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $notice) -Destination $releaseFolder
    }
    $releaseDocs = Join-Path $releaseFolder 'docs'
    New-Item -ItemType Directory -Path $releaseDocs -Force | Out-Null
    Copy-Item -Path (Join-Path $PSScriptRoot 'docs\*') -Destination $releaseDocs -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'examples') -Destination $releaseFolder -Recurse -Force
    & $Python (Join-Path $PSScriptRoot 'tools\collect_licenses.py') (Join-Path $releaseFolder 'third-party-licenses')
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
    $archivePath = Join-Path $releaseRoot 'FMNewgenFaceInstaller-win-x64.zip'
    Compress-Archive -LiteralPath $releaseFolder -DestinationPath $archivePath -Force
    $archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    ($archiveHash + '  FMNewgenFaceInstaller-win-x64.zip') | Set-Content -LiteralPath ($archivePath + '.sha256') -Encoding ascii
    Write-Host ('Built: ' + (Join-Path $releaseFolder 'FMNewgenFaceInstaller.exe'))
    Write-Host ('Portable ZIP: ' + (Join-Path $releaseRoot 'FMNewgenFaceInstaller-win-x64.zip'))
    Write-Host 'Distribute the entire FMNewgenFaceInstaller folder, including _internal.'
} finally {
    Pop-Location
}
