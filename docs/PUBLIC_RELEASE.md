# Public Repository Release Guide

## Purpose

This field lab is intended to become public portfolio evidence when it can be
shared without exposing credentials, identities, private infrastructure, client
information, or misleading proof. Public access is valuable because readers can
inspect the code, reproduce the synthetic experiments, and audit the evidence
behind published findings.

Public visibility also exposes the repository's full reachable Git history—not
only the files visible on the default branch. Preparing the repository means
auditing current content, history, documentation, dependencies, evidence,
licenses, links, and GitHub settings before changing visibility.

## Non-negotiable boundary

Assume every tracked byte can become public. Do not publish:

- credentials, API keys, tokens, cookies, private keys, or environment values;
- real AWS account IDs, unredacted ARNs, resource IDs, session identifiers, or
  private endpoints;
- client, employer, customer, or collaborator information not explicitly
  approved for public use;
- personal data, private email addresses, local machine paths, or operational
  metadata that identifies a person or environment;
- raw cloud exports, private evidence, sensitive prompts, production data, or
  realistic examples copied from private work;
- third-party material without a compatible license and attribution; or
- generated, reconstructed, or synthetic material presented as original proof.

Use synthetic values and obvious placeholders. If provenance or privacy is
uncertain, keep the artifact out of Git and report the uncertainty.

## Release gates

### 1. Establish exact scope

- Record the repository, default branch, visibility, candidate release commit,
  and all local worktrees and branches.
- Confirm whether the goal is only public visibility or also a tagged release.
- Do not change visibility until the user explicitly approves it after seeing
  the audit report.

### 2. Audit the current tree

- Inspect all tracked filenames, including hidden files and evidence folders.
- Verify `.env`, credential files, private keys, Terraform state, raw evidence,
  cloud-private evidence, and local tool state are ignored and untracked.
- Search tracked content for secret formats, account IDs, ARNs, emails, private
  URLs, IP addresses, local absolute paths, names, and organization identifiers.
- Inspect images, PDFs, archives, notebooks, logs, CSV, JSON, and JSONL—not only
  source code and Markdown.
- Confirm every committed cloud artifact is redacted and privacy-safe.

### 3. Audit full Git history

- Use a dedicated history-aware scanner such as Gitleaks or TruffleHog when it
  is available from an approved source.
- Also run targeted history searches for provider keys, private-key headers,
  tokens, credentials, account IDs, and sensitive filenames.
- Report scanner availability, version, command, scope, and findings.
- A clean current tree is not enough. If a secret or private artifact ever
  entered reachable history, stop. Plan history remediation and credential
  rotation before visibility changes.

### 4. Verify evidence and claims

- Re-run applicable tests from a clean checkout of the candidate public commit.
- Trace every headline number to a committed privacy-safe artifact.
- Confirm redacted evidence cannot be joined with another file to recover a real
  identity or environment.
- Label estimates, synthetic data, reconstructed visuals, partial results,
  absent measurements, and untested claims accurately.
- Confirm teardown evidence contains no recoverable private identifiers.

### 5. Review public presentation

- Make the root README accurate about completed, planned, rejected, and partial
  experiments.
- Explain that the repository is a synthetic research lab and not production
  software or a production-readiness certification.
- Add or confirm an owner-approved license. Do not choose a license silently;
  explain the practical difference and ask when no durable choice exists.
- Add `SECURITY.md` if the owner wants a private vulnerability-reporting route.
- Verify third-party notices and attribution for copied code, schemas, images,
  datasets, or documentation excerpts.
- Remove stale branches or public-facing text only when doing so is safe and
  explicitly in scope. Do not rewrite history casually.

### 6. Review GitHub settings

- Confirm repository description, homepage, topics, default branch, and feature
  settings are intentional.
- Review Actions and workflow files for secret assumptions or unsafe pull-request
  behavior from forks.
- Review branch protection, Dependabot, code scanning, secret scanning, push
  protection, and vulnerability reporting options available for the account.
- Confirm issues, discussions, wiki, projects, releases, environments, webhooks,
  deploy keys, collaborators, and Pages expose nothing unintended.

### 7. Validate anonymously

After an explicitly approved visibility change:

- open the repository and every externally referenced evidence URL without an
  authenticated GitHub session;
- require successful responses for the experiment README, scenario contract,
  comparison CSV, S08 event evidence, and any article links;
- verify raw-file links download the intended redacted content;
- inspect the public repository landing page on desktop and mobile; and
- update the Blogger handoff and ClickUp only after the public URLs persist.

## Copy-ready prompt for a public-readiness session

```text
Prepare the AI Infrastructure Field Lab repository for a possible change from
private to public. Read AGENTS.md and docs/PUBLIC_RELEASE.md completely before
acting.

Repository:
Run this session from the root of the AI Infrastructure Field Lab checkout.

Objective:
Produce an evidence-backed public-readiness audit, make safe repository-only
corrections on a focused branch, and leave the repository ready for Collin's
final visibility decision. Treat every tracked file, reachable commit, branch,
PR, issue, log, artifact, and GitHub setting as potentially public.

Required work:
1. Record the exact repository visibility, default branch, clean/dirty state,
   worktrees, local and remote branches, candidate commit, and relevant open PRs.
2. Audit all tracked files and the full reachable Git history for credentials,
   tokens, private keys, environment values, real account IDs, ARNs, resource
   identifiers, private URLs, IPs, emails, names, client/employer information,
   local machine paths, sensitive prompts, production data, raw cloud evidence,
   and sensitive binary metadata.
3. Use a dedicated history-aware secret scanner when safely available. Record
   its name, version, exact command, scope, and result. If one is unavailable,
   do not call the audit complete; report that limitation and run documented
   targeted history searches as a partial fallback.
4. Verify .gitignore and Git tracking behavior for .env files, Terraform state,
   provider state, private evidence, raw evidence, logs, caches, and local tool
   directories. Remember that ignore rules do not remove prior history.
5. Review every committed evidence artifact and visual for redaction,
   provenance, synthetic labeling, cross-file re-identification risk, and claim
   traceability. Give special attention to Experiment 06 cloud evidence.
6. Re-run the relevant test suites from the candidate public commit and verify
   every externally referenced headline result.
7. Review README accuracy, documentation navigation, license status,
   third-party attributions, SECURITY.md need, GitHub Actions safety, repository
   description/topics/homepage, branch protection, scanning settings, issues,
   discussions, wiki, releases, Pages, environments, webhooks, deploy keys, and
   collaborators.
8. Check the blog and ClickUp handoff links. Identify which links currently
   require authentication and prepare an anonymous verification list for after
   visibility changes.
9. Make only clearly safe repository-content corrections on a focused branch.
   Do not expose or reproduce a discovered secret in output, commits, PR text,
   or task descriptions. If history remediation, credential rotation, license
   selection, collaborator removal, or another owner decision is needed, stop
   and request it explicitly.
10. Deliver a concise final report with CONFIRMED SAFE, REMEDIATED, BLOCKED,
    OWNER DECISION, and POST-VISIBILITY CHECKS sections. Include commands and
    proof without printing sensitive values.

Authorization boundary:
- Do not change repository visibility, publish a release, enable GitHub Pages,
  rewrite Git history, delete branches, remove collaborators, rotate credentials,
  or change external settings without Collin's explicit approval after the audit.
- Do not create cloud resources or incur paid usage.
- Do not weaken tests, remove honest limitations, or replace real redacted
  evidence with generated evidence to make the repository look cleaner.
- A clean scan is necessary but not sufficient. Confirm documentation,
  licensing, evidence integrity, and anonymous link behavior too.
```

## Final approval packet

Before requesting permission to change visibility, provide:

- candidate public commit and branch;
- clean working-tree proof;
- full-history scanner result and limitations;
- tracked-file privacy and evidence audit result;
- tests and exact pass counts;
- license and third-party attribution status;
- GitHub settings requiring an owner decision;
- exact visibility-change command or UI action, not yet executed; and
- the anonymous URL checklist to run immediately afterward.
