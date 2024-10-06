import pygame
from flask import Flask, render_template, jsonify, request
import multiprocessing
import nmap
import socket
import time
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize the nmap scanner
nm = nmap.PortScanner()

# Queue to store host information
hosts_info_queue = multiprocessing.Queue()

# Dictionary to track active processes
active_processes = {}

def scan_network():
    while True:
        print("Scanning network...")
        nm.scan(hosts='192.168.1.0-255', arguments='-sP')
        hosts_info = {}
        for host in nm.all_hosts():
            if 'pico' in nm[host].hostname():
                hosts_info[host] = {
                    'log': [],
                    'hostname': nm[host].hostname() if nm[host].hostname() else host
                }
        hosts_info_queue.put(hosts_info)
        print(f"Discovered hosts: {list(hosts_info.keys())}")
        time.sleep(60)  # Scan every 60 seconds

def monitor_host(host, hosts_info_queue):
    port = 4242
    song_played_count = 0
    max_plays = 5
    previous_setpoint = None
    while True:
        try:
            print(f"Connecting to {host}:{port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.settimeout(10)  # Increase timeout to 10 seconds
            print(f"Connected to {host}:{port}")
            while True:
                try:
                    data = sock.recv(1024).decode('utf-8')
                    if not data:
                        print(f"No data received from {host}, closing connection.")
                        break
                    hosts_info = hosts_info_queue.get()
                    hosts_info[host]['log'].append(data.strip())
                    hosts_info_queue.put(hosts_info)
                    print(f"Received data from {host}: {data.strip()}")

                    # Parse the current temperature and setpoint from the received data
                    temp_str = data.split(',')[0].split(':')[1]
                    current_temp, setpoint = map(float, temp_str.split('/'))

                    # Check if temperature setpoint is reached
                    if current_temp >= setpoint:
                        if setpoint != previous_setpoint:
                            song_played_count = 0
                            previous_setpoint = setpoint
                        if song_played_count < max_plays:
                            print(f"Temperature setpoint {setpoint} reached. Playing song in browser.")
                            socketio.emit('play_song', {'host': host}, room=host)
                            song_played_count += 1

                except socket.timeout:
                    print(f"Socket timeout while receiving data from {host}")
                    continue
                except ValueError as e:
                    print(f"Error parsing temperature data: {e}")
                    continue
        except Exception as e:
            hosts_info = hosts_info_queue.get()
            hosts_info[host]['error'] = str(e)
            hosts_info_queue.put(hosts_info)
            print(f"Error connecting to {host}: {e}")
        finally:
            sock.close()
            print(f"Connection to {host} closed.")
        time.sleep(1) 

@app.route('/')
def index():
    hosts_info = hosts_info_queue.get()
    hosts = list(hosts_info.keys())
    hosts_info_queue.put(hosts_info)
    return render_template('index.html', hosts=hosts, hosts_info=hosts_info)

@app.route('/host/<host>')
def host_page(host):
    # Start a new process to monitor the host if not already started
    if host not in active_processes:
        print(f"Starting new process to monitor host: {host}")
        process = multiprocessing.Process(target=monitor_host, args=(host, hosts_info_queue))
        process.daemon = True
        process.start()
        active_processes[host] = process
    else:
        print(f"Host {host} is already being monitored.")
    
    hosts_info = hosts_info_queue.get()
    hosts_info_queue.put(hosts_info)
    return render_template('host.html', host=host, hostname=hosts_info[host]['hostname'])

@app.route('/host/<host>/log')
def get_host_log(host):
    hosts_info = hosts_info_queue.get()
    log = hosts_info.get(host, {}).get('log', [])
    hosts_info_queue.put(hosts_info)
    return jsonify(log)

@app.route('/host/<host>/send', methods=['POST'])
def send_data_to_host(host):
    data = request.json.get('data')
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if host not in active_processes:
        return jsonify({'error': 'Host not connected'}), 400

    try:
        print(f"Resolving hostname {host}")
        resolved_ip = socket.gethostbyname(host)
        print(f"Resolved IP for {host}: {resolved_ip}")

        print(f"Sending data to {host} ({resolved_ip}): {data}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((resolved_ip, 4242))
        sock.sendall(data.encode('utf-8'))
        sock.close()
        print(f"Data sent to {host} ({resolved_ip}) successfully")
        return jsonify({'status': 'Data sent successfully'})
    except Exception as e:
        print(f"Error sending data to {host} ({resolved_ip}): {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/host/<host>/stop', methods=['POST'])
def stop_monitoring_host(host):
    # Stop the current process if it exists
    if host in active_processes:
        print(f"Stopping process for host: {host}")
        active_processes[host].terminate()
        active_processes[host].join()
        del active_processes[host]
    return jsonify({'status': 'Monitoring stopped'})

@socketio.on('join')
def on_join(data):
    host = data['host']
    join_room(host)
    print(f"Client joined room for host: {host}")

@socketio.on('leave')
def on_leave(data):
    host = data['host']
    leave_room(host)
    print(f"Client left room for host: {host}")

if __name__ == '__main__':
    scan_process = multiprocessing.Process(target=scan_network)
    scan_process.daemon = True
    scan_process.start()
    socketio.run(app, host='0.0.0.0', debug=True)