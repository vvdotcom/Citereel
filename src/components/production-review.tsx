"use client";
import { FormEvent, useState } from "react";
import { PrelineDisclosure } from "./preline-disclosure";
import { apiEndpoint, apiFetch } from "@/lib/api";
import { serviceMessage } from "@/lib/service-message";

export type ChangeProposal = {
  checked_at: number;
  affected_scenes: number[];
  changes: {
    url: string;
    kind: string;
    before: string | null;
    after: string | null;
  }[];
  decision?: string;
  method: string;
};
export type TestSession = {
  participant: string;
  simulated: boolean;
  production_elapsed_seconds: number;
  revision_requests: number;
  manual_baseline_seconds: number | null;
  notes: string;
};

async function mutate(id: string, suffix: string, body: object) {
  const current = await apiFetch("jobs/" + id).then((r) => r.json());
  const res = await apiFetch("jobs/" + id + suffix, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, version: current.version }),
  });
  const result = await res.json();
  if (!res.ok)
    throw new Error(
      typeof result.detail === "string"
        ? serviceMessage(result.detail)
        : "The request could not be completed.",
    );
  return result;
}

export function WebsiteUpdates({
  job,
  refresh,
}: {
  job: {
    id: string;
    state: string;
    change_proposal?: ChangeProposal;
    capture_reuse?: { reused: number; recorded: number };
  };
  refresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function act(suffix: string, body: object = {}) {
    setBusy(true);
    setError("");
    try {
      await mutate(job.id, suffix, body);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const proposal = job.change_proposal;
  return (
    <section className="lp-updates" aria-label="Website updates">
      <div className="lp-section-heading">
        <h2>Keep this video up to date</h2>
        {["ready_for_review", "approved", "blocked"].includes(job.state) && (
          <button disabled={busy} onClick={() => act("/changes")}>
            Check website for changes
          </button>
        )}
      </div>
      <PrelineDisclosure
        key={job.id + job.state}
        title={
          proposal
            ? proposal.changes.length + " changed pages · Review source details"
            : "How website updates work"
        }
        defaultOpen={job.state === "awaiting_changes_approval"}
      >
        <p>
          Compare the previously inspected pages. Review affected scenes before
          authorizing a Bedrock rewrite. Unchanged recordings and previous
          exports are retained.
        </p>
        {job.capture_reuse && (
          <p>
            {job.capture_reuse.reused} recordings reused ·{" "}
            {job.capture_reuse.recorded} newly captured
          </p>
        )}
        {proposal && (
          <div>
            <p>
              {proposal.changes.length} changed pages · Affected scenes:{" "}
              {proposal.affected_scenes.join(", ") || "none"}
            </p>
            <p>
              Checked {new Date(proposal.checked_at * 1000).toLocaleString()}.{" "}
              {proposal.method}
            </p>
            {proposal.changes.map((change, index) => (
              <details key={index}>
                <summary>
                  {change.kind}: {change.url}
                </summary>
                <div className="lp-diff">
                  <section>
                    <h3>Previous source</h3>
                    <p>{change.before ?? "No previous page"}</p>
                  </section>
                  <section>
                    <h3>Current source</h3>
                    <p>{change.after ?? "Page unavailable or removed"}</p>
                  </section>
                </div>
              </details>
            ))}
            {job.state === "awaiting_changes_approval" && (
              <div className="lp-review-actions">
                <button
                  className="lp-primary"
                  disabled={busy}
                  onClick={() =>
                    act("/decision", { action: "approve_changes" })
                  }
                >
                  {proposal.affected_scenes.length
                    ? "Propose updated storyboard with Bedrock"
                    : "Acknowledge changes"}
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    act("/decision", { action: "dismiss_changes" })
                  }
                >
                  Keep current video
                </button>
              </div>
            )}
            {proposal.decision && (
              <p>Decision: {proposal.decision.replaceAll("_", " ")}</p>
            )}
          </div>
        )}
      </PrelineDisclosure>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export function TrialReview({
  job,
  refresh,
}: {
  job: { id: string; state: string; test_sessions?: TestSession[] };
  refresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await mutate(job.id, "/trial", {
        participant: form.get("participant"),
        notes: form.get("notes"),
        baseline_seconds: form.get("baseline")
          ? Number(form.get("baseline")) * 60
          : null,
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="lp-trials">
      <h2>Simulated founder sessions</h2>
      <p>
        These names are fictional test personas. Timing comes from the actual
        production; this is not customer validation, a testimonial, or evidence
        of real-world time savings.
      </p>
      <form onSubmit={save}>
        <label>
          Fictional participant
          <select name="participant">
            {[
              "Maya Chen",
              "Jordan Brooks",
              "Sam Patel",
              "Alex Rivera",
              "Taylor Morgan",
            ].map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          Manual baseline, minutes (optional)
          <input
            type="number"
            name="baseline"
            min="0.1"
            step="0.1"
            placeholder="Leave blank if not measured"
          />
        </label>
        <label>
          Test observations
          <textarea
            name="notes"
            maxLength={1000}
            placeholder="What worked, corrections needed, and any failures"
          />
        </label>
        <button
          disabled={
            busy || !["ready_for_review", "approved"].includes(job.state)
          }
        >
          Save simulated test session
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {job.test_sessions?.map((session, index) => (
        <article key={index}>
          <h3>{session.participant} · fictional test persona</h3>
          <p>
            Production elapsed:{" "}
            {(session.production_elapsed_seconds / 60).toFixed(1)} minutes,
            including waits and review. Revision requests:{" "}
            {session.revision_requests}.
          </p>
          <p>
            Manual baseline:{" "}
            {session.manual_baseline_seconds == null
              ? "not measured"
              : (session.manual_baseline_seconds / 60).toFixed(1) +
                " minutes (tester-entered)"}
          </p>
          <p>{session.notes}</p>
        </article>
      ))}
      <a href={apiEndpoint("jobs/" + job.id + "/receipt")} download>
        Download receipt and test sessions
      </a>
    </section>
  );
}
