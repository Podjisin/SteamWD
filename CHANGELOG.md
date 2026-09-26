# Changelog

## [Unreleased]

## [0.1.0] - 2026-09-26

### Added
- Tkinter GUI with Downloads, Settings and Log tabs, and light and dark themes.
- Download Workshop items and collections (including nested ones) from links or IDs through steamcmd.
- Automatic steamcmd download and bootstrap.
- Download queue with per-item status, batching, automatic retries, Stop, Retry failed and Clear finished.
- Anonymous or account login; passwords stored in Windows Credential Manager; Steam Guard prompt.
- Configurable output folder, naming template, grouping, copy/move/leave, cache cleanup and skipping up-to-date items.
- Download history, used to skip items that haven't changed.
- Settings stored in `%APPDATA%\SteamWD`, with validation, reset, import and export.
- Log files with secret redaction.
- PyInstaller build script for a standalone `SteamWD.exe`.
