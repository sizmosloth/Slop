# Qwen Hallucinations

## What happened
`qwen2.5:0.5b` sometimes gave the wrong name for itself, and later
forgot the user's name even though it had answered correctly before.

## What we thought caused it
- Being a Chinese/Alibaba model
- A bug in how memory.json stores data

## What actually caused it
Checked memory.json directly — the data was saved correctly, so storage
wasn't the problem. The real cause is model size: `qwen2.5:0.5b` is only
0.5B parameters, which is too small to reliably find one fact inside a
growing conversation history. It gets it right sometimes, wrong other
times, and once it gives a bad answer, that bad answer gets saved too —
so mistakes pile up over a session.

## What we learned
- Hallucination comes from model size, not the model's origin/language.
- Re-reading the whole chat history isn't reliable memory for a small model.
- Fix: pull out key facts (like name) with simple code the moment they're
  said, save them separately, and tell the model directly instead of
  making it search old messages for them.