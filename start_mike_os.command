#!/bin/sh

# Mike OS one-click launcher for macOS.
# It starts the local server in the background and opens the browser.
cd "$(dirname "$0")" || exit 1
URL="http://127.0.0.1:8765"

# If Mike OS is already running, simply open it.
if curl -fsS "$URL/api/tasks" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

# Start Mike OS independently of this Terminal window.
nohup python3 run.py > mike_os.log 2>&1 < /dev/null &

# Wait briefly for the server. server.py also opens the browser itself;
# this fallback makes the launcher reliable if that browser call is delayed.
i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS "$URL/api/tasks" >/dev/null 2>&1; then
    open "$URL"
    exit 0
  fi
  i=$((i + 1))
  sleep 0.2
done

printf '\nMike OS did not start successfully.\nCheck this log for details:\n%s/mike_os.log\n\n' "$(pwd)"
printf 'Press Return to close this window.'
read _
exit 1
