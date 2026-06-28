#!/usr/bin/env bash
# scripts/archive-pods.sh
#
# Archives old pod digests from .agent-inbox/ and .agent-handoffs/ to
# .agent-logs/archive/YYYY-MM/ to keep the inbox manageable.
#
# Rules:
#   - Files older than KEEP_DAYS days are moved to archive
#   - Archive directory is .agent-logs/archive/YYYY-MM/
#   - Resolved handoffs (status: complete/rejected) are archived immediately
#   - Log is appended to .agent-logs/archive.log
#
# Usage: bash scripts/archive-pods.sh [--dry-run] [--keep-days N]
#
# Install via crontab (see scripts/org.crontab).

set -euo pipefail

KEEP_DAYS="${PRYTAN_ARCHIVE_KEEP_DAYS:-14}"
DRY_RUN=false
INBOX_DIR=".agent-inbox"
HANDOFFS_DIR=".agent-handoffs"
ARCHIVE_BASE=".agent-logs/archive"
LOG_FILE=".agent-logs/archive.log"
ARCHIVE_DIR="${ARCHIVE_BASE}/$(date +%Y-%m)"

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --keep-days) KEEP_DAYS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

mkdir -p "${ARCHIVE_DIR}"

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
    echo "$msg"
    echo "$msg" >> "${LOG_FILE}"
}

move_file() {
    local src="$1"
    local dst="${ARCHIVE_DIR}/$(basename "${src}")"
    if [[ "${DRY_RUN}" == "true" ]]; then
        log "DRY-RUN: would move ${src} -> ${dst}"
    else
        mv "${src}" "${dst}"
        log "Archived: ${src} -> ${dst}"
    fi
}

archived=0
skipped=0

log "Archive run started (keep_days=${KEEP_DAYS}, dry_run=${DRY_RUN})"

# ── Archive old inbox files ──
if [[ -d "${INBOX_DIR}" ]]; then
    while IFS= read -r -d '' file; do
        move_file "${file}"
        ((archived++))
    done < <(find "${INBOX_DIR}" -maxdepth 1 -name "*.md" -mtime +"${KEEP_DAYS}" -print0 2>/dev/null)
fi

# ── Archive resolved handoffs ──
if [[ -d "${HANDOFFS_DIR}" ]]; then
    for file in "${HANDOFFS_DIR}"/*.md; do
        [[ -f "${file}" ]] || continue
        # Check if file contains "Status: complete" or "Status: rejected"
        if grep -qi "status:.*\(complete\|rejected\)" "${file}" 2>/dev/null; then
            move_file "${file}"
            ((archived++))
        else
            ((skipped++))
        fi
    done
fi

log "Archive run complete: ${archived} files archived, ${skipped} handoffs still open"

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "(Dry run — no files were actually moved)"
fi
