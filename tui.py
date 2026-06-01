import asyncio
from statistics import mode
import subprocess
from unittest import result
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input, Static
from textual.containers import Container
from scanner import scan_network
from portdb import lookup_port

class CommandBar(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_command = ""

    def compose(self):
        yield Input(placeholder="Enter Command>", id="command_input")

    async def on_input_submitted(self, message: Input.Submitted):
        raw = message.value.strip()
        self.last_command = raw

        lower_cmd = raw.lower()

        
        if lower_cmd in ("quit", "exit"):
            self.app.exit()
            return

        if lower_cmd.startswith("autorefresh="):
            value = lower_cmd.split("=")[1]
            if value == "1":
                await self.app.set_auto_refresh(True)
            elif value == "0":
                await self.app.set_auto_refresh(False)

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
    BINDINGS = [
        ("r", "refresh_devices", "Refresh"),
    ]

    auto_refresh = False
    auto_task = None
    current_worker = None

    def compose(self) -> ComposeResult:
        yield Header()
        self.table = DataTable()
        yield self.table
        yield CommandBar(id="command_bar")
        yield StatusBar(id="status_bar")
        yield Footer()

    async def on_mount(self):
        status = self.query_one(StatusBar)
        status.show_message("Loading...")

        self.table.add_columns(
            "IP Address",
            "MAC Address",
            "Hostname",
            "Vendor"
        )

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
        while self.auto_refresh:
            self.current_worker = self.run_worker(self.refresh_devices, exclusive=True)

            for _ in range(50):
                if not self.auto_refresh:
                    return
                await asyncio.sleep(0.1)

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

    async def handle_command(self, command: str):
        status = self.query_one(StatusBar)
        parts = command.split()

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
                    status.show_message("Invalid duration. Example: 192.168.1.1 /ping -90s")
                    return

            status.show_message(f"Pinging {ip} for {duration}s...")
            self.current_worker = self.run_worker(
                self.run_ping(ip, duration),
                exclusive=True
            )
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
                    status.show_message("Unknown scan mode. Use -Fast, -Normal, -Full")
                    return

            status.show_message(f"Scanning {ip} ({mode})...")
            self.current_worker = self.run_worker(
                self.run_scan(ip, mode),
                exclusive=True
            )
            return

        status.show_message("Unknown command. Use /ping or /scan")

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

        port_strings = []
        for entry in result["open_ports"]:
            port = entry["port"]
            proto = entry["protocol"]
            name = lookup_port(port, proto)
            port_strings.append(f"{port}/{proto} ({name})")

        open_ports = ", ".join(port_strings) or "none"

        status.show_message(
            f"Scan {ip} ({mode}): ping {result['ping']['avg']}ms, open ports: {open_ports}"
        )
if __name__ == "__main__":
    NetworkMonitor().run()
