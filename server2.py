from flask import Flask, render_template, jsonify, request
import threading
import nmap
import socket
import time

app = Flask(__name__)

# Initialize the nmap scanner
nm = nmap.PortScanner()

# Global variable to store host information
hosts_info = {}

# Lock for thread-safe updates to hosts_info
lock = threading.Lock()

# Global variable for client socket
client_socks = {}

def scan_network():
    global hosts_info
    while True:
        nm.scan(hosts='192.168.0.0-255', arguments='-sP')
        with lock:
            hosts_info = {host: {'log': []} for host in nm.all_hosts()}
        time.sleep(60)  # Scan every 60 seconds

def monitor_host(host):
    port = 4242
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.settimeout(3)
            with lock:
                client_socks[host] = sock
            while True:
                data = sock.recv(1024).decode('utf-8')
                if not data:
                    break
                with lock:
                    hosts_info[host]['log'].append(data)
                    hosts_info[host]['log'] = hosts_info[host]['log'][-10:]  # Keep only the last 10 lines
        except Exception as e:
            with lock:
                hosts_info[host]['error'] = str(e)
        finally:
            with lock:
                if host in client_socks:
                    del client_socks[host]
            sock.close()
        time.sleep(10)  # Reconnect every 10 seconds

@app.route('/')
def index():
    with lock:
        hosts = list(hosts_info.keys())
    return render_template('index.html', hosts=hosts)

@app.route('/host/<host>', methods=['GET', 'POST'])
def host_page(host):
    if request.method == 'POST':
        with lock:
            client_sock = client_socks.get(host)
        if client_sock:
            pwm = request.form.get('pwm')
            if pwm != '':
                if int(pwm) <= 50 and int(pwm) >= 0:
                    string = "pwm " + pwm
                    client_sock.send(string.encode())
            temp = request.form.get('temp')
            if temp != '':
                if int(temp) <= 1250 and int(temp) >= 0:
                    string = "temp " + temp
                    client_sock.send(string.encode())
                    global count
                    count = 0
            auto = request.form.get('auto')
            if auto != '':
                if int(auto) <= 1 and int(auto) >= 0:
                    string = "auto " + auto
                    client_sock.send(string.encode())
        return render_template('host.html', host=host)
    return render_template('host.html', host=host)

@app.route('/host/<host>/log')
def get_host_log(host):
    with lock:
        log = hosts_info.get(host, {}).get('log', [])
    return jsonify(log)

if __name__ == '__main__':
    # Start network scanning thread
    scan_thread = threading.Thread(target=scan_network)
    scan_thread.daemon = True
    scan_thread.start()

    # Start monitoring threads for each host
    for host in nm.all_hosts():
        monitor_thread = threading.Thread(target=monitor_host, args=(host,))
        monitor_thread.daemon = True
        monitor_thread.start()

    app.run(debug=True, port=5050)