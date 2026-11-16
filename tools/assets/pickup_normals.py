"""Local pickup shading islands; retain every triangle corner position and UV."""
import numpy as np


class PickupNormals:
    def __init__(self,mesh):
        self.mesh=mesh
        self.points=np.asarray(mesh['vertices'],dtype=float)
        self.faces=np.asarray(mesh['faces'],dtype=int)
        self.triangles=self.points[self.faces]
        cross=np.cross(self.triangles[:,1]-self.triangles[:,0],self.triangles[:,2]-self.triangles[:,0])
        self.face_normals=cross/np.linalg.norm(cross,axis=1)[:,None]
        self.corner_normals=np.asarray(mesh['normals'])[self.faces].copy()

    def part(self,name):
        p=next(p for p in self.mesh['parts'] if p['name']==name)
        return np.arange(p['first_triangle'],p['first_triangle']+p['triangle_count'])

    def smooth(self,faces):
        """Angle-weight across coincident corners, independent of UV seams/fans."""
        faces=np.asarray(faces,dtype=int)
        accumulated={}
        for face in faces:
            triangle=self.triangles[face]
            for corner,point in enumerate(triangle):
                a=triangle[(corner+1)%3]-point;b=triangle[(corner+2)%3]-point
                angle=np.arctan2(np.linalg.norm(np.cross(a,b)),np.dot(a,b))
                key=tuple(np.round(point,7))
                accumulated[key]=accumulated.get(key,np.zeros(3))+self.face_normals[face]*angle
        for face in faces:
            for corner,point in enumerate(self.triangles[face]):
                direction=accumulated[tuple(np.round(point,7))]
                length=np.linalg.norm(direction)
                if length<1e-8:raise ValueError('Opposed surfaces in a pickup smoothing island')
                self.corner_normals[face,corner]=direction/length

    def flat(self,faces):
        self.corner_normals[faces]=self.face_normals[faces,None,:]

    def rounded_sides(self,name,axis=2):
        faces=self.part(name)
        caps=np.abs(self.face_normals[faces,axis])>.99999
        self.smooth(faces[~caps]);self.flat(faces[caps])

    def bevel_box(self,name):
        """Round each XY chamfer into adjacent flat panels; keep cap creases."""
        faces=self.part(name)
        points=self.triangles[faces].reshape(-1,3)
        low,high=points.min(axis=0),points.max(axis=0)
        for face in faces:
            if abs(self.face_normals[face,2])>.99999:continue
            for corner,point in enumerate(self.triangles[face]):
                normal=np.zeros(3)
                for axis in (0,1):
                    if abs(point[axis]-low[axis])<1e-7:normal[axis]=-1
                    elif abs(point[axis]-high[axis])<1e-7:normal[axis]=1
                if np.count_nonzero(normal)!=1:raise ValueError('Expected a beveled box corner')
                self.corner_normals[face,corner]=normal

    def finish(self):
        # Split only vertices that need both a curved wall normal and a flat
        # cap normal. Geometry, triangle order, UVs and material IDs stay fixed.
        points=self.points.tolist();normals=[None]*len(points);faces=self.faces.copy();indices={}
        for face in range(len(faces)):
            for corner,original in enumerate(self.faces[face]):
                normal=self.corner_normals[face,corner]
                key=(int(original),*np.round(normal,10))
                if key not in indices:
                    index=int(original)
                    if normals[index] is not None:
                        index=len(points);points.append(self.points[original].tolist());normals.append(None)
                    normals[index]=normal.tolist();indices[key]=index
                faces[face,corner]=indices[key]
        if any(n is None for n in normals):raise ValueError('Unused pickup vertex')
        self.mesh.update(vertices=points,normals=normals,faces=faces.tolist())
        return self.mesh
