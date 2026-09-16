# Acceptance Tests

## Bootstrap milestone

| ID | Acceptance criterion | Verification |
|---|---|---|
| B-01 | The six bootstrap deliverables exist at repository root. | `test -f` for every required file. |
| B-02 | Bootstrap contains no product implementation. | Review the branch diff and repository file list. |
| B-03 | Existing HORUS systems, providers, credentials, routing, and unrelated config are untouched. | Changes are confined to this new repository and bootstrap documents. |
| B-04 | No paid service or billing action is introduced. | Review diff and GitHub activity. |
| B-05 | No secret material is committed. | Manual review plus secret-pattern scan of tracked text. |
| B-06 | `STATUS.md` states milestone, last completed test, blockers, next action, and human-input requirement. | Read `STATUS.md`. |
| B-07 | The milestone is submitted for review through a feature-branch pull request. | Inspect the GitHub pull request. |

## Product milestones

Product acceptance tests are intentionally deferred until the product specification and architecture are approved through GitHub.
