# LLM models for T1/T2 (PROTOCOL_ICPC.md section 6.1)

Fixed on 2026-10-21, before any LLM run, from GPU memory alone (the protocol's rule).

| Arm | Model | Serving | Revision |
|---|---|---|---|
| Claude | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | Anthropic API | The model id returned by the API is logged per call |
| O-mid | `Qwen/Qwen2.5-Coder-32B-Instruct` | vLLM 0.31.0, `--quantization fp8` (8-bit), on the author's GPU machine | Recorded from the HF cache after download |
| O-small | `Qwen/Qwen2.5-Coder-1.5B-Instruct` | vLLM 0.31.0, bf16 | Recorded from the HF cache after download |

**GPU:** NVIDIA RTX 6000 Ada Generation, 49,140 MiB (`nvidia-smi`, 2026-10-21), reached over VPN
(the author's GPU machine).

**Size rule:** use the largest Qwen2.5-Coder-Instruct that fits in bf16 or 8-bit.
- 32B in bf16 is about 64 GB, which does not fit.
- 32B in 8-bit is about 33 GB, which fits with headroom for prompts of at most about 8k tokens.
- So O-mid is the 32B model at FP8.
