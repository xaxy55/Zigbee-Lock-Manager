# ==============================================================================
# Zigbee Lock Manager — Developer Makefile
# ==============================================================================

# ── Colours ───────────────────────────────────────────────────────────────────
RESET   := \033[0m
BOLD    := \033[1m
RED     := \033[31m
GREEN   := \033[32m
YELLOW  := \033[33m
CYAN    := \033[36m
WHITE   := \033[37m
DIM     := \033[2m

# ── Config ────────────────────────────────────────────────────────────────────
MANIFEST := custom_components/zigbee_lock_manager/manifest.json
VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
TEST_DIR := tests

# Extract current version from manifest.json (e.g. "0.0.4")
CURRENT_VERSION := $(shell python3 -c "import json; print(json.load(open('$(MANIFEST)'))['version'])")

# Split into major.minor.patch
VERSION_MAJOR := $(shell echo "$(CURRENT_VERSION)" | cut -d. -f1)
VERSION_MINOR := $(shell echo "$(CURRENT_VERSION)" | cut -d. -f2)
VERSION_PATCH := $(shell echo "$(CURRENT_VERSION)" | cut -d. -f3)

.DEFAULT_GOAL := help

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  $(BOLD)$(CYAN)Zigbee Lock Manager$(RESET)  $(DIM)v$(CURRENT_VERSION)$(RESET)"
	@echo ""
	@echo "  $(BOLD)Testing$(RESET)"
	@echo "    $(GREEN)make test$(RESET)           Run the full test suite"
	@echo "    $(GREEN)make test-v$(RESET)         Run tests with verbose output"
	@echo "    $(GREEN)make lint$(RESET)           Run flake8 linter"
	@echo ""
	@echo "  $(BOLD)Versioning & Tagging$(RESET)"
	@echo "    $(YELLOW)make bump-patch$(RESET)     Test + bump patch + push tag (release)"
	@echo "    $(YELLOW)make bump-minor$(RESET)     Test + bump minor + push tag (release)"
	@echo "    $(YELLOW)make bump-major$(RESET)     Test + bump major + push tag (release)"
	@echo "    $(YELLOW)make tag$(RESET)            Create + push a git tag for the current version"
	@echo "    $(YELLOW)make release-patch$(RESET)  Alias of bump-patch"
	@echo "    $(YELLOW)make release-minor$(RESET)  Alias of bump-minor"
	@echo "    $(YELLOW)make release-major$(RESET)  Alias of bump-major"
	@echo ""
	@echo "  $(BOLD)Development$(RESET)"
	@echo "    $(CYAN)make install$(RESET)        Install Python dev dependencies"
	@echo "    $(CYAN)make update$(RESET)         Upgrade all dev dependencies"
	@echo "    $(CYAN)make clean$(RESET)          Remove __pycache__ and .pytest_cache"
	@echo ""
	@echo "  $(BOLD)Info$(RESET)"
	@echo "    $(WHITE)make version$(RESET)        Print the current version"
	@echo ""

# ── Version info ──────────────────────────────────────────────────────────────
.PHONY: version
version:
	@echo "$(BOLD)$(CYAN)Current version:$(RESET) $(CURRENT_VERSION)"

# ── Testing ───────────────────────────────────────────────────────────────────
.PHONY: test
test:
	@echo "$(BOLD)$(CYAN)Running tests…$(RESET)"
	@$(PYTHON) -m pytest $(TEST_DIR) -q && \
		echo "$(BOLD)$(GREEN)All tests passed.$(RESET)" || \
		(echo "$(BOLD)$(RED)Tests failed.$(RESET)" && exit 1)

.PHONY: test-v
test-v:
	@echo "$(BOLD)$(CYAN)Running tests (verbose)…$(RESET)"
	@$(PYTHON) -m pytest $(TEST_DIR) -v && \
		echo "$(BOLD)$(GREEN)All tests passed.$(RESET)" || \
		(echo "$(BOLD)$(RED)Tests failed.$(RESET)" && exit 1)

.PHONY: lint
lint:
	@echo "$(BOLD)$(CYAN)Linting…$(RESET)"
	@$(PYTHON) -m flake8 custom_components/ tests/ --max-line-length=120 && \
		echo "$(BOLD)$(GREEN)Lint clean.$(RESET)" || \
		(echo "$(BOLD)$(RED)Lint errors found.$(RESET)" && exit 1)

# ── Dependencies ──────────────────────────────────────────────────────────────
.PHONY: install
install:
	@echo "$(BOLD)$(CYAN)Installing dev dependencies…$(RESET)"
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --quiet pytest flake8 voluptuous jinja2 aiofiles
	@echo "$(GREEN)Done.$(RESET)"

.PHONY: update
update:
	@echo "$(BOLD)$(CYAN)Upgrading dev dependencies…$(RESET)"
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --quiet --upgrade pytest flake8 voluptuous jinja2 aiofiles
	@echo "$(GREEN)Done.$(RESET)"

# ── Clean ─────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	@echo "$(BOLD)$(CYAN)Cleaning build artifacts…$(RESET)"
	@find . -type d -name __pycache__ -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache
	@echo "$(GREEN)Clean.$(RESET)"

# ── Bump helpers ──────────────────────────────────────────────────────────────
# _set-version is an internal target called with NEW_VERSION=x.y.z
.PHONY: _set-version
_set-version:
	@if [ -z "$(NEW_VERSION)" ]; then echo "$(RED)NEW_VERSION not set$(RESET)"; exit 1; fi
	@$(PYTHON) -c "\
import json, sys; \
path='$(MANIFEST)'; \
data=json.load(open(path)); \
data['version']='$(NEW_VERSION)'; \
json.dump(data, open(path,'w'), indent=4); \
print(''); \
"
	@echo "$(BOLD)$(YELLOW)Version bumped:$(RESET) $(CURRENT_VERSION) → $(BOLD)$(NEW_VERSION)$(RESET)"
	@git add $(MANIFEST)
	@git commit -m "chore: bump version to $(NEW_VERSION)"
	@git push
	@echo "$(GREEN)Pushed version bump commit.$(RESET)"

.PHONY: bump-patch
bump-patch: test
	@$(MAKE) --no-print-directory _set-version \
		NEW_VERSION=$(VERSION_MAJOR).$(VERSION_MINOR).$(shell expr $(VERSION_PATCH) + 1)
	@$(MAKE) --no-print-directory tag

.PHONY: bump-minor
bump-minor: test
	@$(MAKE) --no-print-directory _set-version \
		NEW_VERSION=$(VERSION_MAJOR).$(shell expr $(VERSION_MINOR) + 1).0
	@$(MAKE) --no-print-directory tag

.PHONY: bump-major
bump-major: test
	@$(MAKE) --no-print-directory _set-version \
		NEW_VERSION=$(shell expr $(VERSION_MAJOR) + 1).0.0
	@$(MAKE) --no-print-directory tag

# ── Tagging ───────────────────────────────────────────────────────────────────
.PHONY: tag
tag:
	$(eval TAG_VERSION := $(shell python3 -c "import json; print(json.load(open('$(MANIFEST)'))['version'])"))
	@echo "$(BOLD)$(YELLOW)Creating tag v$(TAG_VERSION)…$(RESET)"
	@git tag -a "v$(TAG_VERSION)" -m "Release v$(TAG_VERSION)"
	@git push origin "v$(TAG_VERSION)"
	@echo "$(BOLD)$(GREEN)Tag v$(TAG_VERSION) pushed. GitHub Actions will create the release.$(RESET)"

# ── One-step release targets ──────────────────────────────────────────────────
.PHONY: release-patch
release-patch: bump-patch

.PHONY: release-minor
release-minor: bump-minor

.PHONY: release-major
release-major: bump-major
