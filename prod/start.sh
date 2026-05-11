#!/usr/bin/env bash
# =============================================================================
# Sentrix NOC Platform — One-Click Startup Script
# =============================================================================
# Usage:
#   ./start.sh           Smart start (build on first run, up on subsequent)
#   ./start.sh --fresh   Full reset — wipes all data and rebuilds from scratch
#   ./start.sh --stop    Stop all services
#   ./start.sh --logs    Follow live logs for all services
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INFRA_DIR="$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[Sentrix]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*"; }
header()  { echo -e "\n${BOLD}${BLUE}$*${NC}"; }

# =============================================================================
# Handle flags
# =============================================================================
MODE="start"
case "${1:-}" in
  --fresh) MODE="fresh" ;;
  --stop)  MODE="stop" ;;
  --logs)  MODE="logs" ;;
  --help|-h)
    echo "Usage: ./start.sh [--fresh|--stop|--logs|--help]"
    echo ""
    echo "  (no flag)  Smart start — builds on first run, just starts on subsequent runs"
    echo "  --fresh    Full reset — wipes all data volumes and rebuilds from scratch"
    echo "  --stop     Stop all running services"
    echo "  --logs     Follow live logs for all services"
    exit 0
    ;;
esac

cd "$INFRA_DIR"

# =============================================================================
# STOP
# =============================================================================
if [ "$MODE" = "stop" ]; then
  info "Stopping all Sentrix services..."
  docker compose down
  success "All services stopped."
  exit 0
fi

# =============================================================================
# LOGS
# =============================================================================
if [ "$MODE" = "logs" ]; then
  docker compose logs -f
  exit 0
fi

# =============================================================================
header "Sentrix NOC Platform — Startup"
echo ""

# =============================================================================
# 1. Check Docker is installed and running
# =============================================================================
info "Checking Docker..."

if ! command -v docker &>/dev/null; then
  error "Docker is not installed."
  echo "  Install Docker Desktop from: https://www.docker.com/get-started"
  exit 1
fi

if ! docker info &>/dev/null 2>&1; then
  error "Docker is installed but not running."
  echo "  Start Docker Desktop and try again."
  exit 1
fi

# Check Docker Compose v2
if ! docker compose version &>/dev/null 2>&1; then
  error "Docker Compose v2 is required (bundled with Docker Desktop 4.0+)."
  echo "  Update Docker Desktop: https://www.docker.com/get-started"
  exit 1
fi

success "Docker is running ($(docker --version | cut -d' ' -f3 | tr -d ','))"

# =============================================================================
# 2. Check Git submodules are initialised
# =============================================================================
info "Checking submodules..."

cd "$PROJECT_ROOT"
if git submodule status 2>/dev/null | grep -q "^-"; then
  warn "Submodules not initialised — running git submodule update..."
  git submodule update --init --recursive
  success "Submodules ready."
else
  success "Submodules initialised."
fi
cd "$INFRA_DIR"

# =============================================================================
# 3. Check for port conflicts
# =============================================================================
info "Checking ports..."

PORTS=(3000 8080 5432 9092)
LABELS=(Frontend "API Gateway" PostgreSQL Kafka)
PORT_CONFLICT=0

for i in "${!PORTS[@]}"; do
  PORT="${PORTS[$i]}"
  LABEL="${LABELS[$i]}"
  if lsof -i ":$PORT" &>/dev/null 2>&1; then
    PROCESS=$(lsof -i ":$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1)
    PNAME=$(ps -p "$PROCESS" -o comm= 2>/dev/null || echo "unknown")
    warn "Port $PORT ($LABEL) is in use by: $PNAME (PID $PROCESS)"
    PORT_CONFLICT=1
  fi
done

if [ "$PORT_CONFLICT" = "1" ]; then
  echo ""
  warn "Port conflicts detected. Stop the conflicting processes or change ports in docker-compose.yml."
  echo "  To see what's on a port: lsof -i :PORT"
  echo ""
  read -rp "Continue anyway? (y/N): " CONTINUE
  [[ "$CONTINUE" =~ ^[Yy]$ ]] || exit 1
else
  success "All required ports are free."
fi

# =============================================================================
# 4. Set up .env file
# =============================================================================
info "Checking environment configuration..."

if [ ! -f ".env" ]; then
  if [ ! -f ".env.example" ]; then
    error ".env.example not found in $INFRA_DIR"
    exit 1
  fi
  cp .env.example .env
  warn ".env created from .env.example"
  echo ""
  echo "  You must set the following values in infra/prod/.env:"
  echo "  1. JWT_SECRET  — run: openssl rand -hex 32"
  echo "  2. POSTGRES_PASSWORD — any password you choose"
  echo ""
  read -rp "Open .env now to fill in secrets? (Y/n): " OPEN_ENV
  if [[ ! "$OPEN_ENV" =~ ^[Nn]$ ]]; then
    ${EDITOR:-nano} .env
  fi
fi

# Validate JWT_SECRET is not placeholder
JWT=$(grep "^JWT_SECRET=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ -z "$JWT" ] || echo "$JWT" | grep -qi "change\|paste\|your\|example\|secret-here"; then
  warn "JWT_SECRET looks like a placeholder."
  echo ""
  read -rp "Auto-generate a secure JWT_SECRET? (Y/n): " AUTO_JWT
  if [[ ! "$AUTO_JWT" =~ ^[Nn]$ ]]; then
    NEW_JWT=$(openssl rand -hex 32)
    # Replace JWT_SECRET line in .env
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^JWT_SECRET=.*|JWT_SECRET=$NEW_JWT|" .env
    else
      sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$NEW_JWT|" .env
    fi
    success "JWT_SECRET generated and saved to .env"
  else
    warn "Proceeding with placeholder JWT_SECRET — authentication may not work."
  fi
else
  success "JWT_SECRET is set."
fi

# Validate POSTGRES_PASSWORD
PG_PASS=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ -z "$PG_PASS" ] || echo "$PG_PASS" | grep -qi "change\|choose\|your\|example"; then
  warn "POSTGRES_PASSWORD looks like a placeholder."
  read -rp "Set a password (leave blank for 'sentrix123'): " NEW_PG
  NEW_PG="${NEW_PG:-sentrix123}"
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PG|" .env
  else
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PG|" .env
  fi
  success "POSTGRES_PASSWORD set."
else
  success "POSTGRES_PASSWORD is set."
fi

# =============================================================================
# 5. Detect architecture (ARM vs x86)
# =============================================================================
ARCH=$(uname -m)
COMPOSE_CMD="docker compose"
COMPOSE_FILES="-f docker-compose.yml"

if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
  if [ -f "docker-compose.arm.yml" ]; then
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.arm.yml"
    info "ARM architecture detected — using Bitnami Kafka (KRaft mode, no Zookeeper)"
  fi
fi

# =============================================================================
# 6. Detect first run vs restart
# =============================================================================
FIRST_RUN=false
if ! docker volume ls --format "{{.Name}}" 2>/dev/null | grep -q "prod_postgres_data"; then
  FIRST_RUN=true
fi

# Full reset
if [ "$MODE" = "fresh" ]; then
  warn "Fresh mode — this will DELETE all data (alerts, tickets, users, audit logs)."
  read -rp "Are you sure? (y/N): " CONFIRM
  [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
  info "Stopping and removing all volumes..."
  $COMPOSE_CMD $COMPOSE_FILES down -v 2>/dev/null || true
  FIRST_RUN=true
  info "Clean slate ready."
fi

# =============================================================================
# 7. Build and start
# =============================================================================
echo ""
if [ "$FIRST_RUN" = "true" ]; then
  header "First run — building all services (3–5 min)..."
  $COMPOSE_CMD $COMPOSE_FILES build --parallel
  $COMPOSE_CMD $COMPOSE_FILES up -d
else
  header "Starting services..."
  $COMPOSE_CMD $COMPOSE_FILES up -d
fi

# =============================================================================
# 8. Wait for API health (poll instead of fixed sleep)
# =============================================================================
header "Waiting for services to be healthy..."

MAX_WAIT=120
WAITED=0
INTERVAL=5

while [ "$WAITED" -lt "$MAX_WAIT" ]; do
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/health 2>/dev/null || echo "000")
  if [ "$HTTP_STATUS" = "200" ]; then
    success "API Gateway is healthy."
    break
  fi
  echo -n "."
  sleep "$INTERVAL"
  WAITED=$((WAITED + INTERVAL))
done

echo ""

if [ "$WAITED" -ge "$MAX_WAIT" ]; then
  error "API Gateway did not become healthy within ${MAX_WAIT}s."
  echo ""
  echo "  Checking for failed services..."
  FAILED=$($COMPOSE_CMD ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null | grep -i "restarting\|exit\|error" || true)
  if [ -n "$FAILED" ]; then
    error "Failed services:"
    echo "$FAILED"
    echo ""
    info "Showing logs for failed services:"
    $COMPOSE_CMD $COMPOSE_FILES logs --tail=30 2>/dev/null | grep -A10 "Error\|error\|FATAL\|panic" | head -40
  else
    info "All containers seem to be running — check logs: ./start.sh --logs"
  fi
  exit 1
fi

# =============================================================================
# 9. Check all 11 services are up
# =============================================================================
info "Checking all services..."
UNHEALTHY=$($COMPOSE_CMD ps --format "{{.Name}} {{.Status}}" 2>/dev/null | grep -v "Up\|healthy\|running" | grep -v "^$" || true)
if [ -n "$UNHEALTHY" ]; then
  warn "Some services may need a moment:"
  echo "$UNHEALTHY"
fi

# =============================================================================
# 10. Print summary
# =============================================================================
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Sentrix is running!${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Frontend:${NC}    http://localhost:3000"
echo -e "  ${BOLD}API:${NC}         http://localhost:8080/api/v1/health"
echo -e "  ${BOLD}PgAdmin:${NC}     http://localhost:5050   (DB browser)"
echo -e "  ${BOLD}Kafka UI:${NC}    http://localhost:8090   (queue browser)"
echo ""
echo -e "  ${BOLD}Login:${NC}       admin@admin.com / admin123"
echo -e "  ${BOLD}Role:${NC}        sysadmin (full access to all 22 features)"
echo ""
echo -e "  ${BOLD}Alerts appear on the dashboard within ~60 seconds.${NC}"
echo ""
echo "  Useful commands:"
echo "    Stop:    cd infra/prod && ./start.sh --stop"
echo "    Logs:    cd infra/prod && ./start.sh --logs"
echo "    Reset:   cd infra/prod && ./start.sh --fresh"
echo ""
