import nmap
import socket 

nm = nmap.PortScanner()
nm.scan(hosts='192.168.0.0-255', arguments='-sP' )

print(nm.all_hosts())

for host in nm.all_hosts():
    print(host.get('addresses').get('ipv4'))