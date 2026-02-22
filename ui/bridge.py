"""
YantraOS — IPC Bridge
Model Route: Claude Opus 4.6

Asynchronous IPC client connecting the Yantra Shell TUI to the Daemon
via UNIX Domain Sockets. Fetches telemetry and reasoning blocks.
"""

import asyncio
import json
import logging

class IPCBridge:
    def __init__(self, socket_path: str = "/tmp/yantra.sock"):
        self.socket_path = socket_path
        self.reader = None
        self.writer = None
        self.connected = False

    async def connect(self):
        """Establish asynchronous connection to the YantraOS daemon."""
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
            self.connected = True
            logging.info(f"IPC connected to {self.socket_path}")
            return True
        except Exception as e:
            logging.error(f"IPC Connection failed: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Close the socket connection."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False
        self.reader = None
        self.writer = None

    async def send_command(self, action: str, payload: dict = None) -> dict:
        """Send a JSON command to the daemon and await response."""
        if not self.connected:
            await self.connect()
            if not self.connected:
                return {"error": "Not connected to daemon"}

        msg = {
            "action": action,
            "payload": payload or {}
        }
        
        try:
            data = json.dumps(msg).encode('utf-8')
            self.writer.write(data + b'\n')
            await self.writer.drain()

            # Wait for response
            response_data = await self.reader.readline()
            if not response_data:
                await self.disconnect()
                return {"error": "Connection lost"}
                
            return json.loads(response_data.decode('utf-8'))
            
        except Exception as e:
            await self.disconnect()
            return {"error": str(e)}

    async def fetch_telemetry(self) -> dict:
        """Fetch the latest telemetry snapshot from the daemon."""
        res = await self.send_command("get_telemetry")
        if "error" in res:
            return {}
        return res.get("data", {})