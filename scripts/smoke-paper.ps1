param(
    [switch]$Public,
    [switch]$ActivateWallet
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python da .venv indisponível.' }
$arguments = @((Join-Path $PSScriptRoot 'smoke_paper.py'))
if ($Public) { $arguments += '--public' }
if ($ActivateWallet) { $arguments += '--activate-wallet' }
& $python @arguments
exit $LASTEXITCODE
