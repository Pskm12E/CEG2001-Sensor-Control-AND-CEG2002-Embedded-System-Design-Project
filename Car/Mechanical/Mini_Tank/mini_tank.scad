// Provisional two-part tank. Units: mm. Part: tank, holder, assembly.
// Exact nominal sizes match supplied STL. No sensor clip or splash lid included.
part = "assembly";
tank_width = 25;
tank_depth = 15;
tank_height = 55;
tank_wall = 2;
tank_floor = 3;
holder_wall = 2;
holder_floor = 3;
holder_height = 75;
holder_lip_height = 28;
clearance_per_side = 0.5;
drain_size = 4;
water_depth = 35;
example_sensor_height = 62;
example_sensor_width = 20;
example_pcb_thickness = 1.6;
example_sensor_envelope_depth = 8;
sensor_floor_clearance = 2;
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
