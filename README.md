# iD14 Volume Control

An unofficial Windows tray utility that controls the **hardware monitor volume** of an Audient iD14 MKII. It keeps the Windows mixer at 100% while providing a convenient software slider, global hotkeys, mute, and automatic recovery after sleep or a USB reconnect.

> [!WARNING]
> This project is unofficial and is not affiliated with or endorsed by Audient Ltd. Audient and iD14 are trademarks of their respective owners.

## Features

- Direct control of the iD14 MKII monitor level through the installed Audient USB driver
- Tray slider with a user-defined safe volume ceiling
- `Ctrl+Alt+Up` and `Ctrl+Alt+Down` volume hotkeys
- `Ctrl+Alt+M` mute toggle
- Compact on-screen volume indicator
- Automatic reconnection and restoration after sleep or USB reset
- Optional startup with Windows
- Single-instance protection

## Requirements

- Windows 10 or Windows 11, 64-bit
- Audient iD14 MKII
- The official Audient USB audio driver / iD application installed

The Audient driver DLL is **not** included. By default the app loads:

```text
C:\Program Files\Audient\USBAudioDriver\x64\audientusbaudioapi_x64.dll
```

For a custom driver location, set the `AUDIENT_USB_AUDIO_DLL` environment variable to the full DLL path.

## Installation

1. Install the official Audient driver and confirm that the iD14 works in the Audient iD application.
2. Download `id14-volume-control.exe` from the latest GitHub release.
3. Run the app. It starts in the notification area.
4. Open the tray icon and choose **Use current level as ceiling** after setting a comfortable maximum level with the physical knob.
5. Optionally enable **Start with Windows** from the tray menu.

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
%APPDATA%\iD14 Volume\config.json
```

The configuration contains only the safe ceiling and the last selected volume percentage.

## Build from source

Install Python 3.11 or newer, then run:

```powershell
git clone https://github.com/ph4113n/id14-volume-control.git
cd id14-volume-control
.\build.ps1
```

The executable will be created at `dist\id14-volume-control.exe`.

## Compatibility and safety

The USB control identifiers used by this project were verified on an Audient iD14 MKII. Other Audient models and future driver versions may use different controls and are not currently supported.

Start with playback stopped or at a low level when testing a new driver version. Audio hardware control software can change the physical output level immediately.

## License

The project source code is licensed under the [MIT License](LICENSE). The Audient driver and its DLL remain the property of Audient and are not redistributed by this project.
