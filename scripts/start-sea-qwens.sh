#!/usr/bin/env bash
#
# start-sea-qwens.sh — Orchestrated startup for Sea Qwens
#
# Starts services in dependency order:
#   1. Infrastructure (Neo4j, ChromaDB)
#   2. Librarian (knowledge service)
#   3. Application services (atomizer, kanban, worker, tester, manager)
#
# Usage: ./scripts/start-sea-qwens.sh

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

DB_WAIT_SECONDS=30
LIBRARIAN_WAIT_SECONDS=10

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Pre-flight checks ────────────────────────────────────────────────────────
check_docker_compose() {
    if command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        error "Neither 'docker-compose' nor 'docker compose' found."
        error "Install Docker Compose and try again."
        exit 1
    fi
    success "Found compose via: ${COMPOSE_CMD}"
}

check_compose_file() {
    if [[ ! -f "${COMPOSE_FILE}" ]]; then
        error "docker-compose.yml not found at ${COMPOSE_FILE}"
        exit 1
    fi
}

# ── Helper: run compose with project dir ─────────────────────────────────────
compose() {
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" --project-directory "${PROJECT_DIR}" "$@"
}

# ── Helper: wait with countdown ──────────────────────────────────────────────
wait_seconds() {
    local total=$1
    local label=$2
    info "Waiting ${total}s for ${label}…"
    for ((i = total; i > 0; i--)); do
        printf "  %2ds\r" "${i}"
        sleep 1
    done
    printf "   \r"  # clear countdown line
    success "${label} ready."
}

# ── Step 1: Start infrastructure (Neo4j + ChromaDB) ──────────────────────────
start_infrastructure() {
    info "Starting infrastructure services (Neo4j, ChromaDB)…"
    compose up -d neo4j chromadb
    success "Neo4j and ChromaDB containers started."
}

# ── Step 2: Start Librarian ──────────────────────────────────────────────────
start_librarian() {
    info "Starting Librarian…"
    compose up -d librarian
    success "Librarian container started."
}

# ── Step 3: Start remaining application services ─────────────────────────────
start_application_services() {
    info "Starting application services (atomizer, kanban, worker, tester, manager)…"
    compose up -d atomizer kanban worker tester manager
    success "All application containers started."
}

# ── Step 4: Print service URLs ───────────────────────────────────────────────
print_urls() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Sea Qwens — Services Started${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${CYAN}Service${NC}          ${CYAN}URL${NC}"
    echo -e "  ─────────────────────────────────────────────────"
    echo -e "  Neo4j Browser    http://localhost:7474"
    echo -e "  Neo4j Bolt       bolt://localhost:7687"
    echo -e "  ChromaDB         http://localhost:8000"
    echo -e "  Librarian        http://localhost:8001"
    echo -e "  Atomizer         http://localhost:8002"
    echo -e "  Kanban           http://localhost:8003"
    echo -e "  Worker           http://localhost:8004"
    echo -e "  Tester           http://localhost:8005"
    echo -e "  Manager          http://localhost:8006"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Useful commands:"
    echo "    ${YELLOW}docker compose -f docker-compose.yml ps${NC}          # Check status"
    echo "    ${YELLOW}docker compose -f docker-compose.yml logs -f${NC}     # Follow all logs"
    echo "    ${YELLOW}docker compose -f docker-compose.yml logs <svc>${NC}  # Logs for one service"
    echo "    ${YELLOW}docker compose -f docker-compose.yml down${NC}        # Stop everything"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    info "Sea Qwens — Starting all services…"
    echo ""

    check_docker_compose
    check_compose_file

    # Phase 1: Infrastructure
    start_infrastructure
    wait_seconds "${DB_WAIT_SECONDS}" "databases to initialize"

    # Phase 2: Librarian
    start_librarian
    wait_seconds "${LIBRARIAN_WAIT_SECONDS}" "Librarian to boot"

    # Phase 3: Application services
    start_application_services

    # Phase 4: Summary
    print_urls

    success "Sea Qwens is up and running!"
    echo ""
}

main "$@"
