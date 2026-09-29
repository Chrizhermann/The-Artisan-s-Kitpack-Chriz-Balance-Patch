# Fork versions and upstream provenance

Starting with this release, use `v<upstream-version>-chriz.<revision>`.
For an untagged upstream snapshot, include `-dev.<short-upstream-commit>` before
the fork suffix. All three main TP2 installers, the Git tag and release metadata
must use the same full identity. This follows the September 29, 2026 decision
shared with CEBG and the other Chriz forks.

The migration is **`chriz-v1.6.0` ->
`v4.81a-dev.85928f9-chriz.1`**. The new `.1` starts the upstream-based naming
scheme; it does not discard or undo the previously released fork changes.
Published `chriz-v1.x` tags, archives and historical release notes stay unchanged.

## Upstream base for the first release using this scheme

- Repository: <https://github.com/TheArtisanBG/The-Artisan-s-Kitpack>
- Upstream release label: `v4.81a`.
- Release commit: `a4b469988a568f8f7b943d67512297e05da03eeb`.
- Included snapshot: `85928f964f6965fd37980bf679d7eeb9af410256`.
- The snapshot is 297 commits beyond the release commit. Upstream supplies no
  TP2 VERSION or newer development version label for it, so the snapshot
  qualifier is required. Plain `v4.81a-chriz.1` would misidentify this source.
- Fork revision: `1`.

The release-label evidence was verified on September 29. Before future releases,
record the actual chosen base; a new upstream commit is not automatically part
of this checkout or a release.

## Advancing the version

- Our patch changes: advance the `chriz.N` suffix.
- Upstream changes with our patch layer unchanged: change the upstream version
  or snapshot qualifier and retain the suffix.
- Upstream changes requiring changes to our patch layer: advance both parts.
- Do not reset the suffix just because the upstream base changes.
- Record the full upstream commit in each release's notes and contents manifest.
  The short hash in the version identifies the snapshot but does not replace
  its full provenance.

## Offline version helper

There is no committed release-packaging workflow. The helper only reads or
updates the three main TP2 VERSION values; it never installs, commits, tags,
pushes, creates an archive or publishes a release.

```text
python tools/version.py --set v4.81a-dev.85928f9-chriz.1
python tools/version.py --check --expect v4.81a-dev.85928f9-chriz.1
python -m unittest discover -s tests -p test_release_version.py -v
```

The helper preserves bytes outside those VERSION values and validates all
three files before writing. It accepts numeric upstream versions with an
optional trailing letter, an optional `-dev.<7-to-40-character-hex-commit>`
qualifier and a positive `-chriz.N` suffix. If future upstream naming requires
another format, update the helper explicitly; do not fall back to independent
fork numbering.

For a future release, prepare `docs/releases/<full-version>.md` as well. Use
`ArtisansKitpack-Chriz-Balance-Patch-<full-version>.zip` for the archive, append
`.sha256` for its checksum and use the same prefix with `-contents.json` for the
contents manifest. Preserve the full version in metadata instead of trimming
the snapshot qualifier or suffix. Historical asset names are unchanged.

CEBG updates its immutable artifact pin separately after the owner publishes
and verifies a release. A source VERSION edit or owner release does not itself
update CEBG pins, already installed games or their WeiDU logs.
