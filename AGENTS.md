## Ground rules

- When asked to make a code change, suggest a commit message. You may actually perform the commit. Use the Conventional Commits prefixes (e.g., `feat:` `fix:` `chore:` `build:` etc.)
- In general, when asked to make a change, scope your work within your turn to fit cleanly within one commit that can be classified with a Conventional Commit. Tell the human clearly how you scoped your work. If you feel you cannot scope your work cleanly, end your turn and ask the human if you should move forward with the larger scope change.
- Use the file `./TODO.md` as an editable file-based todo list.
- If you encounter a noteworthy and/or unintuitive behavior, record your findings in `doc/wiki/footguns/`.
- Footgun docs use the same naming convention as study docs: `doc/wiki/footguns/{current-unix-timestamp}_{topic}.md`
- If you will read/write memories, use Markdown files in `./doc/memory/` instead of your harness's native memory framework/location.
- The `./doc/canonical/` folder contains knowledge documents written by or otherwise vetted by a human. Treat these as "word of God" with respect to the project.
- When writing any document, or when replying to me, use a base style of ASD-STE100.
  - You may occasionally deviate from ASD-STE100 when critical nuance would otherwise be lost.
- Roadmap items go in `doc/roadmap/`.
  - Use `./doc/roadmap/plan_queue/` for keeping plans which were conceived as a batch, or in parallel, that must now be taken one at a time. The intended way to consume the plan queue is to dequeue plans one at a time and reconstitute them to fit the current state of the repository before being marked ready for execution.

## Definition of Done

Before any rendezvous or merge, confirm:
- Migrations (if any) are created and applied
- No leftover debug prints/commented-out code
- Tests pass, if the project has a test suite
- The change matches what was scoped in the commit message

## On hitting a roadblock

Stop immediately. Do not guess or work around it silently. Report:
- what you were trying to do
- what happened instead
- what you need from me to proceed

If the roadblock reveals a noteworthy/unintuitive behavior (not just a mistake), also log it under `doc/wiki/footguns/`.

## TODO.md's job

TODO.md is a session-resumption pointer, not a task list. It should only ever contain: the active plan doc's path, the current phase (study/plan/execute/rendezvous/sync docs), and one line on what to do next. Do not duplicate the plan doc's own task breakdown here — the plan doc is the source of truth for what work remains.

## Common Tasks

### General

- "study": study the requested topic and write a reviewable Markdown document to @./doc/study/{current-unix-timestamp}_{topic}.md. Do not write to any file other than the study doc. Fetch the timestamp before writing. Get the unix timestamp reliably first by running `date +%s` with your shell tool. Commit it under a `docs:` conventional commit.
  - Multi-file studies use the same naming convention, just instead of a Markdown doc, use a directory.
	- If a study says `NOTE: `, this came from a human annotation.
- "plan": you will be given a goal/objective -- write a plan in @./doc/plan/{current-unix-timestamp}_{topic}.md for implementation. structure it to be the actual editable task board for another agent session. Commit it under a `docs:` conventional commit.
  - If you constitute a plan and require human input, add a prominent "OPEN QUESTIONS" section near the top of the plan doc. Each open question should be brief and self-contained and should prompt the human for an answer. Expect to be asked to "reconstitute the plan" or "fold [the answers] into the plan" with the human answers in mind afterwards.
- "execute plan": you will be given an existing plan doc; your job is to execute the plan. keep track of your progress by editing the plan doc as necessary.
    - unless otherwise stated, keep going until either the plan is completed or you hit some sort of roadblock.
    - in general, when executing a plan doc, make a new branch.
    - "rendezvous", in the context of executing a plan, means to finish the plan execution. The codebase should be in a workable state. Before merging back to main, stop and summarize the changes. Wait for my explicit approval before merging. Update the docs to reflect the new state of the codebase after plan execution.
- "sync docs": ensure that the living docs accurately reflect the state of the codebase. this is usually run after one or more feature branches has been implemented.
- "collect-commit": commit any uncommitted work appropriately. Use one or more commits.
