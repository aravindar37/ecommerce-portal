Hard Rules for Codex

1. All tasks or sub-tasks performed should be summarized in two lines in the task-log.md

2. Read ecommerce-demo-spec.md before writing any code. If this prompt and the spec contradict each other, the spec wins. Flag the contradiction in the task log and follow the spec.

3. Complete tasks in order. Do not skip ahead. A task is not complete until its validation command passes (exit code 0). If validation fails, fix the code and re-run before marking [x]. Mark [x] and append to the Completed Task Log before starting the next task.

4. No # TODO, pass, throw new Error("not implemented"), or stub bodies
in non-abstract classes. Write real, working code. Every import / require must refer to a module that exists in the repo or is declared in the dependency manifest. All functions that can fail must handle errors explicitly — no silent swallows.

5. No hardcoded secrets or environment-specific values. 
All secrets, URLs, API keys, and environment-specific paths come from environment variables loaded at runtime. Provide .env.example with placeholder values and inline comments. Never commit a .env file (ensure it is in .gitignore).

6. Type safety
Python: type hints on every function signature. Pydantic models for all
API request/response bodies.
TypeScript: no any. All API responses typed with interfaces.
Other languages: use the idiomatic type system fully.

7. Before using any third-party library, add it to the dependency manifest
(requirements.txt, package.json, Cargo.toml, etc.). Never import a library that is not declared.

8. Configuration Contract
Define every environment variable the app needs. The agent will create .env.example from this table.

9. Directory structure
Follow the directory structure defined in Readme.md for organizing code.