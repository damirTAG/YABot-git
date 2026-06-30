# Yerzhan bot — task runner. Run `just` (or `just --list`) to see recipes.

# show available recipes
default:
    @just --list

# install deps (incl. dev tools) from the lockfile
install:
    uv sync

# run the bot locally
run:
    PYTHONPATH=src uv run python src/app.py

# lint with ruff
lint:
    uv run ruff check src tests

# auto-fix lint issues + format
fmt:
    uv run ruff check --fix src tests
    uv run ruff format src tests

# verify formatting without writing (CI parity)
fmt-check:
    uv run ruff format --check src tests

# type check (advisory, mirrors CI)
typecheck:
    uv run ty check src

# run the test suite
test:
    uv run pytest -q

# full local CI gate: lint + format check + tests
check: lint fmt-check test

# remove caches and temp download dirs
clean:
    rm -rf .ruff_cache .pytest_cache temp_downloads
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
