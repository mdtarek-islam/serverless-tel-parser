---
description: Run the adversarial image suite, dependency audit, static scan, IAM and container review. Report only.
---

# /security-audit

Agent: secops-pentest-auditor. Skill: secops-pentest.

## Steps

1. Record the commit SHA and the date.
2. Run the fuzz tests in `tests/security/`. If the folder is empty, write the cases listed in secops-pentest first, each failing before it passes.
3. Run pip-audit over requirements.txt. Triage each CVE as reachable or not.
4. Run bandit over `src/`. Triage each finding.
5. Run the secret scans: gitleaks at the CI-pinned version, then the regex scan.
6. Review `terraform/` for IAM least privilege and `Dockerfile` for hardening, using the skill checklists.
7. Write the report in the skill format. Show it in the reply.

## Rules

1. Change no source file, terraform file or Dockerfile. Report the finding and the proposed fix.
2. Send no traffic to a live AWS account.
3. Print no secret value.
4. List critical and high findings first.
