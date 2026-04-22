[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$VenvDir = ""
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

function Resolve-ExistingPath([string]$PathValue, [string]$Label) {
    try {
        return (Resolve-Path -LiteralPath $PathValue).Path
    } catch {
        Fail "$Label not found: $PathValue"
    }
}

function Get-PythonCommand {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "python"; Args = @() },
        @{ Exe = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            & $candidate.Exe @($candidate.Args + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")) *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }

    Fail "Python 3.11 or newer was not found. Install Python 3.11+ and try again."
}

function Invoke-Step([string]$Label, [string]$Exe, [string[]]$Arguments, [switch]$QuietSuccess) {
    Write-Host "==> $Label"
    if ($QuietSuccess) {
        $output = & $Exe @Arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            $trimmed = $output.Trim()
            if ($trimmed) {
                Write-Host $trimmed
            }
            Fail "$Label failed with exit code $exitCode."
        }
        return
    }

    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "$Label failed with exit code $LASTEXITCODE."
    }
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot "..\.."
}

$resolvedRepoRoot = Resolve-ExistingPath -PathValue $RepoRoot -Label "Repo root"
$pyprojectPath = Join-Path $resolvedRepoRoot "pyproject.toml"
if (-not (Test-Path -LiteralPath $pyprojectPath)) {
    Fail "Invalid Cerebro repository root: pyproject.toml not found in $resolvedRepoRoot"
}

if ([string]::IsNullOrWhiteSpace($VenvDir)) {
    $VenvDir = Join-Path $resolvedRepoRoot "venv"
} elseif (-not [System.IO.Path]::IsPathRooted($VenvDir)) {
    $VenvDir = Join-Path $resolvedRepoRoot $VenvDir
}

$pythonCommand = Get-PythonCommand

Invoke-Step -Label "Creating virtual environment" -Exe $pythonCommand.Exe -Arguments ($pythonCommand.Args + @("-m", "venv", $VenvDir))

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
$venvCerebro = Join-Path $VenvDir "Scripts\cerebro.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Fail "Virtual environment was created without Scripts\python.exe at $venvPython"
}

Invoke-Step -Label "Installing Cerebro" -Exe $venvPython -Arguments @(
    "-m",
    "pip",
    "install",
    "--disable-pip-version-check",
    "--quiet",
    "-e",
    $resolvedRepoRoot,
    "--no-deps"
) -QuietSuccess

if (-not (Test-Path -LiteralPath $venvCerebro)) {
    Fail "Install completed but cerebro.exe was not created at $venvCerebro"
}

Invoke-Step -Label "Validating Cerebro CLI" -Exe $venvCerebro -Arguments @("--help") -QuietSuccess

Write-Host ""
Write-Host "Install complete."
Write-Host "Repo root: $resolvedRepoRoot"
Write-Host "Virtual environment: $VenvDir"
Write-Host "CLI path: $venvCerebro"
Write-Host "Runtime note: run Cerebro from the target project root; `.cerebro\\` will be created there, not in this repository."
Write-Host ""
$activationScript = Join-Path $VenvDir "Scripts\Activate.ps1"
Write-Host "Next steps:"
Write-Host "  1. Activate:  $activationScript"
Write-Host "     or call:   $venvCerebro"
Write-Host "  2. Change into the target project root."
Write-Host "  3. Bootstrap once: init -> import-context -> checkpoint -> validate"
