Pod artifacts copied off yfhzy2r86j9akc (H100 NVL, g7-moshi-single-h100) on 2026-11-14 before termination.

quantize.py      Patched file from /workspace/moshi-rag-src/moshi/moshi/utils/quantize.py.
                 Only change vs upstream: line `state.SCB = self.weight_scb.float()`.
                 Required for q8 weights to load. Not in the repo.
quantize.py.orig NOT saved as a separate file. Upstream original differs only in the
                 `state.SCB = self.weight_scb` line (no `.float()`).
hs_timing.py     Warm websocket handshake timing script run on the pod.
hs_timing.log    conn1 handshake 1.1 s, conn2 handshake 1.4 s.
moshi_8998.tail.log      Tail of the Moshi server log, including one live session
                         (VAD, STT display, RAG reference via vLLM :8002 and encoder :8011).
ref_encoder_8011.tail.log Tail of the reference encoder log (startup and /embed 200 OK).

Not copied: /workspace/q8 weights (local copy verified by SHA256 at
D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors),
.cache (re-downloadable from Hugging Face), vllm2_install.log.
