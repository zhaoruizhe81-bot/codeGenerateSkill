# AGENTS.md

This file is for coding agents working in this repository.

## Project Summary

- Language: Python 3.9+.
- Packaging: `pyproject.toml` with `setuptools`.
- CLI entrypoint: `codegen` -> `codegen.cli:main`.
- Purpose: generate Spring Boot 2 + MyBatis-Plus CRUD projects from JSON config.
- Main inputs: JSON config files like `examples/sample.json`.
- Main outputs: rendered Java/Maven project files written under a target directory.

## Repository Layout

- `codegen/cli.py`: command-line parsing, top-level error reporting, exit codes.
- `codegen/parser.py`: JSON loading, schema validation, semantic validation, IR construction.
- `codegen/schema.py`: JSON Schema definition plus validation error formatting.
- `codegen/ir.py`: dataclasses representing the internal render model.
- `codegen/render.py`: Jinja-based rendering into an in-memory file map.
- `codegen/type_mapping.py`: DB type normalization, Java type mapping, naming helpers.
- `codegen/writer.py`: filesystem writes with overwrite control.
- `codegen/templates/`: Jinja templates for generated Java, XML, YAML, and Maven files.
- `tests/test_smoke.py`: current test coverage, based on `unittest`.
- `examples/sample.json`: the canonical sample config for manual smoke checks.

## Agent Rules From Other Tools

- No `.cursorrules` file was found.
- No `.cursor/rules/` directory was found.
- No `.github/copilot-instructions.md` file was found.
- Treat this document as the active agent guidance unless newer repo-local rules are added.

## Environment Notes

- Use Python tooling, not Node, Go, or Rust commands.
- There is no Makefile, tox config, pytest config, ruff config, or mypy config in the repo.
- Tests currently use `unittest` discovery rather than `pytest`.
- The package installs cleanly in editable mode.

## Setup And Build Commands

- Install in editable mode: `python -m pip install -e .`
- Run the CLI module directly: `python -m codegen -c examples/sample.json -o /tmp/codegen-out`
- Run the console script after install: `codegen -c examples/sample.json -o /tmp/codegen-out`
- Build backend is `setuptools.build_meta`; there is no custom build wrapper.
- If you need a packaging sanity check, prefer reinstalling editable mode over inventing new scripts.

## Test Commands

- Run the full suite: `python -m unittest discover -s tests -v`
- Run one test file: `python -m unittest discover -s tests -p 'test_smoke.py' -v`
- Run one test method: `python -m unittest discover -s tests -k test_parse_and_render_sample -v`
- Another single-test example: `python -m unittest discover -s tests -k test_write_project -v`
- Syntax-only sanity check: `python -m compileall codegen tests`

## Known Test Quirks

- `python -m unittest -v` reports `Ran 0 tests`; do not rely on that form here.
- `tests/` is not a package, so dotted module paths like `tests.test_smoke...` do not work.
- Use `-k <substring>` for a single test method instead of trying pytest-style node ids.

## Lint And Formatting Reality

- No dedicated linter is configured in the repository.
- No autoformatter is configured in the repository.
- Do not add repo-wide formatting churn unless the task explicitly requires it.
- Preserve the existing local style in touched files.
- Use `python -m compileall codegen tests` as the lightest built-in syntax gate.

## Core Workflow Expectations

- Keep the pipeline shape intact: load -> validate -> parse -> render -> write.
- Keep parsing and rendering mostly pure; isolate filesystem effects in `writer.py` and CLI boundaries.
- Update tests whenever behavior changes, especially parser validation or rendered output.
- When changing generated Java structure, verify template paths and imports remain consistent.

## Imports

- Follow the existing order: standard library, third-party packages, then local imports.
- Separate import groups with a single blank line.
- Prefer explicit imports over wildcard imports.
- Preserve existing relative-import style inside the `codegen` package.

## Formatting

- Use 4-space indentation.
- Keep code PEP 8 aligned, but do not reformat unrelated lines.
- Favor short, readable functions over dense control flow.
- Keep a blank line between top-level definitions.
- End written text files with a single trailing newline.
- Prefer ASCII in new source text unless the file already needs non-ASCII content.

## Types

- Add type hints to public functions and non-trivial internal helpers.
- Follow the style already present in the file you are editing.
- This repo mixes built-in generics like `list[str]` with `typing.Dict` and `typing.List`.
- In existing files, consistency with neighboring code is more important than modernizing syntax.
- Use `from __future__ import annotations` in new Python modules to match the codebase.
- Use `slots=True` on dataclasses when they model stable internal structures.

## Naming

- Modules, functions, variables: `snake_case`.
- Classes and dataclasses: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Internal representation classes use the `IR` suffix, for example `ProjectIR`.
- Keep generated-Java naming logic centralized in parser or type-mapping helpers, not scattered through templates.

## Error Handling

- Prefer collecting validation issues and raising one `ConfigError` over failing fast on the first bad field.
- Include precise paths in validation messages, matching the current `tables[0].field` style.
- Raise domain-specific exceptions when the parser detects invalid config.
- Keep user-facing CLI errors readable and printed to stderr.
- Preserve exit code conventions in `codegen/cli.py`.
- If you must catch a broad exception in the CLI, convert it into a concise message rather than a traceback dump.

## Filesystem And Paths

- Use `pathlib.Path` for filesystem work.
- Always read and write text with explicit UTF-8 encoding.
- Keep overwrite behavior explicit; current writer defaults to overwrite unless `--no-force` is used.
- Do not embed OS-specific path separators in rendered paths.

## Templates And Generated Output

- Templates live under `codegen/templates/` and are part of the package data.
- Generated output targets Java 8 and Spring Boot 2.x; do not introduce Java 11+ or Boot 3 assumptions.
- Generated mappers, DTOs, services, controllers, and resources follow existing folder conventions.
- Keep import generation deterministic; `render.py` currently sorts Java imports.
- Preserve stable output when input order is unchanged.
- Security role config is normalized to `ROLE_*` during parsing; config may accept either `ADMIN` or `ROLE_ADMIN`, but generated runtime behavior must stay consistent with Spring Security role semantics.
- When `security.enabled = true`, default registration roles must be reflected consistently across parser seed data, generated `init.sql`, and `UserDetailsServiceImpl`.
- When `security.enabled = true` and `frontend.enabled = true`, generated Vue 2 code must consume `/auth/me` consistently across route guards, sidebar/menu filtering, dashboard links, and CRUD button visibility.
- Table-scoped `POST /import` endpoints must stay aligned with create-level RBAC rules; do not leave them as authenticated-only when create is restricted.
- When `global.enableSwagger = true`, generated `application.yml` and security config must include the Spring Boot 2.6+ compatibility and docs-endpoint allowlist needed for Knife4j/Springfox startup and access.

## Testing Guidance For Changes

- Parser changes should add both success and failure tests.
- Renderer changes should assert on concrete generated file paths or content snippets.
- Writer changes should verify filesystem results with temporary directories.
- Use `examples/sample.json` when a realistic end-to-end input is needed.

## Change Boundaries

- Do not introduce new dependencies unless they are clearly justified and added to `pyproject.toml`.
- Do not switch the test framework unless explicitly requested.
- Do not add a formatter or linter config as drive-by cleanup.
- Do not break the console script name `codegen`.
- Do not change schema semantics silently; reflect behavior changes in docs and tests.

## Good Agent Habits In This Repo

- Read the touched templates and parser code together before changing generation behavior.
- Verify command examples against `examples/sample.json` whenever possible.
- Keep edits small and localized.
- If you add new conventions, document them here so the next agent inherits them.
- For RBAC fixes, verify both generated Java and generated `init.sql`; seed data mismatches are a common source of “generation succeeds but runtime is broken”.
- For frontend RBAC fixes, verify generated `frontend/src/api/auth.js`, `frontend/src/utils/auth.js`, `frontend/src/router/index.js`, `frontend/src/layout/Layout.vue`, and the affected `frontend/src/views/*/index.vue` files together.
