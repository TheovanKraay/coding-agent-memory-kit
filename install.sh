#!/usr/bin/env bash
# coding-agent-memory-kit universal installer
# Usage: curl -sL https://raw.githubusercontent.com/TheovanKraay/coding-agent-memory-kit/main/install.sh | bash
# Flags: --yes/-y (skip prompts), --skip-cosmos (skip Cosmos DB init)
set -e

# ── Globals ──────────────────────────────────────────────────────────────────
REPO_URL="https://raw.githubusercontent.com/TheovanKraay/coding-agent-memory-kit/main"
SKILL_DIR=".github/skills/repo-memory"
VENV_DIR="${SKILL_DIR}/.venv"
AUTO_YES=false
SKIP_COSMOS=false
CREATED_TEMPLATES=()
SKIPPED_TEMPLATES=()

# ── Colors ───────────────────────────────────────────────────────────────────
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

info()    { printf "${BLUE}ℹ ${NC}%s\n" "$*"; }
success() { printf "${GREEN}✔ ${NC}%s\n" "$*"; }
warn()    { printf "${YELLOW}⚠ ${NC}%s\n" "$*"; }
error()   { printf "${RED}✖ ${NC}%s\n" "$*"; }
header()  { printf "\n${BOLD}── %s ──${NC}\n" "$*"; }

die() { error "$*"; exit 1; }

cleanup() {
  local code=$?
  if [ $code -ne 0 ]; then
    error "Installation failed (exit code $code). Check messages above for details."
  fi
}
trap cleanup EXIT

# ── Parse args ───────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --yes|-y) AUTO_YES=true ;;
    --skip-cosmos) SKIP_COSMOS=true ;;
    *) warn "Unknown flag: $arg" ;;
  esac
done

confirm() {
  if $AUTO_YES; then return 0; fi
  printf "${YELLOW}? ${NC}%s [y/N] " "$1"
  read -r answer
  case "$answer" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

# ── 1. Detect OS & Architecture ─────────────────────────────────────────────
header "Detecting OS and architecture"

OS="unknown"; DISTRO="unknown"; ARCH="$(uname -m)"
case "$(uname -s)" in
  Darwin)
    OS="macos"
    case "$ARCH" in
      arm64) DISTRO="apple-silicon" ;;
      *)     DISTRO="intel" ;;
    esac
    ;;
  Linux)
    OS="linux"
    if [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; then
      OS="wsl"
    fi
    if [ -f /etc/os-release ]; then
      . /etc/os-release
      case "${ID:-}" in
        ubuntu|debian|pop|mint|elementary) DISTRO="debian" ;;
        fedora|rhel|centos|rocky|alma)     DISTRO="rhel" ;;
        arch|manjaro|endeavouros)          DISTRO="arch" ;;
        alpine)                            DISTRO="alpine" ;;
        *)                                 DISTRO="${ID:-unknown}" ;;
      esac
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*)
    die "Native Windows is not supported. Please use WSL2: https://learn.microsoft.com/en-us/windows/wsl/install"
    ;;
esac

info "OS: ${OS} | Distro: ${DISTRO} | Arch: ${ARCH}"

# ── 2. Check / Install Python 3.9+ ──────────────────────────────────────────
header "Checking Python"

PYTHON_CMD=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ver="$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    major="${ver%%.*}"; minor="${ver#*.}"
    if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 9 ]; then
      PYTHON_CMD="$cmd"
      break
    fi
  fi
done

if [ -n "$PYTHON_CMD" ]; then
  success "Found $PYTHON_CMD ($("$PYTHON_CMD" --version 2>&1))"
else
  warn "Python 3.9+ not found."
  install_python() {
    case "$OS-$DISTRO" in
      macos-*)
        if command -v brew >/dev/null 2>&1; then
          info "Installing Python via Homebrew..."
          brew install python3
        else
          error "Homebrew not found. Install Python manually:"
          error "  • Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
          error "  • Then: brew install python3"
          error "  • Or download from https://www.python.org/downloads/"
          return 1
        fi
        ;;
      *-debian)
        info "Installing Python via apt (requires sudo)..."
        sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
        ;;
      *-rhel)
        info "Installing Python via dnf (requires sudo)..."
        sudo dnf install -y python3 python3-pip
        ;;
      *-arch)
        info "Installing Python via pacman (requires sudo)..."
        sudo pacman -S --noconfirm python python-pip
        ;;
      *-alpine)
        info "Installing Python via apk (requires sudo)..."
        sudo apk add python3 py3-pip
        ;;
      *)
        error "Cannot auto-install Python for $OS/$DISTRO."
        error "Please install Python 3.9+ manually and re-run this script."
        return 1
        ;;
    esac
  }

  if confirm "Install Python 3.9+? (may require sudo)"; then
    install_python || die "Python installation failed. Install manually and re-run."
  else
    die "Python 3.9+ is required. Install it and re-run this script."
  fi

  # Re-check
  for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      ver="$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
      major="${ver%%.*}"; minor="${ver#*.}"
      if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 9 ]; then
        PYTHON_CMD="$cmd"
        break
      fi
    fi
  done
  [ -n "$PYTHON_CMD" ] || die "Python 3.9+ still not found after installation."
  success "Installed $PYTHON_CMD ($("$PYTHON_CMD" --version 2>&1))"
fi

# ── 3. Create virtual environment ───────────────────────────────────────────
header "Setting up virtual environment"

mkdir -p "$SKILL_DIR"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
  info "Virtual environment already exists, reusing."
else
  info "Creating venv at ${VENV_DIR}..."
  "$PYTHON_CMD" -m venv "$VENV_DIR" || die "Failed to create venv. You may need python3-venv: sudo apt-get install python3-venv"
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"
success "Virtual environment active"

# ── 4. Install Python dependencies ──────────────────────────────────────────
header "Installing Python dependencies"

pip install --upgrade pip --quiet 2>/dev/null || true
pip install "agent-memory-toolkit @ git+https://github.com/TheovanKraay/AgentMemoryToolkit.git" "azure-identity>=1.17" --quiet || die "Failed to install Python dependencies."
success "Installed agent-memory-toolkit and azure-identity"

# ── 5. Download skill files ─────────────────────────────────────────────────
header "Downloading skill files"

SKILL_FILES=(
  ".github/skills/repo-memory/SKILL.md"
  ".github/skills/repo-memory/skill.json"
  ".github/skills/repo-memory/requirements.txt"
  ".github/skills/repo-memory/scripts/memory_cli.py"
  ".github/skills/repo-memory/scripts/session_sync/__init__.py"
  ".github/skills/repo-memory/scripts/session_sync/base.py"
  ".github/skills/repo-memory/scripts/session_sync/claude_code.py"
  ".github/skills/repo-memory/scripts/session_sync/copilot.py"
  ".github/skills/repo-memory/scripts/session_sync/cursor.py"
  ".github/skills/repo-memory/scripts/session_sync/codex.py"
  ".github/skills/repo-memory/scripts/session_sync/openclaw.py"
  ".github/skills/repo-memory/scripts/session_sync/store.py"
)

for file in "${SKILL_FILES[@]}"; do
  dir="$(dirname "$file")"
  mkdir -p "$dir"
  if curl -sfL "${REPO_URL}/${file}" -o "$file"; then
    success "Downloaded ${file}"
  else
    error "Failed to download ${file}"
    die "Download failed. Check your internet connection and try again."
  fi
done

# ── 6. Copy markdown templates ──────────────────────────────────────────────
header "Setting up markdown templates"

TEMPLATES=("STATE.md" "DECISIONS.md" "CHANGELOG.md" "FAILURES.md" "AGENTS.md")

for tmpl in "${TEMPLATES[@]}"; do
  if [ -f "$tmpl" ]; then
    SKIPPED_TEMPLATES+=("$tmpl")
    info "Skipped ${tmpl} (already exists)"
  else
    src="${SKILL_DIR}/templates/${tmpl}"
    # Download template if not already present
    mkdir -p "${SKILL_DIR}/templates"
    if curl -sfL "${REPO_URL}/.github/skills/repo-memory/templates/${tmpl}" -o "$src" 2>/dev/null; then
      cp "$src" "$tmpl"
      CREATED_TEMPLATES+=("$tmpl")
      success "Created ${tmpl}"
    else
      warn "Could not download template ${tmpl}"
    fi
  fi
done

# ── 7. Update .gitignore ────────────────────────────────────────────────────
header "Updating .gitignore"

touch .gitignore
GITIGNORE_ENTRIES=(".github/skills/repo-memory/.venv/" "__pycache__/")
for entry in "${GITIGNORE_ENTRIES[@]}"; do
  if ! grep -qF "$entry" .gitignore; then
    echo "$entry" >> .gitignore
    success "Added '${entry}' to .gitignore"
  else
    info "'${entry}' already in .gitignore"
  fi
done

# ── 8. Check Azure environment variables ────────────────────────────────────
header "Checking Azure configuration"

COSMOS_OK=false
FOUNDRY_OK=false

if [ -n "${COSMOS_DB_ENDPOINT:-}" ]; then
  success "COSMOS_DB_ENDPOINT is set"
  COSMOS_OK=true
else
  warn "COSMOS_DB_ENDPOINT is not set."
  warn "  You need an Azure Cosmos DB account (NoSQL API) with vector search enabled."
  warn "  Set it: export COSMOS_DB_ENDPOINT=\"https://your-account.documents.azure.com:443/\""
  warn "  Docs: https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/"
fi

if [ -n "${AI_FOUNDRY_ENDPOINT:-}" ]; then
  success "AI_FOUNDRY_ENDPOINT is set"
  FOUNDRY_OK=true
else
  warn "AI_FOUNDRY_ENDPOINT is not set."
  warn "  Required for semantic/hybrid search (vector embeddings)."
  warn "  Set it: export AI_FOUNDRY_ENDPOINT=\"https://your-resource.cognitiveservices.azure.com/\""
  warn "  Docs: https://ai.azure.com/"
fi

if $COSMOS_OK && ! $SKIP_COSMOS; then
  echo ""
  info "Cosmos DB requires a database and container. With Entra ID auth, these must be created beforehand."
  info "You can create them in the Azure Portal, or run:"
  info "  az cosmosdb sql database create --account-name <account> --resource-group <rg> --name agent_memory"
  info "  az cosmosdb sql container create --account-name <account> --resource-group <rg> --database-name agent_memory --name memories --partition-key-path /userId"
  echo ""

  if [ -z "${COSMOS_DB_DATABASE:-}" ]; then
    printf "${YELLOW}? ${NC}Cosmos DB database name [agent_memory]: "
    read -r db_name
    [ -n "$db_name" ] && export COSMOS_DB_DATABASE="$db_name"
  fi
  if [ -z "${COSMOS_DB_CONTAINER:-}" ]; then
    printf "${YELLOW}? ${NC}Cosmos DB container name [memories]: "
    read -r container_name
    [ -n "$container_name" ] && export COSMOS_DB_CONTAINER="$container_name"
  fi

  if confirm "Run 'memory_cli.py init' to set up Cosmos DB? (will fail if database doesn't exist with Entra ID auth)"; then
    info "Initializing Cosmos DB..."
    if python "${SKILL_DIR}/scripts/memory_cli.py" init; then
      success "Cosmos DB initialized"
    else
      warn "Cosmos DB init failed. You can run it later:"
      warn "  .github/skills/repo-memory/memory init"
    fi
  fi
fi

# ── 9. Create convenience wrapper ───────────────────────────────────────────
header "Creating CLI wrapper"

cat > "${SKILL_DIR}/memory" << 'WRAPPER'
#!/usr/bin/env bash
# Convenience wrapper for memory_cli.py
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/scripts/memory_cli.py" "$@"
WRAPPER
chmod +x "${SKILL_DIR}/memory"
success "Created ${SKILL_DIR}/memory (executable)"

# ── 10. Configure agent instruction files ────────────────────────────────────
header "Configuring agent instruction files"

SNIPPET_PATH="${SKILL_DIR}/agent-instructions.md"
if [ ! -f "$SNIPPET_PATH" ]; then
  warn "agent-instructions.md not found — skipping agent config"
else
  SNIPPET=$(cat "$SNIPPET_PATH")

  inject_snippet() {
    local file="$1" name="$2" create_if_missing="$3"
    if [ "$create_if_missing" = "false" ] && [ ! -f "$file" ]; then
      return
    fi
    if [ -f "$file" ]; then
      if grep -q "repo-memory" "$file" 2>/dev/null; then
        info "$name already mentions repo-memory — skipped"
        return
      fi
      printf "\n\n%s" "$SNIPPET" >> "$file"
      success "Updated $name (appended)"
    else
      mkdir -p "$(dirname "$file")"
      printf "%s\n" "$SNIPPET" > "$file"
      success "Created $name"
    fi
  }

  inject_snippet ".github/copilot-instructions.md" ".github/copilot-instructions.md" "true"
  inject_snippet "CLAUDE.md" "CLAUDE.md" "true"
  inject_snippet ".cursorrules" ".cursorrules" "true"
  inject_snippet "AGENTS.md" "AGENTS.md" "false"
fi

# ── 11. Summary ──────────────────────────────────────────────────────────────
header "Installation complete! 🎉"

printf "\n"
success "Skill installed to: ${SKILL_DIR}/"
success "Virtual environment: ${VENV_DIR}/"

if [ ${#CREATED_TEMPLATES[@]} -gt 0 ]; then
  success "Templates created: ${CREATED_TEMPLATES[*]}"
fi
if [ ${#SKIPPED_TEMPLATES[@]} -gt 0 ]; then
  info "Templates skipped (already exist): ${SKIPPED_TEMPLATES[*]}"
fi

printf "\n"
if $COSMOS_OK && $FOUNDRY_OK; then
  success "Azure: fully configured ✔"
elif $COSMOS_OK; then
  warn "Azure: Cosmos DB configured, AI Foundry missing (search won't work)"
else
  warn "Azure: not configured (set COSMOS_DB_ENDPOINT and AI_FOUNDRY_ENDPOINT)"
fi

printf "\n${BOLD}Usage:${NC}\n"
echo "  # Store a memory"
echo "  .github/skills/repo-memory/memory add --user-id agent-1 --thread-id sess-001 --role agent --content \"your memory\""
echo ""
echo "  # Search memories"
echo "  .github/skills/repo-memory/memory search --query \"auth\" --user-id agent-1 --hybrid"
echo ""
echo "  # Initialize Cosmos DB (if not done during install)"
echo "  .github/skills/repo-memory/memory init"

printf "\n${BOLD}Documentation:${NC}\n"
echo "  https://github.com/TheovanKraay/coding-agent-memory-kit"
echo "  ${SKILL_DIR}/SKILL.md"
printf "\n"
