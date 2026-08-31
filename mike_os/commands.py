from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from .db import TaskStore


class CommandProcessor:
    def __init__(self, store: TaskStore):
        self.store = store

    def _match_task(self, phrase: str) -> dict[str, Any]:
        matches = self.store.list(query=phrase.strip())
        exact = [task for task in matches if task["title"].lower() == phrase.strip().lower()]
        if len(exact) == 1:
            return exact[0]
        open_matches = [task for task in matches if task["status"] != "completed"]
        candidates = open_matches or matches
        if not candidates:
            raise ValueError(f'I could not find a task matching "{phrase.strip()}".')
        if len(candidates) > 1:
            titles = ", ".join(task["title"] for task in candidates[:4])
            raise ValueError(f"That matches more than one task: {titles}. Please use the exact title.")
        return candidates[0]

    def execute(self, text: str) -> dict[str, Any]:
        original = text.strip()
        lower = original.lower()
        if not original:
            raise ValueError("Enter a command.")

        add = re.match(r"^(?:add|create|remember)(?: task)?\s+(.+)$", original, re.I)
        if add:
            title = add.group(1).strip()
            target_date = None
            due = re.search(r"\s+due\s+(\d{4}-\d{2}-\d{2})$", title, re.I)
            if due:
                target_date = due.group(1)
                title = title[:due.start()].strip()
            task = self.store.create({"title": title, "target_date": target_date}, source="command")
            return {"message": f'Added "{task["title"]}" to Inbox.', "tasks": [task], "changed": True}

        complete = re.match(r"^(?:complete|finish|finished|done with)\s+(.+?)(?:\s+(?:today|yesterday))?$", original, re.I)
        if complete:
            task = self._match_task(complete.group(1))
            completed_at = None
            if lower.endswith(" yesterday"):
                completed_at = (date.today() - timedelta(days=1)).isoformat() + "T12:00:00+00:00"
            task = self.store.update(task["id"], {"status": "completed", "completed_at": completed_at}, source="command")
            return {"message": f'Completed "{task["title"]}". It remains in your history.', "tasks": [task], "changed": True}

        move = re.match(r"^move\s+(.+?)\s+to\s+(inbox|active|backlog|completed)$", original, re.I)
        if move:
            task = self._match_task(move.group(1))
            status = move.group(2).lower()
            task = self.store.update(task["id"], {"status": status}, source="command")
            return {"message": f'Moved "{task["title"]}" to {status.title()}.', "tasks": [task], "changed": True}

        if re.search(r"(?:due|next two weeks|this week)", lower):
            days = 14 if "two weeks" in lower else 7
            end = date.today() + timedelta(days=days)
            tasks = [task for task in self.store.list() if task["status"] != "completed" and task["target_date"] and date.fromisoformat(task["target_date"][:10]) <= end]
            return {"message": f"Found {len(tasks)} unfinished task{'s' if len(tasks) != 1 else ''} due by {end.isoformat()}.", "tasks": tasks, "changed": False}

        if "accomplish" in lower or ("completed" in lower and ("month" in lower or "today" in lower)):
            today = date.today()
            start = today.replace(day=1) if "month" in lower else today
            tasks = [task for task in self.store.list(status="completed") if task["completed_at"] and date.fromisoformat(task["completed_at"][:10]) >= start]
            return {"message": f"You completed {len(tasks)} task{'s' if len(tasks) != 1 else ''} since {start.isoformat()}.", "tasks": tasks, "changed": False}

        find = re.match(r"^(?:find|search(?: for)?|show)\s+(.+)$", original, re.I)
        query = find.group(1) if find else original
        tasks = self.store.list(query=query)
        return {"message": f"Found {len(tasks)} matching task{'s' if len(tasks) != 1 else ''}.", "tasks": tasks, "changed": False}

