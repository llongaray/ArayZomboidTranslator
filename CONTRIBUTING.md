# Contributing

## Local environment (PowerShell)

```powershell
git clone git@github.com:llongaray/ArayZomboidTranslator.git
cd ArayZomboidTranslator
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . pytest build
.\.venv\Scripts\python.exe -m pytest -q
```

## Development workflow

1. Create a branch from up-to-date `main`: `git switch -c feat/description`.
2. Keep changes focused and add regression tests for behavior changes.
3. Run `python -m pytest -q` before pushing.
4. Open a pull request targeting `main` and inspect GitHub Actions.
5. Do not commit translation workspaces, game files, credentials, models, or virtual environments.

## Releasing

1. Update `CHANGELOG.md` and the version in `pyproject.toml`.
2. Merge the change after CI passes.
3. Create an annotated tag, such as `git tag -a v0.4.1 -m "v0.4.1"`, and push it.
4. Check the tagged GitHub Actions run and download its distribution artifact.
5. Create the corresponding GitHub Release, using the changelog notes. A Git tag alone does not publish a GitHub Release.

## Quality and safety

- Preserve placeholders, formatting tokens and existing PTBR strings.
- Keep output separate from the original game installation.
- Avoid shipping copyrighted game assets or generated translation data without permission.
- Local Ollama is not required for tests that do not call the model.
