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

function Test-CerebroPathCommand([string]$ExpectedCliPath) {
    $commands = @(Get-Command cerebro -All -ErrorAction SilentlyContinue)
    if ($commands.Count -eq 0) {
        Write-Warning "No cerebro command is currently visible on PATH. Use the venv CLI path printed below."
        return
    }

    $firstCommand = $commands[0]
    if ($firstCommand.CommandType -ne "Application") {
        Write-Warning "First cerebro command on PATH is not an application: $($firstCommand.Source)"
        return
    }

    $firstPath = [System.IO.Path]::GetFullPath($firstCommand.Source)
    $expectedPath = [System.IO.Path]::GetFullPath($ExpectedCliPath)
    if ([string]::Equals($firstPath, $expectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        try {
            $process = Start-Process -FilePath $firstPath -ArgumentList @("--help") -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        } catch {
            Write-Warning "The first cerebro command on PATH is not this venv and could not be started: $firstPath"
            Write-Warning $_.Exception.Message
            Write-Warning "Prefer calling $expectedPath directly or put its directory before the stale command on PATH."
            return
        }
        $output = @(
            Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
            Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue
        ) -join "`n"
        $exitCode = $process.ExitCode
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    if ($exitCode -ne 0) {
        $trimmed = $output.Trim()
        Write-Warning "The first cerebro command on PATH is not this venv and failed: $firstPath"
        if ($trimmed) {
            Write-Warning $trimmed
        }
        Write-Warning "Prefer calling $expectedPath directly or put its directory before the stale command on PATH."
        return
    }

    Write-Warning "The first cerebro command on PATH is not this venv: $firstPath"
    Write-Warning "This install validated $expectedPath; use that path if command resolution is ambiguous."
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
Test-CerebroPathCommand -ExpectedCliPath $venvCerebro

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
