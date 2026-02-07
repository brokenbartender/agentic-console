# Versioning

Agentic Console does not impose a release schema in code. Use git tags or releases to track versions.

## Practical guidance

- Tag deployments in git.
- Record the commit hash in run notes or release logs.
- Keep `data/` compatible by testing on a copy before upgrades.

## Run artifacts

Run artifacts capture the model name and timestamps, which helps compare behavior across versions.
