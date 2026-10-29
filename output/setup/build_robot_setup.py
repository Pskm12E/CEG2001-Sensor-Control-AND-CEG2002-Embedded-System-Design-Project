from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4

ROOT = Path(r'D:\Programing\Sensor Joined Prj')
OUT = ROOT / 'output' / 'pdf' / 'plant-care-robot-setup-guide.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
INK = colors.HexColor('#15304A')
TEAL = colors.HexColor('#087E83')
PALE = colors.HexColor('#EDF7F6')
AMBER = colors.HexColor('#FFF2D9')
GREY = colors.HexColor('#526275')
LINE = colors.HexColor('#D3DEE6')
W = A4[0] - 88
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleCustom', fontName='Helvetica-Bold', fontSize=23, leading=27, textColor=INK, spaceAfter=12))
styles.add(ParagraphStyle(name='SubCustom', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=6))
styles.add(ParagraphStyle(name='BodyCustom', fontName='Helvetica', fontSize=10, leading=14, textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name='SmallCustom', fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name='CellCustom', fontName='Helvetica', fontSize=9, leading=12, textColor=INK))
styles.add(ParagraphStyle(name='HeadCustom', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white))
story=[]

def p(text, style='BodyCustom'):
    return Paragraph(text, styles[style])
def add(text): story.append(p(text))
def sub(text): story.append(p(text,'SubCustom'))
def title(n,text):
    if story: story.append(PageBreak())
    story.append(p(f'BUILD STAGE {n}  /  6 OCTOBER 2026','SmallCustom'))
    story.append(p(text,'TitleCustom'))
def table(headers, rows, widths=None):
    data=[[p(h,'HeadCustom') for h in headers]]+[[p(str(c),'CellCustom') for c in row] for row in rows]
    t=Table(data, colWidths=widths or [W/len(headers)]*len(headers), hAlign='LEFT', repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),INK),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
        ('LINEBELOW',(0,0),(-1,0),.5,INK),('LINEBELOW',(0,1),(-1,-1),.4,LINE)]))
    story.extend([t,Spacer(1,8)])
def note(text, amber=False):
    t=Table([[p(text,'SmallCustom')]],colWidths=[W])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),AMBER if amber else PALE),('BOX',(0,0),(-1,-1),.5,LINE),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story.extend([t,Spacer(1,9)])

class Divider(Flowable):
    def __init__(self): Flowable.__init__(self); self.width=W; self.height=124
    def draw(self):
        c=self.canv; c.setStrokeColor(INK); c.setLineWidth(1.5); c.setFont('Helvetica',9); c.setFillColor(INK)
        c.drawString(8,102,'HC-SR04 ECHO'); c.drawString(380,102,'Pico GP5 (pin 7)')
        c.line(20,85,105,85); c.rect(105,77,74,16); c.line(179,85,280,85); c.line(280,85,440,85)
        c.drawCentredString(142,100,'10 kOhm'); c.circle(280,85,2.5,fill=1)
        c.line(280,85,280,63); c.rect(272,28,16,35); c.line(280,28,280,15)
        c.line(265,15,295,15); c.line(270,10,290,10); c.line(275,5,285,5)
        c.drawString(306,46,'15 kOhm'); c.drawString(310,12,'Shared GND')
        c.setFont('Helvetica-Bold',9); c.drawString(8,46,'5 V HIGH becomes approximately 3.0 V.')

class PowerMap(Flowable):
    def __init__(self): Flowable.__init__(self); self.width=W; self.height=169
    def draw(self):
        c=self.canv
        def box(x,y,w,h,lines,fill=PALE):
            c.setFillColor(fill); c.setStrokeColor(LINE); c.roundRect(x,y,w,h,5,fill=1,stroke=1); c.setFillColor(INK)
            c.setFont('Helvetica-Bold',9)
            for i,line in enumerate(lines): c.drawCentredString(x+w/2,y+h-16-i*12,line)
        def line(x1,y1,x2,y2): c.setStrokeColor(TEAL); c.setLineWidth(1.5); c.line(x1,y1,x2,y2)
        box(0,62,107,55,['Protected 2S pack','7.4 V nominal','8.4 V full'])
        box(127,70,86,39,['Fuse + switch'])
        line(107,89,127,89); line(213,89,228,89); line(228,28,228,143)
        for y in [143,88,28]: line(228,y,249,y)
        box(249,123,246,39,['5 V regulator -> USB power','Pico W + small sensor supplies'])
        box(249,68,246,39,['Motor-rated regulator -> H-bridge','Left wheel + right wheel'])
        box(249,8,246,39,['Pump-rated regulator -> switch driver','Water pump'])

title('1','Start with a working bench')
add('A practical wiring and power-up guide for your sensor-based plant-care robot. Start with USB and individual sensors. Add actuators only after their ratings and drivers are identified. Battery wiring comes last.')
note('<b>Known from your photos:</b> Uno R3, DFRobot FireBeetle ESP32 V4.0, Raspberry Pi Pico W, webcam, two IR modules, ultrasonic module, soil probe and interface, pump, tubing and chassis. <b>Unconfirmed:</b> exact sensor variants/pin order, MSP430 model, motor driver, pump-switch model, motor/pump ratings and battery lead functions.',True)
table(['Where','Planned role'],[
('Fixed station','Laptop + webcam; MSP430 LaunchPad + course Booster Board; FireBeetle ESP32 if needed as the USB/UART/Wi-Fi gateway.'),
('Moving robot','Pico W; two IR sensors; ultrasonic sensor; dual wheel driver; pump switch; tank; regulated battery supply.'),
('Uno R3','Temporary sensor tester. It does not have to remain in the finished design.'),
('One test pot','Keep the moisture probe in this pot. Final analog input goes to the fixed MSP430 after its pinout is known.')],[104,W-104])
sub('1. Gather the small parts')
add('Use a multimeter, breadboard, male/female jumper wires, USB-B data cable for the Uno, micro-USB data cables for the Pico/ESP32, black tape and a light floor sample. For the ultrasonic divider, get one 10 kOhm and one 15 kOhm resistor (1% preferred). A ruler and measuring cup are useful for calibration.')
add('For later power wiring: correctly rated dual motor driver, pump driver, regulators, fuse/holder, switch, terminal connectors, insulated stranded wire and the battery manufacturer-matched charger. Their current ratings remain to be selected.')
sub('2. Make the work area readable')
add('Label rails <b>GND</b>, <b>3V3</b> and <b>5V</b>. A breadboard colour stripe does not create a voltage; only the wire feeding it does. Rail segments can be split: check continuity with all power disconnected. Mount the Pico across the centre gap so opposite pins are not shorted together.')
note('<b>Power-off rule:</b> unplug USB and disconnect battery/bench supplies before changing wires. Keep motor and pump current out of breadboard rails and thin signal jumpers. Use a dry tray for water tests and keep water away from the electronics.')

title('2','Power up each board separately')
add('Leave sensors, drivers and inter-board wires disconnected for these first checks. USB power tests do not require a robot battery.')
table(['Item','Action','Pass condition'],[
('Uno R3','Connect its USB-B socket to the laptop. In Arduino IDE select Arduino Uno and its port. Open the supplied uno_sensor_bench sketch with TEST_MODE = 0; upload. Open Serial Monitor at 115200 baud.','Repeated heartbeat=OK messages; built-in LED toggles.'),
('Pico W','Hold BOOTSEL while connecting micro-USB, then release it. The bootloader should appear as RPI-RP2. This identifies the bootloader; it is not the final program.','RPI-RP2 drive appears. A dark LED alone does not indicate a fault.'),
('FireBeetle ESP32 V4.0','Connect micro-USB. Use the DFRobot DFR0478 getting-started instructions for its board package and CH340 driver if needed. Upload a simple serial test and check its port.','The expected serial message appears; no resets when idle.'),
('Webcam','Connect directly to laptop USB. Open Windows Camera, select the USB camera, and check the view of the pot. Close Camera before another app uses it.','Clear, stable image of the intended pot.'),
('MSP430 + Booster','Identify the exact LaunchPad first. Follow your lab orientation/jumper instructions for fitting the Booster with power removed. Use the course IDE and its original lab blink/serial test.','The known lab example runs. No external sensor wiring yet.')],[91,270,W-361])
sub('3. Prepare Pico C/C++ development')
add('Use the official Raspberry Pi Pico VS Code extension. Create a C/C++ project for <b>Pico W / RP2040</b>, enable USB stdio, build a basic serial hello-world, and copy its UF2 to RPI-RP2. Reopen the serial port after the board restarts. Selecting plain Pico or using GP25 as the Pico W LED can give misleading results. [R1, R2]')
note('<b>Voltage check:</b> put the meter black lead in COM and red lead in V/Ohm; select DC volts. With USB connected, measure Uno 5V-to-GND and Pico 3V3(OUT)-to-GND. Expect about 5 V and 3.3 V. Never put an ammeter directly across a supply.')
add('Keep the FireBeetle white battery socket empty in this shared-pack design. It is intended for a single-cell 3.7 V lithium battery, not a 7.4 V pack. [R3]')

title('3','Read the sensors with the Uno')
add('These are <b>USB-only bench tests</b>. Test one mode at a time. The exact pin order varies between modules: follow printed VCC/GND/OUT/AO labels, not the left-to-right order in a generic photo. If labels cannot be identified, leave that module disconnected.')
table(['Test mode','Module connection','Uno connection'],[
('1: soil moisture','VCC on a module confirmed to support 5 V','5V'),
('','GND / AO (analog output)','GND / A0'),
('','Two-prong probe','Its matching two-terminal interface connection; DO unused'),
('2: IR pair','Each VCC / each GND, for 5 V-capable modules','5V / GND'),
('','Left OUT / right OUT','D2 / D3'),
('3: standard HC-SR04','VCC / GND','5V / GND'),
('','TRIG / ECHO','D4 / D5, direct on the 5 V Uno only')],[94,247,W-341])
sub('4. Soil probe')
add('With USB removed, wire the probe/interface. Set TEST_MODE = 1, reconnect and upload. Read soil_adc at 115200 baud. Record dry and damp samples at the same insertion depth; wait for each reading to settle. Keep the small interface board above the soil. Do not assume a higher number means wetter: verify the direction experimentally.')
add('The Uno uses a nominal 5 V ADC reference by default; raw counts range from 0 to 1023. They are not moisture percent. Unplug after tests; continuous power can accelerate corrosion of exposed resistive probes.')
sub('5. IR pair')
add('Set TEST_MODE = 2. Aim both modules downwards and move black tape and the light surface underneath. Adjust the trim pots and mounting height until both distinguish the surfaces repeatedly. Write down which output means black. These appear to be proximity-style modules: they must pass this test before being accepted as line sensors. [R5]')
sub('6. Ultrasonic sensor')
add('Set TEST_MODE = 3. Place a flat target at measured distances such as 10, 20 and 40 cm; compare the reported values with a ruler. NO_ECHO means an invalid measurement, not a clear route. The sketch waits between pings and limits its echo wait. [R4]')
note('<b>Pass before moving on:</b> clear dry/damp separation; reliable black/light readings on BOTH IR sensors; sensible distance readings. This sketch uses blocking delays for testing and does not fulfil the final timers/ISRs/control requirements.')

title('4','Move navigation sensors to Pico W')
add('Disconnect their Uno wires completely before moving them. Below is a <b>proposed pin assignment</b>, not a claim that these wires are already fitted. The soil sensor stays at the fixed pot in the final system.')
table(['Connection','Pico signal','Physical pin'],[
('Left IR OUT (0-3.3 V only)','GP2','4'),
('Right IR OUT (0-3.3 V only)','GP3','5'),
('IR VCC, if rated for 3.3 V','3V3(OUT)','36'),
('IR/ultrasonic ground','GND','38, or another GND'),
('HC-SR04 trigger','GP4','6'),
('HC-SR04 echo via divider below','GP5','7'),
('HC-SR04 VCC during Pico USB-only bench test','VBUS (USB 5 V)','40')],[270,155,W-425])
add('<b>Count carefully:</b> with components facing you and USB at the top, physical pin 1 is top left; pin 20 bottom left; pin 21 bottom right; pin 40 top right. GP numbers are not physical pin numbers. Check the official pinout before wiring. [R1]')
sub('7. Build the ECHO voltage divider')
story.append(Divider())
add('Connect ECHO through 10 kOhm to a junction. Connect that junction to GP5 and through 15 kOhm to GND. The calculation is 5 x 15/(10+15) = 3.0 V. Before attaching GP5, test the divider using a steady 5 V input and a voltmeter. Remove that test input, then reconnect the sensor ECHO.')
note('<b>Never put 5 V on a Pico or ESP32 GPIO.</b> The standard HC-SR04 uses 5 V power; its ECHO needs level reduction. GP4 gives a 3.3 V trigger: verify that your module responds; if it requires a higher trigger voltage, add an appropriate buffer rather than feeding 5 V into the Pico. [R1, R4]',True)
add('Power the Pico by laptop USB for this stage. Do not inject external power into VBUS while laptop USB is connected. IR outputs must be checked in both states before connecting; if the module needs 5 V power, provide suitable output level conversion as well.')

title('5','Add wheels and the water pump')
note('<b>Identification checkpoint:</b> you have not confirmed the wheel-driver model, pump-switch model or actuator ratings. The connections on this page are conditional. Do not energise a motor or pump by guessing its voltage or the meaning of an unlabelled terminal.',True)
sub('8. Wheel driver: two independent motor channels')
add('A pump switch is not a dual motor driver. Get a 3.3 V-compatible H-bridge whose supply range and continuous/starting-current ratings suit your two motors. A TB6612FNG carrier is one possible type only if its ratings are sufficient; do not buy it solely from the example below. [R7]')
table(['If using a verified TB6612FNG carrier','Proposed Pico connection'],[
('VCC / GND','3V3(OUT), pin 36 / shared GND'),
('AIN1 / AIN2 / PWMA','GP6 pin 9 / GP7 pin 10 / GP8 pin 11'),
('BIN1 / BIN2 / PWMB','GP9 pin 12 / GP10 pin 14 / GP11 pin 15'),
('STBY','GP12 pin 16; hold LOW during startup; use a 10 kOhm pulldown if not provided'),
('VM or VMOT','Motor-rated supply from its regulator, not Pico 3V3/5V'),
('AO1 + AO2 / BO1 + BO2','Left motor pair / right motor pair')],[271,W-271])
add('Use the carrier manufacturer\'s decoupling and wiring guidance. With wheels lifted clear of the table, test one wheel at low duty cycle, then the other, then reverse. If direction is wrong, remove power before swapping that motor pair. Keep STBY LOW until valid firmware is running. Do not add a single flyback diode across a bidirectional wheel motor.')
sub('9. Pump driver and tubing')
add('If the black board is confirmed as DFRobot DFR0457, use its labelled VIN/GND input and VOUT/GND load terminals, and follow its S/+/- control labels. Its VIN minimum is 5 V; this must also suit the pump rating. It is not suitable simply because it resembles the photo. [R6]')
add('For that confirmed module: GP13 (physical pin 17) is the proposed control signal, with shared signal GND and 3.3 V control supply according to the module pinout. Default OFF and a suitable pulldown are required. A flyback diode across the DC pump has its banded cathode at pump positive and anode at pump negative; choose ratings for the pump. Confirm whether the module already provides protection.')
add('Secure the tank and tubing, identify inlet/outlet and follow the pump\'s priming/submersion instructions. Test short, supervised pulses into a measuring cup using a rated, current-limited supply. Record mL per pulse. Do not run an unknown pump dry or assume it is submersible.')

title('6','Wire the fixed station')
add('Keep the stationary boards on laptop USB or their documented regulated supplies. The robot battery only needs to ride on the robot. Wireless data does not transfer electrical power.')
sub('10. Fit the MSP430 and course Booster')
add('Your manual requires an MSP430 LaunchPad and use of the CEG2002 Booster Board, plus at least one other microcontroller. The exact LaunchPad model and Booster schematic are needed to choose free ADC, UART and timer pins. Do not copy a pin number from a different LaunchPad. [R8]')
table(['Function','Connection once the board pinout is confirmed'],[
('Soil measurement','Sensor AO -> a free MSP430 ADC input. GND -> MSP430 GND. Use a sensor supply/output range compatible with that specific ADC and its reference; never assume 5 V is acceptable.'),
('Approval / pause','Use an appropriate Booster button or interface already available in your lab setup. Confirm any shared pins before assigning an interrupt.'),
('Status','Use an available Booster LED/display/buzzer as appropriate. This makes the Booster contribute to the application.'),
('ESP32 gateway','MSP430 UART TX -> FireBeetle IO16 (configured RX); MSP430 UART RX <- FireBeetle IO17 (configured TX); GND <-> GND. Only after verifying compatible logic levels and free MSP430 pins.')],[113,W-113])
sub('11. Connect communications in small steps')
add('First keep both fixed boards on their own USB supply. Join only UART TX/RX/GND between them; do not join their positive power rails. On the FireBeetle, IO16 and IO17 refer to the printed GPIO labels, not Arduino D16/D17. Configure the serial peripheral explicitly (for example, RX=16 and TX=17).')
add('Prove UART using a counter and acknowledgment. Then prove ESP32-to-Pico W communication over ordinary 2.4 GHz Wi-Fi; do not assume ESP-NOW compatibility with the Pico W. A shared local access point or ESP32 access-point arrangement can be used after individual links work.')
add('Keep motor and pump outputs inhibited while testing communication. Include a job identifier, fresh sensor status and acknowledgments. Repeated receipt of the same watering job must not repeat a dose. Loss of commands, invalid sensor data or a pause request must stop the affected outputs.')
sub('12. Camera and soil feedback')
add('The webcam stays plugged into the laptop. Match each image and moisture reading to the test-pot ID. Begin with user approval of watering; a webcam alone does not diagnose plant disease. Use only one instrumented pot initially; additional independently controlled pots need their own valid moisture information.')
note('The Uno test wiring is temporary. Do not leave the same analog output attached to differently powered boards while one is off. Move and recalibrate the soil sensor when its supply voltage or ADC reference changes.')

title('7','Commission the battery supply last')
note('<b>The linked Unicell pack remains a shortlist.</b> Its page lists 7.4 V, 2600 mAh, protection PCB and three wires, but not its allowable discharge current or the three-wire functions. Get those details and a compatible charger/connector from the supplier before connecting it. Do not assume the third wire is ground, a balance lead or a sensor lead. [R9]',True)
story.append(PowerMap())
sub('13. Select the power components')
add('Use an assembled protected pack and manufacturer-matched 2S lithium charger (typically 8.4 V CC/CV for this chemistry). The pack, protection, fuse, switch, connectors and regulators must support measured running and startup loads. A protection PCB is not a charger. The pack\'s mAh value does not establish its allowable current.')
add('Choose the electronics regulator to maintain regulated 5 V across the chosen pack operating range. Choose wheel and pump supply voltages from their actual ratings. One actuator regulator can be shared only if both voltage requirements match and its current/transient capacity is sufficient. Never assume a fully charged 8.4 V pack can connect directly to 5 V or 6 V actuators.')
sub('14. Set voltages before connecting any board')
add('With all loads disconnected, have the lab technician verify the pack\'s protected output pair and polarity. Connect pack positive through an appropriately selected fuse near the pack, then the main switch, to regulator IN+. Connect protected negative to IN-. If adjustable, set each output using a DC voltmeter, then disconnect power and secure the adjustment.')
add('Confirm about 5.0 V at the electronics output. Have the supply checked under a representative test load. Label every output. Wire non-isolated regulator negatives, Pico GND and driver signal grounds to a common distribution return; route motor/pump return current directly there rather than through sensor ground wires.')
sub('15. Bring up the robot on battery')
add('Disconnect laptop USB from the Pico. Feed the verified regulated 5 V into a correctly wired USB output socket and use a normal micro-USB cable to the Pico. Connect one load branch at a time: controller, sensors, wheels, then pump. Check for resets and voltage drops at each step. Keep the main switch reachable.')
note('To program again, switch OFF and disconnect battery power before attaching laptop USB. Do not use a USB Y-cable to combine supplies. Charge with the pack disconnected from the robot, while attended, following the pack/charger instructions. Manual charging and refill remain the project scope.')

title('8','Make the complete system work')
sub('16. Mount and route cables')
add('Put the battery and water tank low and secure them to the chassis. Mount the IR sensors rigidly, facing the route at the tested height; mount the ultrasonic sensor forward with a clear view. Keep nozzle aim fixed at the watering point. Keep hoses away from the wheels and route motor wires separately from analog sensor wires. Use strain relief and insulated terminals.')
sub('17. Bring functions together in this order')
table(['Step','Demonstration','Expected result'],[
('A','Dry / damp soil samples, no actuators','Correct raw readings and calibrated categories; invalid/stale readings inhibit watering.'),
('B','IR sensors and ultrasonic only','Black/light transitions and measured distances are logged reliably.'),
('C','Low-speed travel, pump physically disconnected','Line following and obstacle stop work. Missing echoes and lost line cause a stop, not continued travel.'),
('D','Single-pot stopping marker','Robot repeatedly stops at the intended service point. A wide black marker needs route/state logic; two IR bits alone cannot identify an arbitrary pot.'),
('E','Stationary robot, pump test into a cup','Calibrated volume within the chosen time limit; default/startup state is OFF.'),
('F','One approved dry-soil job','Arrive, stop, dose, wait for absorption, read soil again; enforce maximum total dose/time.'),
('G','Wet-soil request / obstacle / pause / lost link','No unwanted watering. Stop affected outputs; require a valid authorized state before resuming.'),
('H','Repeat a previously handled job ID','No second dose from a duplicate message.')],[46,230,W-276])
sub('18. Record evidence for the sensor lab')
add('Keep a log of timestamps, raw moisture ADC, both IR states, ultrasonic distance/validity, job ID, robot state and pump-on time. Measure actual delivered volume separately; pump time only estimates volume after calibration. Compare moisture readings against a defensible reference or characterize repeatability and error.')
add('Your final code must include the required original C/C++, two explicit ISRs, two timer functions, ADC, communications and power saving. The supplied Uno diagnostics are deliberately not final firmware. At least one chosen sensor must differ from sensors used in your regular CEG2001 labs; confirm that with the group. [R8]')
note('<b>First session target:</b> finish stages 2 and 3. You should have a working webcam, verified USB connections and raw readings from each identified sensor. Motor/battery commissioning starts only once the information on the next page has been filled in.')

title('9','Bench record and source links')
table(['Ask the lab / supplier','Record before actuator and battery power-up'],[
('MSP430 + Booster','LaunchPad model: __________  Booster revision: __________'),
('IR / soil / ultrasonic','Model and supply range: ______________________________'),
('Wheel motors','Rated voltage: ______  Running current: ______  Stall/start: ______'),
('Dual motor driver','Model: ______  Per-channel continuous / peak current: ______'),
('Water pump','Rated voltage/current: ______  Startup current: ______'),
('Pump switch','Model, logic voltage, output terminal polarity: ______________'),
('Battery','Protected + / - / third wire functions: ____________________'),
('Battery limits','Continuous/peak discharge; cutoff; charger model: __________'),
('Regulators / fuse','Outputs/current ratings; fuse and wire ratings: ______________')],[125,W-125])
sub('Reference documents')
refs=[
('R1','Raspberry Pi: Pico series, official pinouts and Pico W power documentation','https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html'),
('R2','Raspberry Pi: C/C++ SDK and VS Code setup','https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html'),
('R3','DFRobot DFR0478 FireBeetle ESP32 documentation and board setup','https://wiki.dfrobot.com/dfr0478/'),
('R4','HC-SR04 datasheet hosted by SparkFun: 5 V supply and timing','https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf'),
('R5','SunFounder: analogous 3.3-5 V IR proximity module; verify your own variant','https://docs.sunfounder.com/projects/sf-components/en/latest/component_avoidance_module.html'),
('R6','DFRobot DFR0457: power and logic limits; inductive-load protection','https://wiki.dfrobot.com/dfr0457/'),
('R7','Pololu TB6612FNG carrier: ratings for this specific carrier','https://www.pololu.com/product/713/specs'),
('R8','CEG2001/2002 Group Project Manual 2026, supplied PDF, pp. 2-5 and 7',None),
('R9','Unicell LI18650PB112W3: shortlisted pack; incomplete current/wiring specification','https://www.battery.com.sg/product/4-v-2600mah-18650-2s1p-li-ion-battery-with-protection-pcb-and-three-cable'),
('R10','Arduino Uno R3: power inputs and board specifications','https://store.arduino.cc/products/arduino-uno-rev3')]
for key,label,url in refs:
    text=f'<b>{key}</b>  '+(f'<link href="{escape(url)}" color="#087E83">{escape(label)}</link>' if url else escape(label))
    story.append(p(text,'SmallCustom'))
story.append(Spacer(1,7))
note('Prepared from the supplied hardware photos and manufacturer documentation. Generic sensor examples do not identify an unmarked module. No physical wiring, firmware flashing, battery-load test or robot operation has been performed by this guide.')

def footer(c,doc):
    c.saveState(); c.setStrokeColor(LINE); c.line(44,40,A4[0]-44,40)
    c.setFont('Helvetica',8); c.setFillColor(GREY)
    c.drawString(44,27,'PLANT-CARE ROBOT  |  SETUP & FIRST POWER-UP')
    c.drawRightString(A4[0]-44,27,f'{doc.page}')
    c.restoreState()

doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=38,bottomMargin=53,title='Plant-care robot: wiring and first power-up',author='Project setup guide')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
