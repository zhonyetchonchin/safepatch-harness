# AGENTS.md

## Agent: MyCodingAgent

- **Description**: A custom coding agent for the AI4SE project.
- **Commands**:
  - `/plan`: Switch to plan mode (suggest changes without executing)
  - `/build`: Switch to build mode (execute changes)
  - `/undo`: Revert last change
  - `/test`: Run tests after changes
- **Config**: `opencode.json`
- **Files**: `src/agent.ts`, `src/utils.ts`