"""Create actual CSG print meshes, editable OpenSCAD, CAD previews and checks.

All model units are millimetres. The fitted Uno is a REFERENCE KEEP-OUT,
never a printable holder or a part to move. Edit parameters.json and rebuild.
Nominal reference geometry is not a physical fit/load certification.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import json, math, hashlib, zipfile, importlib.metadata
import numpy as np
import manifold3d as md
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / 'parameters.json').read_text())
OUT = ROOT / 'exports'
OUT.mkdir(exist_ok=True)
W = P['hardware']
C = P['dry_case']
UNO = P['mounted_uno']
DECK = UNO['solder_top_from_mount_plane'] + UNO['rear_wire_loop_allowance'] + UNO['wire_margin']
TOP = DECK + P['carrier']['deck']
CASE_Z = TOP
TRAY_Z = CASE_Z + C['tray_bottom']
SLEEVE_Z = CASE_Z + C['lower_height']
LID_Z = SLEEVE_Z + C['upper_height']
TANK_X = P['bottle']['center_x']
CASE_CX = (C['x_min'] + C['x_max']) / 2
EPS = 0.05

def fmt(v):
    if isinstance(v, (list,tuple,np.ndarray)):
        return '[' + ','.join(fmt(x) for x in v) + ']'
    return f'{float(v):.7g}'

@dataclass
class Solid:
    m: object
    scad: str
    def moved(self, xyz):
        return Solid(self.m.translate(tuple(xyz)), f'translate({fmt(xyz)}){{{self.scad}}}')
    def turned(self, xyz):
        return Solid(self.m.rotate(tuple(xyz)), f'rotate({fmt(xyz)}){{{self.scad}}}')

def box(x0,x1,y0,y1,z0,z1):
    assert x1>x0 and y1>y0 and z1>z0, (x0,x1,y0,y1,z0,z1)
    q=(x1-x0,y1-y0,z1-z0)
    return Solid(md.Manifold.cube(q).translate((x0,y0,z0)),
                 f'translate({fmt([x0,y0,z0])})cube({fmt(q)});')

def cyl(x,y,z,r,h,n=48,r2=None):
    r2=r if r2 is None else r2
    return Solid(md.Manifold.cylinder(h,r,r2,n).translate((x,y,z)),
                 f'translate({fmt([x,y,z])})cylinder(h={fmt(h)},r1={fmt(r)},r2={fmt(r2)},$fn={n});')

def union(*items):
    items=[s for s in items if s is not None]
    assert items
    if len(items)==1:return items[0]
    return Solid(md.Manifold.batch_boolean([s.m for s in items],md.OpType.Add),
                 'union(){'+''.join(s.scad for s in items)+'}')

def cut(base,*tools):
    if not tools:return base
    return Solid(md.Manifold.batch_boolean([base.m]+[s.m for s in tools],md.OpType.Subtract),
                 'difference(){'+base.scad+''.join(s.scad for s in tools)+'}')

def intersect(a,b):
    return md.Manifold.batch_boolean([a.m,b.m],md.OpType.Intersect)

def beam(a,b,width,z0,z1):
    ax,ay=a;bx,by=b
    length=math.hypot(bx-ax,by-ay)
    if length < 1e-8:return cyl(ax,ay,z0,width/2,z1-z0)
    q=box(0,length,-width/2,width/2,z0,z1).turned((0,0,math.degrees(math.atan2(by-ay,bx-ax)))).moved((ax,ay,0))
    return union(q,cyl(ax,ay,z0,width/2,z1-z0),cyl(bx,by,z0,width/2,z1-z0))

def slot(x,y,length,width,z0,z1,axis='y'):
    travel=max(0,length-width)/2
    a=(x-travel,y) if axis=='x' else (x,y-travel)
    b=(x+travel,y) if axis=='x' else (x,y+travel)
    return beam(a,b,width,z0,z1)

def ring(x,y,ro,ri,z0,z1):
    return cut(cyl(x,y,z0,ro,z1-z0),cyl(x,y,z0-EPS,ri,z1-z0+2*EPS))

def rect_ring(x0,x1,y0,y1,z0,z1,t):
    return cut(box(x0,x1,y0,y1,z0,z1),box(x0+t,x1-t,y0+t,y1-t,z0-EPS,z1+EPS))

def cs_hole(x,y,z0,z1,r=1.7,head=3.1,depth=1.8):
    return union(cyl(x,y,z0-EPS,r,z1-z0+2*EPS),cyl(x,y,z1-depth,r,depth+EPS,r2=head))

def hole_x(x0,x1,y,z,r):
    return cyl(0,0,0,r,x1-x0).turned((0,90,0)).moved((x0,y,z))

def hole_y(y0,y1,x,z,r):
    return cyl(0,0,0,r,y1-y0).turned((-90,0,0)).moved((x,y0,z))

def mesh_of(s):
    q=s.m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(q.vert_properties)[:,:3],faces=np.asarray(q.tri_verts),process=True)

PARTS=[]
def add(name,shape,qty=1,print_rotation=(0,0,0),color=(124,137,144),role='production prototype'):
    PARTS.append(dict(name=name,s=shape,qty=qty,print_rotation=print_rotation,color=color,role=role))
    return shape

def original_mounts():
    r=P['reference_mounts']; y=r['front_rear_pitch']/2
    return [(-r['front_spacing']/2,y),(r['front_spacing']/2,y),
            (-r['rear_spacing']/2,-y),(r['rear_spacing']/2,-y)]

MOUNTS=original_mounts()
# Offset posts clear the mounted Uno reference; rear-left is moved outboard
# to leave the USB-B pod corridor. Actual track/blade geometry must be tried.
POSTS=[(-27.5,43.5),(27.5,43.5),(-42.0,-52.0),(33.0,-52.0)]
BODY_BOLTS=[(1.5,-65.0),(71.5,-65.0),(1.5,55.0),(71.5,55.0)]
EAR_CENTRES=[(C['x_min']-6,y) for y in (-52.0,52.0)]+[(C['x_max']+6,y) for y in (-52.0,52.0)]
CUP_BOLTS=[(TANK_X,-37.0),(TANK_X,37.0)]

def foot(index):
    anchor=MOUNTS[index]; post=POSTS[index]
    washer=W['isolation_washer']; thickness=3.2
    path=[anchor,(-42.0,anchor[1]),post] if index==2 else [anchor,post]
    a=union(*[beam(u,v,5.4,washer,washer+thickness) for u,v in zip(path,path[1:])])
    a=union(a,slot(*anchor,9,5.4,washer,washer+thickness),
            box(post[0]-5,post[0]+5,post[1]-6,post[1]+6,washer,DECK),
            *[beam(u,v,2.4,washer+thickness-EPS,washer+thickness+3) for u,v in zip(path,path[1:])])
    a=cut(a,slot(*anchor,5.5,W['chassis_clearance'],washer-EPS,washer+thickness+3.1),
          cyl(*post,DECK-11,1.7,11.1),
          cyl(*post,DECK-5.6,W['m3_nut_circumradius'],W['m3_nut_depth'],n=6))
    # Side-loadable captive nut, not a screw driven into the PCB or a guessed
    # printed thread. Opening faces front/back for tool access.
    if index<2:
        opening=box(post[0]-3.1,post[0]+3.1,post[1],post[1]+6.1,DECK-5.6,DECK-2.9)
    else:
        opening=box(post[0]-3.1,post[0]+3.1,post[1]-6.1,post[1],DECK-5.6,DECK-2.9)
    return cut(a,opening)

def carrier():
    x0,x1=C['x_min'],C['x_max']; y0,y1=C['rear_y'],C['front_y']; h=P['carrier']['deck']
    a=rect_ring(x0,x1,y0,y1,0,h,5)
    a=union(a,ring(TANK_X,0,34,29,0,h),
            box(-37,37,-42,38,1.8,h),
            beam((-33,-52),(-33,43.5),8,0,h),
            beam((-48,-47),(38,-47),8,0,h))
    for y in (-30,30):a=union(a,beam((-39,y),(74,y),6,0,h))
    for p in POSTS:
        nearest=(-4.5,p[1])
        a=union(a,cyl(*p,0,6,h),beam(p,nearest,8,0,h))
    for p in CUP_BOLTS:
        a=union(a,cyl(*p,0,6,h),beam(p,(-33,p[1]),8,0,h))
    for p in BODY_BOLTS:
        a=union(a,cyl(*p,0,5,h))
    # Integral, open-bottom guard fits AROUND the existing Uno. Print upside
    # down so its flat roof is on the bed and the walls grow upward.
    guard=rect_ring(-37,37,-42,38,-P['carrier']['guard_drop'],2,P['carrier']['guard_wall'])
    guard=cut(guard,box(-33,33,-43,-39,-27,-10),box(-29,29,35.9,39,-27,-9))
    for i,(anchor,post) in enumerate(zip(MOUNTS,POSTS)):
        path=[anchor,(-42.0,anchor[1]),post] if i==2 else [anchor,post]
        guard=cut(guard,box(post[0]-5.4,post[0]+5.4,post[1]-6.4,post[1]+6.4,-27,.1),
                  *[beam(u,v,6.4,-27,.1) for u,v in zip(path,path[1:])])
    a=union(a,guard)
    holes=[cyl(*p,-1,1.7,h+2) for p in POSTS]
    for p in BODY_BOLTS+CUP_BOLTS:
        holes.extend([cyl(*p,-1,1.7,h+2),cyl(*p,0,3.3,2.7,n=6)])
    holes.append(slot(0,-47,66,3.4,-1,5,axis='x'))
    qx0,qx1,qy0,qy1=P['uno_cable_duct']['chute_bounds']
    holes.append(box(qx0-.3,qx1+.3,qy0-.3,qy1+.3,-27,h+1))
    for x in (-19,19):
        a=union(a,cyl(x,69,0,5,h),beam((x,69),(-4.5,59),6,0,h))
        holes.extend([cyl(x,69,-1,1.7,h+2),cyl(x,69,0,3.3,2.7,n=6)])
    return cut(a,*holes).moved((0,0,DECK))

def dry_base():
    x0,x1=C['x_min'],C['x_max'];y0,y1=C['rear_y'],C['front_y'];t=C['wall'];h=C['lower_height']
    a=cut(box(x0,x1,y0,y1,0,h),box(x0+t,x1-t,y0+t,y1-t,C['floor'],h+1))
    # Raised strap eyes keep the straps INSIDE the case, under the lifted bank.
    for x in (0.3,72.7):
        for y in (0,35):
            eye=cut(box(x-2,x+2,y-10,y+10,0,10),box(x-2.1,x+2.1,y-8,y+8,3.5,6.5))
            a=union(a,eye)
    # Wall ledge supports a removable, universal controller tray.
    a=union(a,rect_ring(x0+t-EPS,x1-t+EPS,y0+t-EPS,y1-t+EPS,C['tray_bottom']-C['tray_thickness'],C['tray_bottom'],2.0))
    for x,y in BODY_BOLTS:
        a=union(a,cyl(x,y,0,4.5,3.6))
    # External cover-screw ears leave the entire board width unobstructed.
    for x,y in EAR_CENTRES:
        wallx=x0 if x<x0 else x1
        a=union(a,cyl(x,y,28,4.5,h-28),beam((x,y),(wallx,y),3,28,h),
                beam((x,y),(wallx,y),3,0,28))
    # Fixed camera/nozzle bracket bosses, on the LOWER case only.
    for y in (-2,26):
        for z in (9,25):
            a=union(a,box(x1-0.1,x1+5,y-4,y+4,z-4,z+4))
    tools=[cs_hole(x,y,0,3.6) for x,y in BODY_BOLTS]
    tools.append(box(43.2,64.8,y0+t,-49.2,-1,C['floor']+1))
    for x,y in EAR_CENTRES:
        tools.extend([cyl(x,y,26,1.7,h-26+1),cyl(x,y,h-2.7,3.3,2.8,n=6)])
    for y in (-2,26):
        for z in (9,25):
            tools.extend([hole_x(x1-2,x1+5.1,y,z,1.7),
                          cyl(0,0,0,3.3,2.7,n=6).turned((0,90,0)).moved((x1+2.3,y,z))])
    return cut(a,*tools).moved((0,0,CASE_Z))

def sleeve():
    x0,x1=C['x_min'],C['x_max'];y0,y1=C['rear_y'],C['front_y'];h=C['upper_height']
    a=rect_ring(x0,x1,y0,y1,0,h,C['wall'])
    for x,y in EAR_CENTRES:
        wallx=x0 if x<x0 else x1
        a=union(a,cyl(x,y,0,4.2,h),beam((x,y),(wallx,y),3,0,h))
    return cut(a,*[cyl(x,y,-1,1.7,h+2) for x,y in EAR_CENTRES]).moved((0,0,SLEEVE_Z))

ACCESSORY_CENTRE=(CASE_CX,-45.0)
ACCESSORY_BOLTS=[(CASE_CX+sx*34,-45+sy*17) for sx in (-1,1) for sy in (-1,1)]
def lid():
    x0,x1=C['x_min'],C['x_max'];y0,y1=C['rear_y'],C['front_y'];h=C['lid_thickness']
    a=box(x0,x1,y0,y1,0,h)
    for x,y in EAR_CENTRES:
        wallx=x0 if x<x0 else x1
        a=union(a,cyl(x,y,0,4.5,h),beam((x,y),(wallx,y),4,0,h))
    a=union(a,rect_ring(x0+1.9,x1-1.9,y0+1.9,y1-1.9,-2,EPS,0.8))
    for x,y in ACCESSORY_BOLTS:a=union(a,cyl(x,y,-2,3.5,2.1))
    tools=[cyl(x,y,-3,1.7,h+4) for x,y in EAR_CENTRES+ACCESSORY_BOLTS]
    for x in (14,36.5,59):
        for y in (8,16,24):tools.append(slot(x,y,18,2.4,-1,h+1,axis='x'))
    return cut(a,*tools).moved((0,0,LID_Z))

def controller_tray():
    clear=C['wall']+C['fit_clearance']; x0,x1=C['x_min']+clear,C['x_max']-clear
    y0,y1=C['rear_y']+clear,C['front_y']-clear;h=C['tray_thickness']
    a=box(x0,x1,y0,y1,0,h)
    tools=[]
    for x in np.arange(0.4,74.5,7):
        for ya,yb in [(-62,-38),(-32,2),(8,36),(44,52)]:
            tools.append(slot(float(x),(ya+yb)/2,yb-ya,3.4,-1,h+1))
    tools.append(box(43,66,-66,-50,-1,h+1))
    for x0w,x1w,ya,yb in [(4,68,13,35),(12,62,-23,-12)]:
        tools.append(box(x0w,x1w,ya,yb,-1,h+1))
    return cut(a,*tools).moved((0,0,TRAY_Z))

def pcb_clip():
    # Local y=0 is a PCB edge. Foot lies under the PCB, outer wall/lip beyond it.
    b=P['boards'];t=b['pcb_thickness_assumption'];ledge=b['clip_ledge']
    a=union(box(-4,4,-11,2,0,2.4),box(-4,4,-2,2,0,ledge+2.0+1.2),
            box(-4,4,-4,0,2.3,ledge),box(-4,4,-2,2,ledge+2.0,ledge+3.2))
    a=cut(a,box(-4.1,4.1,-4,0,ledge,ledge+2.0),slot(0,-5.5,8,3.4,-1,2.5))
    return a

def accessory_tray():
    cx,cy=ACCESSORY_CENTRE;z=0
    a=cut(box(cx-30,cx+30,cy-22,cy+22,0,12),box(cx-28.4,cx+28.4,cy-20.4,cy+20.4,1.6,13))
    for x,y in ACCESSORY_BOLTS:
        wx=cx-30 if x<cx else cx+30
        a=union(a,cyl(x,y,0,4,12),beam((x,y),(wx,y),6,0,12))
    for x,y in ACCESSORY_BOLTS:
        a=cut(a,cyl(x,y,1,1.7,12),cyl(x,y,9.3,3.3,2.8,n=6))
    for x in (cx-24,cx+24):
        for y in (cy-14,cy+14):a=cut(a,slot(x,y,8,3.0,-1,2,axis='y'))
    return a.moved((0,0,LID_Z-14))

def bank_pad():return box(-5,5,-4,4,0,P['bank']['printed_pad_height'])

def bottle_cup():
    b=P['bottle'];cx=b['center_x'];ro=b['cup_outside_diameter']/2;ri=b['cup_inside_diameter']/2;h=b['cup_height']
    a=cut(cyl(cx,0,0,ro,h),cyl(cx,0,b['floor'],ri,h+1))
    for sx in (-1,1):
        x=cx+sx*31.5
        a=union(a,box(x-1.2,x+1.2,-6,6,0,b['spine_height']))
        for z in b['band_heights']:
            a=cut(a,box(x-1.4,x+1.4,-1.6,1.6,z-8,z+8))
    for x,y in CUP_BOLTS:
        a=union(a,cyl(x,y,0,5,3.0),beam((x,y),(cx,math.copysign(ro+2,y)),7,0,3))
    for x,y in CUP_BOLTS:a=cut(a,cs_hole(x,y,0,3.0))
    # Drain only in the holder, not the bottle; physical drainage path to check.
    a=cut(a,cyl(cx,0,-1,2,b['floor']+2))
    return a.moved((0,0,TOP))

def bottle_cap():
    b=P['bottle'];ri=31;ro=32.6
    a=cut(cyl(0,0,0,ro,8),cyl(0,0,-1,ri,7.4))
    # A vent and two small pilot holes; actual hose/probe holes are not guessed.
    a=cut(a,cyl(0,0,5,1.0,5),cyl(-9,0,5,1.0,5),cyl(9,0,5,1.0,5))
    return a.moved((TANK_X,0,TOP+b['floor']+b['height']-6.4))

def cable_duct():
    d=P['uno_cable_duct'];cx=d['center_x'];w=d['wall'];half=d['pod_clear_width']/2+w
    x0,x1=cx-half,cx+half;y0,y1=d['pod_back_y'],d['pod_front_y'];z0=d['bottom_z'];top=z0+w+d['pod_clear_height']
    rx0,rx1=cx+6,d['raceway_end_x'];ry0,ry1=d['raceway_rear_y'],d['raceway_front_y']
    qx0,qx1,qy0,qy1=d['chute_bounds']
    a=union(box(x0,x1,y0,y1,z0,top),box(rx0,rx1,ry0,ry1,z0,top),box(qx0,qx1,qy0,qy1,z0,TOP))
    tools=[box(x0+w,x1-w,y0+w,y1+1,z0+w,TOP+1),
           box(rx0,rx1-w,ry0+w,ry1-w,z0+w,TOP+1),
           box(qx0+w,qx1-w,qy0+w,qy1-w,z0+w,TOP+1)]
    a=cut(a,*tools)
    # A raised cable crossing leaves a rear tool-access tunnel to the ORIGINAL
    # switch. It is an assumed location, to try on the reference-print stage.
    access=P['rear_switch_access'];ax=access['center_x'];aw=access['width']/2
    a=union(a,box(ax-aw,ax+aw,ry0,ry1,access['height'],access['height']+w))
    a=cut(a,box(ax-aw,ax+aw,ry0-1,ry1+1,z0-1,access['height']))
    # Four external cover pilots are away from chassis feet and the rear switch.
    centres=[(x0-3,-90),(x1+3,-90),(25,ry0-3),(rx1+3,-96)]
    for x,y in centres:
        if y<-100:near=(x,ry0)
        elif x<x0:near=(x0,y)
        elif x>x1 and y==-90:near=(x1,y)
        else:near=(rx1,y)
        a=union(a,cyl(x,y,z0,3.5,top-z0),beam((x,y),near,3,z0,top))
    for x,y in centres:a=cut(a,cyl(x,y,top-6,W['m2_cover_pilot']/2,7))
    return a

def duct_cover():
    d=P['uno_cable_duct'];cx=d['center_x'];w=d['wall'];half=d['pod_clear_width']/2+w
    x0,x1=cx-half,cx+half;y0,y1=d['pod_back_y'],d['pod_front_y'];z=d['bottom_z']+w+d['pod_clear_height']
    rx0,rx1=cx+6,d['raceway_end_x'];ry0,ry1=d['raceway_rear_y'],d['raceway_front_y'];t=1.6
    a=union(box(x0,x1,y0,y1,z,z+t),box(rx0,rx1,ry0,ry1,z,z+t))
    qx0,qx1,qy0,qy1=d['chute_bounds']
    a=cut(a,box(qx0-.3,qx1+.3,qy0-.3,qy1+.3,z-1,z+t+1))
    centres=[(x0-3,-90),(x1+3,-90),(25,ry0-3),(rx1+3,-96)]
    for x,y in centres:
        if y<-100:near=(x,ry0)
        elif x<x0:near=(x0,y)
        elif x>x1 and y==-90:near=(x1,y)
        else:near=(rx1,y)
        a=union(a,cyl(x,y,z,3.5,t),beam((x,y),near,3,z,z+t))
    tools=[cyl(x,y,z-1,1.1,t+2) for x,y in centres]
    for x in (cx-12,cx+12):
        a=union(a,cyl(x,-47,z,4,DECK-z))
        tools.extend([cyl(x,-47,z-1,1.7,DECK-z+2),cyl(x,-47,z,3.3,2.7,n=6)])
    return cut(a,*tools)

def camera_plate():
    a=box(-21,21,-39,39,0,2.0)
    mounts=[(u,v) for u in (-14,14) for v in (-31,-15)]
    for u,v in mounts:a=union(a,cyl(u,v,-1.5,3.5,1.6))
    tools=[cyl(u,v,-2,1.7,6) for u,v in mounts]
    tools.extend([cyl(0,18,-1,7,5),slot(0,-18,16,10,-1,4)])
    for u in (-13,13):tools.append(slot(u,18,20,3,-1,4))
    for u in (-10,10):tools.append(slot(u,-18,14,3,-1,4))
    return cut(a,*tools).turned((90,0,90)).moved((84,12,CASE_Z+40))

def front_sensor_bracket():
    # Universal strap window; not a claimed HC-SR04 hole-pattern match.
    y=75.0;z=TOP-12
    a=cut(box(-26,26,y,y+3,z-15,z+15),box(-22,22,y-1,y+4,z-11,z+11))
    for x in (-19,19):
        a=union(a,box(x-4,x+4,65,y+2,TOP,TOP+3))
        a=cut(a,cyl(x,69,TOP-1,1.7,5))
    for x in (-24,24):a=cut(a,box(x-1,x+1,y-1,y+4,z-7,z+7))
    return a

def templates():
    for name,spacing in [('00_fit_front_55mm',55),('00_fit_rear_50mm',50)]:
        a=box(-spacing/2-6,spacing/2+6,-4.5,4.5,0,1.6)
        a=cut(a,*[slot(x,0,5.5,2.6,-1,3,axis='x') for x in (-spacing/2,spacing/2)])
        add(name,a,role='FIT TEMPLATE ONLY - do not use as a load-bearing adapter')
    a=beam((-1.25,-31.5),(1.25,31.5),9,0,1.6)
    a=cut(a,slot(-1.25,-31.5,5.5,2.6,-1,3,axis='x'),slot(1.25,31.5,5.5,2.6,-1,3,axis='x'))
    add('00_fit_right_row_63mm',a,role='FIT TEMPLATE ONLY - 63 mm row pitch and 2.5 mm lateral offset')

def build():
    templates()
    for i,name in enumerate(['front_left','front_right','rear_left','rear_right']):
        add('01_mount_'+name,foot(i),color=(98,114,122))
    add('02_chassis_isolating_washer',ring(0,0,3,1.3,0,W['isolation_washer']),qty=4,role='Prototype insulating spacer; compare with original hardware stack')
    add('03_carrier_and_uno_wire_guard',carrier(),print_rotation=(180,0,0))
    add('04_lower_power_case',dry_base())
    add('05_controller_tray',controller_tray(),color=(158,171,177))
    add('06_upper_wall_sleeve',sleeve())
    add('07_removable_lid',lid(),print_rotation=(180,0,0))
    add('08_bottle_cradle',bottle_cup(),color=(95,130,135))
    add('09_bottle_splash_cap',bottle_cap(),print_rotation=(180,0,0),color=(148,170,173),role='Prototype splash cap; actual bottle rim/vent/hose fit unverified')
    add('10_rear_cable_duct',cable_duct(),color=(103,122,130))
    add('11_rear_duct_cover',duct_cover(),color=(127,145,152))
    add('12_fixed_camera_nozzle_plate',camera_plate(),print_rotation=(0,90,0),role='Universal fixed bracket; actual camera/nozzle mounts unmeasured')
    add('13_front_sensor_bracket',front_sensor_bracket(),print_rotation=(90,0,0),role='Universal strap bracket; actual sensor fit unverified')
    add('14_pcb_edge_clip',pcb_clip(),qty=8,color=(72,147,150),role='Movable edge clip, assumed 1.6 mm PCB; confirm component-free edge contact')
    add('15_accessory_breadboard_tray',accessory_tray(),color=(128,150,155),role='Accessory allowance only; actual breadboard unknown')
    add('16_power_bank_support_pad',bank_pad(),qty=4,color=(105,134,139),role='Use with 1 mm soft pad to achieve 5 mm lift')

def placed_copies():
    copies=[]
    for part in PARTS:
        name=part['name']
        if name.startswith('00_'):continue
        if name=='14_pcb_edge_clip':
            for bounds,ys in [(P['boards']['msp_bounds'],[10,48]),(P['boards']['esp_bounds'],[-25,-10])]:
                left,right,_,_=bounds
                for x,angle in [(left,90),(right,-90)]:
                    for y in ys:
                        q=part.copy();q['s']=part['s'].turned((0,0,angle)).moved((x,y,TRAY_Z+C['tray_thickness']));copies.append(q)
        elif name=='16_power_bank_support_pad':
            for x in (16,57):
                for y in (-9,51):
                    q=part.copy();q['s']=part['s'].moved((x,y,CASE_Z+C['floor']));copies.append(q)
        elif name=='02_chassis_isolating_washer':
            for x,y in MOUNTS:
                q=part.copy();q['s']=part['s'].moved((x,y,0));copies.append(q)
        else:copies.append(part)
    return copies

def references():
    bank=P['bank'];bz=CASE_Z+C['floor']+bank['lift'];bb=bank['height']
    refs=[]
    def ref(name,s,color):refs.append(dict(name=name,s=s,color=color,reference=True))
    ref('Existing Zumo body - reference',box(-33,33,-43,43,-23,0),(47,58,62))
    for x0,x1 in [(-49,-34),(34,49)]:
        # Capsule track outline is illustrative, not a manufacturer 3D model.
        track=union(box(x0,x1,-29,29,-25,-1),
                    cyl(0,0,0,12,x1-x0).turned((0,90,0)).moved((x0,-29,-13)),
                    cyl(0,0,0,12,x1-x0).turned((0,90,0)).moved((x0,29,-13)))
        ref('Original track - reference',track,(30,36,39))
    ref('Original blade - illustrative',box(-34,34,50,51.2,-25,5),(155,164,169))
    ref('Mounted Uno PCB - keep-out',box(-26.7,26.7,-34.3,34.3,UNO['solder_top_from_mount_plane']-1.6,UNO['solder_top_from_mount_plane']),(216,220,211))
    ux,uy,uz=UNO['usb_b_center_x'],UNO['usb_b_mouth_y'],UNO['usb_b_center_z']
    ref('Existing USB-B socket - reference',box(ux-6,ux+6,uy,uy+12,uz-6,uz+4),(174,181,185))
    ref('Original rear switch - illustrative',box(10,23,-42,-35,1,8),(44,51,54))
    ref('AUKEY PB-Y91 - reference',box(bank['center_x']-bank['width']/2,bank['center_x']+bank['width']/2,
        bank['center_y']-bank['length']/2,bank['center_y']+bank['length']/2,bz,bz+bb),(110,124,135))
    pcb_z=TRAY_Z+C['tray_thickness']+P['boards']['clip_ledge']
    for name,bounds,color in [('MSP430 reference',P['boards']['msp_bounds'],(166,68,63)),('FireBeetle reference',P['boards']['esp_bounds'],(52,70,73))]:
        x0,x1,y0,y1=bounds;ref(name,box(x0,x1,y0,y1,pcb_z,pcb_z+1.6),color)
    b=P['bottle'];bottom=TOP+b['floor'];waterh=b['water_ml']*1000/(math.pi*(b['diameter']/2)**2)
    ref('Bottle outline - illustrative',ring(TANK_X,0,30,29.5,bottom,bottom+b['height']),(198,221,224))
    ref('100 mL water - idealized reference',cyl(TANK_X,0,bottom,29.4,waterh),(84,162,181))
    # Visible bands illustrate purchased 15 mm textile straps, NOT printable parts.
    for z in b['band_heights']:
        ref('Bottle strap - not printed',ring(TANK_X,0,34,33.1,TOP+z-7.5,TOP+z+7.5),(27,139,145))
    return refs

def verify_and_export():
    records=[];scad=[]
    for part in PARTS:
        s=part['s'];m=mesh_of(s)
        if s.m.is_empty():raise RuntimeError('Empty solid: '+part['name'])
        if not m.is_watertight or not m.is_winding_consistent or not m.is_volume:
            raise RuntimeError('Invalid solid: '+part['name'])
        count=len(m.split(only_watertight=False))
        if count!=1:raise RuntimeError(f'Disconnected part: {part["name"]}, {count} shells')
        print_s=s.turned(part['print_rotation']);pm=mesh_of(print_s)
        shift=-pm.bounds[0];pm.apply_translation(shift)
        path=OUT/(part['name']+'.stl');pm.export(path)
        # Re-open actual exported STL: ensure serialization remains a valid solid.
        reopened=trimesh.load_mesh(path,process=True)
        if not reopened.is_watertight or not reopened.is_volume:raise RuntimeError('STL roundtrip failed '+part['name'])
        rec=dict(name=part['name'],quantity=part['qty'],size_mm=np.round(pm.extents,4).tolist(),
                 assembly_bounds_mm=np.round(m.bounds,4).tolist(),triangles=len(m.faces),
                 closed_manifold=True,connected_shells=count,volume_mm3=round(float(m.volume),3),
                 full_solid_mass_g=round(float(m.volume)*P['material']['solid_density_g_cm3']/1000,2),
                 print_rotation=part['print_rotation'],print_translation=np.round(shift,5).tolist(),role=part['role'],
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        records.append(rec)
        scad.append(f'module part_{part["name"]}(){{{s.scad}}}\n')
    # Actual default CSG assembly intersections. Templates/proxies are excluded.
    assembly=placed_copies();collisions=[]
    meshes=[mesh_of(p['s']) for p in assembly]
    for i,a in enumerate(assembly):
        for j in range(i+1,len(assembly)):
            if np.any(meshes[i].bounds[1] <= meshes[j].bounds[0]+1e-5) or np.any(meshes[j].bounds[1] <= meshes[i].bounds[0]+1e-5):continue
            vol=float(intersect(a['s'],assembly[j]['s']).volume())
            if vol>0.15:collisions.append(dict(a=a['name'],b=assembly[j]['name'],intersection_mm3=round(vol,4)))
    # A reference Uno is a keep-out, not a printable part or a board remount.
    keepout=box(-26.7,26.7,-34.3,34.3,UNO['solder_top_from_mount_plane']-1.6,UNO['solder_top_from_mount_plane'])
    keepout_hits=[]
    for p in assembly:
        vol=float(intersect(p['s'],keepout).volume())
        if vol>.1:keepout_hits.append(dict(part=p['name'],volume_mm3=round(vol,4)))
    component_hits=[]
    critical_refs=[r for r in references() if r['name'] in [
        'AUKEY PB-Y91 - reference','MSP430 reference','FireBeetle reference',
        'Existing USB-B socket - reference','Original rear switch - illustrative',
        'Bottle outline - illustrative','Original track - reference','Original blade - illustrative']]
    for ref in critical_refs:
        for p in assembly:
            vol=float(intersect(p['s'],ref['s']).volume())
            if vol>.15:component_hits.append(dict(component=ref['name'],part=p['name'],volume_mm3=round(vol,4)))
    bay=P['usb_bank_bay'];bank=P['bank'];port_y=bank['center_y']-bank['length']/2
    envelopes=[('Bank USB plug/bend allowance',box(bank['center_x']-bay['clear_width']/2,bank['center_x']+bay['clear_width']/2,
                 port_y-bay['clear_depth'],port_y,CASE_Z+bay['floor_from_case_bottom'],CASE_Z+bay['floor_from_case_bottom']+bay['clear_height'])),
              ('MSP header-height allowance',box(*P['boards']['msp_bounds'][:2],*P['boards']['msp_bounds'][2:],
                 TRAY_Z+C['tray_thickness']+P['boards']['clip_ledge']+3.2,
                 TRAY_Z+C['tray_thickness']+P['boards']['clip_ledge']+1.6+P['boards']['header_headroom_assumption'])),
              ('ESP header-height allowance',box(*P['boards']['esp_bounds'][:2],*P['boards']['esp_bounds'][2:],
                 TRAY_Z+C['tray_thickness']+P['boards']['clip_ledge']+3.2,
                 TRAY_Z+C['tray_thickness']+P['boards']['clip_ledge']+1.6+P['boards']['header_headroom_assumption']))]
    envelope_hits=[]
    for name,shape in envelopes:
        for p in assembly:
            vol=float(intersect(p['s'],shape).volume())
            if vol>.15:envelope_hits.append(dict(envelope=name,part=p['name'],volume_mm3=round(vol,4)))
    # Measured geometry, not the earlier 155 x 135 planning footprint.
    all_bounds=np.array([m.bounds for m in meshes])
    assembly_bounds=np.array([all_bounds[:,0].min(0),all_bounds[:,1].max(0)])
    report=dict(status='DIGITAL PROTOTYPE; no physical fit, load, print or electrical validation',units='mm',
        default_uno_stays_installed=True,reference_mounts_mm=MOUNTS,post_centres_mm=POSTS,
        deck_underside_from_mount_plane_mm=DECK,parts=records,
        full_solid_plastic_mass_g=round(sum(r['quantity']*r['full_solid_mass_g'] for r in records if not r['name'].startswith('00_')),2),
        default_assembly_intersections=collisions,mounted_uno_pcb_keepout_hits=keepout_hits,
        reference_component_intersections=component_hits,reserved_envelope_intersections=envelope_hits,
        printed_assembly_bounds_mm=assembly_bounds.round(3).tolist(),printed_assembly_size_mm=np.diff(assembly_bounds,axis=0)[0].round(3).tolist(),
        assumptions=P['mounted_uno'],physical_validation=False,
        package_versions={n:importlib.metadata.version(n) for n in ['numpy','trimesh','manifold3d','pillow']})
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2))
    mode='// Generated CSG source. Units mm. Edit parameters.json and run build_enclosure.py to regenerate.\n'
    mode+='// Fitted Uno is not exported as a print part. This is a fit-check prototype.\n'
    mode+='part_name="03_carrier_and_uno_wire_guard";\nmode="assembly"; // assembly or print\n'
    mode+=''.join(scad)
    mode+='if(mode=="assembly"){\n'
    for p in assembly:mode+=p['s'].scad+'\n'
    mode+='} else {\n'
    for r in records:
        mode+=f'if(part_name=="{r["name"]}")translate({fmt(r["print_translation"])})rotate({fmt(r["print_rotation"])})part_{r["name"]}();\n'
    mode+='}\n'
    (ROOT/'zumo_enclosure.scad').write_text(mode)
    scene=trimesh.Scene()
    for i,p in enumerate(assembly+references()):
        mesh=mesh_of(p['s']);mesh.visual.vertex_colors=list(p['color'])+[255]
        scene.add_geometry(mesh,node_name=f'{p["name"]}_{i}')
    scene.apply_scale(0.001)  # glTF uses metres; CAD/STL/source remain mm.
    scene.metadata['units']='m'
    (ROOT/'assembly-reference.glb').write_bytes(scene.export(file_type='glb'))
    return report,assembly

def rasterize(im,faces,mn,scale,ox,oy,clip):
    # Per-pixel depth avoids painter-order artefacts on long intersecting faces.
    pixels=np.asarray(im).copy();depth=np.full(pixels.shape[:2],-np.inf,np.float32)
    for zs,tri,col in faces:
        xy=np.column_stack([ox+(tri[:,0]-mn[0])*scale,oy-(tri[:,1]-mn[1])*scale])
        x0=max(clip[0],int(np.floor(xy[:,0].min())));x1=min(clip[2],int(np.ceil(xy[:,0].max())))
        y0=max(clip[1],int(np.floor(xy[:,1].min())));y1=min(clip[3],int(np.ceil(xy[:,1].max())))
        if x1<x0 or y1<y0:continue
        (ax,ay),(bx,by),(cx,cy)=xy
        den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(den)<1e-9:continue
        yy,xx=np.mgrid[y0:y1+1,x0:x1+1];xx=xx+.5;yy=yy+.5
        wa=((by-cy)*(xx-cx)+(cx-bx)*(yy-cy))/den
        wb=((cy-ay)*(xx-cx)+(ax-cx)*(yy-cy))/den;wc=1-wa-wb
        z=wa*zs[0]+wb*zs[1]+wc*zs[2]
        region=depth[y0:y1+1,x0:x1+1]
        mask=(wa>=-1e-7)&(wb>=-1e-7)&(wc>=-1e-7)&(z>region)
        region[mask]=z[mask];pixels[y0:y1+1,x0:x1+1][mask]=col
    im.paste(Image.fromarray(pixels))

def render_cad(assembly):
    # Orthographic rendering of ACTUAL generated meshes, not an AI mockup.
    font_path=Path('C:/Windows/Fonts/segoeui.ttf'); bold_path=Path('C:/Windows/Fonts/segoeuib.ttf')
    font=lambda size,bold=False:ImageFont.truetype(str(bold_path if bold else font_path),size)
    im=Image.new('RGB',(2000,1300),(245,247,248));dr=ImageDraw.Draw(im)
    dr.text((60,35),'ZUMO ENCLOSURE | PRINTABLE PROTOTYPE',font=font(38,True),fill=(30,45,54))
    dr.text((60,88),'Actual CAD meshes - the Uno remains mounted on the Zumo',font=font(24),fill=(76,91,101))
    panels=[(30,155,1000,1090,'ASSEMBLED',False),(1010,155,1970,1090,'EXPLODED PARTS',True)]
    refs=references()
    for l,t,r,b,title,exploded in panels:
        dr.text((l+25,t+10),title,font=font(25,True),fill=(45,66,77))
        entries=[]
        for p in assembly:
            q=p.copy()
            if exploded:
                n=q['name'];delta=(0,0,0)
                if n in ['06_upper_wall_sleeve','07_removable_lid','15_accessory_breadboard_tray']:
                    delta=(0,0,42 if n=='06_upper_wall_sleeve' else 70)
                elif n in ['05_controller_tray','14_pcb_edge_clip']:delta=(0,0,23)
                elif n=='11_rear_duct_cover':delta=(0,-12,18)
                elif n=='09_bottle_splash_cap':delta=(0,0,20)
                q['s']=q['s'].moved(delta)
            entries.append(q)
        entries+=refs
        eye=np.array([1.0,1.3,0.95]);eye/=np.linalg.norm(eye)
        right=np.cross(np.array([0.,0.,1.]),eye);right/=np.linalg.norm(right)
        up=np.cross(eye,right)
        allpts=[];faces=[]
        for p in entries:
            mesh=mesh_of(p['s']);v=mesh.vertices
            proj=np.column_stack([v@right,v@up]);allpts.append(proj)
            tris=v[mesh.faces];norm=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]);nn=np.linalg.norm(norm,axis=1);norm/=np.maximum(nn[:,None],1e-12)
            for inds,normv,tri in zip(mesh.faces,norm,tris):
                if np.dot(normv,eye)<-.001:continue
                shade=.56+.44*max(0,float(np.dot(normv,np.array([-.35,.25,.90]))))
                col=tuple(min(255,int(c*shade)) for c in p['color'])
                faces.append((tri@eye,proj[inds],col))
        pts=np.vstack(allpts);mn=pts.min(0);mx=pts.max(0)
        scale=min((r-l-55)/(mx[0]-mn[0]),(b-t-80)/(mx[1]-mn[1]))
        ox=l+25+(r-l-50-(mx[0]-mn[0])*scale)/2;oy=b-25
        rasterize(im,faces,mn,scale,ox,oy,(l,t+50,r,b))
        dr=ImageDraw.Draw(im)
    dr.line((60,1140,1940,1140),fill=(198,207,210),width=2)
    dr.text((60,1160),'Print the three thin fit templates and mounting feet first.',font=font(27,True),fill=(38,74,83))
    dr.text((60,1210),'Defaults include unmeasured wire/USB/board heights. No physical fit or water-load rating is claimed.',font=font(23),fill=(81,96,104))
    im.save(ROOT/'cad-preview.png')

def manifest(report):
    rows=['# Print manifest - actual generated prototype','',
          'All sizes are millimetres. STL files are individually rotated onto their intended flat print face.',
          'Print templates/feet first. Reference electronics/bottle in the GLB and preview are NOT print parts.','',
          '| Part | Qty | Print bounding box (mm) | Full-solid mass (g each) |','| --- | ---: | --- | ---: |']
    for r in report['parts']:
        rows.append(f'| {r["name"]}.stl | {r["quantity"]} | '+ ' x '.join(f'{v:.1f}' for v in r['size_mm'])+f' | {r["full_solid_mass_g"]:.2f} |')
    rows+=['',f'Full-solid plastic estimate, excluding templates: **{report["full_solid_plastic_mass_g"]:.1f} g** at the stated density.',
           'This is a geometry estimate; weigh the sliced/printed parts. No bolts, textile bands, foam or electronics are included.',
           '',f'Default printed-part overlap findings: {len(report["default_assembly_intersections"])}. Mounted Uno PCB keep-out findings: {len(report["mounted_uno_pcb_keepout_hits"])}.',
           f'Reference component overlap findings: {len(report["reference_component_intersections"])}. Reserved envelope overlap findings: {len(report["reserved_envelope_intersections"])}.',
           'Printed assembly envelope, excluding hardware/reference components: '+ ' x '.join(str(v) for v in report['printed_assembly_size_mm'])+' mm.',
           'Read validation.json for exact assumptions and check results.']
    (ROOT/'PRINT_MANIFEST.md').write_text('\n'.join(rows)+'\n')

def package():
    target=ROOT/'zumo-enclosure-printable-prototype-v1.zip'
    files=[ROOT/'parameters.json',ROOT/'build_enclosure.py',ROOT/'requirements.txt',ROOT/'zumo_enclosure.scad',
           ROOT/'validation.json',ROOT/'PRINT_MANIFEST.md',ROOT/'cad-preview.png',ROOT/'assembly-reference.glb']
    if (ROOT/'README.md').exists():files.append(ROOT/'README.md')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files+list(OUT.glob('*.stl')):z.write(p,p.relative_to(ROOT))
    return target

if __name__=='__main__':
    build();report,assembly=verify_and_export()
    findings=sum(len(report[k]) for k in ['default_assembly_intersections','mounted_uno_pcb_keepout_hits','reference_component_intersections','reserved_envelope_intersections'])
    if findings:raise RuntimeError(f'{findings} assembly/reference collisions: inspect validation.json before printing')
    render_cad(assembly);manifest(report);archive=package()
    print(json.dumps({'stl_files':len(report['parts']),'closed_solids':True,'plastic_mass_full_solid_g':report['full_solid_plastic_mass_g'],
                      'printed_part_intersections':report['default_assembly_intersections'],'uno_keepout_hits':report['mounted_uno_pcb_keepout_hits'],
                      'zip':str(archive)},indent=2))
