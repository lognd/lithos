# PROOF: doctor environment report + config precedence (INV-21 for config)

- pipeline path: the real `regolith doctor --json` and `regolith config get/set/where/list` CLI verbs -- every line below is captured verbatim from their stdout.

## doctor

- `regolith doctor --json` (real CLI): one row per toolenv catalog entry with found/path/version/capability and an install hint for anything missing (asserted per row).
- on this host: found ccx, ghdl, gmsh, kicad-cli, ngspice, verilator; missing (none).
- `doctor.json` is marked deterministic=False: it reports HOST facts (paths, versions), not repo facts -- honest churn across machines by design.

## config precedence

- exercised on a demo-owned scratch project (never a fleet manifest; the user's global file is never written).
- the three `config where` answers, verbatim in `config_precedence.txt`: default (8765, source=default) -> project file after `config set --local` (9100, source=project; the write visible in the shipped scratch `magnetite.toml` `[tool.regolith]`) -> `REGOLITH_UI_PORT` env (9200, source=env, outranking the file that still carries 9100).
- each level asserted programmatically; `config list` shows every registered key with its winning source.

## Re-run

```
uv run python -m demos.demo16_doctor_config
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `config_precedence.txt` | 710 | `sha256:bf8af8d56b35f393cbb7929f7b5edcd3a7f60d05b81e671181872c9f1cef1a07` |
| `doctor.json` | 1413 | `sha256:7fdca33cac0412a244b62fdad5e0ed229f19aafe9c7a8f2a9bd6d4d05d533c00` |
| `scratch_project/magnetite.toml` | 87 | `sha256:ba999462f7381408dc5036c94d632732e6540114e87e3327583283d189330408` |
