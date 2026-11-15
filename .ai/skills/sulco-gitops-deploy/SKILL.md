---
name: sulco-gitops-deploy
description: GitOps release engineering and pre-flight validation tooling for SULCO to audit secret hygiene, author signatures, and CI/CD pipelines.
---

# SULCO GitOps & Release Engineering Skill

This skill provides automated validation and GitOps procedures to ensure safe, audited, and seamless code promotions for the SULCO repository.

## Quick Start: Pre-Flight Release Audit

Run the pre-flight verification script before pushing or creating pull requests:

```bash
node .ai/skills/sulco-gitops-deploy/scripts/validate_preflight.cjs --repo-dir ./sulco-nasa
```

### Pre-Flight Verification Criteria

1. **Working Tree Cleanliness:** Verifies that no untracked or half-edited files are left floating.
2. **Author Identity Alignment:** Ensures all commits are signed by `Antenor Pires <contato@antenorpires.eng.br>`.
3. **Secret Leak Detection:** Scans tracked files for `.env`, `.pat`, `.pem`, or leaked keys.
4. **Branch Isolation:** Validates that development occurs on dedicated feature branches, not directly on `main`.

## CI/CD Pipeline & Vercel Templates

For complete GitHub Actions workflows and Vercel hybrid deployment configurations:
- [github_actions_templates.md](references/github_actions_templates.md)
