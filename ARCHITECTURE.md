# HORUS AI Agent — Architecture

## Bootstrap architecture

GitHub is the coordination plane for this project:

- **Issue #1** is the bootstrap entry point and initial control contract.
- **Feature branches** isolate proposed changes.
- **Pull requests** carry milestone artifacts, tests, reports, review comments, and requested changes.
- **`main`** is the reviewed baseline.
- **Repository documents** hold durable, non-secret project state.

## System boundary

Existing HORUS systems are external protected dependencies during bootstrap. This repository does not modify or reconfigure them. Providers, credentials, routing, deployments, and runtime integrations are out of scope until explicitly specified and reviewed.

## Future architecture decision points

Before product implementation, the project must decide and document the runtime components, interfaces, data flows, trust boundaries, failure behavior, deployment model, observability, and rollback strategy. These decisions must be testable and must not require paid services or billing by default.

## Change control

Structural changes require a checkpoint, a reversible change, tests, and review in a pull request. Secrets belong only in the approved runtime secret-management mechanism; never in GitHub repository content.
