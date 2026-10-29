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

## [0.5.2] - 2026-10-28

### Fixes
- Reject filename/field/identifier echoes from generated translations and revalidate reused checkpoints.
- Remove file and key metadata from the translation prompt to reduce metadata copying.
- Require requested IDs in the Ollama JSON schema and recover one-entry responses with an alternate field name.
- Preserve successful entries when a partial batch needs individual retries.

### Safety
- Previously accepted checkpoints are reclassified on every run; suspicious strings are never exported automatically.

## [0.7.0] - 2026-10-28

### Added
- Atomic per-entry translation with an orchestrator and a bounded 1–4 concurrent Ollama request pool.
- Translator → rule-based Supervisor → Manager (one rework attempt) → Supervisor → Delivery/review flow.
- Per-entry checkpoint persistence by the orchestrator, never by workers.
- Real percentage completion and worker count in the dashboard.

### Notes
- Concurrent requests share the configured Ollama endpoint/model, not independent VRAM model copies.
- A single RX 6600 may perform best with one worker; measure throughput before increasing concurrency.

## [0.8.0] - 2026-10-28

- Cyclic translator-supervisor-manager review with up to three feedback-guided attempts.
- Suspect checkpoint entries return to retranslation instead of staying permanently in review.
- Agent history persisted in agent-history.json.
- Explicit export_error and failed delivery status.
- Improved dashboard progress typography, pipeline stages and hover effects.
- Supervisor and manager are deterministic rules, not independent LLM agents.

## [0.9.1] - 2026-10-29
- Reject contaminated agent feedback and un-restored translation markers.
- Detect basic hunger/thirst semantic confusion.
- Reclassify invariant values, brand terms and empty original strings.
- Revalidate checkpoint approvals; record invalidations for recovery.
- Compare Lua export parser warnings against the original PTBR files.

## [0.9.3] - 2026-10-29
- Validate complete generated PTBR Lua files using luaparser, never execute the game scripts.
- Repair unambiguous missing commas and unescaped inner quotes in working copies only, requiring full syntax validation and exact translated-key preservation.
- Block files that fail certification; keep originals untouched and report failures.
- Exclude empty English entries from translation selection instead of consuming agent retries.
- Apply curated Portuguese translations even when an older cached translation had previously passed heuristic review.
- Add regression tests for malformed strings, blocked output, original preservation and blank entries.

## [0.9.4] - 2026-10-29
- Repair invalid legacy Lua bare keys containing spaces into bracket-string field syntax in export copies.
- Correct literal invalid backslash-percent escapes and internal quotes in simple entries.
- Comment out orphaned continuation strings following commented-out concatenation headers.
- Retain Lua full-grammar validation and reject anything still invalid; original game files untouched.
- Added regression tests for actual ContextMenu/UI syntax patterns from the PTBR reports.

## [0.9.5] - 2026-10-29
- Accumulate independent safe legacy syntax repairs before checking full Lua validity.
- Normalize PZ localization keys with spaces, hyphens, and slashes into Lua bracket keys.
- Preserve checkpoint and fail-closed export: any remaining invalid Lua stays quarantined.
- Add combined regression coverage for UI_PTBR legacy key and escape patterns.

## [0.9.6] - 2026-10-29
- Repair trailing unpaired Lua backslash before closing quote, preserving a literal trailing path separator.
- Regression based on actual UI_ServerOption_Map_tooltip file from blocked v0.9.5 export.
- Keep strict Lua certification, isolated quarantine and persistent checkpoint.

## [0.9.7] - 2026-10-29
- Expand dashboard default translation groups beyond UI/ContextMenu/Moodles to include ItemName, ItemType, ItemCategory, Tooltip, IG_UI, Recipes and Fluids.
- Clarify that full-game audit reads only base game's Translate/EN and not necessarily active mods.
- Preserve existing checkpoints; previously completed groups do not need to be translated again.

## [0.9.8] - 2026-10-29
- Audit all EN translation file paths recursively against PTBR and list missing PTBR files, unknown PTBR-only files, and PTBR keys absent from the matching EN dictionary.
- EN is canonical for selecting translation keys; never silently rename or delete divergent PTBR keys.
- Save workspace/en-reference-audit.json for manager review, including canonical file inventory.
- Use all supported translation groups by default in the React dashboard; preserve existing checkpoint and exported source files.
- Separate special RadioData, Recorded_Media and SurvivorNames formats for dedicated handling rather than falsely claiming full automatic coverage.

## [0.9.9] - 2026-10-29
- Track each concurrent worker independently through translator, supervisor and manager stages.
- Publish live worker telemetry on /api/status without serializing independent translation tasks.
- Update React dashboard to display simultaneously active agents and worker-specific key/cycle.
- Add barrier-based regression verifying three workers are active concurrently.

## [0.10.0] - 2026-10-29
- Replace rigid agent pipeline cards with illustrated, lightweight animated SVG robot workstations; statuses Working/Waiting/Finished follow live worker telemetry.
- Add per-file human instructions: send Brazilian Portuguese guidance to the local Ollama for pending review keys without source-code changes.
- Validate every proposed translation and persist approved decisions in workspace/manual-decisions.json for the next safe export.
- Add asynchronous review API with progress state and React form, preserving game files and prior checkpoint.
