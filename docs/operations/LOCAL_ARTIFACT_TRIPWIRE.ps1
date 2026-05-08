param(
    [string]$RepoRoot,
    [Int64]$LocalSizeLimitBytes = 1073741824,
    [int]$StaleDays = 7,
    [datetime]$Now = (Get-Date)
)

$ErrorActionPreference = 'Continue'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
} else {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

$findings = New-Object System.Collections.Generic.List[object]

function Add-Finding {
    param(
        [string]$Rule,
        [string]$Severity,
        [string]$Path,
        [string]$Detail
    )

    $findings.Add([PSCustomObject]@{
        rule = $Rule
        severity = $Severity
        path = $Path
        detail = $Detail
    }) | Out-Null
}

function Get-DirectorySizeBytes {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }

    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) {
        return 0
    }
    return [Int64]$sum
}

function Test-AdjacentManifest {
    param([System.IO.FileSystemInfo]$Item)

    $parent = $Item.DirectoryName
    if ($Item.PSIsContainer) {
        $parent = $Item.Parent.FullName
        $insideManifest = Join-Path $Item.FullName 'MANIFEST.md'
        if (Test-Path -LiteralPath $insideManifest) {
            return $true
        }
    }

    $siblingManifest = Join-Path $parent ($Item.BaseName + '_MANIFEST.md')
    if (Test-Path -LiteralPath $siblingManifest) {
        return $true
    }

    $parentManifest = Join-Path $parent 'MANIFEST.md'
    if (Test-Path -LiteralPath $parentManifest) {
        $manifestText = Get-Content -LiteralPath $parentManifest -Raw -ErrorAction SilentlyContinue
        if ($manifestText -match [regex]::Escape($Item.Name)) {
            return $true
        }
    }

    return $false
}

$localPath = Join-Path $RepoRoot '_local'
if (Test-Path -LiteralPath $localPath) {
    $localBytes = Get-DirectorySizeBytes -Path $localPath
    if ($localBytes -gt $LocalSizeLimitBytes) {
        Add-Finding `
            -Rule 'local_size_limit' `
            -Severity 'warning' `
            -Path $localPath `
            -Detail ("_local size is {0:N1} MiB; threshold is {1:N1} MiB." -f ($localBytes / 1MB), ($LocalSizeLimitBytes / 1MB))
    }

    $cutoff = $Now.AddDays(-1 * $StaleDays)
    Get-ChildItem -LiteralPath $localPath -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -eq 'MANIFEST.md' -or $_.Name -like '*_MANIFEST.md') {
            return
        }

        if ($_.LastWriteTime -le $cutoff -and -not (Test-AdjacentManifest -Item $_)) {
            Add-Finding `
                -Rule 'local_entry_without_manifest' `
                -Severity 'warning' `
                -Path $_.FullName `
                -Detail ("Top-level _local entry is older than {0} days and has no adjacent MANIFEST.md contract." -f $StaleDays)
        }
    }
}

$allowedRootScratch = @(
    '.tmp_claims',
    '.tmp_live_proofs',
    '.tmp_test'
)

Get-ChildItem -LiteralPath $RepoRoot -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -eq '.git') {
        return
    }

    if ($_.Name -in $allowedRootScratch) {
        return
    }

    $isSuspicious =
        ($_.PSIsContainer -and $_.Name -eq 'node_modules') -or
        ($_.PSIsContainer -and $_.Name -like '.tmp_*') -or
        ($_.PSIsContainer -and $_.Name -like '*.git') -or
        (-not $_.PSIsContainer -and $_.Name -like '*.zip') -or
        ($_.PSIsContainer -and $_.Name -like 'cerebro-workingtree-backup-*')

    if ($isSuspicious) {
        Add-Finding `
            -Rule 'repo_root_suspicious_local_artifact' `
            -Severity 'warning' `
            -Path $_.FullName `
            -Detail 'Repo-root local artifact matches backup, scratch, bundle, or embedded dependency pattern.'
    }
}

Get-ChildItem -LiteralPath $RepoRoot -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '_local_cleanup_quarantine_*' } |
    ForEach-Object {
        $manifest = Join-Path $_.FullName 'MANIFEST.md'
        if (-not (Test-Path -LiteralPath $manifest)) {
            Add-Finding `
                -Rule 'quarantine_without_manifest' `
                -Severity 'warning' `
                -Path $_.FullName `
                -Detail 'Quarantine directory has no root MANIFEST.md with retention_until.'
            return
        }

        $content = Get-Content -LiteralPath $manifest -Raw -ErrorAction SilentlyContinue
        if ($content -notmatch 'retention_until\s*:') {
            Add-Finding `
                -Rule 'quarantine_without_retention_until' `
                -Severity 'warning' `
                -Path $manifest `
                -Detail 'Quarantine MANIFEST.md exists but does not declare retention_until.'
        }
    }

$summary = [PSCustomObject]@{
    repo_root = $RepoRoot
    checked_at = $Now.ToString('o')
    authority = 'advisory-only'
    finding_count = $findings.Count
}

$summary | Format-List

if ($findings.Count -gt 0) {
    $findings | Sort-Object rule, path | Format-Table -AutoSize -Wrap
} else {
    Write-Output 'No local artifact retention drift found.'
}

Write-Output 'LOCAL_ARTIFACT_TRIPWIRE_ADVISORY_COMPLETE'
