# Docs

Read them in this order:

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | The two diagrams: **A** is the production AWS design, **B** is what Terraform builds in Floci |
| [match-delta.md](match-delta.md) | Where B matches A (**C**, checked by `scripts/delta.sh`) and what is still different (**D**) |
| [floci-runtime.md](floci-runtime.md) | What B looks like on your machine: the Docker containers and the Floci web console, with screenshots |
| [manual-testing.md](manual-testing.md) | Step-by-step curl commands to test the stack by hand |

Images are in [images/](images/). Back to the [project README](../README.md).
