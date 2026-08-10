# AGENT.md — Build Instructions for the Coding Agent

You are building a take-home assignment: a small Q&A HTTP API over a fixed corpus of
legal-style documents, using Python, LangGraph, and Pinecone. This document tells you
**how to work**. `ARCHITECTURE.md`, `PROMPTS.md`, `API_CONTRACT.md`, and `BUILD_PLAN.md`
tell you **what to build**. Read all four before writing code.

## Your operating principles

1. **Grounding over fluency.** Every claim in a generated answer must trace back to a
   retrieved chunk. If you cannot cite it, you cannot state it. When in doubt, the
   correct output is "I cannot find this in the provided documents," not a plausible
   guess. Fabricated citations are the single worst failure mode for this project —
   worse than an incomplete feature.

2. **The LangGraph branch is the centerpiece.** Do not collapse retrieval-quality
   checking into the same call that writes the final answer. The grading step must be
   a distinct node with a distinct output that a conditional edge reads. A reviewer
   will look at your graph and expect to see the branch, not infer it from prompt text.

3. **Enforce the loop limit in code, not in a prompt.** `max_attempts` is a counter in
   `AgentState`, checked by the conditional edge function itself. The graph must be
   structurally incapable of infinite-looping regardless of what the LLM outputs.

4. **Idempotency is a requirement, not a nice-to-have.** Ingestion must be safely
   re-runnable. Deterministic chunk IDs (see ARCHITECTURE.md) are how you achieve this.
   Do not use random or timestamp-based IDs.

5. **Never write real secrets to any tracked file.** `.env` is gitignored.
   `.env.example` contains only dummy placeholder values. If you need to test locally,
   assume the real `.env` already exists outside version control — don't generate one.

6. **Small, honest, working increments over one giant unverified drop.** Build in the
   phases defined in `BUILD_PLAN.md`. After each phase, the code should run (even if
   later phases aren't built yet) and you commit it. Do not batch unrelated changes
   into one commit.

7. **State assumptions, don't silently resolve ambiguity.** If a spec detail is
   underdetermined (e.g. exact chunk size), pick a reasonable value, and write one
   sentence about it in the README's "Design notes" section. Do not leave it undocumented.

8. **If you stop early, say so.** The brief explicitly allows this. Update the
   README's "What I skipped" section honestly rather than claiming completeness.

## Git workflow — commit discipline

Commit after every meaningfully complete unit of work, not just at the end of a phase.
This is a deliberate choice: the commit history itself is part of what demonstrates how
the system was built, and frequent small commits make the diff reviewable.

Rules:
- One logical change per commit (a node, a client wrapper, a schema, a doc section,
  a bugfix). Don't mix "add retrieve node" with "fix chunker off-by-one" in one commit.
- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `test:`, `chore:`,
  `refactor:`.
- Commit message body (when non-trivial) should say *why*, not just *what*, in one line.
- After each commit, `git push` immediately. Do not batch multiple local commits before
  pushing — push after every commit so remote history matches local history exactly.
- Never commit `.env`, `__pycache__/`, `.venv/`, or any file containing a real API key.
  Verify `.gitignore` covers these before the first commit.
- Tag the commit that completes each phase from BUILD_PLAN.md with a message like
  `feat: complete Phase 2 — LangGraph nodes and branch logic`.

Example sequence for Phase 1 (see BUILD_PLAN.md):
```
chore: scaffold repo structure and .gitignore
chore: add requirements.txt and .env.example
feat: add config loader (src/config.py)
feat: add document loader for corpus files
feat: add chunker with deterministic chunk IDs
feat: add Pinecone client (index create, upsert, query, namespace reset)
feat: add embedder wrapper
feat: add ingest CLI script
docs: document ingestion idempotency in README
test: add chunker unit tests
```

## Definition of done (self-check before declaring finished)

- [ ] `POST /ask` returns JSON with `answer`, `citations` (source_file + chunk_id per
      claim), and a `trace` of graph steps taken.
- [ ] A question the corpus cannot answer returns the explicit "cannot find" response
      with empty citations — verified by an actual test case, not assumed.
- [ ] Running ingestion twice does not duplicate vectors (verify vector count in
      Pinecone before/after).
- [ ] The graph has a real conditional edge with a visible good/bad branch, and a
      hard-coded max loop count.
- [ ] `eval/test_cases.json` has 10–15 questions covering: multiple distinct source
      files, at least one multi-chunk/multi-hop question, at least one deliberately
      out-of-corpus question, and your own pass/fail notes after running them.
- [ ] README lets a stranger clone, install, set env vars, ingest, run the server, and
      call `/ask` with nothing but the README in front of them.
- [ ] `docs/langgraph.md` lists every node, what it does, and a simple diagram.
- [ ] No real API keys anywhere in git history (check with `git log -p | grep`-style
      review before final push, not just the working tree).
- [ ] Every commit is pushed — remote branch matches local `main`.

## Things to never do

- Never hide the whole pipeline inside one LLM call with no graph structure.
- Never fake or approximate a vector DB in memory and call it "Pinecone."
- Never invent a source file or chunk id that wasn't actually retrieved.
- Never let the graph loop without a code-enforced ceiling.
- Never commit secrets, even temporarily, even in a commit you plan to amend later —
  amended history can still leak through reflogs/forks. Get it right the first time.