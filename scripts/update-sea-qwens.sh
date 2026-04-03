#!/usr/bin/env bash
#
# update-sea-qwens.sh — Update and restart Sea Qwens containers
#
# Rebuilds images and recreates containers with latest changes.
# Handles the full lifecycle: stop → rebuild → start → verify
#
# Usage: ./scripts/update-sea-qwens.sh

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

# ── Step 1: Stop and remove all running containers ───────────────────────────
stop_containers() {
    info "Stopping and removing all Sea Qwens containers…"
    
    # Try graceful shutdown first
    if compose ps --quiet 2>/dev/null | grep -q .; then
        compose down --remove-orphans 2>/dev/null || true
        success "Containers stopped and removed."
    else
        info "No running containers found via compose."
    fi
    
    # Force-remove any lingering containers by name
    info "Checking for lingering containers…"
    local container_names=("sea-qwens-neo4j" "sea-qwens-chromadb" "sea-qwens-librarian" "sea-qwens-manager" "sea-qwens-atomizer" "sea-qwens-kanban" "sea-qwens-worker" "sea-qwens-tester")
    
    for name in "${container_names[@]}"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${name}$"; then
            warn "Removing lingering container: ${name}"
            docker rm -f "${name}" 2>/dev/null || true
        fi
    done
    
    success "All containers cleaned up."
}

# ── Step 2: Pull latest base images ──────────────────────────────────────────
pull_base_images() {
    info "Pulling latest base images (Neo4j, ChromaDB)…"
    compose pull neo4j chromadb || warn "Some base images may not have updates."
    success "Base images pulled."
}

# ── Step 3: Rebuild service images ───────────────────────────────────────────
rebuild_images() {
    info "Rebuilding all service images from source…"
    compose build --no-cache
    success "All service images rebuilt."
}

# ── Step 4: Start infrastructure (Neo4j + ChromaDB) ──────────────────────────
start_infrastructure() {
    info "Starting infrastructure services (Neo4j, ChromaDB)…"
    compose up -d neo4j chromadb
    success "Neo4j and ChromaDB containers started."
}

# ── Step 5: Start Librarian ──────────────────────────────────────────────────
start_librarian() {
    info "Starting Librarian…"
    compose up -d librarian
    success "Librarian container started."
}

# ── Step 6: Start remaining application services ─────────────────────────────
start_application_services() {
    info "Starting application services (atomizer, kanban, worker, tester, manager)…"
    compose up -d atomizer kanban worker tester manager
    success "All application containers started."
}

# ── Step 7: Verify all services are running ──────────────────────────────────
verify_services() {
    info "Verifying all services are running…"
    echo ""
    
    local failed=0
    local services=("neo4j" "chromadb" "librarian" "manager" "atomizer" "kanban" "worker" "tester")
    
    for service in "${services[@]}"; do
        if compose ps --quiet "${service}" 2>/dev/null | grep -q .; then
            success "${service}: running"
        else
            error "${service}: NOT running"
            failed=1
        fi
    done
    
    echo ""
    if [[ ${failed} -eq 0 ]]; then
        success "All services verified successfully!"
    else
        error "Some services failed to start. Check logs with:"
        echo "    ${YELLOW}docker compose -f docker-compose.yml logs${NC}"
        exit 1
    fi
}

# ── Step 8: Print service URLs ───────────────────────────────────────────────
print_urls() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Sea Qwens — Updated and Running${NC}"
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
    info "Sea Qwens — Updating all services…"
    echo ""

    check_docker_compose
    check_compose_file

    # Phase 1: Stop existing containers
    stop_containers
    echo ""

    # Phase 2: Pull latest base images
    pull_base_images
    echo ""

    # Phase 3: Rebuild service images
    rebuild_images
    echo ""

    # Phase 4: Start infrastructure
    start_infrastructure
    wait_seconds "${DB_WAIT_SECONDS}" "databases to initialize"
    echo ""

    # Phase 5: Librarian
    start_librarian
    wait_seconds "${LIBRARIAN_WAIT_SECONDS}" "Librarian to boot"
    echo ""

    # Phase 6: Application services
    start_application_services
    echo ""

    # Phase 7: Verify
    verify_services
    echo ""

    # Phase 8: Summary
    print_urls

    success "Sea Qwens update complete!"
    echo ""
}

main "$@"
