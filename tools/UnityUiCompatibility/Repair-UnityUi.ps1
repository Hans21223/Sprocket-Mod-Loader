[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GamePath,
    [string]$DotNetPath = 'dotnet',
    [string]$RepairTool = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $RepairTool) {
    $RepairTool = Join-Path $PSScriptRoot 'UnityUiCompatibility.dll'
    if (-not (Test-Path -LiteralPath $RepairTool -PathType Leaf)) {
        $RepairTool = Join-Path $PSScriptRoot 'bin\Release\net8.0\UnityUiCompatibility.dll'
    }
}
$gameRoot = (Resolve-Path -LiteralPath $GamePath).Path.TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $gameRoot 'Sprocket.exe') -PathType Leaf)) {
    throw 'GamePath must point to a Sprocket installation containing Sprocket.exe.'
}
if (Get-Process -Name Sprocket -ErrorAction SilentlyContinue) {
    throw 'Save and close Sprocket before repairing its Unity wrapper cache.'
}
if (-not (Test-Path -LiteralPath $RepairTool -PathType Leaf)) {
    throw 'Build UnityUiCompatibility first, or provide -RepairTool pointing to the built DLL.'
}
$cacheFolders = @(@('BepInEx\interop', 'MLLoader\MelonLoader\Il2CppAssemblies') | Where-Object {
    Test-Path -LiteralPath (Join-Path $gameRoot (Join-Path $_ 'UnityEngine.CoreModule.dll')) -PathType Leaf
})
if (-not $cacheFolders) { throw 'No existing Unity interop cache was found. This repair does not install a loader.' }
$backupRoot = Join-Path $gameRoot ('UnityUiRepair\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
$entries = @()
function Invoke-RepairTool([string[]]$ToolArguments) {
    & $DotNetPath $RepairTool @ToolArguments
    if ($LASTEXITCODE -ne 0) { throw ('Unity UI repair failed: ' + $ToolArguments[0]) }
}
foreach ($relativeFolder in $cacheFolders) {
    $cacheFolder = Join-Path $gameRoot $relativeFolder
    $originalFolder = Join-Path $backupRoot (Join-Path 'original' $relativeFolder)
    $stagedFolder = Join-Path $backupRoot (Join-Path 'repaired' $relativeFolder)
    New-Item -ItemType Directory -Path $originalFolder, $stagedFolder -Force | Out-Null
    foreach ($name in @('UnityEngine.CoreModule.dll', 'MethodAddressToToken.db')) {
        $destination = Join-Path $cacheFolder $name
        $original = Join-Path $originalFolder $name
        $repaired = Join-Path $stagedFolder $name
        Copy-Item -LiteralPath $destination -Destination $original
        $entries += [pscustomobject]@{ Destination = $destination; Original = $original; Repaired = $repaired; Before = (Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash; After = '' }
    }
    Invoke-RepairTool -ToolArguments @('apply', (Join-Path $originalFolder 'UnityEngine.CoreModule.dll'), (Join-Path $stagedFolder 'UnityEngine.CoreModule.dll'))
    Invoke-RepairTool -ToolArguments @('remap', (Join-Path $originalFolder 'UnityEngine.CoreModule.dll'), (Join-Path $stagedFolder 'UnityEngine.CoreModule.dll'), (Join-Path $originalFolder 'MethodAddressToToken.db'), (Join-Path $stagedFolder 'MethodAddressToToken.db'))
    Invoke-RepairTool -ToolArguments @('verify', (Join-Path $stagedFolder 'UnityEngine.CoreModule.dll'))
}
foreach ($entry in $entries) { $entry.After = (Get-FileHash -LiteralPath $entry.Repaired -Algorithm SHA256).Hash }
$entries | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupRoot 'manifest.json') -Encoding utf8
# Stage and validate every cache before changing any installed file.
foreach ($entry in $entries) {
    if ((Get-FileHash -LiteralPath $entry.Destination -Algorithm SHA256).Hash -ne $entry.Before) {
        throw 'A cache changed during preparation. Nothing was installed; retry with the game closed.'
    }
}
if (Get-Process -Name Sprocket -ErrorAction SilentlyContinue) { throw 'Sprocket started during preparation; nothing was installed.' }
$installed = @()
try {
    foreach ($entry in $entries) {
        $installed += $entry
        Copy-Item -LiteralPath $entry.Repaired -Destination $entry.Destination -Force
        if ((Get-FileHash -LiteralPath $entry.Destination -Algorithm SHA256).Hash -ne $entry.After) { throw 'Installed cache checksum failed.' }
    }
} catch {
    foreach ($entry in $installed) { Copy-Item -LiteralPath $entry.Original -Destination $entry.Destination -Force }
    throw
}
Write-Output ('UNITY_UI_REPAIR_INSTALLED: ' + $cacheFolders.Count + ' existing caches. Backup: ' + $backupRoot)
