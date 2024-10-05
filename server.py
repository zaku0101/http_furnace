from flask import Flask
from flask import render_template
from flask import request

import os
import errno

from datetime import datetime
from pygame import mixer

import threading
from threading import Lock
import nmap

import socket

app = Flask(__name__)

# nm = nmap.PortScanner()
# nm.scan(hosts='192.168.0.0-255', arguments='-sP' )

# host_list = nm.all_hosts()

global temp, pwm, dess_temp, auto, count
temp = 'n/c'
pwm = 'n/c'
des_temp = 'n/c'
auto = 'n/c'
count = 0

try:
    host = os.environ["HEATER_NAME"]
except Exception as e:
    print(e)
    exit(1)
port = 4242

global client_sock
client_sock = socket.socket()

def do_furnace_work():
    mixer.init()


    while(1):
        client_sock.settimeout(3.0)
        try:
            data = client_sock.recv(1024).decode('utf-8')
        except socket.error as e:
           if e == errno.EWOULDBLOCK:
                continue
           break
        if data == '':
           continue

        global temp, pwm, des_temp, auto, count
        f = open("./log/furnace_" + datetime.now().strftime("%m_%d") + ".log", 'a')
        f.write(datetime.now().strftime("%H:%M:%S : ") + data)
        f.close()
        temp = data.split(',')[0].split(':')[1]
        pwm = data.split(',')[1].split(':')[1].split('/')[0]
        des_temp = data.split(',')[2].split(':')[1]
        auto = data.split(',')[3].split(':')[1]

        if int(temp) >= int(des_temp) - 5 and int(temp) <= int(des_temp) + 5 and int(count) <= 10:
            mixer.music.load('./mus/jestem_nagrzany.mp3')
            mixer.music.play()
            count += 1


    client_sock.close()
    temp = "n/c"
    pwm = "n/c"
    des_temp = "n/c"
    auto = "n/c"

def do_conn_work():

    global client_sock
    while(True):
        try:
            client_sock.connect((host, port))
        except socket.error as e:
            print(e)
            continue
        do_furnace_work()
        client_sock = socket.socket()



thread = threading.Thread(target=do_conn_work)
thread.start()

def show_monitor():
    return render_template('monitor.html',name=host, temp=temp, pwm=pwm, auto=auto, des_temp=des_temp)

@app.route("/monitor", methods=['GET', 'POST'])
def monitor():
    if request.method == 'GET':
        return show_monitor()
    if request.method == 'POST':
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
        return show_monitor()

@app.route("/monitor/values", methods=['GET'])
def values():
    if(thread.is_alive() == False):
        os._exit(1)
    string = str(temp)+':'+str(pwm)+':'+str(auto) + ':' + str(des_temp)
    return string


if __name__ == '__main__':
    app.run()