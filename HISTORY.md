# History and upstream credits

The public Plastic Platoon repository begins with a clean source snapshot
prepared on 2026-11-04. The earlier development history contained legacy Quake II
fallback media and obsolete binary packages. That history was backed up
privately and is not an ancestor of the new public main branch.

Plastic Platoon's engine is derived from Yamagi Quake II, which builds on
Icculus Quake II and id Software's GPL source release. The clean-history import
does not change those copyrights or licenses. Original source headers,
LICENSE, the Yamagi CHANGELOG and the preserved upstream README remain in this
repository. Third-party library notices remain in the relevant source files.

Original Plastic Platoon models, animation, textures, maps and recordings were
created by the project owner. Their license and provenance are recorded in
ASSET-LICENSE.md and tools/assets/asset-provenance.json. Editable Blender rigs,
Photoshop texture source and map sources remain available alongside checked
conversion source archives. Archive manifests identify the original inputs;
rebuilding no longer depends on access to the earlier Git objects.

A complete pre-cleanup snapshot, including editable source backups and all old
Git refs, is retained outside the public repository. Backup details and removed
file hashes are in tools/assets/review/public-cleanup.json. Do not publish that
private archive or merge the old development history into the public branch.
