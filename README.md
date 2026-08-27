# Mike OS v0.1

Mike OS is a local-first task system that keeps completed work as permanent,
searchable history. This first vertical slice does not require an AI model or a
paid API.

## Run

Requires Python 3.11 or newer.

```powershell
python run.py
```

Then open <http://127.0.0.1:8765>. Mike OS attempts to open the browser
automatically.

On Windows, you can also double-click `start_mike_os.bat`. On macOS, open
Terminal in the Mike OS folder and run `sh start_mike_os.command`. If macOS
blocks a direct double-click because the file came from another computer, the
Terminal command will still work.

Personal data is stored separately from application code:

- Windows: `%LOCALAPPDATA%\MikeOS\mike_os.db`
- macOS/Linux: `~/.local/share/mike-os/mike_os.db`
- Override: set `MIKE_OS_DATA_DIR` to another directory.

Do not synchronize the live SQLite file with iCloud, Dropbox, or Google Drive.
Use **Export backup** in the application instead.

## Included

- Inbox, Active, Backlog, and Completed task states
- Permanent completion records and append-only task history
- Project, due date, next action, notes, and optional accomplishment marking
- Search and filters
- Deterministic command box (no LLM required)
- JSON backup export
- Local-only server binding by default

Example commands:

- `add Update my LinkedIn due 2026-08-28`
- `complete Update my LinkedIn`
- `move Update my LinkedIn to backlog`
- `show due this week`
- `what did I accomplish this month`
- `find LinkedIn`

## Test

```powershell
python -m unittest discover -s tests -v
```
