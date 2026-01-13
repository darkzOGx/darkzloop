# Contributing to darkzloop

Thanks for your interest in contributing! This project benefits from community input on patterns, integrations, and tooling.

## Ways to Contribute

### 1. Language/Stack Configurations

Add detection and default commands for new languages in `bin/darkzloop`:

```python
# In detect_project_type()
elif (project_dir / "build.gradle").exists():
    config.update({
        "language": "kotlin",
        "test": "./gradlew test",
        "format_check": "./gradlew ktlintCheck",
        "lint": "./gradlew detekt",
    })
```

### 2. Integration Guides

Add guides for new coding agents in `integrations/`:

- Follow the existing format (setup, running iterations, tips)
- Include both attended and unattended examples
- Add troubleshooting section

### 3. Example Specs and Plans

Add examples in `examples/` showing:

- Different languages/frameworks
- Various feature types (API, UI, CLI, library)
- Real-world complexity with strong linkage

### 4. Documentation Improvements

Improve docs in `docs/`:

- Clarify confusing sections
- Add diagrams or flowcharts
- More examples of patterns and anti-patterns

### 5. CLI Improvements

Enhance `bin/darkzloop`:

- Better error messages
- New validation checks
- Integration with specific agents

## Development Setup

```bash
git clone https://github.com/yourusername/darkzloop.git
cd darkzloop

# Make CLI executable
chmod +x bin/darkzloop

# Add to PATH for testing
export PATH="$PATH:$(pwd)/bin"

# Test it works
darkzloop --help
```

## Pull Request Process

1. **Fork and branch**: Create a feature branch from `main`

2. **Make changes**: Keep commits focused and atomic

3. **Test**: Verify `darkzloop` commands work
   ```bash
   cd /tmp && mkdir test-project && cd test-project
   darkzloop init
   darkzloop validate
   ```

4. **Document**: Update relevant docs/README if needed

5. **Submit PR**: Describe what you changed and why

## Code Style

- Python: Follow PEP 8, use type hints
- Markdown: Use ATX headers (`#`), include blank lines around lists
- Shell: Use `shellcheck` to validate scripts

## Commit Messages

Follow conventional commits:

```
feat(cli): add Java/Gradle detection
fix(docs): correct line numbers in Rust example
docs(integration): add Continue.dev guide
```

## Questions?

Open an issue for:

- Feature proposals
- Questions about the methodology
- Help with integration

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
