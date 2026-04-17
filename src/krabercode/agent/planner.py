"""
Task planning for KraberCode agent.

Handles planning complex multi-step tasks.
"""

from typing import Any, Optional


class TaskPlanner:
    """Plans and tracks multi-step tasks."""
    
    def __init__(self):
        """Initialize task planner."""
        self.tasks: list[dict[str, Any]] = []
    
    def create_plan(self, request: str) -> list[dict[str, Any]]:
        """Create a plan for a complex request."""
        # Simple heuristic: if request mentions multiple steps
        steps = self._extract_steps(request)
        
        tasks = []
        for i, step in enumerate(steps):
            tasks.append({
                "id": str(i + 1),
                "description": step,
                "status": "pending",
            })
        
        self.tasks = tasks
        return tasks
    
    def _extract_steps(self, request: str) -> list[str]:
        """Extract steps from request."""
        # Look for numbered steps or action words
        import re
        
        # Check for numbered list
        numbered = re.findall(r"\d+\.\s+(.+)", request)
        if numbered:
            return [s.strip() for s in numbered]
        
        # Check for action verbs
        actions = ["create", "add", "update", "delete", "fix", "write", "implement", "test", "refactor"]
        steps = []
        
        for action in actions:
            if action in request.lower():
                steps.append(f"Perform {action} operation")
        
        if not steps:
            steps = ["Complete the requested task"]
        
        return steps
    
    def get_next_task(self) -> Optional[dict[str, Any]]:
        """Get the next pending task."""
        for task in self.tasks:
            if task["status"] == "pending":
                return task
        return None
    
    def mark_in_progress(self, task_id: str) -> None:
        """Mark a task as in progress."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "in_progress"
                return
    
    def mark_completed(self, task_id: str) -> None:
        """Mark a task as completed."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "completed"
                return
    
    def add_task(self, description: str) -> None:
        """Add a new task."""
        task_id = str(len(self.tasks) + 1)
        self.tasks.append({
            "id": task_id,
            "description": description,
            "status": "pending",
        })
    
    def get_status_summary(self) -> str:
        """Get summary of task status."""
        pending = sum(1 for t in self.tasks if t["status"] == "pending")
        in_progress = sum(1 for t in self.tasks if t["status"] == "in_progress")
        completed = sum(1 for t in self.tasks if t["status"] == "completed")
        
        return f"Tasks: {pending} pending, {in_progress} in progress, {completed} completed"