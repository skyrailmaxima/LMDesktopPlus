# Release & CI

LMDesktopPlus ships four kinds of artifact. CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml))
builds the light ones on every push and the heavy images only when gated.

| Artifact | Size | Built | Hosted |
|---|---|---|---|
| `lmdesktopplus_<ver>_all.deb` (control center) | small | every push | GitHub Release + CI artifact |
| `lmdesktopplus-desktop_<ver>_all.deb` (metapackage) | tiny | every push | GitHub Release + CI artifact |
| `lmdesktopplus-<ver>-freebsd.txz` (UI pkg) | small | every push | GitHub Release + CI artifact |
| `lmdesktopplus-mint-<ver>.iso` (Mint respin) | ~2–3 GB | gated | external storage (checksum in Release) |
| `lmdesktopplus-freebsd-<ver>.img` (FreeBSD image) | ~2–4 GB | gated | external storage (checksum in Release) |

## CI stages

The `test (ubuntu)` job runs the full `./tests/run-all.sh`, which already covers:
unit tests, node behaviour tests, the Xvfb screenshot smoke, the `.deb` +
`lmdesktopplus-desktop` metapackage + FreeBSD metaport + FreeBSD UI pkg builds,
and the Mint ISO / FreeBSD image **assembly gates** (`build-iso.sh --check`,
`build-image.sh --check`). The `ui screenshots (xvfb)` job captures the
per-scene + responsive screenshots. Both run on every push/PR.

### Gated image builds

The `mint respin iso (gated)` and `freebsd install image (gated)` jobs are heavy
(they bootstrap full base systems) so they only run when:

- a version tag `v*` is pushed, or
- a manual `workflow_dispatch` is triggered with **`build_images: true`**.

`mint-iso` installs `live-build` on the Ubuntu runner and runs
`sudo ./packaging/iso/mint/build-iso.sh --build`. `freebsd-image` runs inside a
FreeBSD VM (via `vmactions/freebsd-vm`) where it builds the local poudriere repo
(`packaging/freebsd/poudriere/build-repo.sh`) and then
`./packaging/freebsd/image/build-image.sh --build`. Each emits a `.sha256`
alongside the image.

## Large-artifact hosting strategy

GitHub Releases cap individual files at 2 GiB, and the Mint ISO / FreeBSD image
can exceed that. So:

1. **Small artifacts** (`.deb`s, FreeBSD `.txz`, and a `SHA256SUMS`) are attached
   directly to the GitHub Release by the `release` job (draft) on a `v*` tag.
2. **Large images** are uploaded to external object storage (e.g. an S3/R2/B2
   bucket or a self-hosted mirror). The image build jobs also upload them as
   short-retention CI artifacts for verification.
3. The Release body links each image URL and records its **SHA-256 checksum** (the
   `.sha256` files the image jobs produce), so downloads are verifiable even
   though the bytes live off-GitHub.

### Cutting a release

```sh
# 1. Tag (pushing the tag fires the gated image jobs + the draft release job).
git tag -a v0.7.0 -m "v0.7.0"
git push origin v0.7.0

# 2. Download the ISO/image CI artifacts, verify their .sha256, and upload them
#    to the external bucket.

# 3. Edit the draft Release: paste the image URLs + checksums, then publish.
```

For a fully self-hosted flow, point step 2 at your mirror and add its URLs to the
Release template; the checksums make the split hosting tamper-evident.
