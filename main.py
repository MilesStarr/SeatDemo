import rp2
import network
from machine import Pin
import time
import uasyncio as asyncio
from microdot import Microdot, send_file
from actuator import Actuator, CMD

run_loop = Pin(7, mode=Pin.IN, pull=Pin.PULL_UP)  # mechanical stoppage of motion

RFS = Actuator(15, 1_200_000, 200_000)
RMS = Actuator(14, 1_500_000, 200_000)
RRS = Actuator(13, 1_500_000, 200_000)
LFS = Actuator(11, 1_675_000, -200_000)
LMS = Actuator(10, 1_600_000, -200_000)
LRS = Actuator( 9, 1_650_000, -200_000)

# Initialize WiFi
rp2.country('US')
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
ap.config(essid="Dyn_Seat", password="iamaseat")
time.sleep(2)
print("AP Mode Activated")
print("IP Address:", ap.ifconfig()[0])

# Initialize variables with default values
pitch = CMD()
roll = CMD()
lift = CMD()
running = False

# Web server setup
app = Microdot()


# Serve the main configuration page
@app.route('/')
async def index(request):
    # Render HTML template with current values
    return send_file('templates/index.html')

@app.route('/shutdown')
async def shutdown(request):
    request.app.shutdown()
    return 'The server is shutting down...'

@app.route('/static/<path:path>')
async def static(request, path):
    if '..' in path:
        # directory traversal is not allowed
        return 'Not found', 404
    return send_file('static/' + path)

@app.post('/period')
async def update_period(request):
    global period
    period = int(request.form.get('period'))
    lift.period= period
    roll.period = period
    pitch.period = period
    return f"{period}"

@app.get('/start')
async def start(request):
    global running
    running = True
    return "Running.  Stop to change period."

@app.get('/stop')
async def stop(request):
    global running, period, lift, roll, pitch
    running = False
    RFS.out(0.0)
    RMS.out(0.0)
    RRS.out(0.0)
    LFS.out(0.0)
    LMS.out(0.0)
    LRS.out(0.0)
    pitch = CMD()
    roll = CMD()
    lift = CMD()
    return f"""Stop state, set period in ms before restarting <br>
            <label for="phase">Period: <span id="period-val">{period}</span></label> <br>
            <input type="range" 
                   name="period" 
                   min="0" 
                   max="1000" 
                   step="5" 
                   value="{period}"
                   hx-post="/period" 
                   hx-trigger="input delay:20ms" 
                   hx-target="#period-val"
                   hx-swap="innerHTML">
            """

@app.post('/graph')
async def graph(request):
    global running, period, lift, roll, pitch
    x = request.form.get('offsetX')
    y = request.form.get('offsetY')
    wrong = True

    try:
        x = int(x)
        y = int(y)
    except:
        print(f"{type(x)} is {x}, {type(y)} is {y}")
        return

    if 50 <= x <= 70 and 50 <= y <= 250:
        # collective
        wrong = False
        lift_val = (150-y)/100.
        remainder = 1 - abs(lift_val)
        if abs(pitch.cmd) + abs(roll.cmd) <= remainder:
            pitch_val = pitch.cmd
            roll_val = roll.cmd
        else:
            pitch_val = remainder * (pitch.cmd / (abs(roll.cmd) + abs(pitch.cmd)))
            roll_val = remainder * (roll.cmd / (abs(roll.cmd) + abs(pitch.cmd)))

    if 100 <= x <= 300 and 50 <= y <= 250:
        # pitch/roll
        wrong = False
        pitch_val = (150-y)/100.
        roll_val  = (x-200)/100.
        total = abs(pitch) + abs(roll)
        if total > 1:
            pitch_val = pitch_val / total
            roll_val  = roll_val  / total
        remainder = 1 - (abs(pitch) + abs(roll))
        if abs(lift.cmd) < remainder:
            lift_val = lift.cmd
        else:
            lift_val = remainder * lift.cmd / abs(lift.cmd)
    
    if wrong:
        # no click inside command areas
        lift_val = 0
        roll_val = 0
        pitch_val = 0

    lift.target(lift_val)
    roll.target(roll_val)
    pitch.target(pitch_val)

    return f"""            <!-- Hidden inputs for coordinates -->
            <input type="hidden" id="offset-x" name="offsetX" value="">
            <input type="hidden" id="offset-y" name="offsetY" value="">


            <svg width="400" 
                height="300"
                hx-on:click="
                    document.getElementById('offset-x').value = event.offsetX; 
                    document.getElementById('offset-y').value = event.offsetY;
                "
                xmlns="http://www.w3.org/2000/svg">
                <!-- Background -->
                <rect width="100%" height="100%" fill="#f0f8ff" />

                <!-- Pitch/Roll Graph -->
                <g transform="translate(200, 150)">
                    <!-- Graph background -->
                    <rect x="-100" y="-100" width="200" height="200" fill="#ffffff" stroke="#ccc" stroke-width="1"/>
                    
                    <!-- Grid lines -->
                    <line x1="-100" y1="0" x2="100" y2="0" stroke="#ccc" stroke-width="1"/>
                    <line x1="0" y1="-100" x2="0" y2="100" stroke="#ccc" stroke-width="1"/>
                    
                    <!-- Axis labels -->
                    <text x="90" y="15" font-family="Arial" font-size="12" fill="#000">Roll</text>
                    <text x="-15" y="-95" font-family="Arial" font-size="12" fill="#000">Pitch</text>
                    
                    <!-- Axis ticks -->
                    <line x1="-100" y1="0" x2="-95" y2="0" stroke="#000" stroke-width="1"/>
                    <line x1="0" y1="-100" x2="0" y2="-95" stroke="#000" stroke-width="1"/>
                    <line x1="100" y1="0" x2="95" y2="0" stroke="#000" stroke-width="1"/>
                    <line x1="0" y1="100" x2="0" y2="95" stroke="#000" stroke-width="1"/>
                    
                    <!-- X and Y axis labels -->
                    <text x="-105" y="5" font-family="Arial" font-size="10" fill="#000">-100</text>
                    <text x="95" y="5" font-family="Arial" font-size="10" fill="#000">100</text>
                    <text x="-10" y="-105" font-family="Arial" font-size="10" fill="#000">100</text>
                    <text x="-10" y="110" font-family="Arial" font-size="10" fill="#000">-100</text>
                    
                    <!-- Pitch/Roll indicator point -->
                    <circle cx="{int(100*roll_val)}" cy="{int(-100*pitch_val)}" r="6" fill="#ff4444" />
                    <circle cx="{int(100*roll_val)}" cy="{int(-100*pitch_val)}" r="10" fill="none" stroke="#ff4444" stroke-width="2" stroke-dasharray="4,4"/>
                    
                    <!-- Center point -->
                    <circle cx="0" cy="0" r="2" fill="#000" />
                </g>
                    
                <!-- Collective Slider -->
                <g transform="translate(50, 150)">
                    <rect x="0" y="-100" width="20" height="200" fill="#ccc" />
                    <circle cx="10" cy="{int(-100*lift_val)}" r="8" fill="#000080" />
                </g>

            </svg>
            <BR>
            Pitch: {int(100*pitch_val)}<BR>
            Roll: {int(100*roll_val)}<BR>
            Collective: {int(100*lift_val)}"""

async def main_logic():
    global running, period, lift, roll, pitch
    while True:

        # lift = lift.out
        # roll = roll.out
        # pitch = pitch.out
        then = time.ticks_ms()

        while running: #not run_loop():
            now = time.ticks_ms()
            dt = time.ticks_diff(now, then)

            lift.out = lift.out + (lift.rate(now) + lift.washrate(now)) * dt
            roll.out = roll.out + (roll.rate(now) + roll.washrate(now)) * dt
            pitch.out = pitch.out + (pitch.rate(now) + pitch.washrate(now)) * dt

            RFS.out(lift.out - pitch.out - roll.out)
            RMS.out(lift.out - roll.out)
            RRS.out(lift.out + pitch.out - roll.out)
            LFS.out(lift.out - pitch.out + roll.out)
            LMS.out(lift.out + roll.out)
            LRS.out(lift.out + pitch.out + roll.out)
            
            then = now

            await asyncio.sleep_ms(8)
        await asyncio.sleep_ms(100)

async def main():
    web_srv = asyncio.create_task(app.start_server(debug=True))
    servos  = asyncio.create_task(main_logic())
    
    await web_srv

# Start the web server
print("Starting web server on http://" + ap.ifconfig()[0])
asyncio.run(main())
