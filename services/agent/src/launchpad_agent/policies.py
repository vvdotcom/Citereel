"""Strands runtime controls; prompts cannot override these checks."""
import threading
from strands.hooks import HookProvider, BeforeToolCallEvent, AfterToolCallEvent, BeforeModelCallEvent
from launchpad_api.audit import policy


class ProductionPolicy(HookProvider):
    def __init__(self, db, job_id):
        self.db, self.job_id = db, job_id
        self.calls = 0
        self.lock = threading.Lock()
        self.completed = set()

    def register_hooks(self, registry):
        registry.add_callback(BeforeToolCallEvent, self.before_tool)
        registry.add_callback(AfterToolCallEvent, self.after_tool)
        registry.add_callback(BeforeModelCallEvent, self.before_model)

    def before_model(self, event):
        self.db.check(self.job_id)
        job = self.db.get(self.job_id)
        if job.get("needs_decision") or self.calls >= 10:
            event.cancel = "Human decision or tool budget reached. Stop planning."
        policy(self.db, self.job_id, "model_call", "before", "blocked" if event.cancel else "passed",
               "Maximum 8 turns and 45,000 total tokens; cancellation checked")

    def before_tool(self, event):
        self.db.check(self.job_id)
        name = event.tool_use["name"]
        with self.lock:
            self.calls += 1
            job = self.db.get(self.job_id)
            reason = None
            if self.calls > 10:
                reason = "Ten-tool-call limit reached."
            elif job.get("needs_decision") or job.get("plan"):
                reason = "Planning is complete or waiting for a human decision."
            elif name == "submit_storyboard" and not {"get_production_brief", "inspect_authorized_site"} <= self.completed:
                reason = "Read the brief and inspect sources before submitting a storyboard."
            if reason:
                event.cancel_tool = reason
        policy(self.db, self.job_id, name, "before", "blocked" if reason else "passed",
               reason or "Scoped tool; authorization, prerequisite order and call budget checked")

    def after_tool(self, event):
        name = event.tool_use["name"]
        failed = event.exception or event.cancel_message or event.result.get("status") == "error"
        # A schema-rejected submission is a tool success at transport level, but
        # not a saved storyboard. Record the actual postcondition.
        if name == "submit_storyboard" and not self.db.get(self.job_id).get("plan"):
            failed = True
        if not failed:
            with self.lock:
                self.completed.add(name)
        policy(self.db, self.job_id, name, "after", "blocked" if failed else "passed",
               "Tool did not satisfy its postcondition" if failed else "Tool postcondition verified")
