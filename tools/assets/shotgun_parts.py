"""Closed oval sections and the support hand shared by both toy shotguns."""
import math


def oval_sections(stations, sides):
    """Elliptical loft rings through (x, y, z, half-width, half-height)."""
    angles = [math.tau * (i+.5) / sides for i in range(sides)]
    return [[(x, y+w*math.cos(a), z+h*math.sin(a)) for a in angles]
            for x,y,z,w,h in stations]


def add_support_hand(m, shift=0., sleeve=None):
    """Cup the fore-end, keeping the elbow planted during pump travel."""
    if sleeve is None:
        sleeve = [(10,12,-32,3.8,3.3),(37,3.8,-20,3.25,2.8),
                  (52,4.2,-7.45,2.6,2.15),(53.8,3.65,-6.30,2.55,2.05),
                  (56,2.6,-5.35,1.85,1.55)]
    # Taper the pump travel from the cuff back to the planted elbow.
    elbow_x, cuff_x = sleeve[0][0], sleeve[2][0]
    stations = [(x-shift*min(1.,(x-elbow_x)/(cuff_x-elbow_x)),y,z,w,h)
                for x,y,z,w,h in sleeve]
    start = len(m.faces)
    m.loft('arm_left', oval_sections(stations,6))
    m.materials[start+24:start+36] = ['cuff']*12
    hand_start = len(m.vertices)
    m.loft('hand_left_palm', oval_sections([
        (54.4,2.65,-5.45,1.7,1.3),(56.4,1.2,-4.40,2.75,1.75),
        (60.1,.25,-3.85,3.35,1.65),
        (63.7,.15,-3.55,1.45,.7)], 8))
    m.loft('hand_left_fingers', oval_sections([
        (55.9,-1.7,-3.45,.75,1.1),(57.5,-2.5,-2.35,1.3,2.0),
        (61.4,-2.65,-1.95,1.3,2.15),(63.35,-2.15,-2.45,.85,1.35)], 6),
        'fingers', uv_axes=(2,0))
    m.finger('hand_left_thumb',
             [(55.9,2.8,-4.6),(57.6,3.65,-2.95),(60.1,3.18,-1.40),
              (63.1,2.65,-1.05)], [1.5,1.4,1.08,.54])
    for point in m.vertices[hand_start:]:
        point[0] -= shift
