# Public standalone source cleanup — 2026-11-04

The reclaimed copy is prepared as a standalone Plastic Platoon source snapshot
with a new local Git root. The original development history is retained in a
private backup outside this repository. Original GPL engine code, copyright
headers, component notices and upstream credits remain intact.

## Preserved source and private backup

The private directory is `../plasticPlatoon-private-backup-20261104T204722Z`.
It is outside the public checkout and is not a Git input.

| Backup | Contents |
| --- | --- |
| `reclaimed-before-public-cleanup.tar` | Complete pre-cleanup checkout, old Git database, source and ignored build/release files. 645,109,760 bytes; SHA-256 `3258559a6851a17846d4bcd80143b62fb613e9bcc06f070b0cdbb84f8d064cc9`. |
| `editable-sources.tar` | All 31 editable-source inputs from the initial inventory, including primary/backup Blender rigs, PSD, map sources and material source images. 100,454,400 bytes; SHA-256 `0b08e8a79db06d13ce2556f35a51c0682b91fb254f13d88483086cc9981240f1`. Every member was checked against its original hash. |
| `original-git/` | The original Git database, refs, remote metadata and reflogs moved out of the public checkout. |
| `backup-manifest.json` | Original refs, archive hashes and editable-source inventory. |

Primary `.blend` rigs, the PSD, authored `.map` files, original material sources
and authorized model/audio source archives remain available in the public source
because they are editable development inputs. Editor `.blend1` backups, autosaves,
compiler debris and obsolete diagnostic output were removed from this checkout.
They are preserved in the private archives.

Nothing under the Documents working copy was edited. No remote repository was
pushed, deleted or rewritten during this cleanup.

## Removed and replaced

- Removed legacy `baseq2/players/male/` models and grunt artwork. Client/server
  fallbacks use the project's soldier, and its ten portraits are original art.
- Removed the stock-palette crosshair source directory. Map generators now use
  the original generated project palette, without a stock palette hash or font.
- Reindexed 195 loose/archive WAL representations using their original PNG/TGA
  companions. Texture headers, flags, animation metadata, truecolor artwork and
  BSP bytes were preserved. Seven mission archives were updated consistently.
- Replaced the embedded Quake logo with original SDL/Windows project branding.
- Removed the obsolete macOS app bundle and its prebuilt utilities. The macOS
  workflow packages source-built portable output and its SDL dependency.
- Removed old runtime/in-game screenshots, stock-map diagnostic captures,
  compiler scratch files and the optional legacy exporter ZIP. Offline
  comparisons containing project models remain as asset verification inputs.
- Replaced private-Git source reads with a checked 146-entry original source
  archive. Converters now validate 66 custom MD2s, 77 PNGs and 16 pickup pairs
  without any older commits or home-directory data.
- Retained licenses, source headers, upstream CHANGELOG and upstream README.
  The new history does not change those source-code credits.

[public-cleanup.json](review/public-cleanup.json) records removed file hashes,
backup details and source/palette migration. [HISTORY.md](../../HISTORY.md)
describes the clean public starting point.

## Build and verify

```sh
make -j4 all
./release/play-portable.sh
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
python3 tools/assets/build_overlay.py --verify
python3 tools/assets/audit_standalone.py --strict --output /tmp/platoon-runtime-audit.json
python3 tools/assets/audit_public_source.py --history --strict
python3 tools/assets/smoke_standalone.py --renderer gl3 --renderer gl1 --renderer soft
```

The public-source guard checks the working snapshot and Git object store,
including unreachable blobs and nested archive entries. Known removed game
media and private backups must not return in future commits. Checks for removed
content do not mean every filename containing `quake2` should disappear: the GPL
engine source, compatibility resource names, standard formats and notices are
part of the legitimate project implementation.

See [the asset build guide](README.md) for pinned conversion dependencies and
source archive verification. All source assets use the terms and owner declaration
in [ASSET-LICENSE.md](../../ASSET-LICENSE.md).

## Validation and limits

A separate `git clone --no-local --no-hardlinks` of the new one-commit main
built with `make -j4 all`, passed all **77 asset tests with no skips**, verified
66 original MD2s / 77 PNGs and 16 pickup pairs, and retained a clean Git status
after building and testing. Palette and runtime archive verifiers passed there.
The updated runtime then passed **30/30 isolated captures**: ten maps across
GL1, GL3 and software rendering, **900 complete frames**, with zero actual
missing resources. Current reports are retained in `review/standalone-audit.json`
and `review/standalone-smoke.json`.

The public-source guard reports zero violations across 1,254 tracked source
files, eleven archives and 1,098 archive members. It also scans every local Git
blob, including unreachable objects, and checks that the old baseline commit
and alternate object stores are absent. The largest source file is the
47,317,833-byte checked originals archive. There is no Git LFS or external Git
object dependency.

Source conversion checks cover 66 MD2s, 77 PNGs, 16 pickup pairs, 23 conversion/
archive regressions and an exactly reproduced pickup model/texture pair. Palette
migration tests cover original-palette selection, opaque indexing and unchanged
WAL metadata/nonmaterial inputs. Branding checks compare the generated RGBA
pixels across the SDL header, PNG and Windows icon.

These are source/readiness and bounded map-load checks. Provisional UI, support
sounds and props still need an art pass. Existing green-helicopter animation
frame fallbacks, soldier skin-number fallbacks, small-resolution software HUD
clipping and unknown tuning ammo identifiers remain documented technical debt.
A full playthrough, every dynamic effect, all controller/splitscreen combinations,
Windows/macOS execution and Raspberry Pi performance have not been certified.
Installed CMake 3.28.3 is below the repository's 3.31 minimum; the Make build and
shared asset scripts are verified here.
