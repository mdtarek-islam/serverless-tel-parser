# serverless-tel-parser: Main Office

Owner: Md Tarek Islam (GitHub: mdtarek-islam). Output style: action first, numbered steps, max 5 items per list.

## 1. Purpose and Zones

This office keeps production healthy: maintenance, security and CI/CD. R&D happens on the generator branch.

Product: a serverless parser for Overwatch and Marvel Rivals scoreboard screenshots.
A PyTorch glyph CNN, int8-quantised to ONNX, runs in ONNX Runtime inside a Lambda container image.
API Gateway fronts the Lambda. DynamoDB stores rows. Terraform builds the stack. Cold-start target: under 200 ms.

| Zone | Path | Rule |
|---|---|---|
| Source | src/tel_parser/ | Handler, extractor, inference, layouts, storage, config, cold_start, model/. |
| Tests | tests/ | One test file per module. Test first. |
| Infrastructure | terraform/, Dockerfile | Review by secops-pentest-auditor before any change. |
| Governance | .claude/, CLAUDE.md, .github/ | Hooks, agents, skills, CI. Changes need owner approval. |
| Local archive | .dump/ | Local only. Timestamped copies. Never staged. |
| Model weights | model/*.onnx, *.pt | Local only. Never committed. |

## 2. Rules

1. Run Python only through the workspace venv: `"/d/Machine Learning/.venv/Scripts/python.exe"`. Install only into that venv.
2. Delete nothing. Never run rm, rmdir, unlink, git rm or git clean.
3. Archive before removal: move to `.dump/<file>.<YYYYMMDD-HHMMSS>.bak`.
4. Stage by exact path. Never use `git add -A` or `git add .`.
5. Sole author: MD Tarek Islam. Add no AI trailer, no Co-Authored-By line, no tool or vendor name.
6. Write British English. Use active voice, imperative verbs and sentences under 20 words.
7. Use zero emojis, zero em-dashes and zero en-dashes. Load stop-slop before any prose file.
8. Quote every path. Never read secret files: keys, pem files, credentials, local environment files.
9. Never commit, merge, push or deploy without an owner approval token.
10. Keep MAX_THINKING_TOKENS at 16000 or lower.

## 3. Agents

| Agent | Model | Job |
|---|---|---|
| sre-release-steward | haiku | Semver, CHANGELOG.md, PR checks, commit messages. |
| secops-pentest-auditor | sonnet | Hostile images, OWASP API Top 10, CVEs, IAM, container hardening. |
| env-simulation-tester | sonnet | Local Lambda emulator, API events, DynamoDB fake, latency harness. |
| ci-incident-responder | haiku | Diagnose GitHub Actions and CodeRabbit failures. |

1. Route by model: haiku for scouting and CI triage, sonnet for audit and test work.
2. Each agent file lists owned paths and a Definition of Done. Read it before you start.
3. Hand off between agents with caveman compression.

## 4. Skills

1. caveman: terse hand-off style between agents.
2. stop-slop: prose rules. Load before any prose file.
3. senior-commit: branch, stage and commit workflow. Needs the approval token.
4. secops-pentest: OWASP API checklist, image fuzz cases, IAM and container review.
5. ci-cd-harness: CI stages, local reproduction of each job, flaky-test triage, release checklist.

## 5. Branch Policy

1. `main` holds production code and the ops office. Only reviewed changes land here.
2. `generator` holds the R&D office: model work, prompts, scratch, notebooks.
3. Only the `/merge-to-main` command moves code from `generator` to `main`.
4. `/merge-to-main` copies a fixed path list. It never moves `.claude/`, prompts, scratch or weights.
5. Open a pull request for every change to `main`. CI and CodeRabbit must pass.

## 6. Commands and Checks

1. `/release`: bump semver, update CHANGELOG.md, run the release checklist. Stops for the token.
2. `/security-audit`: run the adversarial image suite, pip-audit, bandit, IAM and container review.
3. `/simulate-env`: run the local Lambda emulator and the latency harness.
4. Governance check: `bash .claude/hooks/guard-claude-md.sh --audit`.
5. Skill and hook check: `bash .claude/hooks/scan-skill.sh all`.

Approval tokens come from the owner: `bash .claude/hooks/ipc-bus.sh approve-git`. Agents never create tokens.
Edit CLAUDE.md or hooks only after the owner approves the exact diff.
