# Source Pins

Verified on 2026-09-08.

| Component | Pin | Purpose |
| --- | --- | --- |
| LiteLLM Python proxy | `1.100.0` | Local contract and overhead test |
| LiteLLM source | `e4f25265704e2b2c6cf6e81be2e4c5cffff896f4` | Commit behind release `v1.100.0` |
| AWS/OpenAI guidance | `eb04fe0842249e4583ac4257fed253b2ebf6d10d` | Current public `main` reference |
| AWS reference LiteLLM image | `ghcr.io/berriai/litellm@sha256:65d84a2282137b4dc73bbe184650a7c807177c533e4223b3bfbc87963fe3fabe` | Immutable image recorded by the AWS deployment guide |

## License boundary

The LiteLLM repository license makes code outside `enterprise/` available under
MIT and gives the `enterprise/` directory its separate license. The local test
uses the ordinary proxy without enabling enterprise-only JWT/SSO features. The
`litellm[proxy]` distribution may install separately packaged enterprise
components as dependencies; installation does not establish a license for
enterprise production features.

Before any production recommendation, recheck the license and feature boundary
against the exact deployed version.

## Pinning notes

- The latest stable release observed was `v1.100.0`, published 2026-09-06.
- That release specifically includes a fix for preserving conversations when
  chaining `previous_response_id`, making continuation a required regression
  case in this experiment.
- The AWS reference image digest and the latest PyPI release are separate pins.
  Local results from the wheel must not be represented as results from the AWS
  reference image.
- Docker Desktop was installed locally but its Linux engine was unavailable on
  2026-09-08. The official Python proxy path was used instead.

## Primary evidence

- https://github.com/BerriAI/litellm/releases/tag/v1.100.0
- https://github.com/BerriAI/litellm/blob/e4f25265704e2b2c6cf6e81be2e4c5cffff896f4/LICENSE
- https://github.com/openai-on-aws/guidance-codex/tree/eb04fe0842249e4583ac4257fed253b2ebf6d10d
- https://github.com/openai-on-aws/guidance-codex/blob/eb04fe0842249e4583ac4257fed253b2ebf6d10d/docs/QUICKSTART_LLM_GATEWAY_LITELLM.md
