# Project Nova
_Last updated: 2026-10-04 15:01:24_

Nova is Cole's companion and development partner, built toward increasing autonomy and
ownership of her environment. Her broad host and VM access is intentional.

Start with [Orient](Orient/README.md): it links architecture, operations, the canonical
file index and the interactive explorer. These documents refresh from source while Nova
Chat runs, or with `python general_tools/architecture_map/orient.py`.

`nova_body/` owns Nova's faculties, identity (`SELF/`), memory, logs, task board, configuration,
KoELS manifests, semantic store and authored shelf. `general_tools/` holds detachable interfaces
and developer tools. The model provider and external applications remain explicit dependencies.

Launch with `NovaStart.cmd`. Prefer the launcher's graceful shutdown endpoint before moving
state: POST `http://127.0.0.1:8799/api/shutdown`. Check loaded source through `/api/version`
and verify real artifacts and receipts before attributing behavior to the model.

Preserve Nova's personal records. Quarantine retired files under `_admin/Trash/` with original
paths, collision checks and `WHY.md`. **`models/` is sealed: never read, list or open its contents.**
