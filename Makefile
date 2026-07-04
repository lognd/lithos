# The DX interface (AD-13). `make check` is the single gate; targets
# wrap uv/cargo/maturin so contributors never memorize the underneath.
.DEFAULT_GOAL := help
.PHONY: help install dev check fmt-check test test-rs test-py snapshots \
        schema fmt lint typecheck coverage bench fuzz build clean guard-core

UV ?= uv
CARGO ?= cargo

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install: ## uv sync + build the extension into the venv (debug)
	$(UV) sync
	$(UV) run maturin develop --uv

dev: ## Rebuild the extension into the venv on Rust change
	$(UV) run watchexec -e rs -- $(UV) run maturin develop --uv

check: fmt-check lint typecheck guard-core test-rs test-py ## Full gate, cheapest first

fmt-check:
	$(CARGO) fmt --all --check
	$(UV) run ruff format --check .

fmt: ## Format Rust + Python
	$(CARGO) fmt --all
	$(UV) run ruff format .

lint: ## clippy (-D warnings) + ruff lint
	$(CARGO) clippy --workspace --all-targets -- -D warnings
	$(UV) run ruff check .

typecheck: ## astral ty type-check on the Python package
	$(UV) run ty check python/rockhead

guard-core: ## Enforce: only compiler.py may import rockhead._core (AD-4)
	@bad=$$(grep -rElE '^[[:space:]]*(from[[:space:]]+rockhead[[:space:]]+import[[:space:]]+_core|from[[:space:]]+rockhead\._core[[:space:]]+import|import[[:space:]]+rockhead\._core)' \
		python/rockhead --include='*.py' | \
		grep -vE 'python/rockhead/compiler\.py$$' || true); \
	if [ -n "$$bad" ]; then \
		echo "AD-4 violation: rockhead._core imported outside compiler.py:"; \
		echo "$$bad"; exit 1; \
	fi

test: test-rs test-py ## All tests

test-rs: ## cargo test (workspace)
	$(CARGO) test --workspace

test-py: ## pytest through the real wheel
	$(UV) run pytest

snapshots: ## Review insta snapshots
	$(CARGO) insta review

schema: ## Regenerate _schema/ (stub until WO-18)
	@echo "schema codegen lands in WO-18 (AD-5)"

coverage: ## Rust + Python coverage
	$(CARGO) llvm-cov --workspace
	$(UV) run coverage run -m pytest && $(UV) run coverage report

bench: ## Criterion benchmarks
	$(CARGO) bench --workspace

fuzz: ## Fuzz targets (stub until WO-05; AD-3)
	@echo "cargo-fuzz targets land with the parser in WO-05 (AD-3)"

build: ## Release wheel
	$(UV) run maturin build --release

clean: ## Scrub build artifacts
	$(CARGO) clean
	rm -rf .venv target .pytest_cache .ruff_cache .mypy_cache
