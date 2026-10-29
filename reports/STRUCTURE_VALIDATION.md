# Structure packaging validation

2026-10-22: from the new project root, python -m pytest -q passed all 21 tests. python -m ml.training.train --help succeeded. Actual model outputs and run hashes remain unchanged from the first ML milestone. CI YAML has not been run remotely; pending folders have not been implemented.

An initial pytest command launched from the parent scratch directory encountered duplicate module names because it discovered both the original and copied project. Running from the project root resolved the collection issue. Run commands from the extracted root as documented.
