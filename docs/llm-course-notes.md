# LLM Course Notes (OCR)

Source: new.pdf (OCR)

Key takeaways:
- The course is structured into three tracks: LLM Fundamentals, LLM Scientist, LLM Engineer.
- Scientist track emphasizes: tokenization, transformer/GPT architecture, attention, sampling, pretraining data pipelines, distributed training, post-training, quality filtering, and evaluation.
- Engineer track emphasizes: building LLM apps, LLM APIs, open-source models, prompt/agent programming, deployment, and securing LLM systems.
- Evaluation is highlighted as essential (leaderboards, harnesses, systematic testing).
- Efficiency topics appear (quantization, model optimization) for running models locally.

Implications for this app:
- Keep the architecture modular (planner/executor/verifier/retriever) and testable.
- Treat evaluation and monitoring as first-class features (eval harness + metrics endpoint).
- Maintain local-model support and routing for quota or offline scenarios.
- Add security guardrails and confirmations for risky actions.
