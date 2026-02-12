#!/opt/homebrew/bin/bash
# speckit-sync.sh - Sync speckit template from GitHub to current project
# Usage:
#   ./speckit-sync.sh init              # First-time setup
#   ./speckit-sync.sh sync              # Update from template
#   ./speckit-sync.sh sync --category claude  # Sync specific category
#   ./speckit-sync.sh sync --dry-run    # Preview changes
#   ./speckit-sync.sh sync --force      # Overwrite without prompting
#   ./speckit-sync.sh status            # Show sync info

set -e

# Configuration
REPO="leonardoFu/speckit-wiggum-toolkit"
BRANCH="main"
SYNC_FILE=".speckit-sync.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Syncable categories and their paths
declare -A CATEGORY_PATHS
CATEGORY_PATHS[claude]=".claude/commands .claude/skills .claude/schemas"
CATEGORY_PATHS[specify]=".specify/templates .specify/scripts .specify/memory"
CATEGORY_PATHS[scripts]="loop.sh"

# Files that should never be synced
NEVER_SYNC=".claude/settings.local.json .specify/workflow-state"

# Files that require user confirmation before overwriting
PROMPT_BEFORE_OVERWRITE=".specify/memory/constitution.md loop.sh"

print_usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  init                  Initialize speckit in current project"
    echo "  sync                  Sync template files from GitHub"
    echo "  status                Show current sync status"
    echo ""
    echo "Options for sync:"
    echo "  --category <name>     Sync specific category (claude, specify, scripts, all)"
    echo "  --dry-run             Preview what would be synced"
    echo "  --force               Overwrite all files without prompting"
    echo ""
    echo "Examples:"
    echo "  $0 init"
    echo "  $0 sync"
    echo "  $0 sync --category claude"
    echo "  $0 sync --dry-run"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed. Install with: brew install jq"
        exit 1
    fi
}

# Clone or update template repo to temp directory
fetch_template() {
    local temp_dir="$1"

    log_info "Fetching template from github.com/$REPO..."

    if [ -d "$temp_dir" ]; then
        rm -rf "$temp_dir"
    fi

    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$temp_dir" 2>/dev/null

    if [ $? -ne 0 ]; then
        log_error "Failed to clone template repository"
        exit 1
    fi

    log_success "Template fetched successfully"
}

# Get current git commit hash from template
get_template_commit() {
    local temp_dir="$1"
    git -C "$temp_dir" rev-parse HEAD 2>/dev/null | cut -c1-7
}

# Get template version from package.json
get_template_version() {
    local temp_dir="$1"
    if [ -f "$temp_dir/package.json" ]; then
        jq -r '.version // "0.0.0"' "$temp_dir/package.json"
    else
        echo "0.0.0"
    fi
}

# Check if file should be skipped
should_skip() {
    local file="$1"
    for skip in $NEVER_SYNC; do
        if [[ "$file" == "$skip"* ]]; then
            return 0
        fi
    done
    return 1
}

# Check if file needs user confirmation
needs_confirmation() {
    local file="$1"
    for prompt_file in $PROMPT_BEFORE_OVERWRITE; do
        if [[ "$file" == "$prompt_file" ]]; then
            return 0
        fi
    done
    return 1
}

# Calculate MD5 checksum of file
get_checksum() {
    local file="$1"
    if [ -f "$file" ]; then
        if command -v md5sum &> /dev/null; then
            md5sum "$file" | cut -d' ' -f1
        else
            md5 -q "$file"
        fi
    else
        echo ""
    fi
}

# Check if file was modified since last sync
was_modified() {
    local file="$1"

    if [ ! -f "$SYNC_FILE" ]; then
        return 1
    fi

    local stored_checksum
    stored_checksum=$(jq -r --arg f "$file" '.syncedFiles[] | select(.path == $f) | .checksum // ""' "$SYNC_FILE" 2>/dev/null)

    if [ -z "$stored_checksum" ]; then
        return 1
    fi

    local current_checksum
    current_checksum=$(get_checksum "$file")

    if [ "$stored_checksum" != "$current_checksum" ]; then
        return 0
    fi

    return 1
}

# Sync a single file
sync_file() {
    local src="$1"
    local dst="$2"
    local force="$3"
    local dry_run="$4"

    # Skip if in never sync list
    if should_skip "$dst"; then
        log_info "Skipping $dst (never synced)"
        return 0
    fi

    # Check if destination exists and was modified
    if [ -f "$dst" ]; then
        if was_modified "$dst" && ! $force; then
            if needs_confirmation "$dst"; then
                log_warn "$dst has been modified locally"
                if ! $dry_run; then
                    read -p "Overwrite? [y/N] " -n 1 -r
                    echo
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        log_info "Skipping $dst"
                        return 0
                    fi
                else
                    log_info "Would prompt for: $dst"
                    return 0
                fi
            fi
        fi
    fi

    if $dry_run; then
        if [ -f "$dst" ]; then
            log_info "Would update: $dst"
        else
            log_info "Would create: $dst"
        fi
    else
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
        if [ -f "$dst" ]; then
            log_success "Updated: $dst"
        else
            log_success "Created: $dst"
        fi
    fi
}

# Sync a directory
sync_directory() {
    local src_dir="$1"
    local dst_dir="$2"
    local force="$3"
    local dry_run="$4"

    if [ ! -d "$src_dir" ]; then
        log_warn "Source directory not found: $src_dir"
        return 0
    fi

    # Find all files in source directory
    while IFS= read -r -d '' src_file; do
        local rel_path="${src_file#$src_dir/}"
        local dst_file="$dst_dir/$rel_path"

        sync_file "$src_file" "$dst_file" "$force" "$dry_run"
    done < <(find "$src_dir" -type f -print0 2>/dev/null)
}

# Update sync metadata
update_sync_metadata() {
    local temp_dir="$1"
    local categories="$2"

    local version
    version=$(get_template_version "$temp_dir")

    local commit
    commit=$(get_template_commit "$temp_dir")

    local date
    date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Collect synced files
    local synced_files="[]"
    for category in $categories; do
        if [ -n "${CATEGORY_PATHS[$category]}" ]; then
            for path in ${CATEGORY_PATHS[$category]}; do
                if [ -d "$path" ]; then
                    while IFS= read -r -d '' file; do
                        local checksum
                        checksum=$(get_checksum "$file")
                        synced_files=$(echo "$synced_files" | jq --arg p "$file" --arg c "$checksum" '. + [{"path": $p, "checksum": $c}]')
                    done < <(find "$path" -type f -print0 2>/dev/null)
                elif [ -f "$path" ]; then
                    local checksum
                    checksum=$(get_checksum "$path")
                    synced_files=$(echo "$synced_files" | jq --arg p "$path" --arg c "$checksum" '. + [{"path": $p, "checksum": $c}]')
                fi
            done
        fi
    done

    # Write sync metadata
    jq -n \
        --arg repo "$REPO" \
        --arg version "$version" \
        --arg commit "$commit" \
        --arg date "$date" \
        --arg categories "$categories" \
        --argjson files "$synced_files" \
        '{
            templateRepo: $repo,
            templateVersion: $version,
            templateCommit: $commit,
            lastSyncDate: $date,
            syncedCategories: ($categories | split(" ")),
            syncedFiles: $files
        }' > "$SYNC_FILE"

    log_success "Updated $SYNC_FILE"
}

# Interactive category selection
select_categories() {
    local selected=""

    echo ""
    echo "Select categories to sync:"
    echo ""

    read -p "  [Y/n] .claude/ (commands, skills, schemas)? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        selected="$selected claude"
    fi

    read -p "  [Y/n] .specify/ (templates, scripts, constitution)? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        selected="$selected specify"
    fi

    read -p "  [y/N] loop.sh (automation script)? " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        selected="$selected scripts"
    fi

    echo "$selected"
}

# Initialize command
cmd_init() {
    check_jq

    # Check if already initialized
    if [ -f "$SYNC_FILE" ]; then
        log_warn "Project already initialized. Use 'sync' to update."
        read -p "Reinitialize? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    fi

    # Select categories
    local categories
    categories=$(select_categories)

    if [ -z "$categories" ]; then
        log_error "No categories selected"
        exit 1
    fi

    log_info "Selected categories:$categories"

    # Fetch and sync
    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    fetch_template "$temp_dir"

    # Sync each category
    for category in $categories; do
        log_info "Syncing category: $category"

        if [ -n "${CATEGORY_PATHS[$category]}" ]; then
            for path in ${CATEGORY_PATHS[$category]}; do
                if [ -d "$temp_dir/$path" ]; then
                    sync_directory "$temp_dir/$path" "$path" false false
                elif [ -f "$temp_dir/$path" ]; then
                    sync_file "$temp_dir/$path" "$path" false false
                fi
            done
        fi
    done

    # Update metadata
    update_sync_metadata "$temp_dir" "$categories"

    echo ""
    log_success "Speckit initialized successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Review .specify/memory/constitution.md and customize for your project"
    echo "  2. Run './speckit-sync.sh status' to see what was synced"
    echo "  3. Use /speckit.specify to create your first feature spec"
}

# Sync command
cmd_sync() {
    local category="all"
    local dry_run=false
    local force=false

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --category)
                category="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    check_jq

    # Determine categories to sync
    local categories
    if [ "$category" = "all" ]; then
        if [ -f "$SYNC_FILE" ]; then
            categories=$(jq -r '.syncedCategories | join(" ")' "$SYNC_FILE")
        else
            categories="claude specify"
        fi
    else
        categories="$category"
    fi

    log_info "Syncing categories: $categories"

    if $dry_run; then
        log_info "Dry run mode - no changes will be made"
    fi

    # Fetch template
    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    fetch_template "$temp_dir"

    # Sync each category
    for cat in $categories; do
        log_info "Syncing category: $cat"

        if [ -n "${CATEGORY_PATHS[$cat]}" ]; then
            for path in ${CATEGORY_PATHS[$cat]}; do
                if [ -d "$temp_dir/$path" ]; then
                    sync_directory "$temp_dir/$path" "$path" "$force" "$dry_run"
                elif [ -f "$temp_dir/$path" ]; then
                    sync_file "$temp_dir/$path" "$path" "$force" "$dry_run"
                fi
            done
        fi
    done

    # Update metadata (unless dry run)
    if ! $dry_run; then
        update_sync_metadata "$temp_dir" "$categories"
    fi

    echo ""
    log_success "Sync complete!"
}

# Status command
cmd_status() {
    check_jq

    if [ ! -f "$SYNC_FILE" ]; then
        log_warn "Not initialized. Run './speckit-sync.sh init' first."
        exit 1
    fi

    echo ""
    echo -e "${BLUE}Speckit Sync Status${NC}"
    echo "===================="
    echo ""

    local repo version commit date categories
    repo=$(jq -r '.templateRepo' "$SYNC_FILE")
    version=$(jq -r '.templateVersion' "$SYNC_FILE")
    commit=$(jq -r '.templateCommit' "$SYNC_FILE")
    date=$(jq -r '.lastSyncDate' "$SYNC_FILE")
    categories=$(jq -r '.syncedCategories | join(", ")' "$SYNC_FILE")

    echo "Template Repo:    $repo"
    echo "Template Version: $version"
    echo "Template Commit:  $commit"
    echo "Last Synced:      $date"
    echo "Categories:       $categories"
    echo ""

    # Check for local modifications
    local modified_count=0
    local modified_files=""

    while IFS= read -r file; do
        if [ -f "$file" ] && was_modified "$file"; then
            modified_count=$((modified_count + 1))
            modified_files="$modified_files  $file\n"
        fi
    done < <(jq -r '.syncedFiles[].path' "$SYNC_FILE")

    if [ $modified_count -gt 0 ]; then
        echo -e "${YELLOW}Locally modified files ($modified_count):${NC}"
        echo -e "$modified_files"
    else
        echo -e "${GREEN}No local modifications detected${NC}"
    fi

    # Check for updates
    echo ""
    log_info "Checking for updates..."

    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$temp_dir" 2>/dev/null

    local latest_version latest_commit
    latest_version=$(get_template_version "$temp_dir")
    latest_commit=$(get_template_commit "$temp_dir")

    if [ "$latest_commit" != "$commit" ]; then
        echo -e "${YELLOW}Update available!${NC}"
        echo "  Current: $version ($commit)"
        echo "  Latest:  $latest_version ($latest_commit)"
        echo ""
        echo "Run './speckit-sync.sh sync' to update"
    else
        echo -e "${GREEN}You're up to date!${NC}"
    fi
}

# Main
main() {
    if [ $# -eq 0 ]; then
        print_usage
        exit 1
    fi

    local command="$1"
    shift

    case "$command" in
        init)
            cmd_init "$@"
            ;;
        sync)
            cmd_sync "$@"
            ;;
        status)
            cmd_status "$@"
            ;;
        -h|--help|help)
            print_usage
            ;;
        *)
            log_error "Unknown command: $command"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
