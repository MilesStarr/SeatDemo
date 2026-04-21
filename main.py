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
op_param = {'lift_amp'  : 0.5,		# combined amplitude shouldn't exceed 1
            'pitch_amp' : 0.5,
            'period'    : 2000,		# ms
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
                   max="10000" 
                   step="10" 
                   value="{op_param['period']}"
                   hx-post="/period" 
                   hx-trigger="input delay:20ms" 
                   hx-target="#period-val"
                   hx-swap="innerHTML">
            """

async def main_logic():
    while True:
        start = time.ticks_ms()

        while op_param['running']: #not run_loop():
            now = time.ticks_ms()
            dt1 = ((time.ticks_diff(now, start))                     % op_param['period']) / op_param['period']
            dt2 = ((time.ticks_diff(now, start) + op_param['phase']) % op_param['period']) / op_param['period']

            lift  = trapazoidal(dt1) * op_param['lift_amp']
            pitch = trapazoidal(dt2) * op_param['pitch_amp']
            
            print(lift)
            RFS.out(lift + pitch)
            RMS.out(lift)
            RRS.out(lift - pitch)
            
            await asyncio.sleep_ms(10)
        await asyncio.sleep_ms(100)

async def main():
    web_srv = asyncio.create_task(app.start_server(debug=True))
    servos  = asyncio.create_task(main_logic())
    
    await web_srv

# Start the web server
print("Starting web server on http://" + ap.ifconfig()[0])
asyncio.run(main())
