# network-suite
A fast, modern Python TUI for scanning your local network, discovering devices, resolving hostnames, identifying vendors, and checking open ports — all in one clean interface.
Currently Implemented Features:

ARP device discovery 
mDNS scanning 
Vendor lookup 
Hostname resolution 
Ping statistics 
Port scanning
Auto‑refresh mode 
Textual‑powered TUI


Commands:
Scan a specific host:
Fast: Scans the 10 most common ports to quickly identify devices.

Normal: Scans a curated set of important ports used by routers, printers, IoT, and Windows systems.

Full: Scans all 1024 well‑known ports for maximum detail and security auditing.

<IP ADDRESS> /scan -Fast
<IP ADDRESS> /scan -Normal
<IP ADDRESS> /scan -Full
Ping a device
/ping for one ping, /ping -<number of seconds>s allows you to set pinging time, and see stats such as average, max, min.
<IP ADDRESS> /ping
<IP ADDRESS> /ping -10s
Enable auto‑refresh: autorefresh=1
Disable auto‑refresh: autorefresh=0

Installation steps (python needs to be preinstalled)
1. Download the repository as zip and extract
https://github.com/yourusername/NetworkSuite

2. Install dependencies

pip install -r dependencies.txt
3. Run the app
python tui.py
