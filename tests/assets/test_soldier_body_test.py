#!/usr/bin/env python3
"""Check the reversible anatomy-pinned body trial across every stored pose."""
import hashlib,io,json,sys,unittest,zipfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/assets'))
from md2_assets import MD2
from verify_soldier_body_test import verify

class SoldierTrialTests(unittest.TestCase):
    def test_backup_anatomy_animation_bounds_and_all_pose_winding(self):
        self.assertEqual(verify(),4)
        report=json.loads((ROOT/'tools/assets/soldier-body-test-manifest.json').read_text())
        with zipfile.ZipFile(ROOT/report['source']['archive']) as archive:
            for item in report['models']:
                with self.subTest(model=item['path']):
                    raw=archive.read(item['source']);self.assertEqual(raw,(ROOT/'baseq2'/item['source']).read_bytes())
                    old=MD2.read(raw);new=MD2.read((ROOT/'baseq2'/item['path']).read_bytes())
                    ids=np.asarray(item['source_vertices']);pins=set(item['protected_vertices'])
                    self.assertTrue(pins<=set(ids));self.assertLess(len(new.faces),len(old.faces)*.72)
                    self.assertEqual(new.names,old.names);self.assertEqual(new.skins,old.skins)
                    np.testing.assert_array_equal(new.positions,old.positions[:,ids])
                    np.testing.assert_array_equal(new.normals,old.normals[:,ids])
                    np.testing.assert_array_equal(new.scales,old.scales)
                    source_faces=np.asarray(item['quality']['source_face_indices'])
                    # GL stripification may reorder faces and cyclically
                    # rotate their corners. Match through the encoded table.
                    table=np.frombuffer(new.data,dtype='<u2',count=new.header[8]*6,offset=new.header[13]).reshape(-1,6)[:,:3]
                    key=lambda f:min(tuple(np.roll(f,k)) for k in range(3))
                    lookup={key(f):i for i,f in enumerate(table)}
                    expected_uv=[];expected_faces=[]
                    for face in new.faces:
                        index=lookup[key(face)]
                        shift=next(k for k in range(3) if np.array_equal(np.roll(table[index],k),face))
                        expected_uv.append(np.roll(old.uvs[source_faces[index]],shift,axis=0))
                        expected_faces.append(np.roll(old.faces[source_faces[index]],shift))
                    np.testing.assert_array_equal(new.uvs,np.asarray(expected_uv))
                    def normals(model,faces):
                        p=model.positions[:,faces];return np.cross(p[:,:,1]-p[:,:,0],p[:,:,2]-p[:,:,0])
                    a=normals(old,np.asarray(expected_faces));b=normals(new,new.faces)
                    valid=np.linalg.norm(a,axis=2)>1e-7
                    self.assertTrue(np.all(np.sum(a*b,axis=2)[valid]>0))
    def test_official_default_and_grenades_are_not_selectable(self):
        source=(ROOT/'src/client/cl_entities.c').read_text()
        self.assertIn('Cvar_Get("cl_soldier_body_test", "1", CVAR_ARCHIVE)',source)
        self.assertIn('if (!enabled->value',source)
        self.assertIn('FS_LoadFile(candidate, NULL) > 0',source)
        items=(ROOT/'src/game/g_items.c').read_text();grenade=items.split('/* QUAKED ammo_grenades',1)[1].split('/* QUAKED ammo_gl_rounds',1)[0]
        self.assertIn('IT_AMMO,',grenade);self.assertNotIn('IT_WEAPON',grenade)
        weapon=(ROOT/'src/game/player/weapon.c').read_text()
        self.assertIn('if (item->weapmodel == WEAP_GRENADES)',weapon)
        self.assertIn('Cmd_QuickGrenade_f(ent);',weapon)

if __name__=='__main__':unittest.main()
