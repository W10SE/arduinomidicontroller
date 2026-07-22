import threading
import queue
import serial
import serial.tools.list_ports


class SerialLink:
    """Owns the serial connection and a background reader thread.

    It just moves raw text lines (or hex-encoded raw bytes when in MIDI mode) onto a
    thread-safe queue for something else to consume via poll().
    """

    def __init__(self, baud: int):
        self.baud = baud
        self.ser = None
        self.running = False
        self.conn_id = 0  # bumped on connect/disconnect to invalidate stale threads
        self.mode = "DEBUG"  # "DEBUG" (text) or "MIDI" (raw bytes -> hex)
        self.rx_queue = queue.Queue()

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    @property
    def is_connected(self):
        return bool(self.ser and self.ser.is_open)

    def connect(self, port: str):
        """Returns None on success, or the Exception on failure."""
        try:
            self.ser = serial.Serial(port, self.baud, timeout=0.1)
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass
            self.running = True
            self.conn_id += 1
            my_id = self.conn_id
            threading.Thread(target=self._read_loop, args=(my_id,), daemon=True).start()
            return None
        except serial.SerialException as e:
            return e

    def disconnect(self):
        self.running = False
        self.conn_id += 1
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def set_mode(self, mode: str):
        self.mode = mode

    def send(self, line: str):
        if self.is_connected:
            try:
                self.ser.write((line + "\n").encode())
            except Exception as e:
                self.rx_queue.put(f"WRITE ERROR: {e}")

    def _read_loop(self, my_id: int):
        while self.running and my_id == self.conn_id and self.ser and self.ser.is_open:
            try:
                if self.mode == "MIDI":
                    n = self.ser.in_waiting or 1
                    data = self.ser.read(n)
                    if data:
                        hex_str = " ".join(f"{b:02X}" for b in data)
                        self.rx_queue.put(f"MIDI: {hex_str}")
                else:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if line:
                        self.rx_queue.put(line)
            except Exception as e:
                # Catches SerialException AND the Windows pyserial close-race
                # (AttributeError on hEvent) without crashing the thread.
                self.rx_queue.put(f"READ ERROR: {e}")
                break

    def poll(self):
        """Drain and return all currently queued raw lines (non-blocking)."""
        lines = []
        while not self.rx_queue.empty():
            lines.append(self.rx_queue.get())
        return lines
