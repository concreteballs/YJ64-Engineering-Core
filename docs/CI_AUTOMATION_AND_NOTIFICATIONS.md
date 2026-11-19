# Engineering Core — CI evidence source

## Responsibility boundary

This document describes only the Engineering Core build/test pipeline as a source of engineering validation evidence. The autonomous cycle's CI event ingestion, log processing, model-provider analysis, repair proposals and patch-candidate generation are owned by [Motocicl](https://github.com/concreteballs/Motocicl), documented in [CI_EVENT_INGESTION_AND_REPAIR_PIPELINE.md](https://github.com/concreteballs/Motocicl/blob/main/docs/CI_EVENT_INGESTION_AND_REPAIR_PIPELINE.md).

## Engineering Core CI

- `.github/workflows/tests.yml` remains the Engineering Core's authoritative unit/FEM/CAD validation workflow.
- The exact repository, branch, commit SHA, workflow run and test result must accompany any engineering completion evidence returned to Motocicl.
- A passing local discipline test is not proof of whole-system acceptability; the cycle may request independent review or cross-disciplinary validation.
- Engineering Core does not own a durable autonomous queue, provider runtime, cycle scheduler or CI-repair loop.

## Cross-repository event boundary

GitHub Actions `workflow_run` events do not cross repository boundaries. Motocicl starts a fresh CI/build history and must establish its own event source and repository permissions. Legacy workflow history and the old CI-event pipeline remain available in Engineering Core's Git history; they are not migrated or reactivated by this documentation split.

No claim is made here that a live cross-repository event transport or Motocicl deployment is configured.
