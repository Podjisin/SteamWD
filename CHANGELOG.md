# Changelog

## [Unreleased]

## [0.2.0] - 2026-10-02

### Added
- Automatic game-specific mod processors with a generic fallback for unsupported games.
- Stellaris processing for the user `mod` folder, including generated `.mod` descriptors.
- RimWorld processing for the user `Mods` folder while preserving `About\About.xml` metadata.
- Supported Games settings view with configurable processor destinations.
- Processor names in the download queue so automatic routing is visible.
- Info tab with GitHub, issue reporting, contribution, and license links.
- Contributor guide for creating game processor modules.

### Fixed
- Wrapped long processor destination paths in the Supported Games settings section.
- Stellaris launcher descriptors now preserve metadata from the downloaded `descriptor.mod`.

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
