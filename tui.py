import asyncio
import subprocess

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input, Static
from textual.containers import Container

from scanner import scan_network


class CommandBar(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_command = ""

    def compose(self):
        yield Input(placeholder="Enter Command>", id="command_input")

    async def on_input_submitted(self, message: Input.Submitted):
        self.last_command = message.value.strip().lower()

        if self.last_command in ("quit", "exit"):
            self.app.exit()
            return

        if self.last_command.startswith("autorefresh="):
            value = self.last_command.split("=")[1]
            if value == "1":
                await self.app.set_auto_refresh(True)
                print("Auto-refresh ON")
            elif value == "0":
                await self.app.set_auto_refresh(False)
                print("Auto-refresh OFF")

            self.query_one("#command_input").value = ""
            return

        print(f"Command: {self.last_command}")
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

        # RUN IN BACKGROUND (PATCH)
        self.run_worker(self.refresh_devices, exclusive=True)

    async def refresh_devices(self):
        status = self.query_one(StatusBar)
        status.show_message("Scanning network...")

        # RUN SLOW SCAN IN BACKGROUND (PATCH)
        devices = await scan_network()

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
        # RUN IN BACKGROUND (PATCH)
        self.run_worker(self.refresh_devices, exclusive=True)

    async def auto_refresh_loop(self):
        while self.auto_refresh:
            # RUN IN BACKGROUND (PATCH)
            self.run_worker(self.refresh_devices, exclusive=True)

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


if __name__ == "__main__":
    NetworkMonitor().run()
