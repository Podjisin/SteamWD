# SteamWD

I built SteamWD because the other Steam Workshop downloaders annoyed me. I
originally needed it to download Stellaris mods without dealing with them.

SteamWD is a Windows desktop app that downloads Steam Workshop items and
collections through `steamcmd`.

[![Release](https://github.com/Podjisin/SteamWD/actions/workflows/release.yml/badge.svg)](https://github.com/Podjisin/SteamWD/actions/workflows/release.yml)

## Features

- Download items or collections from Workshop links or IDs
- Expand nested collections
- Download `steamcmd` automatically when it is not installed
- Use anonymous login or a Steam account when a game requires ownership
- Queue multiple items and see their status and progress
- Retry failed items
- Skip items that are already downloaded and up to date
- Choose the output folder, naming format, grouping, and transfer mode
- Keep download history and clean the `steamcmd` cache
- Use light or dark mode

## Using SteamWD

Run `SteamWD.exe`. Python is not required for the standalone executable.
SteamWD downloads `steamcmd` automatically the first time it needs it.

1. Open the Downloads tab.
2. Paste Workshop links or IDs into the input box.
3. Click **Add and start**, or add items to the queue first.
4. Double-click a completed item to open its output folder.

Files are saved to `Downloads\SteamWD` by default. The output location and
other options can be changed in the Settings tab.

## Steam account login

Anonymous login is used by default. Some games only allow Workshop downloads
for accounts that own the game. If needed, select **Steam account** under
**Settings > Steam account** and save your password.

Passwords are stored in Windows Credential Manager. SteamWD asks for a Steam
Guard code when Steam requires one.

## File locations

| Data | Location |
| --- | --- |
| Settings and history | `%APPDATA%\SteamWD\` |
| Logs | `%APPDATA%\SteamWD\logs\` |
| `steamcmd` and download cache | `%LOCALAPPDATA%\SteamWD\` |

These locations can be changed in Settings where supported.

## Development

Python 3.12 or newer is required.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the app:

```powershell
python -m steamwd
```

Run the tests and checks:

```powershell
pytest
ruff check --fix .
ruff format .
mypy src tests
```

Build the standalone executable:

```powershell
scripts\build.ps1
```

The executable is written to `dist\SteamWD.exe`.

## Releases

Releases are created by pushing a version tag such as `v0.1.1` to GitHub. The
release workflow runs the tests, builds `SteamWD.exe`, and publishes a
`SHA256SUMS.txt` file alongside the executable. Verify a download in
PowerShell with:

```powershell
Get-FileHash .\SteamWD.exe -Algorithm SHA256
```

To enable an optional VirusTotal scan, add a repository secret named
`VIRUSTOTAL_API_KEY`. When configured, the workflow uploads the executable to
VirusTotal and includes the resulting `VIRUSTOTAL.json` report in the release.
The scan is skipped when the secret is not configured.

## Limitations

- Downloads depend on what Steam and `steamcmd` make available.
- Some games require the logged-in account to own the game.
- Workshop content may change or disappear after it has been downloaded.

### Malware scan disclosure

Every release is uploaded to VirusTotal for scanning and transparency. SteamWD
is intended solely as a utility tool and has no malicious purpose. Antivirus
engines may occasionally flag unsigned or newly built software as suspicious;
if you are concerned about a release, inspect the public source code and build
workflow yourself, verify the checksum, and review the VirusTotal results
before running it.

## License

See [LICENSE](LICENSE). Do whatever you want with this project.
