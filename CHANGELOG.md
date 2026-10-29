# Changelog

All notable changes to Aray Zomboid Translator are documented here.

This project follows [Semantic Versioning](https://semver.org/) for releases.

## [Unreleased]

### Added
- GitHub Actions CI running the test suite on Python 3.10, 3.11, 3.12, and 3.13.
- Python distribution build and downloadable workflow artifact.
- Contributor workflow and release checklist.

## [0.4.0] - 2026-10-28

### Added
- EN/PTBR translation auditing for Project Zomboid B42.
- Local Ollama integration for batch translation.
- Flask dashboard with audit indicators and progress.
- Filtering, checkpoints, cancellation between batches, and independent exports.
- Review reports and placeholder safeguards.

### Notes
- Generated translations must be reviewed before installation.
- The existing AGPL-3.0 license remains in effect.

[Unreleased]: https://github.com/llongaray/ArayZomboidTranslator/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/llongaray/ArayZomboidTranslator/releases/tag/v0.4.0

## [0.5.0] - 2026-10-28

### Added
- Quality review for unchanged English, suspicious English, glossary disagreements, and unusual length.
- New quality-review.json output; suspect strings are not automatically exported.
- Dashboard quality counters, glossary hints, legacy checkpoint loading.

### Notes
- Automated quality rules are conservative heuristics and do not replace manual review.
- Previous v0.4.0 checkpoints remain readable.

## [0.5.1] - 2026-10-28

### Stability
- Bound Ollama HTTP calls to 35 seconds and reduce model context to 4096 tokens / output cap to 768 tokens.
- Fall back to individual translations when a batch fails, to isolate problematic entries.
- Display active batch, elapsed seconds and last-batch duration in the dashboard.
- Preserve legacy checkpoints and process cooperative cancellation between bounded requests.

### Limitations
- Cancellation is bounded by the active HTTP request timeout, not an instantaneous cancellation of GPU inference.
- Very long translations can fail with the 768-token cap; review and rerun these separately.
