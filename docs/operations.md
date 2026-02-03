# Operations

This repo targets Windows-first delivery with CI and simple release artifacts.

## Recommended pipeline
- CI: unit tests + evals on Windows runners (see .github/workflows/ci.yml)
- Build: use scripts/build.ps1 to generate AgenticConsole.exe
- Release: tag version and upload artifact

## Continuous Delivery alignment (Windows/.NET takeaways)
- Version control discipline: trunk or short-lived branches; keep build scripts in repo.
- CI automation: run tests + evals on every commit; fail fast on broken builds.
- Deployment pipeline: separate build/test/release stages; promote artifacts, not source.
- Database changes: treat schema migrations as first-class tests in pipeline.
- Monitoring & APM: collect app metrics and aggregate Windows event logs centrally.
- Infrastructure automation: scripted environment setup; patching and OS updates automated.
- Operational features: health checks, feature flags, rollback plan, config externalization.

## Monitoring
- Local metrics: GET /api/metrics
- Logs: data/agentic.log
- Readiness snapshot: run `readiness` for a quick 4-pillar check

## Infrastructure
- Keep .env local
- Use Windows Task Scheduler for auto-start (optional)
