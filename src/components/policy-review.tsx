import { serviceMessage } from "@/lib/service-message";

export type PolicyReceipt = {
  action: string;
  phase: string;
  outcome: string;
  detail: string;
  at: number;
  attempt: number;
  plan_sha256?: string;
};

export type Observability = {
  job_id: string;
  runtime: string;
  session_id?: string;
  worker_logs?: string;
  dashboard?: string;
  agent_console?: string;
};

export function PolicyReview({ receipts = [] }: { receipts?: PolicyReceipt[] }) {
  return (
    <details className="lp-policy-review" open>
      <summary>Policy and decision receipts ({receipts.length})</summary>
      {receipts.length ? (
        <ol>
          {receipts.slice().reverse().map((receipt, index) => (
            <li key={index}>
              <strong>{receipt.action.replaceAll("_", " ")} · {receipt.outcome.replaceAll("_", " ")}</strong>
              <p>{serviceMessage(receipt.detail)}</p>
              <p>Attempt {receipt.attempt} · {receipt.phase} · {new Date(receipt.at * 1000).toLocaleTimeString()}</p>
              {receipt.plan_sha256 && <details><summary>Storyboard fingerprint</summary><code style={{ overflowWrap: "anywhere" }}>{receipt.plan_sha256}</code></details>}
            </li>
          ))}
        </ol>
      ) : <p>No policy receipts were recorded for this production. New runs record checks as they execute.</p>}
    </details>
  );
}

export function CloudTraceLinks({ trace }: { trace?: Observability }) {
  if (!trace) return null;
  return <div className="lp-cloud-links">
    <p>Planner runtime: {trace.runtime === "agentcore" ? "Amazon Bedrock AgentCore" : "Worker / local"}</p>
    {trace.session_id && <p>Agent session: <code>{trace.session_id}</code></p>}
    {(trace.worker_logs || trace.dashboard) && <>
      <p>AWS console links require operator access. The job trace and receipts below are available in your workspace.</p>
      <nav aria-label="Cloud diagnostics" style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
        {trace.worker_logs && <a href={trace.worker_logs} target="_blank" rel="noreferrer">Worker logs ↗</a>}
        {trace.dashboard && <a href={trace.dashboard} target="_blank" rel="noreferrer">Operations dashboard ↗</a>}
        {trace.agent_console && <a href={trace.agent_console} target="_blank" rel="noreferrer">Agent metrics ↗</a>}
      </nav>
      <p>Full span tracing requires CloudWatch Transaction Search. See <a href="/verification/">the recorded cloud verification</a> for the tested configuration.</p>
    </>}
  </div>;
}
