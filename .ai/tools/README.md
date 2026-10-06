# tools/

Project-specific helper scripts the AI can run as part of its workflows — e.g. a
codegen runner, a schema validator, a data-seeding script, or a lint/format wrapper.

Keep each tool self-contained and documented (what it does, how to run it, what it
needs). Reference them from the relevant workflow file. Delete this folder if the
project has no such helpers.
