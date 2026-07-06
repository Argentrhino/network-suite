import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input, Static
from scanner import scan_network
from portdb import lookup_port
from history import HistoryManager

class CommandBar(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_command = ""

    def compose(self):
        yield Input(placeholder="Enter Command>", id="command_input")

    async def on_input_submitted(self, message: Input.Submitted):
        raw = message.value.strip()
        self.last_command = raw
        lower = raw.lower()
        status = self.app.query_one(StatusBar)

        if lower in ("quit", "exit"):
            self.app.exit()
            return

        if lower.startswith("autorefresh="):
            value = lower.split("=")[1]
            try:
                interval = int(value)
            except:
                status.show_message("auto-refresh must be a number")
                self.query_one("#command_input").value = ""
                return

            if interval == 0:
                await self.app.set_auto_refresh(False)
                status.show_message("Auto-refresh disabled.")
                self.query_one("#command_input").value = ""
                return

            if interval < 5:
                interval = 5

            self.app.autorefresh_interval = interval
            await self.app.set_auto_refresh(True)
            status.show_message(f"Logging, interval: {interval}s")

            self.query_one("#command_input").value = ""
            return

        await self.app.handle_command(raw)
        self.query_one("#command_input").value = ""

class StatusBar(Static):
    def on_mount(self):
        self.display = "none"

    def show_message(self, msg):
        self.display = "block"
        self.update(msg)

    def hide(self):
        self.display = "none"

class NetworkMonitor(App):
    TITLE = "Network Suite"
    BINDINGS = [("r", "refresh_devices", "Refresh")]

    auto_refresh = False
    auto_task = None
    current_worker = None
    autorefresh_interval = 5

    log_enabled = False
    log_interval = 5
    log_task = None

    def compose(self) -> ComposeResult:
        yield Header()
        self.table = DataTable()
        yield self.table
        yield CommandBar(id="command_bar")
        yield StatusBar(id="status_bar")
        yield Footer()

    async def on_mount(self):
        self.history = HistoryManager()
        status = self.query_one(StatusBar)
        status.show_message("Loading...")
        self.table.add_columns("IP Address", "MAC Address", "Hostname", "Vendor")
        self.current_worker = self.run_worker(self.refresh_devices, exclusive=True)

    async def refresh_devices(self):
        status = self.query_one(StatusBar)
        status.show_message("Scanning network...")
        devices = await asyncio.to_thread(scan_network)
        self.table.clear()
        for d in devices:
            self.table.add_row(
                d.get("ip", "-"),
                d.get("mac", "-"),
                d.get("hostname", "-"),
                d.get("vendor", "-")
            )
        status.hide()

    async def action_refresh_devices(self):
        self.current_worker = self.run_worker(self.refresh_devices, exclusive=True)

    async def auto_refresh_loop(self):
        status = self.query_one(StatusBar)
        while self.auto_refresh:
            status.show_message(f"Auto-refresh ({self.autorefresh_interval}s)")
            self.current_worker = self.run_worker(self.refresh_devices, exclusive=True)
            await self.current_worker.wait()
            await asyncio.sleep(self.autorefresh_interval)

    async def set_auto_refresh(self, enabled: bool):
        self.auto_refresh = enabled
        if enabled:
            if self.auto_task is None or self.auto_task.done():
                self.auto_task = asyncio.create_task(self.auto_refresh_loop())
        else:
            if self.auto_task:
                self.auto_task.cancel()
                self.auto_task = None
            if self.current_worker and not self.current_worker.is_finished:
                self.current_worker.cancel()
            status = self.query_one(StatusBar)
            status.hide()

    async def logging_loop(self):
        status = self.query_one(StatusBar)
        while self.log_enabled:
            status.show_message(f"Logging, interval: {self.log_interval}s")
            devices = await asyncio.to_thread(scan_network)

            online_ips = set()

            for d in devices:
                ip = d["ip"]
                mac = d["mac"]
                hostname = d["hostname"]
                vendor = d["vendor"]

                online_ips.add(ip)

                if ip not in self.history.data:
                    self.history.ensure_device(ip, mac, hostname, vendor)
                else:
                    self.history.update_online(ip, mac, hostname, vendor)

            for ip in list(self.history.data.keys()):
                if ip not in online_ips:
                    self.history.update_offline(ip)

            await asyncio.sleep(self.log_interval)

    async def set_logging(self, enabled: bool):
        self.log_enabled = enabled
        if enabled:
            if self.log_task is None or self.log_task.done():
                self.log_task = asyncio.create_task(self.logging_loop())
        else:
            if self.log_task:
                self.log_task.cancel()
                self.log_task = None

    async def handle_command(self, command: str):
        status = self.query_one(StatusBar)
        parts = command.split()
        if len(parts) < 1:
            status.show_message("Invalid command")
            return

        if parts[0].lower() == "/log":
            if len(parts) < 2:
                status.show_message("Usage: /log -<seconds> (0 to stop)")
                return

            flag = parts[1]
            try:
                interval = int(flag[1:])
            except:
                status.show_message("Invalid log interval")
                return

            if interval == 0:
                await self.set_logging(False)
                status.show_message("Logging disabled.")
                return

            if interval < 3:
                interval = 3

            self.log_interval = interval
            await self.set_logging(True)
            status.show_message(f"Logging enabled, interval: {interval}s")
            return

        if len(parts) < 2:
            status.show_message("Format: <ip> /ping or <ip> /scan [-Fast|-Normal|-Full]")
            return

        ip = parts[0]
        cmd = parts[1].lower()
        flag = parts[2] if len(parts) > 2 else None

        if cmd == "/ping":
            duration = 5
            if flag and flag.startswith("-") and flag.endswith("s"):
                try:
                    duration = int(flag[1:-1])
                except:
                    status.show_message("Invalid duration")
                    return
            status.show_message(f"Pinging {ip} for {duration}s...")
            self.current_worker = self.run_worker(self.run_ping(ip, duration), exclusive=True)
            return

        if cmd == "/scan":
            mode = "normal"
            if flag:
                f = flag.lower()
                if f == "-fast":
                    mode = "fast"
                elif f == "-normal":
                    mode = "normal"
                elif f == "-full":
                    mode = "full"
                else:
                    status.show_message("Unknown scan mode")
                    return
            status.show_message(f"Scanning {ip} ({mode})...")
            self.current_worker = self.run_worker(self.run_scan(ip, mode), exclusive=True)
            return

        status.show_message("Unknown command")

    async def run_ping(self, ip: str, duration: int):
        from scanner import ping_stats
        status = self.query_one(StatusBar)
        result = await asyncio.to_thread(ping_stats, ip, duration)
        if not result["success"]:
            status.show_message(f"Ping failed ({result['loss']}% loss)")
        else:
            status.show_message(
                f"Ping {ip}: avg {result['avg']}ms (min {result['min']}ms, max {result['max']}ms)"
            )

    async def run_scan(self, ip: str, mode: str):
        from scanner import host_scan
        status = self.query_one(StatusBar)
        result = await asyncio.to_thread(host_scan, ip, mode)
        if not result["ping"]["success"]:
            status.show_message("Host did not respond to ping")
            return
        ports = []
        for entry in result["open_ports"]:
            port = entry["port"]
            proto = entry["protocol"]
            name = lookup_port(port, proto)
            ports.append(f"{port}/{proto} ({name})")
        open_ports = ", ".join(ports) or "none"
        status.show_message(
            f"Scan {ip} ({mode}): ping {result['ping']['avg']}ms, open ports: {open_ports}"
        )

if __name__ == "__main__":
    NetworkMonitor().run()