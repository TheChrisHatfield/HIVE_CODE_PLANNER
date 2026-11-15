# G7-q8: quantize.py float cast (pod runbook note)

Status: documented 2026-11-14. Not applied in this repo. The patch lives in the Moshi source tree on the pod, not in `HIVE_CODE_PLANNER`.

## What changed

File on the pod: `/workspace/moshi-rag-src/moshi/moshi/utils/quantize.py` (copy kept as `quantize.py` in this folder).

In `QLinear.forward`, the scale line is cast to float:

```python
# Patched (required for q8 weights to load)
state.SCB = self.weight_scb.float()  # type: ignore
```

Line 31 of the saved copy. Upstream reads `state.SCB = self.weight_scb` (no `.float()`).

## Why it is needed

`forward` raises `RuntimeError` unless `state.SCB` is `torch.float`. The model is cast to bfloat16 after init, which turns the int8 scale parameter into bfloat16. The cast restores float at forward time. Without it, the q8 model loads but fails on the first matmul.

## Caveat

The upstream original was not saved as `quantize.py.orig`. The statement that this one line is the only change comes from the pod README. It has not been diffed against upstream. Before relying on it, diff the pod's file against the upstream Moshi release.

## Repeatable apply (on the pod, before `moshi.server`)

Idempotent: it only edits when the upstream line is present.

```bash
F=/workspace/moshi-rag-src/moshi/moshi/utils/quantize.py
sed -i '/state\.SCB = self\.weight_scb\b/{/\.float()/!s/state\.SCB = self\.weight_scb/state.SCB = self.weight_scb.float()/}' "$F"
grep -n 'state.SCB = self.weight_scb' "$F"
```

Expected output: one line containing `self.weight_scb.float()`.

## Related pod-only steps (see `cursor-g7-runpod-handoff.md`)

- `HF_HUB_ENABLE_HF_TRANSFER=0`
- `PYTHONPATH=/tmp/enc-libs:/workspace/moshi-rag-src/moshi`
- `msgpack` and `gradium` in `/tmp/vllm-venv`
- `moshi.server --host 0.0.0.0`

## Local q8 weights

`D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors`, SHA256 `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc`.
