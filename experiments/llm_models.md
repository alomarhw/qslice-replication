# LLM models for T1/T2 (PROTOCOL_ICPC.md section 6.1)

Fixed on 2026-10-21, before any LLM run, from GPU memory alone (the protocol's rule).

| Arm | Model | Serving | Revision |
|---|---|---|---|
| Claude | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | Anthropic API | The model id returned by the API is logged per call |
| O-mid | `Qwen/Qwen2.5-Coder-32B-Instruct` | vLLM 0.31.0, `--quantization fp8` (8-bit), on the author's GPU machine | `381fc969f78efac66bc87ff7ddeadb7e73c218a7` (14 safetensors shards, 62 GB; downloaded 2026-10-21) |
| O-small | `Qwen/Qwen2.5-Coder-1.5B-Instruct` | vLLM 0.31.0, bf16 | `2e1fd397ee46e1388853d2af2c993145b0f1098a` (downloaded 2026-10-21) |

**GPU:** NVIDIA RTX 6000 Ada Generation, 49,140 MiB (`nvidia-smi`, 2026-10-21), reached over VPN
(the author's GPU machine).

**Size rule:** use the largest Qwen2.5-Coder-Instruct that fits in bf16 or 8-bit.
- 32B in bf16 is about 64 GB, which does not fit.
- 32B in 8-bit is about 33 GB, which fits with headroom for prompts of at most about 8k tokens.
- So O-mid is the 32B model at FP8.

**Serving (2026-10-21).** `serve.sh` on the GPU machine runs
`vllm serve <repo> --revision <rev> --host 127.0.0.1 --port 8000 --served-model-name <repo>`.
- O-mid adds `--quantization fp8 --max-model-len 16384 --gpu-memory-utilization 0.92`; the
  KV cache holds 37,712 tokens.
- `VLLM_USE_FLASHINFER_SAMPLER=0`: the FlashInfer sampling kernel must be JIT-compiled, and no
  matching CUDA toolkit is installed. vLLM's own sampler is used instead. Greedy decoding at
  temperature 0 is the same algorithm either way.
