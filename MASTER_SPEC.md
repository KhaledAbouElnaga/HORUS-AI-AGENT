# HORUS AI Agent — Master Specification

## Purpose

This repository is the single shared coordination workspace for the HORUS AI Agent project. Bootstrap establishes the shared contract and review loop; it does not implement product behavior.

## Bootstrap boundary

This milestone creates and reviews project-control documents only. No product code, irreversible integration, provider change, credential change, routing change, billing enablement, or modification of existing HORUS systems is authorized.

## Product specification status

The product requirements are intentionally **not yet defined** in this repository. The next planning/review cycle must establish, at minimum:

- users, roles, and supported interaction surfaces;
- required capabilities and explicit non-goals;
- data handling, privacy, and retention requirements;
- reliability, observability, and recovery expectations;
- security boundaries and human approval gates;
- testable acceptance criteria for each milestone.

Until those decisions are reviewed through GitHub, implementation must not begin.

## Collaboration contract

- Work on feature branches; do not push unreviewed implementation directly to `main`.
- Each milestone is delivered through a pull request with tests and a concise test report.
- Review comments and requested changes are part of the delivery loop.
- Preserve checkpoints and provide rollback for structural changes.
- Never put secrets, tokens, cookies, API keys, or credentials in GitHub.
- Do not use paid services or enable billing during bootstrap.
