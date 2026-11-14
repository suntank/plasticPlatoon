#!/usr/bin/env python3
"""Pistol silhouette, fitted grip, pose transfer and exact shipped assets."""
from collections import Counter
import io
import json
from pathlib import Path
import sys
import unittest
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/assets'))
import build_pistol as builder
from asset_sources import source_bytes
from md2_assets import MD2
from m16_geometry import build_m16
from pistol_geometry import build_pistol
from build_m16 import rigid_transforms


class PistolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets,cls.manifest,cls.header=builder.build_assets()
        cls.meshes={kind:build_pistol(kind) for kind in ('world','view')}

    @staticmethod
    def part_vertices(mesh, name):
        part=next(p for p in mesh['parts'] if p['name']==name)
        start=part['first_triangle'];stop=start+part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'][start:stop])].reshape(-1,3)

    def test_exact_shipped_models_atlas_manifest_and_sight_header(self):
        for path,raw in self.assets.items():
            with self.subTest(path=path):self.assertEqual((ROOT/'baseq2'/path).read_bytes(),raw)
        self.assertEqual(json.loads(builder.MANIFEST.read_text()),self.manifest)
        self.assertEqual(builder.ADS_HEADER.read_bytes(),self.header)

    def test_budgets_frames_and_skin_closure(self):
        frames={'view':1,'pickup':1,'player':198,'enemy':475,'enemy_tall':475}
        for entry in self.manifest['models']:
            model=MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertLess(len(model.faces),650 if entry['role']=='view' else 220)
                self.assertEqual(model.header[10],frames[entry['role']])
                self.assertEqual(model.command_triangles,len(model.faces))
                self.assertEqual(model.header[4],40+4*model.header[6])
                for skin in model.skins:self.assertIn(skin,self.assets)

    def test_fitted_right_mitten_keeps_army_man_scale_and_style(self):
        pistol=self.meshes['view'];rifle=build_m16('view')
        hand_parts={p['name'] for p in pistol['parts']
                    if p['name'].startswith(('arm_','cuff_','hand_'))}
        self.assertEqual(hand_parts,{'arm_right','hand_right_palm','hand_right_thumb'})
        from build_m16 import placement
        np.testing.assert_array_equal(builder.placement('view')[0],placement('view')[0])
        # A new fit may move and reshape the mitten, while its width/height
        # should still belong to the same soldier as the rifle's hand.
        palm=self.part_vertices(pistol,'hand_right_palm')
        rifle_palm=self.part_vertices(rifle,'hand_right_palm')
        ratios=np.ptp(palm,axis=0)/np.ptp(rifle_palm,axis=0)
        self.assertTrue(np.all((ratios>.65)&(ratios<1.35)))
        thumb=self.part_vertices(pistol,'hand_right_thumb')
        self.assertGreater(thumb[:,1].max(),palm[:,1].max(),
                           'wrapping thumb must remain distinct from the palm')
        self.assertFalse(any(p['name'].startswith(('arm_','hand_','cuff_')) for p in self.meshes['world']['parts']))

    def test_long_beveled_slide_and_shallow_rear_frame(self):
        mesh=self.meshes['world']
        slide=self.part_vertices(mesh,'slide');frame=self.part_vertices(mesh,'frame')
        height=np.ptp(slide[:,2])
        self.assertGreater(np.ptp(slide[:,0])/height,5.5)
        rear=slide[np.isclose(slide[:,0],slide[:,0].min())]
        self.assertLess(np.ptp(rear[:,1]),np.ptp(slide[:,1])*.9,
                        'rear shoulders must taper into the long upper body')
        rear_frame=frame[frame[:,0]<=frame[:,0].min()+1.0]
        self.assertLess(np.ptp(rear_frame[:,2]),height*.65,
                        'rear frame must not form a second slide-sized tier')

    def test_hand_web_is_tucked_under_the_rear_of_the_slide(self):
        mesh=self.meshes['view']
        slide=self.part_vertices(mesh,'slide')
        palm=self.part_vertices(mesh,'hand_right_palm')
        thumb=self.part_vertices(mesh,'hand_right_thumb')
        height=np.ptp(slide[:,2]);bottom=slide[:,2].min()
        self.assertLess(bottom-palm[:,2].max(),height*.75,
                        'low palm exposes an excessively long neck beneath the slide')
        self.assertLess(bottom-thumb[:,2].max(),height*.55,
                        'thumb web must sit high against the backstrap')

    def test_exported_hand_wrap_stays_outside_the_grip_interior(self):
        mesh=self.meshes['view']
        # Recover the actual extruded grip profile from its +Y cap boundary,
        # rather than duplicating the artist's outline in this regression.
        grip=self.part_vertices(mesh,'grip').reshape(-1,3,3)
        half_width=grip[:,:,1].max()
        edges=Counter()
        for triangle in grip[np.all(np.isclose(grip[:,:,1],half_width),axis=1)]:
            points=[tuple(p[[0,2]]) for p in triangle]
            for a,b in zip(points,points[1:]+points[:1]):
                edges[tuple(sorted((a,b)))]+=1
        neighbors={}
        for (a,b),count in edges.items():
            if count==1:
                neighbors.setdefault(a,[]).append(b)
                neighbors.setdefault(b,[]).append(a)
        self.assertTrue(neighbors)
        self.assertTrue(all(len(n)==2 for n in neighbors.values()))
        outline=[min(neighbors)]
        previous=None
        while True:
            candidates=neighbors[outline[-1]]
            following=next(p for p in candidates if p!=previous)
            if following==outline[0]:break
            previous=outline[-1];outline.append(following)
            self.assertLess(len(outline),len(neighbors)+1)
        self.assertEqual(len(outline),len(neighbors))
        outline=np.asarray(outline)

        def deep_inside(points):
            xz=points[:,[0,2]]
            inside=np.zeros(len(points),dtype=bool)
            boundary_distance=np.full(len(points),np.inf)
            for a,b in zip(outline,np.roll(outline,-1,axis=0)):
                if abs(b[1]-a[1])>1e-12:
                    crossing=(a[1]>xz[:,1])!=(b[1]>xz[:,1])
                    hit_x=a[0]+(xz[:,1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
                    inside^=crossing & (xz[:,0]<hit_x)
                edge=b-a
                fraction=np.clip((xz-a)@edge/np.dot(edge,edge),0,1)
                distance=np.linalg.norm(xz-(a+fraction[:,None]*edge),axis=1)
                boundary_distance=np.minimum(boundary_distance,distance)
            # About a tenth of a canonical unit covers the MD2 byte lattice
            # and deliberate surface contact. A buried palm face does not.
            return inside & (boundary_distance>.12) & (np.abs(points[:,1])<half_width-.12)

        model=MD2.read(self.assets['models/weapons/v_blast/tris.md2'])
        faces=np.frombuffer(model.data,dtype='<u2',count=model.header[8]*6,
                            offset=model.header[13]).reshape(-1,6)[:,:3]
        matrix,offset,_=builder.placement('view')
        vertices=(model.positions[0]-offset)@np.linalg.inv(matrix)
        grids={}
        for part in mesh['parts']:
            if not part['name'].startswith(('hand_','arm_','cuff_')):continue
            start=part['first_triangle'];stop=start+part['triangle_count']
            for number,triangle in enumerate(vertices[faces[start:stop]],start):
                # Subdivide to <=0.12-unit edge steps, including triangle
                # interiors. Checking vertices alone misses a face spanning
                # straight through the grip between exterior corners.
                steps=max(1,int(np.ceil(max(np.linalg.norm(triangle[j]-triangle[i])
                                           for i,j in ((0,1),(1,2),(2,0)))/.12)))
                if steps not in grids:
                    grids[steps]=np.array([(i/steps,j/steps) for i in range(steps+1)
                                          for j in range(steps+1-i)])
                uv=grids[steps]
                points=triangle[0]+uv[:,0,None]*(triangle[1]-triangle[0])+uv[:,1,None]*(triangle[2]-triangle[0])
                bad=deep_inside(points)
                if np.any(bad):
                    self.fail(f'{part["name"]} face {number} enters grip interior at {points[np.flatnonzero(bad)[0]].tolist()}')

    def test_every_solid_part_including_hand_arm_and_cuff_is_closed(self):
        for detail,mesh in self.meshes.items():
            vertices=np.round(np.asarray(mesh['vertices']),7)
            for part in mesh['parts']:
                with self.subTest(detail=detail,part=part['name']):
                    a=part['first_triangle'];b=a+part['triangle_count'];edges=Counter()
                    for face in mesh['faces'][a:b]:
                        p=[tuple(vertices[i]) for i in face]
                        for x,y in zip(p,p[1:]+p[:1]):edges[tuple(sorted((x,y)))]+=1
                    self.assertTrue(edges)
                    self.assertTrue(all(n==2 for n in edges.values()),'open surface exposes background')

    def test_sights_have_clear_center_channel_above_slide(self):
        mesh=self.meshes['view'];rear=np.array(mesh['anchors']['rear_sight']);front=np.array(mesh['anchors']['front_sight'])
        np.testing.assert_array_equal(rear[1:],front[1:])
        self.assertGreater(front[0]-rear[0],20)
        # The slide is below the sight ray and the rear wings straddle it.
        for part in mesh['parts']:
            if part['name'] not in ('slide','rear_sight_left','rear_sight_right'):continue
            a=part['first_triangle'];b=a+part['triangle_count']
            pts=np.asarray(mesh['vertices'])[np.asarray(mesh['faces'][a:b])].reshape(-1,3)
            if part['name']=='slide':self.assertLess(pts[:,2].max(),rear[2])
            else:self.assertTrue(pts[:,1].min()>0 or pts[:,1].max()<0)

    def test_all_held_poses_follow_original_rigid_motion_without_collapses(self):
        originals=json.loads((ROOT/'tools/assets/platoon-originals.json').read_text())
        for path,role in builder.MODELS.items():
            if role not in ('player','enemy'):continue
            with self.subTest(role=role):
                source=MD2.read(source_bytes(originals,'baseq2/'+path),source_compat=True)
                out=MD2.read(self.assets[path]);self.assertEqual(out.names,source.names)
                r,t,errors=rigid_transforms(source);self.assertLess(errors.max(),.03)
                matrix,offset,_=builder.placement(role)
                posed=np.asarray(self.meshes['world']['vertices'])@matrix+offset
                expected=np.asarray([posed@a+b for a,b in zip(r,t)])
                distance=np.linalg.norm(out.positions-expected,axis=2)
                limit=np.linalg.norm(out.scales,axis=1)/2+1e-5
                self.assertTrue(np.all(distance<=limit[:,None]))
                p=out.positions[:,out.faces]
                self.assertGreater(np.linalg.norm(np.cross(p[:,:,1]-p[:,:,0],p[:,:,2]-p[:,:,0]),axis=2).min(),1e-9)

    def test_tall_variant_and_existing_color_material_are_preserved(self):
        a=MD2.read(self.assets['models/monsters/soldier/weapon_blaster.md2'])
        b=MD2.read(self.assets['models/monsters/soldier/tall/weapon_blaster.md2'])
        self.assertEqual(a.names,b.names)
        expected=a.positions*1.2;expected[:,:,2]+=4.8
        np.testing.assert_allclose(b.positions,expected,atol=8e-6)
        pistol=np.asarray(Image.open(io.BytesIO(self.assets[builder.TEXTURES[1]])).convert('RGB'))
        rifle=np.asarray(Image.open(ROOT/'baseq2/models/weapons/v_machn/skin.png').convert('RGB'))
        self.assertEqual(pistol.shape,rifle.shape)
        # Local serrations/creases may change. All other plastic, hand and
        # cuff tiles retain the existing soldier's material values exactly.
        for index in range(16):
            row,col=divmod(index,4)
            a=pistol[row*64:(row+1)*64,col*64:(col+1)*64]
            b=rifle[row*64:(row+1)*64,col*64:(col+1)*64]
            with self.subTest(atlas_tile=index):
                if index not in (4,10):np.testing.assert_array_equal(a,b)
                else:
                    np.testing.assert_allclose(np.median(a,axis=(0,1)),
                                               np.median(b,axis=(0,1)),atol=1)
        self.assertEqual(self.assets[builder.TEXTURES[0]],self.assets[builder.TEXTURES[1]])

    def test_legacy_rebuild_cannot_restore_old_pistol(self):
        import build_platoon
        config=json.loads(build_platoon.CONFIG.read_text())
        owned=build_platoon.procedural_paths(config)
        self.assertTrue(set(builder.MODELS)<=owned)
        manifest=json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS)&{e['path'] for e in manifest['models']})


if __name__=='__main__':unittest.main(verbosity=2)
