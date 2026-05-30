---
name: project-venv-map
description: Maps each workspace project to its Python virtualenv path — always activate before pip install
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1b45e6d1-97dd-4040-8221-36d727c41274
---

Always activate the project's venv before running `pip install`. Global pip installs are rejected.

**Why:** User explicitly corrected this — installs must go into the project venv, not system Python.

**How to apply:** Before any `pip install`, find and activate the correct venv using this map:

| Project | venv path |
|---|---|
| india_security_timeline | `/Users/glondhe/Library/CloudStorage/OneDrive-TriNetUSA,Inc/workspace/envs/india_timeline/bin/activate` |
| gov_schemes_tracker | `/Users/glondhe/Library/CloudStorage/OneDrive-TriNetUSA,Inc/workspace/envs/env_gov_scheme/bin/activate` |
| devmind | `/Users/glondhe/Library/CloudStorage/OneDrive-TriNetUSA,Inc/workspace/devmind/venv/bin/activate` |

Activate with: `source <path>` before running pip.
