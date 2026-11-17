"""Generate exact box-CSG STL solids, editable OpenSCAD and dimensioned previews.

STL and validation use the Python standard library. Preview drawing needs Pillow.
This is a dimensional prototype, not physical leak/load/fit validation.
"""
from pathlib import Path
from collections import Counter, defaultdict
import itertools
import json
import math
import struct

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / 'dimensions.json').read_text())
W, D, H = (P['tank_' + k] for k in ('width', 'depth', 'height'))
T, F = P['tank_wall'], P['tank_floor']
C, S, B = P['clearance_per_side'], P['holder_wall'], P['holder_floor']
HW, HD, HH = W + 2 * (C + S), D + 2 * (C + S), P['holder_height']
L, R = P['holder_lip_height'], P['drain_size']
OFFSET = (0, S + C, B)

def box(x0, x1, y0, y1, z0, z1):
    return ((x0, x1), (y0, y1), (z0, z1))

TANK_ADD = [box(-W/2, W/2, 0, D, 0, H)]
TANK_SUB = [box(-W/2+T, W/2-T, T, D-T, F, H+1)]
HOLDER_ADD = [box(-HW/2, HW/2, 0, HD, 0, B),
              box(-HW/2, HW/2, 0, S, 0, HH),
              box(-HW/2, -HW/2+S, S, HD, B, L),
              box(HW/2-S, HW/2, S, HD, B, L),
              box(-HW/2, HW/2, HD-S, HD, B, L)]
HOLDER_SUB = [box(-R/2, R/2, HD/2-R/2, HD/2+R/2, -1, B+0.01)]

def inside(pt, b):
    return all(lo < p < hi for p, (lo, hi) in zip(pt, b))

def solid_mesh(add, subtract):
    # Global breakpoints ensure matching vertices on all adjoining faces.
    axes = [sorted(set(v for b in add+subtract for v in b[a])) for a in range(3)]
    cells = set()
    for index in itertools.product(*(range(len(a)-1) for a in axes)):
        pt = tuple((axes[a][i]+axes[a][i+1])/2 for a, i in enumerate(index))
        if any(inside(pt, b) for b in add) and not any(inside(pt, b) for b in subtract):
            cells.add(index)
    vertices, lookup, faces, quads = [], {}, [], []
    def vertex(pt):
        if pt not in lookup:
            lookup[pt] = len(vertices)
            vertices.append(pt)
        return lookup[pt]
    for i, j, k in sorted(cells):
        x0, x1 = axes[0][i:i+2]
        y0, y1 = axes[1][j:j+2]
        z0, z1 = axes[2][k:k+2]
        sides = [((-1,0,0), [(x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0)]),
                 ((1,0,0), [(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)]),
                 ((0,-1,0), [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)]),
                 ((0,1,0), [(x0,y1,z0),(x0,y1,z1),(x1,y1,z1),(x1,y1,z0)]),
                 ((0,0,-1), [(x0,y0,z0),(x0,y1,z0),(x1,y1,z0),(x1,y0,z0)]),
                 ((0,0,1), [(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)])]
        for delta, q in sides:
            if (i+delta[0], j+delta[1], k+delta[2]) not in cells:
                idx = [vertex(p) for p in q]
                faces.extend([(idx[0],idx[1],idx[2]),(idx[0],idx[2],idx[3])])
                quads.append(q)
    return {'vertices':vertices,'faces':faces,'quads':quads}

def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a,b): return sum(x*y for x,y in zip(a,b))

def validate(mesh, expected_size):
    v, fs = mesh['vertices'], mesh['faces']
    edge_faces = defaultdict(list)
    directed = Counter()
    signed_volume = 0
    for i, (a,b,c) in enumerate(fs):
        assert dot(cross(sub(v[b],v[a]),sub(v[c],v[a])),cross(sub(v[b],v[a]),sub(v[c],v[a]))) > 0
        signed_volume += dot(v[a], cross(v[b],v[c]))/6
        for p,q in ((a,b),(b,c),(c,a)):
            edge_faces[tuple(sorted((p,q)))].append(i)
            directed[p,q] += 1
    assert all(len(ids)==2 for ids in edge_faces.values()), 'Non-manifold edges'
    assert all(directed[a,b]==directed[b,a] for a,b in directed), 'Inconsistent winding'
    seen, stack = set(), [0]
    adjacency = defaultdict(set)
    for ids in edge_faces.values():
        a,b = ids
        adjacency[a].add(b)
        adjacency[b].add(a)
    while stack:
        a = stack.pop()
        if a in seen: continue
        seen.add(a)
        stack.extend(adjacency[a]-seen)
    assert len(seen)==len(fs), 'Disconnected mesh'
    bounds = [[min(p[a] for p in v),max(p[a] for p in v)] for a in range(3)]
    size = [hi-lo for lo,hi in bounds]
    assert all(abs(a-b)<1e-6 for a,b in zip(size,expected_size)), size
    assert signed_volume > 0
    return {'size_mm':size,'triangle_count':len(fs),'closed_manifold':True,
            'consistent_outward_winding':True,'connected_shells':1,
            'solid_volume_mm3':round(signed_volume,6)}

def write_stl(name, mesh):
    with (ROOT/name).open('wb') as f:
        f.write(b'Provisional mini tank; units mm; confirm sensor and mount fit'.ljust(80,b' '))
        f.write(struct.pack('<I',len(mesh['faces'])))
        for ids in mesh['faces']:
            a,b,c = [mesh['vertices'][i] for i in ids]
            n = cross(sub(b,a),sub(c,a))
            length = math.sqrt(dot(n,n))
            f.write(struct.pack('<12fH',*(q/length for q in n),*a,*b,*c,0))

def write_scad():
    values = '\n'.join(f'{key} = {json.dumps(val)};' for key,val in P.items() if isinstance(val,(float,int)))
    source = '''// Provisional two-part tank. Units: mm. Part: tank, holder, assembly.
// Exact nominal sizes match supplied STL. No sensor clip or splash lid included.
part = "assembly";
PARAMETERS
w=tank_width; d=tank_depth; h=tank_height; t=tank_wall; f=tank_floor;
c=clearance_per_side; s=holder_wall; b=holder_floor;
hw=w+2*(c+s); hd=d+2*(c+s); hh=holder_height; lip=holder_lip_height;
module tank(){
  difference(){
    translate([-w/2,0,0]) cube([w,d,h]);
    translate([-w/2+t,t,f]) cube([w-2*t,d-2*t,h-f+1]);
  }
}
module holder(){
  difference(){
    union(){
      translate([-hw/2,0,0]) cube([hw,hd,b]);
      translate([-hw/2,0,0]) cube([hw,s,hh]);
      translate([-hw/2,s,b]) cube([s,hd-s,lip-b]);
      translate([hw/2-s,s,b]) cube([s,hd-s,lip-b]);
      translate([-hw/2,hd-s,b]) cube([hw,s,lip-b]);
    }
    translate([-drain_size/2,hd/2-drain_size/2,-1]) cube([drain_size,drain_size,b+1.01]);
  }
}
if(part=="tank") tank();
else if(part=="holder") holder();
else {
  color([0.25,0.30,0.37]) holder();
  translate([0,s+c,b]) color([0.16,0.63,0.68,0.75]) tank();
}
'''.replace('PARAMETERS',values)
    (ROOT/'mini_tank.scad').write_text(source)

def previews(tank, holder):
    from PIL import Image, ImageDraw, ImageFont
    scale = 2
    im=Image.new('RGB',(1600*scale,1100*scale),'#f6f5f1')
    dr=ImageDraw.Draw(im)
    def font(n,bold=False):
        return ImageFont.truetype('C:/Windows/Fonts/'+('segoeuib.ttf' if bold else 'segoeui.ttf'),n*scale)
    def text(x,y,s,size=20,fill='#25313d',bold=False): dr.text((int(x*scale),int(y*scale)),s,font=font(size,bold),fill=fill)
    def line(points,fill='#53616d',width=1): dr.line([(int(x*scale),int(y*scale)) for x,y in points],fill=fill,width=width*scale)
    def dim(a,b,label,offset=(0,0),labelshift=(0,0)):
        aa=(a[0]+offset[0],a[1]+offset[1]); bb=(b[0]+offset[0],b[1]+offset[1])
        line([a,aa]);line([b,bb]);line([aa,bb])
        dx,dy=bb[0]-aa[0],bb[1]-aa[1]; le=math.hypot(dx,dy); nx,ny=-dy/le*5,dx/le*5
        line([(aa[0]-nx,aa[1]-ny),(aa[0]+nx,aa[1]+ny)])
        line([(bb[0]-nx,bb[1]-ny),(bb[0]+nx,bb[1]+ny)])
        x=(aa[0]+bb[0])/2+labelshift[0];y=(aa[1]+bb[1])/2+labelshift[1]
        bbox=dr.textbbox((0,0),label,font=font(18)); tw=(bbox[2]-bbox[0])/scale
        dr.rectangle(((x-tw/2-5)*scale,(y-3)*scale,(x+tw/2+5)*scale,(y+24)*scale),fill='#f6f5f1')
        text(x-tw/2,y,label,18)
    def render(mesh,cx,cy,k,color,off=(0,0,0),dimmed=False):
        # Orthographic view from positive x/y, above; face normals remove hidden backs.
        yaw=math.radians(30); elev=math.radians(23)
        cam=(math.sin(yaw)*math.cos(elev),math.cos(yaw)*math.cos(elev),math.sin(elev))
        def project(p):
            x,y,z=(p[a]+off[a] for a in range(3))
            return (cx+k*(math.cos(yaw)*x-math.sin(yaw)*y),cy+k*(math.sin(elev)*(math.sin(yaw)*x+math.cos(yaw)*y)-math.cos(elev)*z))
        qs=[]
        for q in mesh['quads']:
            n=cross(sub(q[1],q[0]),sub(q[2],q[0])); nlen=math.sqrt(dot(n,n)); n=tuple(v/nlen for v in n)
            if dot(n,cam)<=0: continue
            depth=sum(dot(tuple(p[a]+off[a] for a in range(3)),cam) for p in q)/4
            lighting=.70+.23*max(0,dot(n,(-.25,.35,.9)))
            rgb=tuple(int(v*lighting) for v in color)
            qs.append((depth,q,rgb))
        for _,q,rgb in sorted(qs,key=lambda a:a[0]):
            poly=[tuple(int(v*scale) for v in project(p)) for p in q]
            dr.polygon(poly,fill=rgb)
        # Flat face shading keeps hidden edges from appearing through the solid.
        return project
    text(64,38,'Mini water tank + glue-on holder',34,bold=True)
    text(64,88,'PROVISIONAL   /   All dimensions in mm   /   Based on an approximate 30 × 75 × 20 mm space',19)
    line([(64,132),(1536,132)],'#c7cdce')
    text(78,160,'01  Removable tank',24,bold=True)
    text(595,160,'02  Glue-on holder',24,bold=True)
    text(1112,160,'03  Sensor clearance',24,bold=True)
    p=render(tank,290,600,6.0,(60,166,175))
    dim(p((-W/2,D,0)),p((W/2,D,0)),f'{W:g}',offset=(0,40),labelshift=(0,-12))
    dim(p((W/2,0,0)),p((W/2,D,0)),f'{D:g}',offset=(45,32),labelshift=(12,-9))
    dim(p((-W/2,0,0)),p((-W/2,0,H)),f'{H:g}',offset=(-65,0),labelshift=(-15,-10))
    q=render(holder,820,650,5.2,(96,110,126))
    dim(q((-HW/2,HD,0)),q((HW/2,HD,0)),f'{HW:g}',offset=(0,38),labelshift=(0,-11))
    dim(q((HW/2,0,0)),q((HW/2,HD,0)),f'{HD:g}',offset=(42,31),labelshift=(8,-10))
    dim(q((-HW/2,0,0)),q((-HW/2,0,HH)),f'{HH:g}',offset=(-61,0),labelshift=(-17,-10))
    # Dimensionally accurate side section. Outer tank walls are drawn as cut material.
    x0,y0,k=1170,650,5.6
    def r(x,z):return(x0+x*k,y0-z*k)
    def rect(a,b,fill,outline=None):dr.rectangle([tuple(int(v*scale) for v in r(*a)),tuple(int(v*scale) for v in r(*b))],fill=fill,outline=outline,width=scale)
    rect((0,H),(D,0),'#3ca6af')
    rect((T,H),(D-T,F),'#f6f5f1')
    rect((T,F+P['water_depth']),(D-T,F),'#bddce7')
    sx=T+1.5;sz=F+P['sensor_floor_clearance'];sh=P['example_sensor_height']
    sd=P['example_sensor_envelope_depth'];sw=P['example_sensor_width'];wd=P['water_depth']
    net_ml=((W-2*T)*(D-2*T)*wd-sw*P['example_pcb_thickness']*max(0,wd-P['sensor_floor_clearance']))/1000
    rect((sx,sz+sh),(sx+P['example_pcb_thickness'],sz),'#b26654')
    rect((sx,sz+sh),(sx+sd,sz+sh-8),'#444e57')
    text(1300,247,'Example sensor',18,bold=True)
    text(1300,275,f'{sh:g} × {sw:g} × {sd:g}',18)
    text(1300,305,'Position only;',17)
    text(1300,329,'clip not included',17)
    line([r(sx+sd,sz+sh-4),(1280,278),(1290,278)])
    text(1300,409,f'{wd:g} mm water',18)
    text(1300,438,f'~{net_ml:.0f} ml with probe',18)
    line([r(D-T,F+wd),(1280,420),(1290,420)])
    dim(r(0,0),r(0,H),f'{H:g}',offset=(-40,0),labelshift=(-14,-10))
    text(1110,700,'Section through tank depth',18)
    line([(64,775),(1536,775)],'#c7cdce')
    iw,id_,ih=W-2*T,D-2*T,H-F
    text(78,802,f'Tank: {W:g} W × {D:g} D × {H:g} H',22,bold=True)
    text(78,843,f'Inside: {iw:g} × {id_:g} × {ih:g}',20)
    text(78,879,f'Walls {T:g}  /  Floor {F:g}',20)
    text(78,915,f'Empty cavity: {iw*id_*ih/1000:.1f} ml to rim',20)
    text(595,802,f'Holder: {HW:g} W × {HD:g} D × {HH:g} H',22,bold=True)
    text(595,843,f'Flat glue face: {HW:g} × {HH:g}',20)
    text(595,879,f'Pocket: {W+2*C:g} × {D+2*C:g}',20)
    text(595,915,f'Sliding gap: {C:g} each side',20)
    text(1112,802,'Before printing',22,bold=True)
    text(1112,843,'Confirm actual sensor dimensions.',19)
    text(1112,879,'Confirm the 20 mm projection limit.',19)
    text(1112,915,'Open top; splash cover not included.',19)
    text(64,1010,'Prototype geometry only. Keep sensor electronics dry. Leak-test away from the robot; verify the glued mount under load.',18)
    im.resize((1600,1100),Image.Resampling.LANCZOS).save(ROOT/'dimensions-and-mockup.png')

def main():
    assert min(W-2*T,D-2*T,H-F)>0
    tank,holder=solid_mesh(TANK_ADD,TANK_SUB),solid_mesh(HOLDER_ADD,HOLDER_SUB)
    results={'tank':validate(tank,[W,D,H]),'holder':validate(holder,[HW,HD,HH])}
    expected_tank=W*D*H-(W-2*T)*(D-2*T)*(H-F)
    assert abs(results['tank']['solid_volume_mm3']-expected_tank)<1e-5
    # Surface solids have 0.5 mm side clearance and contact only at the support floor.
    assert abs((-HW/2+S)-(-W/2-C))<1e-8
    assert abs((HD-S)-(S+C+D+C))<1e-8
    iw,id_,ih=W-2*T,D-2*T,H-F
    displacement=P['example_sensor_width']*P['example_pcb_thickness']*(P['water_depth']-P['sensor_floor_clearance'])/1000
    results['dimensions']={'tank_cavity_mm':[iw,id_,ih],'holder_pocket_mm':[W+2*C,D+2*C],
        'nominal_side_clearance_mm':C,'empty_brim_capacity_ml':iw*id_*ih/1000,
        'illustrated_water_depth_mm':P['water_depth'],
        'illustrated_net_water_ml':round(iw*id_*P['water_depth']/1000-displacement,3),
        'example_sensor_width_clearance_each_mm':(iw-P['example_sensor_width'])/2}
    results['physical_validation']='NOT PERFORMED: actual sensor fit, printing, leaks, splash, adhesive, wheel clearance'
    for name,m in [('tank-provisional.stl',tank),('holder-provisional.stl',holder)]:write_stl(name,m)
    write_scad()
    previews(tank,holder)
    (ROOT/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
