# Python CLI Example

Example spec and plan for adding a new command to a Python CLI tool.

## DARKZLOOP_SPEC.md

```markdown
# Export Command Spec

## Objective

Add an `export` command to the CLI that exports data in multiple formats (JSON, CSV, YAML).

## Keywords & Synonyms

- export, dump, output, serialize
- json, csv, yaml, format
- click, typer (CLI frameworks)
- pandas, csv module (data handling)

## Existing System Links

**CLI structure:**
- Main entry: `src/cli/main.py` (lines 1-30, click group)
- Commands: `src/cli/commands/` directory
- Config loading: `src/cli/config.py`

**Data layer:**
- Models: `src/models/` directory
- Database: `src/db/connection.py`
- Queries: `src/db/queries.py`

**Patterns:**
- Command file: `src/cli/commands/import_cmd.py`
- Output formatting: `src/utils/formatters.py`

## Requirements

1. `mycli export [--format FORMAT] [--output FILE]`
2. Supported formats: json (default), csv, yaml
3. Output to stdout by default, file if --output specified
4. Progress bar for large exports
5. Proper error messages for invalid formats

## Constraints

**Must follow:**
- Use Click decorators (match import_cmd.py pattern)
- Use existing formatters in utils/formatters.py
- Use rich for progress bars (already a dependency)
- Follow existing error handling patterns

**Must avoid:**
- No new dependencies
- No direct database calls (use queries.py)
- No print() statements (use click.echo)

## Non-Goals

- Incremental/streaming export
- Compression
- Cloud storage upload
- Schema customization

## Success Criteria

- [ ] `mycli export` outputs JSON to stdout
- [ ] `mycli export --format csv` outputs CSV
- [ ] `mycli export --output data.json` writes to file
- [ ] Invalid format shows helpful error
- [ ] Progress bar displays for large datasets
- [ ] `pytest` passes
- [ ] `ruff check` clean
```

## DARKZLOOP_PLAN.md

```markdown
# Implementation Plan: Export Command

**Spec**: DARKZLOOP_SPEC.md
**Status**: Not Started

## Phase 1: Foundation

- [ ] **Task 1.1**: Create export command file
  - New file: `src/cli/commands/export_cmd.py`
  - Modify: `src/cli/main.py` (line 25, import command)
  - Pattern: `src/cli/commands/import_cmd.py` (command structure)
  - Acceptance: `mycli export --help` works

- [ ] **Task 1.2**: Add format option
  - Modify: `src/cli/commands/export_cmd.py` (add --format)
  - Pattern: `src/cli/commands/import_cmd.py` (lines 15-25, options)
  - Acceptance: --format accepts json/csv/yaml

## Phase 2: Formatters

- [ ] **Task 2.1**: Add CSV formatter
  - Modify: `src/utils/formatters.py` (add to_csv function)
  - Pattern: `src/utils/formatters.py` (lines 30-50, to_json)
  - Tests: `tests/utils/test_formatters.py`
  - Acceptance: Formats data as valid CSV

- [ ] **Task 2.2**: Add YAML formatter
  - Modify: `src/utils/formatters.py` (add to_yaml function)
  - Pattern: `src/utils/formatters.py` (to_json structure)
  - Tests: `tests/utils/test_formatters.py`
  - Acceptance: Formats data as valid YAML

## Phase 3: Integration

- [ ] **Task 3.1**: Wire up export logic
  - Modify: `src/cli/commands/export_cmd.py` (main logic)
  - Reference: DARKZLOOP_SPEC.md Requirements #1-3
  - Pattern: `src/cli/commands/import_cmd.py` (lines 40-80)
  - Tests: `tests/cli/test_export.py`
  - Acceptance: Full export flow works

- [ ] **Task 3.2**: Add progress bar
  - Modify: `src/cli/commands/export_cmd.py` (rich progress)
  - Reference: DARKZLOOP_SPEC.md Requirements #4
  - Pattern: `src/cli/commands/import_cmd.py` (lines 60-70)
  - Acceptance: Progress displays for large exports

## Phase 4: Polish

- [ ] **Task 4.1**: Add error handling
  - Modify: `src/cli/commands/export_cmd.py` (error cases)
  - Reference: DARKZLOOP_SPEC.md Requirements #5
  - Pattern: `src/cli/commands/import_cmd.py` (error handling)
  - Acceptance: Invalid format shows clear error

- [ ] **Task 4.2**: Add --output file handling
  - Modify: `src/cli/commands/export_cmd.py` (file output)
  - Acceptance: --output writes to specified file
```

## Key Takeaways

This example shows:
- How to spec a feature addition to existing code
- Referencing existing command patterns for consistency
- Breaking work into testable increments
- Clear acceptance criteria for CLI behavior
