# Audient iD Volume Control

An unofficial Windows tray utility that controls the **hardware monitor volume** of Audient iD USB audio interfaces. It keeps the Windows mixer at 100% while providing a convenient software slider, global hotkeys, mute, and automatic recovery after sleep or a USB reconnect.

> [!WARNING]
> This project is unofficial and is not affiliated with or endorsed by Audient Ltd. Audient and iD are trademarks of their respective owners.

## Features

- Direct control of the hardware monitor level through the installed Audient USB driver
- Tray slider with a user-defined safe volume ceiling
- `Ctrl+Alt+Up` and `Ctrl+Alt+Down` volume hotkeys
- `Ctrl+Alt+M` mute toggle
- Compact on-screen volume indicator
- Automatic reconnection and restoration after sleep or USB reset
- Optional startup with Windows
- Single-instance protection

## Requirements

- Windows 10 or Windows 11, 64-bit
- Audient iD14 MKII (verified)
- Audient iD4 MKII, iD24, or iD44 MKII may work but are not yet verified
- The official Audient USB audio driver / iD application installed

The Audient driver DLL is **not** included. By default the app loads:

```text
C:\Program Files\Audient\USBAudioDriver\x64\audientusbaudioapi_x64.dll
```

Most users do not need to configure anything. If the driver DLL is installed elsewhere, set the `AUDIENT_USB_AUDIO_DLL` environment variable to its full path, then restart the app:

```powershell
setx AUDIENT_USB_AUDIO_DLL "D:\Path\To\audientusbaudioapi_x64.dll"
```

## Installation

1. Install the official Audient driver and confirm that the interface works in the Audient iD application.
2. Download `audient-id-volume-control-windows.zip` from the latest GitHub release.
3. Extract the entire ZIP file.
4. Run `audient-id-volume-control.exe` from the extracted folder. Keep the `_internal` folder next to the executable.
5. Open the tray icon and choose **Use current level as ceiling** after setting a comfortable maximum level with the physical knob.
6. Optionally enable **Start with Windows** from the tray menu.

The first launch treats the current hardware level as the safe 100% ceiling. The application never intentionally raises the monitor level above that saved ceiling.

## Hotkeys

| Shortcut | Action |
| --- | --- |
| `Ctrl+Alt+Up` | Increase volume by 5% |
| `Ctrl+Alt+Down` | Decrease volume by 5% |
| `Ctrl+Alt+M` | Mute or restore the previous level |

These shortcuts can be assigned to mouse buttons through software such as Logitech Options+.

## Configuration

Settings are stored per user in:

```text
%APPDATA%\Audient iD Volume Control\config.json
```

The configuration contains only the safe ceiling and the last selected volume percentage.

## Build from source

Install Python 3.11 or newer, then run:

```powershell
git clone https://github.com/ph4113n/audient-id-volume-control.git
cd audient-id-volume-control
.\build.ps1
```

The distributable ZIP archive will be created at `dist\audient-id-volume-control-windows.zip`.

The app is intentionally distributed as a normal ZIP containing a folder build. It does not use a self-extracting executable.

## Compatibility and safety

The USB control identifiers used by this project were verified on an Audient iD14 MKII. The iD4 MKII, iD24, and iD44 MKII use the same Audient driver family and may work, but their monitor-volume control identifiers have not been verified yet. Treat those models as experimental and report the exact model and driver version when opening an issue.

Start with playback stopped or at a low level when testing a new driver version. Audio hardware control software can change the physical output level immediately.

## License

The project source code is licensed under the [MIT License](LICENSE). The Audient driver and its DLL remain the property of Audient and are not redistributed by this project.
