# Z Files Folders

ZedBiz's operating skill for placing, naming, organizing, and verifying business files against the live Notion folder map and Files & Folders Guide.

## Use And Install

Read the authoritative [SKILL.md](SKILL.md). When to use: ZedBiz file placement, naming, organization, and migration. Do not use for server maintenance or unrelated content work.

Validate with the current Z AI Skill Developer validator using `--repository`, then run `python scripts/build_package.py` and validate `dist/z-files-folders/`. Install only that package in the executing agent's verified workspace skill root. Do not deploy this repository's `docs/` or tests as runtime instructions. Never store secrets in the package. Existing assignment approval covers routine scoped actions; out-of-scope actions need approval.

This skill supplies procedure, not credentials, Google Drive connectivity, a filesystem service, or continuous synchronization. OpenClaw file operations use the existing `z-drive-gog` skill and approved private account/root configuration. It does not change that configuration.

## Sources And Ownership

- Publisher: ZedBiz. Original organization-specific work; no third-party runtime code or dependencies.
- [Folder map](https://www.notion.so/386a3e33d58180ea96fbc50b60102fe2)
- [Files & Folders Guide](https://www.notion.so/3a9a3e33d58180548f4af69e804dcdfc)
- [Implementation and validation contract](docs/implementation.md)
- [Behavior test prompts](tests/prompts.md)

The live Notion sources own the map and policy. This repository owns the executable skill. No new license or third-party publication rights are implied.

## Verification

Use [behavior test prompts](tests/prompts.md) and retain actual named-agent results. A local copy test does not establish Google Drive access.
