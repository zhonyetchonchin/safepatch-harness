export function handlePlanMode(prompt: string) {
  // 模拟 Plan 模式响应
  return `I will implement this in 3 steps:
  1. Add deletion flag in the database
  2. Create a new screen for deleted notes
  3. Add undelete and permanent delete buttons`;
}

export function handleBuildMode(prompt: string) {
  // 模拟 Build 模式响应
  return `I will make the following changes:
  - Edit src/database.ts to add deleted flag
  - Create src/components/DeletedNotesScreen.ts
  - Update src/routes/notes.ts to handle delete/undelete`;
}