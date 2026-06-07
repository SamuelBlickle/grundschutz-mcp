# Releasing

Releases are built and published by [`.github/workflows/release.yml`](.github/workflows/release.yml),
triggered by pushing a `v*` tag. Publishing is **tokenless**: it uses PyPI
Trusted Publishing (OIDC) and Sigstore-signs the artifacts, so no long-lived
PyPI token exists anywhere. The build is attested with SLSA provenance.

## One-time setup (manual, human-only)

These steps need account access and are not automatable from the repo.

1. **PyPI Trusted Publisher.** On PyPI, create the project `grundschutz-mcp`
   (or add a *pending* publisher before the first release) and add a GitHub
   Actions trusted publisher with exactly:
   - Owner: `SamuelBlickle`
   - Repository: `grundschutz-mcp`
   - Workflow name: `release.yml`
   - Environment: `pypi`
2. **GitHub Environment.** Create an Environment named `pypi`
   (Settings → Environments) and add a **required reviewer** so every publish is
   a manual approval. For a security tool this is required, not optional.
   Also add a **tag protection rule** (or ruleset) for `v*` so only you can push
   release tags. The publish job additionally refuses to run outside this repo
   (`if: github.repository == 'SamuelBlickle/grundschutz-mcp'`).
3. **Signing.** No key management is needed: `gh-action-pypi-publish` performs
   keyless Sigstore signing via OIDC, and `attest-build-provenance` records
   keyless build provenance. (No GPG key, no stored secrets.)

## Cutting a release

See [VERSIONING.md](VERSIONING.md) for the SemVer policy (the software contract
is versioned independently of the BSI data version) and how to choose the level.
The first public release is `1.0.0`.

1. Ensure `main` is green and `/ship-check` is GO. For the `1.0.0` tag, also run
   the API-freeze check from VERSIONING.md.
2. Bump the version in `pyproject.toml` and `src/grundschutz_mcp/__init__.py`
   (keep them in sync) to the level chosen per VERSIONING.md, commit.
3. Tag and push:
   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
4. The workflow builds, attests provenance, and (after the `pypi` environment
   approval, if configured) publishes to PyPI with Sigstore signatures.
5. Verify: the package appears on PyPI, `uvx grundschutz-mcp` runs, and the
   provenance/signatures are attached.

## Notes

- The `deny_dangerous` hook blocks `uv publish` / `twine upload` locally on
  purpose: publishing happens only through this reviewed, signed CI path.
- The pinned BSI data commit is independent of the package version; bumping it
  (see the drift monitor) is its own deliberate, tested change.
