#Requires -Version 5.1
<#
.SYNOPSIS
    coding-agent-memory-kit universal installer for Windows PowerShell.
.DESCRIPTION
    Installs the repo-memory skill into the current repository.
    Usage: irm https://raw.githubusercontent.com/TheovanKraay/coding-agent-memory-kit/main/install.ps1 | iex
    Or:    .\install.ps1 [-Yes] [-SkipCosmos]
.PARAMETER Yes
    Skip all confirmation prompts (for CI/automation).
.PARAMETER SkipCosmos
    Skip Cosmos DB initialization step.
#>
param(
    [Alias("y")][switch]$Yes,
    [switch]$SkipCosmos
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Globals ──────────────────────────────────────────────────────────────────
$RepoUrl   = "https://raw.githubusercontent.com/TheovanKraay/coding-agent-memory-kit/main"
$SkillDir  = Join-Path $PWD ".github\skills\repo-memory"
$VenvDir   = Join-Path $SkillDir ".venv"

$CreatedTemplates = @()
$SkippedTemplates = @()

# ── Helpers ──────────────────────────────────────────────────────────────────
function Write-Info    { param($Msg) Write-Host "  i " -ForegroundColor Blue -NoNewline; Write-Host $Msg }
function Write-Ok      { param($Msg) Write-Host "  ✔ " -ForegroundColor Green -NoNewline; Write-Host $Msg }
function Write-Warn    { param($Msg) Write-Host "  ⚠ " -ForegroundColor Yellow -NoNewline; Write-Host $Msg }
function Write-Err     { param($Msg) Write-Host "  ✖ " -ForegroundColor Red -NoNewline; Write-Host $Msg }
function Write-Header  { param($Msg) Write-Host "`n── $Msg ──" -ForegroundColor White }

function Confirm-Action {
    param($Prompt)
    if ($Yes) { return $true }
    $answer = Read-Host "$Prompt [y/N]"
    return ($answer -match '^[yY]')
}

# ── 1. Detect OS & Architecture ─────────────────────────────────────────────
Write-Header "Detecting environment"

$IsWSL = $false
if ($env:WSL_DISTRO_NAME) { $IsWSL = $true }
$Arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture

if ($IsLinux) {
    Write-Info "OS: Linux (detected via PowerShell on Linux) | Arch: $Arch"
    Write-Warn "On Linux/macOS, consider using the bash installer instead:"
    Write-Warn "  curl -sL $RepoUrl/install.sh | bash"
} elseif ($IsMacOS) {
    Write-Info "OS: macOS | Arch: $Arch"
    Write-Warn "On macOS, consider using the bash installer instead:"
    Write-Warn "  curl -sL $RepoUrl/install.sh | bash"
} else {
    Write-Info "OS: Windows | Arch: $Arch"
}

# ── 2. Check / Install Python 3.9+ ──────────────────────────────────────────
Write-Header "Checking Python"

$PythonCmd = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 9) {
                $PythonCmd = $cmd
                break
            }
        }
    } catch { }
}

if ($PythonCmd) {
    $pyVer = & $PythonCmd --version 2>&1
    Write-Ok "Found $PythonCmd ($pyVer)"
} else {
    Write-Warn "Python 3.9+ not found."

    $installPython = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        if (Confirm-Action "Install Python 3.12 via winget?") {
            Write-Info "Installing Python via winget..."
            winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            $installPython = $true
        }
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        if (Confirm-Action "Install Python 3 via Chocolatey?") {
            Write-Info "Installing Python via Chocolatey..."
            choco install python3 -y
            $installPython = $true
        }
    } else {
        Write-Err "No package manager found (winget or choco)."
        Write-Err "Please install Python 3.9+ manually from https://www.python.org/downloads/"
        throw "Python 3.9+ is required."
    }

    if (-not $installPython) {
        throw "Python 3.9+ is required. Install it and re-run this script."
    }

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    # Re-check
    foreach ($cmd in @("python3", "python", "py")) {
        try {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver) {
                $parts = $ver.Split(".")
                if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 9) {
                    $PythonCmd = $cmd
                    break
                }
            }
        } catch { }
    }

    if (-not $PythonCmd) {
        throw "Python 3.9+ still not found after installation. You may need to restart your terminal."
    }
    $pyVer = & $PythonCmd --version 2>&1
    Write-Ok "Installed $PythonCmd ($pyVer)"
}

# ── 3. Create virtual environment ───────────────────────────────────────────
Write-Header "Setting up virtual environment"

New-Item -ItemType Directory -Path $SkillDir -Force | Out-Null

$venvActivate = Join-Path $VenvDir "Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Info "Virtual environment already exists, reusing."
} else {
    Write-Info "Creating venv at $VenvDir..."
    & $PythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) { throw "Venv python not found at $VenvPython" }
Write-Ok "Virtual environment ready ($VenvPython)"

# ── 4. Install Python dependencies ──────────────────────────────────────────
Write-Header "Installing Python dependencies"

& $VenvPip install --upgrade pip --quiet 2>$null
& $VenvPip install "agent-memory-toolkit @ git+https://github.com/TheovanKraay/AgentMemoryToolkit.git" "azure-identity>=1.17" --quiet
if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies. Make sure git is installed (required for git+https:// packages)." }
Write-Ok "Installed agent-memory-toolkit and azure-identity"

# ── 5. Download skill files ─────────────────────────────────────────────────
Write-Header "Downloading skill files"

$SkillFiles = @(
    ".github/skills/repo-memory/SKILL.md",
    ".github/skills/repo-memory/skill.json",
    ".github/skills/repo-memory/requirements.txt",
    ".github/skills/repo-memory/scripts/memory_cli.py",
    ".github/skills/repo-memory/scripts/session_sync/__init__.py",
    ".github/skills/repo-memory/scripts/session_sync/base.py",
    ".github/skills/repo-memory/scripts/session_sync/claude_code.py",
    ".github/skills/repo-memory/scripts/session_sync/copilot.py",
    ".github/skills/repo-memory/scripts/session_sync/cursor.py",
    ".github/skills/repo-memory/scripts/session_sync/codex.py",
    ".github/skills/repo-memory/scripts/session_sync/openclaw.py",
    ".github/skills/repo-memory/scripts/session_sync/store.py"
)

foreach ($file in $SkillFiles) {
    $relativePath = $file -replace "/", "\"
    $localPath = Join-Path $PWD $relativePath
    $dir = Split-Path $localPath -Parent
    if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

    try {
        Invoke-RestMethod -Uri "$RepoUrl/$file" -OutFile $localPath
        Write-Ok "Downloaded $file"
    } catch {
        Write-Err "Failed to download $file"
        throw "Download failed. Check your internet connection and try again."
    }
}

# ── 6. Copy markdown templates ──────────────────────────────────────────────
Write-Header "Setting up markdown templates"

$Templates = @("STATE.md", "DECISIONS.md", "CHANGELOG.md", "FAILURES.md", "AGENTS.md")

foreach ($tmpl in $Templates) {
    if (Test-Path $tmpl) {
        $SkippedTemplates += $tmpl
        Write-Info "Skipped $tmpl (already exists)"
    } else {
        $templateDir = Join-Path $SkillDir "templates"
        New-Item -ItemType Directory -Path $templateDir -Force | Out-Null
        $src = Join-Path $templateDir $tmpl
        try {
            Invoke-RestMethod -Uri "$RepoUrl/.github/skills/repo-memory/templates/$tmpl" -OutFile $src
            Copy-Item $src $tmpl
            $CreatedTemplates += $tmpl
            Write-Ok "Created $tmpl"
        } catch {
            Write-Warn "Could not download template $tmpl"
        }
    }
}

# ── 7. Update .gitignore ────────────────────────────────────────────────────
Write-Header "Updating .gitignore"

if (-not (Test-Path .gitignore)) { New-Item -ItemType File -Path .gitignore | Out-Null }

$gitignoreEntries = @(".github/skills/repo-memory/.venv/", "__pycache__/")
$gitignoreContent = Get-Content .gitignore -Raw -ErrorAction SilentlyContinue

foreach ($entry in $gitignoreEntries) {
    if ($gitignoreContent -notmatch [regex]::Escape($entry)) {
        Add-Content .gitignore $entry
        Write-Ok "Added '$entry' to .gitignore"
    } else {
        Write-Info "'$entry' already in .gitignore"
    }
}

# ── 8. Check Azure environment variables ────────────────────────────────────
Write-Header "Checking Azure configuration"

$CosmosOk = $false
$FoundryOk = $false

if ($env:COSMOS_DB_ENDPOINT) {
    Write-Ok "COSMOS_DB_ENDPOINT is set"
    $CosmosOk = $true
} else {
    Write-Warn "COSMOS_DB_ENDPOINT is not set."
    Write-Warn '  Set it: $env:COSMOS_DB_ENDPOINT = "https://your-account.documents.azure.com:443/"'
    Write-Warn "  Docs: https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/"
}

if ($env:AI_FOUNDRY_ENDPOINT) {
    Write-Ok "AI_FOUNDRY_ENDPOINT is set"
    $FoundryOk = $true
} else {
    Write-Warn "AI_FOUNDRY_ENDPOINT is not set."
    Write-Warn "  Required for semantic/hybrid search (vector embeddings)."
    Write-Warn '  Set it: $env:AI_FOUNDRY_ENDPOINT = "https://your-resource.cognitiveservices.azure.com/"'
    Write-Warn "  Docs: https://ai.azure.com/"
}

if ($CosmosOk -and -not $SkipCosmos) {
    if (Confirm-Action "Run 'memory_cli.py init' to set up Cosmos DB?") {
        Write-Info "Initializing Cosmos DB..."
        try {
            & $VenvPython (Join-Path $SkillDir "scripts\memory_cli.py") init
            if ($LASTEXITCODE -ne 0) { throw "init returned non-zero exit code" }
            Write-Ok "Cosmos DB initialized"
        } catch {
            Write-Warn "Cosmos DB init failed: $_"
            Write-Warn "Run later: .github\skills\repo-memory\memory.ps1 init"
        }
    }
}

# ── 9. Create convenience wrapper ───────────────────────────────────────────
Write-Header "Creating CLI wrapper"

$wrapperPath = Join-Path $SkillDir "memory.ps1"
@'
# Convenience wrapper for memory_cli.py
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
& $VenvPython (Join-Path $ScriptDir "scripts\memory_cli.py") @args
'@ | Set-Content $wrapperPath -Encoding UTF8

# Also create a .cmd wrapper for cmd.exe users
$cmdWrapper = Join-Path $SkillDir "memory.cmd"
@"
@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\memory_cli.py" %*
"@ | Set-Content $cmdWrapper -Encoding ASCII

Write-Ok "Created $wrapperPath (PowerShell)"
Write-Ok "Created $cmdWrapper (cmd.exe)"

# ── 10. Summary ──────────────────────────────────────────────────────────────
Write-Header "Installation complete! 🎉"

Write-Host ""
Write-Ok "Skill installed to: $SkillDir\"
Write-Ok "Virtual environment: $VenvDir\"

if ($CreatedTemplates.Count -gt 0) {
    Write-Ok "Templates created: $($CreatedTemplates -join ', ')"
}
if ($SkippedTemplates.Count -gt 0) {
    Write-Info "Templates skipped (already exist): $($SkippedTemplates -join ', ')"
}

Write-Host ""
if ($CosmosOk -and $FoundryOk) {
    Write-Ok "Azure: fully configured"
} elseif ($CosmosOk) {
    Write-Warn "Azure: Cosmos DB configured, AI Foundry missing (search won't work)"
} else {
    Write-Warn "Azure: not configured (set COSMOS_DB_ENDPOINT and AI_FOUNDRY_ENDPOINT)"
}

Write-Host ""
Write-Host "Usage:" -ForegroundColor White
Write-Host "  # Store a memory"
Write-Host "  .github\skills\repo-memory\memory.ps1 add --user-id agent-1 --thread-id sess-001 --role agent --content `"your memory`""
Write-Host ""
Write-Host "  # Search memories"
Write-Host "  .github\skills\repo-memory\memory.ps1 search --query `"auth`" --user-id agent-1 --hybrid"
Write-Host ""
Write-Host "  # Sync agent sessions"
Write-Host "  .github\skills\repo-memory\memory.ps1 session-sync"
Write-Host ""
Write-Host "Documentation:" -ForegroundColor White
Write-Host "  https://github.com/TheovanKraay/coding-agent-memory-kit"
Write-Host "  $SkillDir\SKILL.md"
Write-Host ""
