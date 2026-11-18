"""Tank shape and molded surface art shared by the backpack and fuel pickup."""
import math

from PIL import Image, ImageDraw


TANK_PROFILE = ((7.8,1.79),(8.67,2.79),(10.02,3.25),
                (19.7,3.25),(21.25,2.89),(22.,1.76))


def add_tank(mesh, name, center, surface, profile=TANK_PROFILE):
    """Add a domed tank with a wrapped texture and plain end caps."""
    cx, cy = center
    loops = [[(cx+radius*math.cos(math.pi/8+i*math.tau/8),
               cy+radius*math.sin(math.pi/8+i*math.tau/8),z) for i in range(8)]
             for z,radius in profile]
    start = len(mesh.faces)
    mesh.loft(name, loops, surface)
    bottom, top = profile[0][0], profile[-1][0]
    for face in range(start,len(mesh.faces)-12):
        mesh.uvs[face] = [[(mesh.vertices[index][2]-bottom)/(top-bottom),v]
                          for index,(_,v) in zip(mesh.faces[face],mesh.uvs[face])]
    mesh.materials[-12:] = ['plastic']*12


def tank_texture():
    tile = Image.new('RGB',(64,64))
    draw = ImageDraw.Draw(tile)
    for y in range(64):
        angle = math.tau*(y-4.5)/55
        curve = .5-.5*math.cos(angle)
        value = round(33+16*curve+7*curve**7)
        draw.line((0,y,63,y),fill=(round(.72*value),value,round(.36*value)))
        for start,end in ((15,19),(48,52)):
            shade = value-12
            draw.line((start,y,end,y),fill=(round(.72*shade),shade,round(.36*shade)))
            rim = value+5
            draw.point((end+1,y),fill=(round(.72*rim),rim,round(.36*rim)))
    draw.rounded_rectangle((24,22,42,40),radius=5,outline=(24,34,13),width=2)
    for x in (29,35):
        draw.line((x,35,x+3,27),fill=(46,64,24),width=2)
    return tile
