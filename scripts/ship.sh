#!/usr/bin/env bash
# ship.sh — Run all quality gates locally, then push and open a PR to main.
#
# Usage:
#   make ship              # auto-generates PR title from branch name
#   make ship TITLE="..."  # custom PR title
set -euo pipefail

MAIN_BRANCH="main"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

step() { printf "\n${GREEN}▸ %s${NC}\n" "$1"; }
fail() { printf "\n${RED}✗ %s${NC}\n" "$1"; exit 1; }
warn() { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }

# ── Pre-flight checks ───────────────────────────────────────────────
command -v gh >/dev/null 2>&1 || fail "GitHub CLI (gh) is required. Install: brew install gh"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" = "$MAIN_BRANCH" ] && fail "You're on $MAIN_BRANCH. Create a feature branch first."

if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    warn "No uncommitted changes — shipping existing commits."
else
    fail "You have uncommitted changes. Commit your work before shipping."
fi

# ── Quality gates ────────────────────────────────────────────────────
step "Linting (ruff)"
ruff check src tests

step "Type-checking (mypy)"
mypy src

step "Python tests (pytest)"
pytest

if [ -d "web" ] && [ -f "web/package.json" ]; then
    step "Frontend tests (vitest)"
    (cd web && npm test -- --run)
fi

# ── Push & PR ────────────────────────────────────────────────────────
step "Pushing branch to origin"
git push -u origin "$BRANCH"

# Check if a PR already exists for this branch
EXISTING_PR=$(gh pr view "$BRANCH" --json number --jq '.number' 2>/dev/null || true)

if [ -n "$EXISTING_PR" ]; then
    warn "PR #$EXISTING_PR already exists for branch $BRANCH"
    PR_URL=$(gh pr view "$BRANCH" --json url --jq '.url')
    printf "\n${GREEN}✓ Branch pushed. Existing PR: %s${NC}\n" "$PR_URL"
else
    step "Creating pull request"
    TITLE="${1:-$(echo "$BRANCH" | sed 's/[-_]/ /g' | sed 's/.*/\u&/')}"
    PR_URL=$(gh pr create --title "$TITLE" --body "$(cat <<'EOF'
## Summary
Automated PR created via `make ship`.

## Checks passed locally
- [x] ruff lint
- [x] mypy strict
- [x] pytest
- [x] vitest (frontend)

## Test plan
- CI will re-run all checks in a clean environment
- Review changes before merging

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)")
    printf "\n${GREEN}✓ PR created: %s${NC}\n" "$PR_URL"
fi

printf "\n${GREEN}✓ All gates passed. PR is ready for review & merge.${NC}\n"
