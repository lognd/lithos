# PROOF: doctor environment report + config precedence (INV-21 for config)

- pipeline path: the real `regolith doctor --json` and `regolith config get/set/where/list` CLI verbs -- every line below is captured verbatim from their stdout.

## doctor

- `regolith doctor --json` (real CLI): one row per toolenv catalog entry with found/path/version/capability and an install hint for anything missing (asserted per row).
- on this host: found ccx, ghdl, gmsh, kicad-cli, ngspice, verilator; missing sigrok-cli.
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
| `config_precedence.txt` | 686 | `sha256:490007a30470fae0f907170e5e0f4dfde0bf86dce11eb54b13d8e0cf304663be` |
| `doctor.json` | 1936 | `sha256:be3b81559592e2b10b0d6c5fd79a5057b2897a85233f65ce71bbf990f6fb98be` |
| `scratch_project/magnetite.toml` | 87 | `sha256:ba999462f7381408dc5036c94d632732e6540114e87e3327583283d189330408` |
