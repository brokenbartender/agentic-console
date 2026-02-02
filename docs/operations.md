# Operations

This repo targets Windows-first delivery with CI and simple release artifacts.

## Recommended pipeline
- CI: unit tests + evals on Windows runners (see .github/workflows/ci.yml)
- Build: use scripts/build.ps1 to generate AgenticConsole.exe
- Release: tag version and upload artifact

## Monitoring
- Local metrics: GET /api/metrics
- Logs: data/agentic.log

## Infrastructure
- Keep .env local
- Use Windows Task Scheduler for auto-start (optional)
