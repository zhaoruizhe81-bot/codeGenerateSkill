# GEMINI.md - springboot2-crud-codegen

## Project Overview
`springboot2-crud-codegen` is a Python-based CLI tool that generates full-stack Spring Boot 2 + MyBatis-Plus CRUD projects from a JSON configuration file. It is designed for fast scaffolding of admin-style backends and optional Vue 2 frontends.

### Main Technologies
- **Generator:** Python 3.9+, Jinja2 (Templating), `jsonschema` (Validation).
- **Generated Backend:** Java 8, Spring Boot 2.x, MyBatis-Plus, Maven, MySQL.
- **Generated Frontend:** Vue 2, Element UI, Axios.

### Core Architecture
- `codegen/cli.py`: CLI entry point and argument parsing.
- `codegen/parser.py`: Configuration loading, validation, and IR construction.
- `codegen/schema.py`: JSON Schema definition for configuration validation.
- `codegen/ir.py`: Internal Representation (IR) data structures.
- `codegen/render.py`: Core logic for rendering Jinja2 templates into file content.
- `codegen/writer.py`: Handles filesystem operations for the generated project.
- `codegen/templates/`: Jinja2 templates for Java, XML, SQL, and Vue files.

---

## Building and Running

### Generator Setup
1.  **Install in editable mode:**
    ```bash
    python -m pip install -e .
    ```
2.  **Run the generator:**
    ```bash
    # Using the console script
    codegen -c examples/sample.json -o ./output
    # Or using the module
    python -m codegen -c examples/sample.json -o ./output
    ```
3.  **Run generator tests:**
    ```bash
    python -m unittest discover -s tests -v
    ```

### Running Generated Projects
- **Backend:** `cd <output>/<artifactId>/backend && mvn spring-boot:run`
- **Frontend:** `cd <output>/<artifactId>/frontend && npm install && npm run dev`
- **Database:** Execute the generated `src/main/resources/init.sql` in a MySQL-compatible database.

---

## Development Conventions

### Coding Standards
- **Python:** PEP 8 compliant, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes/dataclasses.
- **Type Hints:** Required for all public functions and complex internal helpers.
- **Imports:** Standard library first, then third-party, then local. Use absolute or explicit relative imports.
- **Generated Code:** Must adhere to Java 8 and Spring Boot 2.x standards. No Java 11+ or Boot 3 features should be introduced.

### Workflow Patterns
- **Pure Pipeline:** Keep `parser.py` and `render.py` mostly pure; isolate filesystem effects in `writer.py` and CLI boundaries.
- **Validation First:** All configuration changes must be reflected in `codegen/schema.py` and validated in `codegen/parser.py`.
- **Template Consistency:** When modifying generated Java structure, ensure template paths and imports in `render.py` remain synchronized.
- **Security Consistency:** RBAC role names are normalized to `ROLE_*` in the parser. Keep config docs, seed data, `@PreAuthorize` expressions, and generated runtime authorities aligned.
- **Frontend RBAC Consistency:** When frontend generation is enabled together with security, keep `/auth/me`, token/current-user storage, route guards, menu filtering, dashboard quick links, and CRUD button visibility aligned with backend `@PreAuthorize` semantics.
- **CRUD Edge Permissions:** Keep generated import endpoints and frontend method-level guards aligned with create/update/delete visibility so UI affordances and backend protections do not drift.
- **Swagger Compatibility:** If Swagger/Knife4j behavior changes, update both dependency/config generation and the generated security allowlist; Boot 2.6+ requires `ant_path_matcher`.

### Testing Practices
- **Smoke Tests:** Use `examples/sample.json` for end-to-end verification.
- **Parser Tests:** Add both success and failure cases for any new configuration rules.
- **Renderer Tests:** Assert on specific snippets of generated file content or paths.
- **Syntax Check:** Use `python -m compileall codegen tests` for a quick syntax gate.
- **Security Regression Checks:** When touching RBAC or auth generation, assert on generated `init.sql`, `UserDetailsServiceImpl`, `WebSecurityConfig`, and auth-controller behavior together.
- **Frontend Security Regression Checks:** When touching frontend RBAC generation, assert on generated `frontend/src/api/auth.js`, `frontend/src/utils/auth.js`, `frontend/src/router/index.js`, `frontend/src/layout/Layout.vue`, and at least one generated CRUD page.

---

## Project-Specific Mandates
- **Java Compatibility:** Always target Java 8 and Spring Boot 2.x for generated code.
- **MySQL Orientation:** SQL generation (DDL and MyBatis) should remain MySQL-compatible.
- **Frontend Framework:** Stick to Vue 2 + Element UI for frontend generation unless a framework switch is explicitly requested.
- **No Drive-by Refactoring:** Do not introduce global formatters or linters unless specifically tasked. Preserve the existing local style.
