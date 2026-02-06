# AGENTS.md – Guide for AI and automated tooling

This file helps AI coding agents and other tooling work effectively in the CopterFeeder repository.

## Project summary

**CopterFeeder** (project name in pyproject: **FeedCopterSpotter**) is a Python service that:

- Reads ADS-B aircraft data (e.g. from dump1090/readsb)
- Identifies helicopters using Bills operators data and ICAO types
- Reports rotorcraft to a MongoDB-backed API (CopterSpotter)

Typical deployment: Raspberry Pi or Ubuntu host with an SDR, often via [ADSB.im](https://adsb.im) images or Docker.

## Key files and directories

| Path | Purpose |
|------|--------|
| `fcs.py` | Main application entrypoint and logic (~1800+ lines) |
| `icao_heli_types.py` | ICAO helicopter type lookups |
| `get_bills.py` | Fetches/updates Bills operators data |
| `__version__.py` | Single source for version string (also mirrored in `fcs.py:VERSION`) |
| `config/` | Runtime config search path; see `config/README.md` |
| `docker-compose.yml` | Default Compose stack (build + run) |
| `docker-compose-buildx.yml` | Multi-arch build/push (arm64, amd64) for registry |
| `Dockerfile` | Multi-stage Python 3.12 image |
| `kube/dev/`, `kube/prod/` | Kubernetes manifests (deployments, services, configmaps) |
| `buildx/` | Scripts and config for Docker buildx multi-arch (Kubernetes builder) |
| `deprecated/` | Old scripts; avoid modifying for new behavior |
| `Types/` | Reference data (e.g. ICAO_TYPES.csv) |

## Tech stack

- **Python 3.12**
- **Dependencies:** `requirements.txt` (runtime), `requirements-dev.txt` (dev/lint)
- **Config:** `.env` (from `.env.example`), optional `config/` directory
- **Containers:** Docker Compose; multi-arch via Docker buildx
- **Orchestration:** Optional Kubernetes (see `kube/`)

## Commands (Makefile)

Prefer the Makefile for routine tasks:

- **`make`** / **`make build`** – Build container (default target)
- **`make up`** – Start containers in background (builds only if inputs changed, via `.build.done` sentinel)
- **`make down`** – Stop and remove containers
- **`make clean`** – Down + remove `.build.done` (next `make up` will rebuild)
- **`make black`** – Run Black formatter
- **`make pre-commit`** – Run all pre-commit hooks
- **`make bump`** – Bump version with commitizen (requires conventional commits)
- **`make force-bump`** – Force patch bump without conventional commits
- **`make setup-buildx`** – Set up buildx multi-arch builder
- **`make bake`** – Build and push multi-arch images (uses `docker-compose-buildx.yml`)

Run **`make help`** for the full list.

## Version and releases

- **Version** is kept in sync across many files. **Do not** edit version numbers by hand.
- Use **Commitizen** for bumps:
  - **`make bump`** – normal bump from conventional commits
  - **`make force-bump`** – force a patch bump
- Updated files are listed in `pyproject.toml` under `[tool.commitizen]` → `version_files` (e.g. `__version__.py`, `fcs.py:VERSION`, Dockerfile, docker-compose files, kube manifests, pyproject.toml).
- **CHANGELOG.md** is updated automatically on bump (`update_changelog_on_bump = true`).
- Use **conventional commits** so `cz bump` works (e.g. `feat:`, `fix:`, `BREAKING CHANGE:`).

## Code style and quality

- **Formatter:** Black (Python 3.12). Run **`make black`** before committing.
- **Pre-commit:** Hooks include trailing whitespace, end-of-file fixer, YAML/AST checks, Black, blacken-docs, and commitizen (commit-msg). Run **`make pre-commit`** to check everything.
- **Docstrings:** Check-docstring-first is enabled; prefer adding docstrings for new public modules/functions where it helps.

## Config and environment

- **`.env`** is the main config source (not committed; copy from `.env.example`). Contains API keys, feeder id, Mongo settings, optional `DEBUG`, `MONGO_CONN_LOG_*`, etc.
- The app also looks under **`config/`** for `.env` and `bills_operators.csv` (see `fcs.py` and README).
- **Kubernetes:** Env and secrets are in `kube/dev/` and `kube/prod/` (e.g. configmaps); do not commit real secrets.

## Docker and Kubernetes

- **Local run:** `make build` then `make up` (or `make up` alone; it builds when needed).
- **Multi-arch:** Use `make setup-buildx` once, then `make bake` to build and push for linux/arm64 and linux/amd64.
- **Kubernetes:** Use manifests in `kube/dev/` or `kube/prod/`; image is typically from the same registry as in `docker-compose-buildx.yml`.

## Conventions for agents

1. **Commits:** Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat:`, `fix:`) so `make bump` works; the commit-msg hook enforces the format.
2. **Version:** Never manually edit version in `__version__.py`, `fcs.py`, Dockerfile, docker-compose files, or kube manifests; use **`make bump`** or **`make force-bump`**.
3. **Style:** Run **`make black`** and **`make pre-commit`** when changing code or docs.
4. **Docs:** User-facing behavior and setup are in **README.md**; update it when changing install, run, or logging behavior.
5. **Build sentinel:** `.build.done` is used by `make up` to decide whether to rebuild; it’s in `.gitignore`. Don’t commit it.
6. **Legacy:** Code and paths under **`deprecated/`** and **`kube/zzz_deprecated/`** are legacy; prefer not adding new behavior there.
