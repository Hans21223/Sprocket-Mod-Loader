# Sprocket compatibility pack 1.2.2, 2026-10-08. LGPL-3.0-only.
# Prepares files beside this script. Does not install into or launch the game.
[CmdletBinding()]
param([string]$BaseZip)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
# Load this PowerShell installation's built-ins even if a parent app supplied
# a PSModulePath belonging to a different PowerShell version.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Archive\Microsoft.PowerShell.Archive.psd1')
$baseName = 'BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788+5b766a3.zip'
$baseHash = 'F4CC496BD098A0DF4164B81E3737297707F13A47C2478DBA2F60EEFAB784817A'
$download = 'https://builds.bepinex.dev/projects/bepinex_be/788/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788%2B5b766a3.zip'
$patchHashes = @{
    'Il2CppInterop.Generator.dll' = 'A5549C757E91A0AC9ADF30ABCB7D2F12D37664A6B7D12EB2D5CFDCC0EE5AEF6A'
    'Il2CppInterop.Runtime.dll' = 'C9974AC904F01FE37A216F66E408677F8237A02AFA548C9C9F4DC1048208B24D'
    'Il2CppInterop.Common.dll' = '3A19E3B1CDB0620B624A08BB87346B3138F316E8BDC05E745419D8FE170D74C1'
    'Il2CppInterop.HarmonySupport.dll' = 'CFDBF6E6466D5A06B1610A1CD108BAB077A79D12F0D06B820BA40A57CE28D5CE'
    'TerraFX.Interop.Windows.dll' = '6E3DD6E4CDBBC4A9439EAD4F6A49A25911379680C6342562132C3E6B6192969B'
}
$output = Join-Path $PSScriptRoot 'Ready-to-copy'
if (Test-Path -LiteralPath $output) {
    throw 'Ready-to-copy already exists. Extract a fresh copy of this package to prepare again.'
}
foreach ($name in $patchHashes.Keys) {
    $file = Join-Path $PSScriptRoot ('Patch\BepInEx\core\' + $name)
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $patchHashes[$name]) {
        throw ('Patch checksum failed: ' + $name + '. Extract the original package again.')
    }
}
if (-not $BaseZip) {
    $BaseZip = Join-Path $PSScriptRoot $baseName
    if (-not (Test-Path -LiteralPath $BaseZip)) {
        Write-Host 'Downloading official BepInEx be.788 (about 35 MB)...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -UseBasicParsing -Uri $download -OutFile $BaseZip -TimeoutSec 120
    }
}
$BaseZip = (Resolve-Path -LiteralPath $BaseZip).Path
if ((Get-FileHash -LiteralPath $BaseZip -Algorithm SHA256).Hash -ne $baseHash) {
    throw 'Official download checksum failed. Obtain the exact be.788 Windows x64 IL2CPP ZIP named in README.md. Do not use another build.'
}
# Unique staging directory prevents a failed preparation looking complete.
$stage = Join-Path $PSScriptRoot ('preparing-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
Expand-Archive -LiteralPath $BaseZip -DestinationPath $stage
foreach ($name in $patchHashes.Keys) {
    $source = Join-Path $PSScriptRoot ('Patch\BepInEx\core\' + $name)
    $target = Join-Path $stage ('BepInEx\core\' + $name)
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $patchHashes[$name]) {
        throw ('Prepared file checksum failed: ' + $name)
    }
}
foreach ($relative in @('winhttp.dll', 'doorstop_config.ini', 'BepInEx\core\BepInEx.Unity.IL2CPP.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $stage $relative) -PathType Leaf)) {
        throw ('Official archive is missing ' + $relative)
    }
}
Move-Item -LiteralPath $stage -Destination $output
Write-Host ''
Write-Host 'READY. Read README.md, then copy the CONTENTS of Ready-to-copy beside Sprocket.exe.'
Write-Host 'This has not changed your game. Keep this original package for sharing.'
Write-Host ('Prepared folder: ' + $output)
