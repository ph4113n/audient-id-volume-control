import argparse
import ctypes as c
import os
import sys
from pathlib import Path


ENTITY_ID = 0x36
REQUEST_CUR = 0x01
CONTROL_SELECTOR = 0x12
CHANNEL = 0
TIMEOUT_MS = 10_000


class AudientError(RuntimeError):
    pass


def find_driver_dll() -> Path:
    override = os.environ.get("AUDIENT_USB_AUDIO_DLL")
    candidates = []
    if override:
        candidates.append(Path(override))

    for variable in ("ProgramFiles", "ProgramW6432"):
        root = os.environ.get(variable)
        if root:
            candidates.append(
                Path(root)
                / "Audient"
                / "USBAudioDriver"
                / "x64"
                / "audientusbaudioapi_x64.dll"
            )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise AudientError(
        "Audient USB driver DLL was not found. Install the official Audient "
        "driver or set AUDIENT_USB_AUDIO_DLL.\nSearched:\n" + searched
    )


class AudientId14:
    def __init__(self, dll_path: Path | None = None):
        self.dll_path = Path(dll_path) if dll_path else find_driver_dll()
        self.dll = c.WinDLL(str(self.dll_path))
        self.enumerate_devices = self._bind("TUSBAUDIO_EnumerateDevices", c.c_uint32)
        self.get_device_count = self._bind("TUSBAUDIO_GetDeviceCount", c.c_uint32)
        self.open_device = self._bind(
            "TUSBAUDIO_OpenDeviceByIndex",
            c.c_uint32,
            c.c_uint32,
            c.POINTER(c.c_uint32),
        )
        self.close_device = self._bind(
            "TUSBAUDIO_CloseDevice", c.c_uint32, c.c_uint32
        )
        request_args = (
            c.c_uint32,
            c.c_uint8,
            c.c_uint8,
            c.c_uint8,
            c.c_uint8,
            c.c_void_p,
            c.c_uint32,
            c.POINTER(c.c_uint32),
            c.c_uint32,
        )
        self.request_get = self._bind(
            "TUSBAUDIO_AudioControlRequestGet", c.c_uint32, *request_args
        )
        self.request_set = self._bind(
            "TUSBAUDIO_AudioControlRequestSet", c.c_uint32, *request_args
        )
        self.status_string = self._bind(
            "TUSBAUDIO_StatusCodeStringA", c.c_char_p, c.c_uint32
        )
        self.handle = None

    def _bind(self, name, restype, *argtypes):
        function = getattr(self.dll, name)
        function.restype = restype
        function.argtypes = list(argtypes)
        return function

    def _status(self, code):
        raw = self.status_string(code)
        return raw.decode(errors="replace") if raw else f"status {code:#x}"

    def _check(self, code, operation):
        if code != 0:
            raise AudientError(f"{operation}: {code:#x} {self._status(code)}")

    def __enter__(self):
        self._check(self.enumerate_devices(), "EnumerateDevices")
        count = self.get_device_count()
        if count < 1:
            raise AudientError("No compatible Audient device was found")
        handle = c.c_uint32()
        self._check(self.open_device(0, c.byref(handle)), "OpenDeviceByIndex")
        self.handle = handle.value
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def close(self):
        if self.handle is not None:
            self.close_device(self.handle)
            self.handle = None

    def _request(self, function, value):
        if self.handle is None:
            raise AudientError("The Audient device is not open")
        transferred = c.c_uint32()
        code = function(
            self.handle,
            ENTITY_ID,
            REQUEST_CUR,
            CONTROL_SELECTOR,
            CHANNEL,
            c.byref(value),
            c.sizeof(value),
            c.byref(transferred),
            TIMEOUT_MS,
        )
        self._check(code, function.__name__)
        if transferred.value != c.sizeof(value):
            raise AudientError(
                f"{function.__name__}: transferred {transferred.value} bytes, "
                f"expected {c.sizeof(value)}"
            )

    def get_raw(self) -> int:
        value = c.c_int16()
        self._request(self.request_get, value)
        return value.value

    def set_raw(self, raw: int):
        if not -32768 <= raw <= 0:
            raise ValueError("Raw volume must be between -32768 and 0")
        self._request(self.request_set, c.c_int16(raw))

    def get_db(self) -> float:
        return self.get_raw() / 256.0

    def set_db(self, db: float):
        if not -128.0 <= db <= 0.0:
            raise ValueError("Volume must be between -128 dB and 0 dB")
        self.set_raw(round(db * 256))


def main():
    parser = argparse.ArgumentParser(description="Audient iD14 MKII monitor volume")
    parser.add_argument("command", choices=("get", "set-db", "self-test"))
    parser.add_argument("value", nargs="?", type=float)
    args = parser.parse_args()

    with AudientId14() as device:
        if args.command == "get":
            raw = device.get_raw()
            print(f"{raw / 256:.2f} dB (raw {raw}, 0x{raw & 0xFFFF:04x})")
        elif args.command == "set-db":
            if args.value is None:
                parser.error("set-db requires a dB value")
            device.set_db(args.value)
            print(f"Set to {device.get_db():.2f} dB")
        else:
            original = device.get_raw()
            quieter = max(-32768, original - 256)
            print(f"Original: {original / 256:.2f} dB")
            try:
                device.set_raw(quieter)
                print(f"Test:     {device.get_db():.2f} dB")
            finally:
                device.set_raw(original)
            print(f"Restored: {device.get_db():.2f} dB")


if __name__ == "__main__":
    try:
        main()
    except (AudientError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
