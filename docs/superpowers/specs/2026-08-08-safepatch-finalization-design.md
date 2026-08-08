# SafePatch Harness Finalization Design

## Context and audit result

The original Project A implementation covers the required modules and has a
strong deterministic test base, but final acceptance exposed gaps between the
written specification and the delivered WebUI:

- `AgentLoop.run()` executes only one action, so tool feedback does not drive a
  second action in the same run.
- the public WebUI creates a run record but never executes the mock harness;
  approval, check, and diff panels therefore cannot demonstrate their purpose.
- run records are held in process memory even though the design promises SQLite
  run persistence.
- approval IDs omit the run ID and can collide across concurrent runs.
- the public Render deployment exposes a shared credential vault.
- the desktop layout can overflow horizontally and lacks useful loading,
  failure, empty, and pending-approval states.

The finalization must close those gaps without turning the public service into
an arbitrary code-execution endpoint.

## Considered approaches

1. **Recommended: integrated deterministic demo workbench.** Complete the
   multi-step loop, execute curated MockLLM scenarios through that real loop,
   persist their runs/events, wire approval decisions back to the paused run,
   and redesign the existing vanilla WebUI. This directly demonstrates the
   course mechanisms while keeping public deployment safe.
2. **Visual polish only.** Keep the API and loop unchanged and only restyle the
   page. This is low risk but leaves the central demo non-functional and does
   not satisfy the documented feedback-loop behavior.
3. **Public real-LLM/workspace execution.** Connect stored credentials and let
   the hosted app modify user repositories. This would show more functionality,
   but it conflicts with the specification's public-demo safety boundary and
   would require authentication, tenant isolation, and a hardened sandbox.

Approach 1 is selected. The user explicitly authorized implementation without
additional questions and approved agent-selected finalization decisions.

## Core behavior

`AgentLoop` will keep requesting one structured action at a time until one of
these terminal conditions occurs: `finish`, deterministic policy denial,
approval pause, malformed provider output, provider/tool failure that cannot be
continued, cancellation, or budget exhaustion. Every normal tool result is
converted into a tool message and included in the next provider request. Step,
time, and consecutive-failure budgets are checked before each provider call.

The loop will record action payloads, policy decisions, tool start/finish,
feedback, state changes, and final status. Event persistence will continue to
apply recursive secret redaction.

Approval action IDs will include `run_id`, step, and action type. A paused demo
run keeps only the in-process continuation state needed to resume its curated
MockLLM script. Approving consumes the one-time approval, executes the exact
pending action, and continues the same run. Rejecting records structured
feedback and terminates that demo run without executing the action.

## API and persistence

SQLite will own run records as well as events and memories. The runs table will
store task, scenario, status, pending action ID, and timestamps. API list/get/
cancel operations will read from SQLite, so deploy restarts no longer silently
lose the run list.

`POST /runs` remains backwards compatible with `{ "task": ... }` and accepts an
optional curated scenario. In demo mode it executes one of four safe scenarios:

- safe repair: inspect, patch, check, finish;
- feedback recovery: fail a check, inspect, patch, re-check, finish;
- governance block: deny a dangerous command before execution;
- HITL patch: pause a protected-file patch for approve/reject.

No demo scenario opens an arbitrary repository or invokes a shell command. A
metadata endpoint tells the UI which capabilities are available.

Credential endpoints remain available for local use, but the Render blueprint
sets public-demo mode, which disables the shared vault and causes the UI to show
a clear safety notice instead of secret-entry controls. Credential validation
errors must never echo submitted secrets.

## WebUI design

The UI remains a dependency-free workbench. The visual hierarchy is:

1. compact product header with API and demo-safety status;
2. left control rail for scenario, task, and run history;
3. central event timeline with concise event summaries and optional structured
   detail;
4. right inspector for run state, actionable approval, latest check, diff, and
   local credential capability.

The desktop grid must fit at 1280px without horizontal scrolling. It collapses
to two columns and then one column at narrower breakpoints. Every async action
has a busy/error/success state, destructive controls are disabled when invalid,
pending approval data is auto-populated, keyboard focus is visible, colors meet
dark-theme contrast needs, and reduced-motion preferences are respected.

## Safety and error handling

- public mode never enables credential mutation or arbitrary tools;
- HTTP responses receive restrictive browser security headers;
- validation errors for credential routes omit submitted input;
- vault writes use a replace-based temporary file and corrupted vaults return a
  stable `VaultError`;
- terminal runs cannot be canceled or resumed;
- UI errors are rendered as text, never injected as untrusted HTML;
- all stored event payloads pass through secret redaction.

## Testing and delivery

Implementation follows red-green-refactor. New tests will first fail for:

- same-run multi-step feedback and budget behavior;
- globally unique approval IDs and approve/reject continuation;
- persisted run records surviving app recreation;
- public credential disablement and secret-safe validation failures;
- each WebUI demo scenario producing meaningful timeline/check/diff output;
- responsive/accessibility contract markers and deployment configuration.

Final verification includes the full pytest suite, deterministic CLI demo,
wheel/dependency checks, Docker build/run smoke tests, browser tests at desktop
and mobile widths, GitHub Actions, Render deployment health, and a public Docker
Hub image tagged with both the release version and `latest`.

## Spec self-review

The design contains no placeholders or unresolved decisions. It stays within
Project A: the real harness mechanisms are self-implemented and mock-testable,
while public deployment remains a curated sample environment. The unavailable
`writing-plans` skill is handled by recording the equivalent executable tasks
in `PLAN.md` and the live task plan.
