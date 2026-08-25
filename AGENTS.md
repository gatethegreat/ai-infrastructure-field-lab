# AI Infrastructure Field Lab

This repository is a hands-on comparison lab for AI infrastructure. It is not
a production application and it is not committed to becoming a new product.

## Start here

1. Read `README.md`.
2. Read `docs/RESEARCH_PLAN.md`.
3. Read `docs/TOOL_MAP.md`.
4. Read the README for the active experiment.
5. Read `docs/PUBLIC_RELEASE.md` before preparing public content, evidence, or
   a repository-visibility change.
6. Update `results/SCORECARD.md`, `results/FINDINGS.md`, and
   `docs/DECISION_LOG.md` when an experiment reaches a decision boundary.

## Public repository safety boundary

Treat this repository, its Git history, branches, commits, pull requests,
issues, logs, and tracked artifacts as material that may be read by anyone.
This rule applies even while GitHub visibility is still private.

- Use only synthetic scenarios, identities, records, prompts, and simulated
  external actions.
- Never commit credentials, tokens, cookies, private keys, environment values,
  real account IDs, unredacted ARNs, customer or employer information, private
  URLs, personal data, raw cloud exports, sensitive prompts, or local machine
  paths containing personal information.
- Use explicit placeholders such as `<ACCOUNT_ID>`, `<REGION>`, and
  `<ROLE_ARN>` instead of realistic secret or identity values.
- Keep raw or private evidence only in ignored locations documented by
  `.gitignore`. Confirm the file is untracked before writing it; `.gitignore`
  does not protect content already committed to Git history.
- Commit only the minimum redacted evidence needed to reproduce or audit a
  claim. Generated examples must be labeled synthetic; recreated evidence must
  not be presented as an original artifact.
- Before every commit, inspect the staged diff and filenames for accidental
  disclosure. Before a public release, scan the full Git history, not only the
  current tree, using `docs/PUBLIC_RELEASE.md`.
- Treat copied vendor samples, images, datasets, and code as third-party
  material. Record their source and license before publishing them.
- If a value or artifact might identify a real person, organization, account,
  environment, or security boundary, stop and flag it for review rather than
  guessing that it is safe.
- Repository visibility changes, releases, and other public external actions
  still require explicit user approval after the public-readiness report.

## Working rules

- Preserve one shared synthetic incident scenario across experiments.
- Keep shared business contracts and fixtures under `shared/`.
- Keep tool-specific code, configuration, and evidence inside its experiment.
- Change shared contracts only through a documented decision explaining why
  every affected experiment must change.
- Start each experiment with the tool's native storage. Do not add PostgreSQL,
  object storage, Kubernetes, or another service without a test requirement.
- Use synthetic data and simulated external actions only.
- Pin tool, dependency, image, and provider versions used for evidence.
- Prefer primary documentation and record the source and research date.
- Run the official minimal example before adapting the shared scenario.
- A demo or successful exit code is not complete-system proof. Verify persisted
  state, recovery, side effects, and final resource state when applicable.
- Record `PROVEN`, `PARTIAL`, `ABSENT`, or `NOT TESTED`; do not invent scores.
- Keep model testing to one schema-valid smoke path. Do not tune answer quality
  unless an experiment explicitly studies evaluation or optimization.
- Do not create cloud resources, paid services, external repositories, or
  public releases without explicit user approval.
- Do not place secrets, credentials, sensitive prompts, or raw production data
  in the repository or evidence.
- Document and execute teardown after local experiments. Re-read final state.

## Experiment sequence

1. `00-baseline`
2. `01-openenv`
3. `02-model-operations`
4. `03-dapr-agents`
5. `04-vercel`
6. `05-pydanticai-dbos`
7. `06-strands-agentcore`
8. `07-langgraph`
9. `08-microsoft-agent-framework`
10. `09-restate` only if the earlier durability comparisons leave a named gap
11. `targeted` only for questions left open by the primary experiments

Do not skip the active experiment's entry gate or start a targeted tool merely
because it appears in the tool map.

## Required experiment artifacts

Each completed experiment must contain:

- objective and bounded research questions;
- pinned versions and primary sources;
- setup and teardown instructions;
- architecture and storage decisions;
- happy-path and applicable failure tests;
- evidence index;
- findings, limitations, and untested claims; and
- recommendation for the next bounded step.

## Git and external actions

- Use focused branches for experiment implementation.
- Keep commits small and evidence-oriented.
- Pull-request actions are allowed in this repository when the user requests
  them.
- Cloud deployment and paid usage are separate approval gates.
