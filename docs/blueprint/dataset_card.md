# Dataset Card and Provenance

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Source

NASA C-MAPSS simulated turbofan degradation data; official source linked in sources.md. Training histories run to failure, while test histories end earlier with separate true RUL values. FD001 has one operating condition and HPC degradation; FD002 adds operating conditions; FD003/FD004 include fan and HPC degradation modes. Use the archive documentation to verify schema and units.

## Project processing record

Download not included here. Record exact source/archive hash, access date, file hashes, archive README, row/engine counts, parser commit, exclusions, split manifest and preprocessing decisions after acquisition. NASA catalog displays license not specified; confirm redistribution terms before bundling raw files with a public project. This pack redistributes no dataset.

## Scope limitations

Engine simulation does not provide factory location photos, technician schedules, inventory, actual repairs or realized savings. Those are separate labeled sample records in a demo. Do not treat known fault-mode metadata as per-observation component ground truth. Raw sensor meanings must be verified before friendly names and unit conversion are applied.

## Storage

Raw files immutable in private data storage; cleaned derivatives get separate version/hash. Split manifests use engine identifiers including subset/source namespace. Official test labels must not enter online requests or training features. Retention and public redistribution require project review.
