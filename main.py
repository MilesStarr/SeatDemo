import rp2
import network
import machine
from machine import UART, Pin, PWM
import time
import math
import json
import uasyncio as asyncio
from microdot import Microdot, Response, redirect, send_file
from actuator import Actuator, trapazoidal

run_loop = Pin(7, mode=Pin.IN, pull=Pin.PULL_UP)  # mechanical stoppage of motion

RFS = Actuator(15, 1_200_000, 200_000)
RMS = Actuator(14, 1_500_000, 200_000)
RRS = Actuator(13, 1_500_000, 200_000)
LFS = Actuator(12, 1_500_000, -200_000)
LMS = Actuator(11, 1_500_000, -200_000)
LRS = Actuator(10, 1_500_000, -200_000)

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
op_param = {'lift_amp'  : 0.0,		# combined amplitude shouldn't exceed 1
            'pitch_amp' : 0.0,
            'roll_amp'  : 0.0,
            'period'    : 100,		# ms response time to input
            'start'     : time.ticks_ms(),
            'phase'     : 500,		# ms
            'running'   : False
           }

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

@app.post('/lift')
async def update_lift(request):
    flag = ""
    tmp = int(request.form.get('lift'))/100
    if op_param['pitch_amp'] + tmp > 1:
        op_param['pitch_amp'] = 1 - tmp
        flag = "***"
    op_param['lift_amp'] = tmp
    return f"{op_param['lift_amp']}{flag}"

@app.post('/pitch')
async def update_pitch(request):
    flag = ""
    tmp = int(request.form.get('pitch'))/100
    if op_param['lift_amp'] + tmp > 1:
        op_param['lift_amp'] = 1 - tmp
        flag = "***"
    op_param['pitch_amp'] = tmp
    return f"{op_param['pitch_amp']}{flag}"

@app.post('/phase')
async def update_phase(request):
    tmp = int(request.form.get('phase'))
    op_param['phase'] = tmp
    return f"{op_param['phase']}"

@app.post('/period')
async def update_period(request):
    tmp = int(request.form.get('period'))
    op_param['period'] = tmp
    return f"{op_param['period']}"

@app.get('/start')
async def start(request):
    op_param['running'] = True
    return "Running.  Stop to change period."

@app.get('/stop')
async def stop(request):
    op_param['running'] = False
    RFS.out(0.0)
    RMS.out(0.0)
    RRS.out(0.0)
    return f"""Stop state, set period in ms before restarting <br>
            <label for="phase">Period: <span id="period-val">{op_param['period']}</span></label> <br>
            <input type="range" 
                   name="period" 
                   min="0" 
                   max="1000" 
                   step="5" 
                   value="{op_param['period']}"
                   hx-post="/period" 
                   hx-trigger="input delay:20ms" 
                   hx-target="#period-val"
                   hx-swap="innerHTML">
            """

@app.post('/graph')
async def graph(request):
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
        lift = (150-y)/100.
        remainder = 1 - abs(lift)
        if abs(op_param['pitch_amp']) + abs(op_param['roll_amp']) <= remainder:
            pitch = op_param['pitch_amp']
            roll = op_param['roll_amp']
        else:
            pitch = remainder * (op_param['pitch_amp'] / (abs(op_param['roll_amp']) + abs(op_param['pitch_amp'])))
            roll = remainder * (op_param['roll_amp'] / (abs(op_param['roll_amp']) + abs(op_param['pitch_amp'])))

    if 100 <= x <= 300 and 50 <= y <= 250:
        # pitch/roll
        wrong = False
        pitch = (150-y)/100.
        roll  = (x-200)/100.
        total = abs(pitch) + abs(roll)
        if total > 1:
            pitch = pitch / total
            roll  = roll  / total
        remainder = 1 - (abs(pitch) + abs(roll))
        if abs(op_param['lift_amp']) < remainder:
            lift = op_param['lift_amp']
        else:
            lift = remainder * op_param['lift_amp'] / abs(op_param['lift_amp'])
    
    if wrong:
        # no click inside command areas
        lift = 0
        roll = 0
        pitch = 0

    op_param['lift_amp'] = lift
    op_param['roll_amp'] = roll
    op_param['pitch_amp'] = pitch
    op_param['start']     = time.ticks_ms()

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
                    <circle cx="{int(100*roll)}" cy="{int(-100*pitch)}" r="6" fill="#ff4444" />
                    <circle cx="{int(100*roll)}" cy="{int(-100*pitch)}" r="10" fill="none" stroke="#ff4444" stroke-width="2" stroke-dasharray="4,4"/>
                    
                    <!-- Center point -->
                    <circle cx="0" cy="0" r="2" fill="#000" />
                </g>
                    
                <!-- Collective Slider -->
                <g transform="translate(50, 150)">
                    <rect x="0" y="-100" width="20" height="200" fill="#ccc" />
                    <circle cx="10" cy="{int(-100*lift)}" r="8" fill="#000080" />
                </g>

            </svg>
            <BR>
            Pitch: {int(100*pitch)}<BR>
            Roll: {int(100*roll)}<BR>
            Collective: {int(100*lift)}"""

async def main_logic():
    while True:

        lift = op_param['lift_amp']
        roll = op_param['roll_amp']
        pitch = op_param['pitch_amp']

        while op_param['running']: #not run_loop():
            now = time.ticks_ms()
            dt = (op_param['period'] - time.ticks_diff(now, op_param['start'])) / op_param['period']
            dt = 0 if dt < 0 else dt

            lift = op_param['lift_amp'] * (1 - dt) + lift * dt
            roll = op_param['roll_amp'] * (1 - dt) + roll * dt
            pitch = op_param['pitch_amp'] * (1 - dt) + pitch * dt

            RFS.out(lift - pitch - roll)
            RMS.out(lift - roll)
            RRS.out(lift + pitch - roll)
            LFS.out(lift - pitch + roll)
            LMS.out(lift + roll)
            LRS.out(lift + pitch + roll)
            
            await asyncio.sleep_ms(10)
        await asyncio.sleep_ms(100)

async def main():
    web_srv = asyncio.create_task(app.start_server(debug=True))
    servos  = asyncio.create_task(main_logic())
    
    await web_srv

# Start the web server
print("Starting web server on http://" + ap.ifconfig()[0])
asyncio.run(main())
