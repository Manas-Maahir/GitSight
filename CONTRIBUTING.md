# Contributing to GitSight

Thank you for your interest in contributing. This document explains how to get started, the development workflow, and the standards the project follows.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Running Tests](#running-tests)
5. [Submitting a Pull Request](#submitting-a-pull-request)
6. [Reporting Bugs](#reporting-bugs)
7. [Requesting Features](#requesting-features)
8. [Coding Standards](#coding-standards)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to uphold it.

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git

### Local setup

```bash
git clone https://github.com/Manas-Maahir/GitSight.git
cd GitSight/backend

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements-dev.txt
```

Copy the environment template:

```bash
cp .env.example .env
```

Start the server:

```bash
python main.py
```

---

## Development Workflow

1. Fork the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes.
3. Add or update tests in `backend/tests/`.
4. Run the test suite (see below).
5. Push your branch and open a pull request.

Branch naming convention:

| Prefix | Use for |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring without behaviour change |
| `test/` | Test additions or corrections |
| `chore/` | Tooling, dependencies, CI |

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

All tests must pass before a PR can be merged.

For linting:

```bash
pip install ruff
ruff check .
```

---

## Submitting a Pull Request

- Fill in the pull request template.
- Link any related issues using `Closes #<issue-number>`.
- Keep PRs focused — one concern per PR.
- Ensure CI is green before requesting review.
- Maintainers may request changes; please address them promptly.

---

## Reporting Bugs

Open a [Bug Report](https://github.com/Manas-Maahir/GitSight/issues/new?template=bug_report.md) and include:

- Steps to reproduce
- Expected vs. actual behaviour
- Python version and OS
- Any relevant error messages

---

## Requesting Features

Open a [Feature Request](https://github.com/Manas-Maahir/GitSight/issues/new?template=feature_request.md) and describe:

- The problem you are trying to solve
- Your proposed solution
- Any alternatives you have considered

---

## Coding Standards

- **Python:** follow [PEP 8](https://peps.python.org/pep-0008/). Use type hints on all function signatures.
- **Linter:** `ruff` with default settings.
- **Tests:** `pytest`. Aim for coverage of any non-trivial logic you add.
- **Comments:** only when the *why* is non-obvious. No narrative comments.
- **Commits:** use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, etc.).
