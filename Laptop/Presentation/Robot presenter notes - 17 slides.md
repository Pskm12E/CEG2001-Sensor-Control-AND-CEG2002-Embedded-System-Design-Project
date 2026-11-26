# Vision-guided plant-care robot

## Rehearsal script

About 11–12 minutes at a conversational pace, plus the live demonstration. Each heading matches the saved Canva slide order.

### 01 · Vision-guided plant-care robot

If you find pests on one plant, how do you treat that plant and leave its neighbours alone? Our team built a tracked robot to test that idea. On our course, a blue square represents a pest on a plant, and water lets us see exactly where the spray lands. I helped test the Zumo on the track, calibrate its tank probe and check that the car’s MSP430 could switch the pump on and off. Here’s the greenhouse example that motivated us.

### 02 · Spot spraying in a pepper greenhouse

In a greenhouse in Lebanon, scouts found aphids on peppers while the cucumbers growing alongside them stayed aphid-free. They treated the pepper hot spots three times, and beneficial insects also helped keep the aphids under control. That’s why we chose a single plant as our target. A vegetable nursery manager or an orchid grower could try the same idea on one accessible row. We’d start with plants their staff have already marked. The question for that trial is how many unnecessary treatments they could avoid.

### 03 · Why spray only pest-affected plants?

The graph gives us one answer from a different crop. In Kansas, researchers counted one treatment each time one sorghum plant was sprayed. Across two seasons, treating whole plots took 2,588 plant treatments. Treating individual infested plants took 612, about 76% fewer. Whole-plot treatment generally kept aphid counts lower, so a grower would still need to check pest control. Our prototype tested a smaller question. Could the robot deliver water to the location we selected? Let me trace that request through the system.

### 04 · How the robot and dock connect

Start at the camera on the car and follow one frame. The XIAO sends it across the Wi-Fi network hosted by the FireBeetle. The Pico W at the desk passes it to the laptop over USB. When the laptop sees our marker, its request goes back through the Pico and FireBeetle to the car’s MSP430. The docking station has its own USB connection to the laptop. With those paths in mind, we can see who actually decides whether the robot moves.

### 05 · Who makes each decision?

Suppose the camera sees blue while the tracks are moving. The laptop decides whether the image contains our marker. The car’s MSP430 decides whether a spray is allowed and asks the Uno to stop. The Uno controls the tracks and reports when it has stopped. At the dock, a second MSP430 controls a different pump, which refills the car. Those jobs are easier to remember when you see the actual boards.

### 06 · Our robot and dock hardware

The red LaunchPad pictured here is the board we use in two places, on the car and at the dock. Beside it are the three boards that carry video from the robot to the laptop. In the lower row, notice the water probe and the Hall sensor. The probe on the car tells us how wet its tank sensor is. The dock has its own water supply sensor, and the Hall sensor detects the magnet on the arriving car. Here’s how those signals reach their controllers.

### 07 · Sensors, display and controller boards

Two connections on this table explain most of the water system. On the car, the probe connects to P6.0. The MSP430 reads a range of voltages, which lets us estimate the tank level. At the station, the reservoir probe goes through an LM339N comparator, so the dock receives one of two signals, enough water or low supply. The station’s LCD shows the operator what’s happening. The six line sensors connect to the Uno. Let’s follow their readings as the car starts a lap.

### 08 · Six reflectance sensors steer the tracks

Picture the black line slipping towards the left side of the car. The six downward-facing sensors see the shift because black and white reflect different amounts of light. The Uno compares the line position with its centre value of 2,500 and adjusts the two track speeds to bring the line back underneath. I ran the calibration sweep on the track, and we save the six sensor ranges so they can be reused after power-up. We slowed the straight-line command to 90 out of 400 to give the camera time to see a target. An obstacle ahead triggers a different response.

### 09 · When the Zumo pauses or beeps

The front ultrasonic sensor measures how long a sound pulse takes to return. At 5 centimetres or closer, the car pauses. It waits for two echoes of at least 7 centimetres before resuming. Using two different distances keeps the tracks from starting and stopping at the boundary. If the echo disappears while it’s paused, the car keeps waiting. For the flip alarm, the Uno uses the accelerometer to compare gravity with the saved upright orientation. If the car stays upside down, the buzzer sounds. A clear path lets the camera look for our target.

### 10 · How the camera confirms a target

Look at the green outline in the camera image. The laptop first isolates blue pixels, then checks whether they form a large enough, roughly square shape. It has to find that shape in a consistent position across three different frames before it sends a target request. That filters out a brief flash of blue as the car moves. The square stands in for a pest during our demo. Once the laptop recognises it, the car still has to stop before any water comes out.

### 11 · The car stops before it sprays

I checked this sequence at the pump itself. The car’s MSP430 asks the Uno to stop and waits for its reply. After about 300 milliseconds for the car to settle, P1.6 goes high. That pin switches the MOSFET, and the separate four-AA battery pack supplies the pump. After three seconds the MSP430 switches the pump off. We saw the pump run and stop after replacing a resistor in the driver circuit. Fresh camera confirmation for the same job lets the car continue. Each spray uses water, so the next decision depends on how much is left.

### 12 · The water reading sets the refill threshold

I took empty and full readings with the probe mounted in the tank. Empty gave us 1,836 counts and full gave us 2,281, a span of 445. Sixty percent of that span is 267 counts above empty, or 2,103. The rule is strictly above 60%, so 2,104 is the first qualifying reading. The 2,225 shown here is an example well above the threshold, about 87.4% full on this scale. That gives the car a way to decide when it can leave after a refill. Here’s how a return visit is meant to work.

### 13 · What happens at the refill station

While the car follows the line, two tank readings below 500 trigger a slow reverse. In the coordinated docking design, the station senses the car’s magnet and the laptop relays a stop request. Once the Uno confirms the stop and the car has settled, the station checks its water supply and can run its refill pump for up to ten seconds. The car can leave once the refill pump is confirmed off and its own tank has stayed above 60% for three seconds. We still need a full track trial of that sequence. The timing behind it also matters elsewhere on the car.

### 14 · Timing, interrupts and power saving

On the car MSP430, Timer_A0 ticks about every 100 milliseconds. Its interrupt switches P1.6 off when the spray time is up, even if the main loop is busy. Timer_A2 measures the ultrasonic echo, and a Port 2 interrupt records its rising and falling edges. The two serial ports use interrupts to receive bytes from the Uno and FireBeetle. The 12-bit ADC samples the tank probe. Between events the CPU can sleep in low-power mode zero and wake on an interrupt. We used that mode, but didn’t measure battery savings. We did measure one timing issue on the camera link.

### 15 · A camera relay fix reduced frame gaps

When video stalled, the detector had to wait for another complete picture. In the Pico relay, part of the next JPEG could overwrite the last complete frame. We changed the relay to keep the complete picture available while the next one arrived. Across the runs shown, the laptop went from roughly 4 to 7 frames per second to about 13. The longest gap fell from around a second or more to about a third of a second. These are frame arrivals at the laptop. What did we actually see on the track?

### 16 · What we demonstrated

On the track, we saw the Zumo complete the marked course, stop for the blue target and pause for an obstacle. We also saw water come out of the nozzle and the pump switch off after its timed pulse. The remaining test is to capture a complete return, magnetic stop, refill and departure in one run. We’d record the Hall signal, the tank reading, the pump switching off and the first forward movement. With that distinction clear, let’s turn to the robot itself.

### 17 · Live demonstration

As we start the demo, watch the tracks, then the nozzle. The car follows the black line. The blue square marks the plant we’ve selected. When the robot reaches it, look for the tracks to stop before the water starts, then watch for the pump to switch off. You can follow the camera image and tank reading on the laptop. [After the demonstration] Thank you. We’re happy to take questions about the sensors, the MSP430 or what we’d test next.
