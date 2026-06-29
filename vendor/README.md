# Hive unified handoff — vendored upstreams



Stage 9 (`unified-handoff-v2`) pins forked **Spec Kit** and **Continual Learning** sources for symbiotic deploy with Hive Planner.



## Layout



```text

vendor/

├── manifest.json          # pin manifest (schema hive-upstream-pins/v1)

├── spec-kit/              # github/spec-kit @ pinned SHA

└── cursor-plugins/

    └── continual-learning/  # cursor/plugins subtree @ pinned SHA

```



## Pinned refs (2026-06-26)



| Component | Upstream | Ref |

|-----------|----------|-----|

| Spec Kit | [github/spec-kit](https://github.com/github/spec-kit) | `b7e67f55` |

| Continual Learning | [cursor/plugins](https://github.com/cursor/plugins) | `0452e08` |



Hive patches (`hive_patch_rev`) are not yet applied — see Tasks 4–5 in the spec.



## Operator guide



See [docs/unified-handoff-upstream-forks.md](../docs/unified-handoff-upstream-forks.md).



## CLI



```powershell

py -3.11 -m hive_planner vendor-sync --check

py -3.11 -m hive_planner vendor-sync --apply

py -3.11 -m hive_planner unified-verify

```



Bootstrapped unified projects receive a snapshot at `.hive/upstream-pins.json`.



## Status



| Task | Status |

|------|--------|

| Manifest skeleton | ✅ |

| vendor-sync / unified-verify CLI | ✅ |

| Bootstrap `.hive/upstream-pins.json` | ✅ |

| Upstream import | ✅ Task 3 |

| Hive patches (SK/CL) | ✅ SK (Task 4) / 📋 CL (Task 5) |

| Bootstrap vendor deploy | 🚧 pins + Spec Kit overlay ✅ |



## License / attribution



Vendored trees are upstream snapshots. Spec Kit and Continual Learning retain their upstream licenses. Do not modify vendored files in-place — apply Hive patches via documented overlay or org forks (Tasks 4–5).

