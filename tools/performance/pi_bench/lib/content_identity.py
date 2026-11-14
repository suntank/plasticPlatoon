#!/usr/bin/env python3
"""Read-only asset, compiled-map and visibility identity for an isolated runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

LUMPS=('entities','planes','vertexes','visibility','nodes','texinfo','faces','lighting',
       'leafs','leaffaces','leafbrushes','edges','surfedges','models','brushes',
       'brushsides','pop','areas','areaportals')


def digest(data):return hashlib.sha256(data).hexdigest()


def bsp_identity(data):
    if len(data)<160 or data[:4]!=b'IBSP' or struct.unpack_from('<i',data,4)[0]!=38:
        raise ValueError('Invalid IBSP38 map in content audit')
    result={}
    for i,name in enumerate(LUMPS):
        offset,size=struct.unpack_from('<ii',data,8+8*i)
        if offset<0 or size<0 or offset+size>len(data):raise ValueError('Map lump outside file')
        result[name]=dict(bytes=size,sha256=digest(data[offset:offset+size]))
    return dict(bytes=len(data),sha256=digest(data),lumps=result)


def content_identity(runtime,file_hashes=None):
    runtime=Path(runtime);base=runtime/'baseq2';files={};maps={}
    skip_dirs={'perf','save','scrnshot'}
    skip_files={'config.cfg','qconsole.log','console_history.txt'}
    for path in sorted(base.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(base)
        if relative.parts[0] in skip_dirs or relative.name in skip_files:continue
        key=path.relative_to(runtime).as_posix()
        files[key]=file_hashes[key] if file_hashes is not None and key in file_hashes else digest(path.read_bytes())
        if path.suffix.lower()=='.bsp':maps[key]=bsp_identity(path.read_bytes())
        if path.suffix.lower()=='.pk3':
            with zipfile.ZipFile(path) as archive:
                for member in sorted(archive.namelist()):
                    if member.lower().endswith('.bsp'):
                        maps[key+':'+member]=bsp_identity(archive.read(member))
        if path.suffix.lower()=='.pak':
            packed=path.read_bytes()
            if len(packed)<12 or packed[:4]!=b'PACK':raise ValueError('Invalid PAK in content audit')
            offset,size=struct.unpack_from('<ii',packed,4)
            if offset<12 or size<0 or size%64 or offset+size>len(packed):raise ValueError('Invalid PAK directory')
            for at in range(offset,offset+size,64):
                raw,start,length=struct.unpack_from('<56sii',packed,at)
                member=raw.split(b'\0',1)[0].decode('latin1')
                if start<0 or length<0 or start+length>len(packed):raise ValueError('Invalid PAK member')
                if member.lower().endswith('.bsp'):maps[key+':'+member]=bsp_identity(packed[start:start+length])
    return dict(schema=1,scope='All runtime baseq2 content except generated saves/perf/screenshots/config/logs; every packed/loose BSP and all nineteen lumps included.',
                files=files,maps=maps,
                signature_sha256=digest(json.dumps(dict(files=files,maps=maps),sort_keys=True,separators=(',',':')).encode()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=content_identity(a.runtime.resolve())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),files=len(result['files']),maps=len(result['maps']),signature=result['signature_sha256']),indent=2))


if __name__=='__main__':main()
