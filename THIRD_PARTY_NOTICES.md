# Third-party notices

This repository is licensed under Apache License 2.0 for original project
content. The following tracked files are adapted from, or directly document,
third-party projects. Their licenses remain in effect for those portions.

## OpenEnv

- Project: [Hugging Face OpenEnv](https://github.com/huggingface/OpenEnv)
- Pinned source: [commit 65c506e](https://github.com/huggingface/OpenEnv/tree/65c506ef94bb1f7279cb4359673b3ef81031d01f)
- License: BSD 3-Clause
- Adapted file: `experiments/01-openenv/official_echo_smoke.py`
- Modification: adds evidence serialization, version capture, and command-line
  handling around the official Echo reset/step quick start.

Required BSD license text:

```text
BSD 3-Clause License

Copyright (c) 2026, Hugging Face, Inc.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Vercel Workflow

- Project: [Vercel Workflow](https://github.com/vercel/workflow)
- Pinned source document: [commit e1e64e3](https://github.com/vercel/workflow/blob/e1e64e3de30e10cba6803907b789699e851d33e2/docs/content/docs/v4/getting-started/next.mdx)
- License: Apache License 2.0
- Adapted files:
  - `experiments/04-vercel/official-minimal/workflows/user-signup.ts`
  - `experiments/04-vercel/official-minimal/api/signup.post.ts`
- Modification: ports the documented signup workflow to the tracked Nitro
  entrypoint and records a bounded local compatibility probe.

The package lock also resolves additional third-party packages under their own
licenses. This repository does not commit `node_modules` or a compiled bundle.
Any distributed bundle must include a generated dependency license report.

## Dogwood

- Project: [Dogwood](https://github.com/dogwood-policy/dogwood)
- Pinned source: [commit c6237c8](https://github.com/dogwood-policy/dogwood/commit/c6237c88099b3f492ecc5fcee42df06a19224b97)
- License: Apache License 2.0
- Use: the Dockerfile builds the reference interpreter locally from the pinned
  source; no Dogwood binary or container image is committed.

The Docker build copies Dogwood's license and NOTICE into the runtime image.
The upstream NOTICE is:

```text
Dogwood
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
```

## Dapr and Dapr Agents

The Dapr experiment records results from Dapr Agents `1.0.5`, Dapr runtime
`1.18.3`, and the official example paths listed in its README. These projects
are licensed under Apache License 2.0. No upstream runtime, binary, or container
image is committed here. The local adapter is identified as project code rather
than an unchanged upstream sample.

## Dependency distributions

Python and JavaScript dependency manifests identify packages required to
reproduce experiments. Dependencies retain their own licenses. Before
distributing a compiled application, container image, or vendored dependency
set, generate and ship an SBOM and resolved license report for that artifact.
