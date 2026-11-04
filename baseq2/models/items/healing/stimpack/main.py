import struct, sys

def md2_info(path):
    with open(path, "rb") as f:
        hdr = f.read(68)
    ident, version = struct.unpack("<4sI", hdr[:8])
    if ident != b"IDP2" or version != 8:
        raise ValueError("Not an MD2 (IDP2 v8)")
    (skinwidth, skinheight, framesize, num_skins, num_xyz, num_st, num_tris,
     num_glcmds, num_frames, ofs_skins, ofs_st, ofs_tris, ofs_frames,
     ofs_glcmds, ofs_end) = struct.unpack("<15i", hdr[8:68])
    return {
        "skin": (skinwidth, skinheight),
        "num_skins": num_skins,
        "num_xyz": num_xyz,
        "num_st": num_st,
        "num_tris": num_tris,
        "num_frames": num_frames
    }

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, md2_info(p))
