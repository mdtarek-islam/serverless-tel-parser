---
name: ci-cd-harness
description: CI/CD map for the serverless telemetry parser. Use to reproduce each CI job locally, triage flaky tests, diagnose failures and run the release checklist.
---

# ci-cd-harness

CI lives in `.github/workflows/ci.yml`. Python version: 3.12. Reproduce every job before you change it.

## Setup

1. Set `PY="/d/Machine Learning/.venv/Scripts/python.exe"`. Run tools through `"$PY" -m`.
2. Install dev tools only into that venv, with the pip in the same folder.

## CI stages and local reproduction

1. Secret scan, gitleaks: run the pinned binary from the CI file over the repo. Check its sha256 first.
2. Secret scan, regex: run the `grep -E` over `git ls-files` with the `SECRET_RE` value from the CI file.
3. pip-audit: `"$PY" -m pip_audit -r requirements.txt`.
4. bandit: `"$PY" -m bandit -r src -ll`.
5. ruff: `"$PY" -m ruff check .` then `"$PY" -m ruff format --check .`.
6. mypy: `"$PY" -m mypy src`.
7. pytest: `"$PY" -m pytest -q`.
8. Governance: `bash .claude/hooks/guard-claude-md.sh --audit` then `bash .claude/hooks/scan-skill.sh all`. Both need jq.
9. Terraform: `terraform -chdir=terraform fmt -check -recursive`, then `init -backend=false`, then `validate`.
10. Docker: `docker build -t tel-parser:ci .` with no push. Add `--progress=plain` to read layer output.

## Failure triage

1. Read the first error, not the last. Quote it.
2. Rerun the single step locally. If it passes locally, suspect runner drift or an unpinned dependency.
3. Compare tool versions: CI log against the local venv.
4. Fix the cause. Never add a skip, a retry or an ignore without a written reason.

## Flaky-test triage

1. Rerun the test 20 times: `"$PY" -m pytest -q path::test -p no:randomly --count 20` if the repeat plugin exists, else loop.
2. Look for: shared module state, test order, wall-clock timing, temp paths, random seeds.
3. Pin seeds. Inject clocks. Use tmp_path for files.
4. Quarantine a flaky test only with an issue reference and an owner. Latency tests need a margin, not a retry.

## Release checklist

1. Branch is `main`. Working tree is clean.
2. All CI stages pass on the release commit.
3. CHANGELOG.md has a dated section. The Unreleased section is empty.
4. The version in pyproject.toml matches the new section and follows semver.
5. The Docker image builds. The cold-start check passes the 200 ms target on the harness.
6. `terraform plan` shows only expected changes. The owner reviews the plan.
7. The tag name is `v<version>`. The owner creates it after the approval token.

## Rules

1. Pin every action to a version tag. Keep workflow permissions at `contents: read`.
2. Add a job only with a local reproduction line in this file.
3. Keep CI offline for AWS. No job holds cloud credentials.
