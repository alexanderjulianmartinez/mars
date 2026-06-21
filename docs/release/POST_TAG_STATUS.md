# Post-Tag Status

**Release:** v1.0.0-rc1 · **Date:** 2026-06-21
Status of post-tag release hygiene. Source of truth for "where the release stands."

---

## Status table

| Item | Status | Detail |
| --- | --- | --- |
| **PR #28 merged** | ✅ DONE | Merge commit `c4ee136` on `main` (merged 2026-06-21T21:23Z). |
| **Tag pushed** | ✅ DONE | Annotated `v1.0.0-rc1` → `2b4d493`, on origin. |
| **GitHub prerelease** | ✅ DONE | `isPrerelease: true`, notes from `RELEASE_NOTES_RC1.md`. https://github.com/alexanderjulianmartinez/mars/releases/tag/v1.0.0-rc1 |
| **Version metadata** | ✅ RESOLVED (Option B) | Framework package stays `0.1.0`; research release = tag `v1.0.0-rc1`; benchmark = `v1.0.0`. Documented; no version-field edits. |
| **Repo visibility** | 🟡 PRIVATE | Held for explicit maintainer action (irreversible). |

---

## Version axes (resolved)

Three deliberately independent versions are tracked:

| Axis | Version | Where | Rationale |
| --- | --- | --- | --- |
| Mars **framework package** | `0.1.0` | `pyproject.toml`, `CITATION.cff` | `name = "mars"` is an early-stage installable library; not at a stable 1.0 API. |
| **Research release** | `v1.0.0-rc1` | git tag, GitHub release | The publishable research artifact (paper + benchmark + results). |
| **Benchmark** | `v1.0.0` (frozen) | corpus manifest | Hash-pinned (`a464085c…`); bytes immutable; bugfix → `v1.0.x`, redesign → `v2`. |

**Decision (Option B):** the package version is *not* bumped to match the release tag.
Bumping `mars` to 1.0 would falsely imply a stable framework API; the research release and
benchmark carry their own version axes. Smallest consistent change — no metadata churn, no
re-pointing of the already-pushed tag.

---

## Remaining manual actions

1. **Flip repository visibility to public** (the one required step — irreversible):
   ```bash
   gh repo edit alexanderjulianmartinez/mars \
     --visibility public \
     --accept-visibility-change-consequences
   ```
   See `PUBLIC_VISIBILITY_CHECKLIST.md` (all pre-flip gates green).

2. **Optional / later:**
   - SVG→PNG export for the blog publishing platform.
   - Mint a Zenodo DOI from the public release for permanent citability.
   - Promote `v1.0.0-rc1` → `v1.0.0` after an external-reproduction soak.

**Blockers: none.** All post-tag hygiene is complete except the deliberate visibility flip.
