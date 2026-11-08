# Plastic Platoon asset license and provenance

The project's original models, textures, animations, maps and sound recordings
are licensed under the **GNU General Public License, version 2 or (at your
option) any later version**, consistent with the project's code license.
The full GPL version 2 text is in [LICENSE](LICENSE). Preserve source materials
and appropriate notices when redistributing or modifying the project.

This covers original Plastic Platoon content under `baseq2/`, its editable
project sources under `blender/` and `maps/`, original texture source artwork,
and the project's original asset inputs under `tools/assets/sources/`.
The original bootstrap, support-model and support-sound generators and their
outputs use these same GPL-2.0-or-later terms. Application icons in
`packaging/branding/` (PNG, ICO and SVG) are generated from the original
toy-soldier artwork in `tools/assets/build_branding.py`, without external
image inputs. Their manifests identify generated
files and disclose provisional artwork and audio.

During the 2026-11-04 reclaimed-install audit, the project owner stated:
“I created them all myself,” in response to whether the imported models,
textures, animations and sound recordings were self-created or from other
creators or asset packs. This is the owner's provenance declaration, recorded
in [asset-provenance.json](tools/assets/asset-provenance.json), rather than an
independent verification of every historical input.

This license statement does **not** cover third-party game data, removed
Quake II male/grunt fallback content or obsolete stock artwork. That content
and the old Git history were removed from the public source snapshot and
preserved only in a separate private pre-cleanup backup. No permission to
redistribute Quake II PAK files is granted here.

Bundled third-party code and optional developer tools retain their existing
licenses and attribution in their source headers. The engine's upstream notices
must remain intact. See [the standalone audit](tools/assets/STANDALONE.md) for
cleanup record, source inputs and technical verification limits.
