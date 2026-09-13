"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { BrandMark } from "./brand-mark";
import { apiEndpoint, apiFetch } from "@/lib/api";
import { serviceMessage } from "@/lib/service-message";
import "./workspace.css";
import {
  PolicyReview,
  CloudTraceLinks,
  type PolicyReceipt,
  type Observability,
} from "./policy-review";
import { PrelineDisclosure } from "./preline-disclosure";
import {
  WebsiteUpdates,
  type ChangeProposal,
  type TestSession,
} from "./production-review";

type Scene = {
  title: string;
  on_screen_copy: string;
  narration: string;
  source_ids: string[];
  page_id: string;
  scroll: "top" | "middle" | "bottom";
};
type Source = {
  id: string;
  page_id: string;
  url: string;
  title: string;
  excerpt: string;
  sha256: string;
  fixture: boolean;
};
type Claim = {
  scene: number;
  kind: "title" | "on_screen_copy" | "narration";
  claim: string;
  status: "source_matched" | "needs_review";
  explanation: string;
  matches?: { source_id: string; quote: string }[];
  sources: {
    id: string;
    title: string;
    url: string;
    sha256: string;
    excerpt: string;
  }[];
};
type Trace = { component: string; event: string; detail: string; at: number };
type Artifact = {
  attempt: number;
  folder: string;
  qa: {
    duration_seconds: number;
    width: number;
    height: number;
    sha256: string;
    bytes: number;
    captions: string;
    voices: {
      provider: string;
      voice?: string;
      voice_style?: "female" | "male";
      engine?: string;
    }[];
  };
};
type Job = {
  id: string;
  state: string;
  version: number;
  attempt: number;
  created_at: number;
  updated_at: number;
  request: {
    title: string;
    website_url: string;
    format: string;
    duration_seconds: number;
    orientation: string;
    narration_voice?: "female" | "male";
    narration_mode?: "voice" | "silent";
    brief: string;
    brand?: { name: string; primary_color: string };
  };
  error: string | null;
  timeline: { stage: string; detail: string; at: number }[];
  evidence: Source[];
  plan: { scenes: Scene[] } | null;
  artifacts: Artifact[];
  tool_receipts: { tool: string; detail: string; at: number }[];
  claim_ledger?: Claim[];
  change_proposal?: ChangeProposal;
  test_sessions?: TestSession[];
  capture_reuse?: { reused: number; recorded: number };
  trace?: Trace[];
  policy_receipts?: PolicyReceipt[];
  observability?: Observability;
  budget?: { tool_calls: number; planning_tokens: number };
  capture_events?: {
    action: string;
    page_id?: string;
    position?: string;
    scene: number;
  }[];
  planner?: string;
  model?: string;
  model_usage?: {
    totalTokens: number;
    inputTokens: number;
    outputTokens: number;
  };
  monitor?: {
    enabled: boolean;
    interval_hours: number;
    next_check_at: number | null;
  };
};
type Settings = {
  bedrock_configured: boolean;
  model: string;
  region: string;
  voice: string;
  fixture: string;
  allowed_origins: string[];
  daily_job_limit: number;
  max_video_duration_seconds: number;
};
type View = "create" | "jobs" | "projects" | "settings";
const activeStates = [
  "queued",
  "inspecting",
  "researching",
  "planning",
  "capturing",
  "narrating",
  "rendering",
  "quality_check",
];
const stageNames = [
  "inspecting",
  "researching",
  "planning",
  "capturing",
  "narrating",
  "rendering",
  "quality_check",
];
const human = (value: string) =>
  value.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
const artifactURL = (job: Job, artifact: Artifact, file: string) =>
  apiEndpoint(`jobs/${job.id}/artifacts/${artifact.attempt}/${file}`);

const progressByStage: Record<string, number> = {
  queued: 2,
  inspecting: 8,
  researching: 18,
  planning: 30,
  awaiting_plan_approval: 40,
  capturing: 48,
  narrating: 72,
  rendering: 84,
  quality_check: 94,
  ready_for_review: 100,
  approved: 100,
  awaiting_changes_approval: 100,
  cancelled: 100,
};

function jobProgress(job: Job) {
  if (job.state === "blocked" || job.state === "failed") {
    const previous = job.timeline
      .slice()
      .reverse()
      .find((entry) => !["blocked", "failed"].includes(entry.stage));
    return progressByStage[previous?.stage ?? "queued"] ?? 2;
  }
  if (job.state === "capturing") {
    const detail = job.timeline.at(-1)?.detail ?? "";
    const match = detail.match(/recording (\d+) of (\d+)/i);
    if (match)
      return 48 + Math.round((Number(match[1]) / Number(match[2])) * 20);
  }
  return progressByStage[job.state] ?? 2;
}

function elapsed(job: Job) {
  const finished = [
    "ready_for_review",
    "approved",
    "blocked",
    "failed",
    "cancelled",
  ].includes(job.state);
  const seconds = Math.max(
    0,
    Math.round(
      (finished ? job.updated_at : Date.now() / 1000) - job.created_at,
    ),
  );
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

function JobProgress({
  job,
  compact = false,
}: {
  job: Job;
  compact?: boolean;
}) {
  const value = jobProgress(job);
  return (
    <div className={`lp-job-progress ${compact ? "compact" : ""}`}>
      <div>
        <span>{human(job.state)}</span>
        <output>{value}%</output>
      </div>
      <progress aria-label="Job progress" max={100} value={value} />
      {!compact && <p>Stage progress, not an estimated completion time.</p>}
    </div>
  );
}

function JobReport({ job }: { job: Job }) {
  const latest = job.timeline.at(-1);
  return (
    <section className="lp-job-report" aria-labelledby="job-report-title">
      <header>
        <div>
          <h2 id="job-report-title">Job report</h2>
          <p>Saved with this production and refreshed automatically.</p>
        </div>
        <a href={apiEndpoint(`jobs/${job.id}/receipt`)} download>
          Download report (.json)
        </a>
      </header>
      <JobProgress job={job} />
      <p className="lp-job-current" role="status">
        {serviceMessage(
          job.error || latest?.detail || "Waiting for the first saved update.",
        )}
      </p>
      <dl>
        <div>
          <dt>Job</dt>
          <dd>
            <code>{job.id}</code>
          </dd>
        </div>
        <div>
          <dt>Attempt</dt>
          <dd>{job.attempt}</dd>
        </div>
        <div>
          <dt>Elapsed</dt>
          <dd>{elapsed(job)}</dd>
        </div>
        <div>
          <dt>Last saved</dt>
          <dd>{new Date(job.updated_at * 1000).toLocaleString()}</dd>
        </div>
      </dl>
      <details
        open={
          activeStates.includes(job.state) ||
          ["blocked", "failed"].includes(job.state)
        }
      >
        <summary>Activity log ({job.timeline.length} saved updates)</summary>
        <div
          className="lp-job-log"
          role="region"
          aria-label="Timestamped activity log"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Stage</th>
                <th>Update</th>
              </tr>
            </thead>
            <tbody>
              {job.timeline
                .slice()
                .reverse()
                .map((entry, index) => (
                  <tr key={`${entry.at}-${index}`}>
                    <td>
                      <time>
                        {new Date(entry.at * 1000).toLocaleTimeString()}
                      </time>
                    </td>
                    <td>{human(entry.stage)}</td>
                    <td>{serviceMessage(entry.detail)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await apiFetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? serviceMessage(result.detail)
        : "The request could not be completed. Check the form and try again.",
    );
  return result;
}

function Glyph({ name }: { name: string }) {
  const paths: Record<string, string> = {
    create: "M12 3v18M3 12h18",
    jobs: "M4 5h16v15H4zM8 2v6M16 2v6M8 12h8M8 16h5",
    projects: "M3 6h7l2 3h9v11H3z",
    settings: "M4 7h16M4 17h16M8 4v6M16 14v6",
    play: "M8 4l13 8-13 8z",
    arrow: "M4 12h16M14 6l6 6-6 6",
    check: "M5 12l4 4L19 6",
  };
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name] || paths.projects} />
    </svg>
  );
}

export function Workspace({ initialView = "create" }: { initialView?: View }) {
  const [view, setView] = useState<View>(initialView);
  const [session, setSession] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewMark, setReviewMark] = useState("");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<
    "preview" | "storyboard" | "claims" | "sources" | "trace" | "receipts"
  >("preview");
  const [draft, setDraft] = useState<Scene[] | null>(null);
  const [selectedAttempt, setSelectedAttempt] = useState<number | null>(null);
  const [source, setSource] = useState("");
  const [brandName, setBrandName] = useState("");
  const [brandColor, setBrandColor] = useState("#ff9900");
  const [format, setFormat] = useState("presentation");
  const [narrationChoice, setNarrationChoice] = useState("female");
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const formRef = useRef<HTMLFormElement>(null);
  const job =
    view === "create"
      ? undefined
      : (jobs.find((j) => j.id === selected) ?? jobs[0]);
  const artifact =
    job?.artifacts.find((a) => a.attempt === selectedAttempt) ??
    job?.artifacts.at(-1);

  const refresh = useCallback(async () => {
    const results = await api<Job[]>("jobs");
    setJobs(results);
  }, []);
  useEffect(() => {
    let active = true;
    api("session")
      .then(() => {
        if (active) setSession(true);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!session) return;
    let stopped = false;
    const update = () =>
      refresh().catch((e) => {
        if (!stopped) setNotice(e.message);
      });
    void update();
    api<Settings>("settings")
      .then(setSettings)
      .catch((e) => setNotice(e.message));
    const timer = setInterval(update, 2500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [session, refresh]);

  async function auth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api("session/" + authMode, "POST", {
        email: data.get("email"),
        password: data.get("password"),
      });
      setSession(true);
      setNotice("");
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    const data = new FormData(event.currentTarget);
    try {
      const request = {
        title: data.get("title"),
        website_url: source,
        authorization_confirmed: data.get("authorization") === "on",
        brief: data.get("brief"),
        audience: data.get("audience"),
        duration_seconds: Number(data.get("duration")),
        tone: data.get("tone"),
        narration_voice:
          narrationChoice === "silent" ? "female" : narrationChoice,
        narration_mode: narrationChoice === "silent" ? "silent" : "voice",
        visual_style: data.get("visual_style"),
        format,
        orientation: data.get("orientation"),
        call_to_action: data.get("cta"),
        captions: narrationChoice !== "silent" && data.get("captions") === "on",
        zoom: false,
        review_plan: data.get("review") === "on",
        brand: {
          name: data.get("brand_name"),
          primary_color: data.get("brand_color"),
        },
        idempotency_key: crypto.randomUUID(),
      };
      const next = await api<Job>("jobs", "POST", {
        request,
        planner_mode: "bedrock",
      });
      setSelected(next.id);
      setTab("preview");
      setDraft(null);
      await refresh();
      setView("jobs");
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function action(action: string) {
    if (!job) return;
    setBusy(true);
    try {
      const fresh = await api<Job>("jobs/" + job.id);
      await api("jobs/" + job.id + "/decision", "POST", {
        action,
        claims_reviewed: reviewMark === JSON.stringify(fresh.plan),
        version: fresh.version,
      });
      await refresh();
      setNotice("");
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function revision(change: string) {
    if (!job) return;
    setBusy(true);
    try {
      const fresh = await api<Job>("jobs/" + job.id);
      await api("jobs/" + job.id + "/revision", "POST", {
        change,
        version: fresh.version,
      });
      await refresh();
      setNotice("Revision queued. Earlier exports remain available.");
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function toggleMonitoring() {
    if (!job) return;
    setBusy(true);
    try {
      const fresh = await api<Job>("jobs/" + job.id);
      const enabled = !fresh.monitor?.enabled;
      await api("jobs/" + job.id + "/monitor", "PUT", {
        enabled,
        interval_hours: 24,
      });
      await refresh();
      setNotice(
        enabled
          ? "Daily source monitoring is on. Changes will always wait for your approval."
          : "Background source monitoring is off.",
      );
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function savePlan() {
    if (!job || !draft) return;
    setBusy(true);
    try {
      await api("jobs/" + job.id + "/storyboard", "PUT", {
        plan: { scenes: draft },
        version: job.version,
      });
      await refresh();
      setDraft(null);
      setNotice(
        "Storyboard saved. Approve the plan or render a revision when ready.",
      );
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function choose(j: Job) {
    setSelected(j.id);
    setSelectedAttempt(null);
    setDraft(null);
    setTab("preview");
    setView("jobs");
  }
  function editScene(index: number, key: keyof Scene, value: string) {
    const scenes = structuredClone(draft ?? job?.plan?.scenes ?? []);
    if (key === "scroll") scenes[index].scroll = value as Scene["scroll"];
    else if (key !== "source_ids") scenes[index][key] = value;
    setDraft(scenes);
  }

  if (!session)
    return (
      <main className="lp-login">
        <section>
          <Link href="/" className="lp-brand">
            <BrandMark />
            citereel
          </Link>
          <h1>Your next product story starts here.</h1>
          <p>
            Research, script, record, narrate and review your product video in
            one workspace.
          </p>
          <form onSubmit={auth}>
            <label>
              Email
              <input name="email" type="email" autoComplete="email" required />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                minLength={10}
                autoComplete={
                  authMode === "login" ? "current-password" : "new-password"
                }
                required
              />
            </label>
            <button className="lp-primary" type="submit" disabled={busy}>
              {authMode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
          <button
            className="lp-text"
            onClick={() =>
              setAuthMode(authMode === "login" ? "register" : "login")
            }
          >
            {authMode === "login"
              ? "Create an account"
              : "Already have an account? Sign in"}
          </button>
          {notice && (
            <p className="lp-error" role="alert">
              {notice}
            </p>
          )}
          <p className="lp-login-foot">AWS Bedrock · Strands Agents</p>
        </section>
      </main>
    );

  return (
    <main className={`lp-app ${view === "create" ? "with-intake" : ""}`}>
      <aside className="lp-nav">
        <Link href="/" className="lp-brand" aria-label="Citereel home">
          <BrandMark />
          <b>citereel</b>
        </Link>
        <nav aria-label="Workspace">
          {(["create", "jobs", "projects", "settings"] as View[]).map(
            (name) => (
              <button
                key={name}
                aria-label={name === "create" ? "Create demo" : human(name)}
                className={view === name ? "selected" : ""}
                onClick={() => {
                  setView(name);
                  if (name === "create") setTab("preview");
                }}
              >
                <Glyph name={name} />
                <span>{name === "create" ? "Create demo" : human(name)}</span>
              </button>
            ),
          )}
        </nav>
        <div className="lp-nav-bottom">
          <span className="lp-avatar">CR</span>
          <div>
            <b>Your workspace</b>
            <span>Citereel Concierge</span>
          </div>
          <button
            aria-label="Sign out"
            onClick={async () => {
              await api("session/logout", "POST");
              setSession(false);
            }}
          >
            ↪
          </button>
        </div>
      </aside>

      {view === "create" && (
        <aside className="lp-intake">
          <header>
            <h1>Create a demo</h1>
            <p>Give your concierge the product and the story.</p>
          </header>
          <form onSubmit={create} ref={formRef}>
            <label>
              Demo title
              <input
                name="title"
                maxLength={100}
                placeholder="Product introduction"
                required
              />
            </label>
            <label>
              Website URL
              <input
                name="url"
                type="url"
                className="form-input"
                placeholder="https://your-product.com"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                required
              />
            </label>
            <button
              type="button"
              onClick={() => {
                setSource(
                  "https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html",
                );
                setBrandName("Amazon Bedrock");
                setBrandColor("#ff9900");
                const form = formRef.current;
                if (!form) return;
                const values: Record<string, string> = {
                  title: "Amazon Bedrock overview",
                  brief:
                    "Explain Amazon Bedrock for a founder evaluating generative AI. Use only the inspected AWS documentation. Show the overview, model availability and getting started. Avoid invented performance or cost claims.",
                  audience: "Founders evaluating generative AI",
                  cta: "Explore the Amazon Bedrock documentation",
                  duration: "30",
                };
                for (const [name, value] of Object.entries(values)) {
                  const field = form.elements.namedItem(name);
                  if (
                    field instanceof HTMLInputElement ||
                    field instanceof HTMLTextAreaElement ||
                    field instanceof HTMLSelectElement
                  )
                    field.value = value;
                }
              }}
            >
              Use public Amazon Bedrock example
            </button>
            {settings && !settings.bedrock_configured && (
              <p className="lp-inline-note">
                AI generation is unavailable. Ask the workspace administrator to
                configure Bedrock.
              </p>
            )}
            <label>
              Demo format
              <select
                value={format}
                onChange={(e) => {
                  setFormat(e.target.value);
                  const duration =
                    formRef.current?.elements.namedItem("duration");
                  if (
                    e.target.value !== "presentation" &&
                    duration instanceof HTMLSelectElement &&
                    duration.value === "180"
                  )
                    duration.value = "120";
                }}
              >
                <option value="presentation">Presentation</option>
                <option value="product">Product demo</option>
                <option value="spotlight">Feature spotlight</option>
                <option value="short">Short</option>
              </select>
            </label>
            <label>
              Visual style
              <select name="visual_style" defaultValue="circuit">
                <option value="circuit">Circuit presentation</option>
                <option value="cinematic">
                  Cinematic demo — animated titles
                </option>
              </select>
            </label>
            <div className="lp-fields">
              <label>
                Duration
                <select name="duration" defaultValue="45">
                  {(format === "presentation"
                    ? [30, 45, 60, 90, 120, 180]
                    : [30, 45, 60, 90, 120]
                  ).map((x) => (
                    <option key={x} value={x}>
                      {x >= 60 && x % 60 === 0
                        ? `${x / 60} minute${x > 60 ? "s" : ""}`
                        : `${x} seconds`}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Orientation
                <select name="orientation" defaultValue="landscape">
                  <option value="landscape">Landscape</option>
                  <option value="portrait">Portrait</option>
                </select>
              </label>
            </div>
            <label>
              Audience
              <input
                name="audience"
                defaultValue="Product teams"
                maxLength={120}
              />
            </label>
            <div className="lp-fields">
              <label>
                Narration
                <select
                  name="narration_voice"
                  value={narrationChoice}
                  onChange={(event) => setNarrationChoice(event.target.value)}
                >
                  <option value="female">Female (Ruth)</option>
                  <option value="male">Male (Matthew)</option>
                  <option value="silent">Silent — add voiceover later</option>
                </select>
              </label>
              <label>
                Delivery style
                <select name="tone">
                  <option>Clear and credible</option>
                  <option>Professional and confident</option>
                  <option>Warm and conversational</option>
                  <option>Energetic and concise</option>
                </select>
              </label>
            </div>
            <label>
              Call to action
              <input
                name="cta"
                placeholder="Explore the product"
                maxLength={100}
              />
            </label>
            <div className="lp-fields">
              <label>
                Brand name
                <input
                  name="brand_name"
                  className="form-input"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  maxLength={60}
                  placeholder="Your product"
                  required
                />
              </label>
              <label>
                Brand color
                <input
                  name="brand_color"
                  type="color"
                  value={brandColor}
                  onChange={(e) => setBrandColor(e.target.value)}
                />
              </label>
            </div>
            <label className="lp-check">
              <input
                name="captions"
                type="checkbox"
                checked={narrationChoice !== "silent" && captionsEnabled}
                onChange={(event) => setCaptionsEnabled(event.target.checked)}
                disabled={narrationChoice === "silent"}
              />
              Captions
            </label>
            <label className="lp-check">
              <input name="review" type="checkbox" />
              Review storyboard before recording
            </label>
            <label className="lp-check">
              <input name="authorization" type="checkbox" required />I have
              permission to record this website.
            </label>
            <div className="lp-brief-bar">
              <label>
                Describe your video
                <textarea
                  name="brief"
                  className="form-textarea"
                  aria-label="Describe your video"
                  rows={7}
                  minLength={10}
                  maxLength={4000}
                  placeholder="Describe the story, pages to show, important details, audience, and what viewers should understand by the end."
                  required
                />
              </label>
              <button className="lp-primary" disabled={busy} type="submit">
                {busy ? "Creating…" : "Create demo"}
                <Glyph name="arrow" />
              </button>
            </div>
          </form>
        </aside>
      )}

      <section className="lp-main">
        <header className="lp-toolbar">
          <div>
            <span>Workspace / {human(view)}</span>
            <h1>
              {view === "create"
                ? "Production studio"
                : view === "jobs"
                  ? (job?.request.title ?? "Production jobs")
                  : view === "projects"
                    ? "Your projects"
                    : "Workspace settings"}
            </h1>
          </div>
          {view !== "create" && (
            <button
              className="lp-primary"
              onClick={() => {
                setView("create");
                setTab("preview");
              }}
            >
              <Glyph name="create" />
              New demo
            </button>
          )}
        </header>
        {notice && (
          <div role="status" className="lp-notice">
            {notice}
            <button
              aria-label="Dismiss notification"
              onClick={() => setNotice("")}
            >
              ×
            </button>
          </div>
        )}

        {view === "settings" ? (
          <div className="lp-settings">
            <h2>Bedrock connection</h2>
            <dl>
              <dt>Configuration</dt>
              <dd>
                {settings?.bedrock_configured
                  ? "Credentials configured; invocation must still succeed"
                  : "Credentials missing"}
              </dd>
              <dt>Model</dt>
              <dd>{settings?.model}</dd>
              <dt>AWS region</dt>
              <dd>{settings?.region}</dd>
              <dt>Narration</dt>
              <dd>
                {settings?.voice === "windows"
                  ? "Windows Speech (local)"
                  : "Amazon Polly Generative · Ruth or Matthew"}
              </dd>
              <dt>Production limit</dt>
              <dd>
                {settings?.daily_job_limit ?? 20} jobs per UTC day · up to{" "}
                {(settings?.max_video_duration_seconds ?? 180) / 60} minutes
              </dd>
            </dl>
            <p>
              Add your Bedrock API key to <code>AWS_BEARER_TOKEN_BEDROCK</code>{" "}
              in the private <code>.env</code> file, then restart the app. Keys
              are never sent to this browser.
            </p>
            <h2>Capture policy</h2>
            {Boolean(settings?.allowed_origins.length) && (
              <p>
                Operator-approved origins:{" "}
                {settings?.allowed_origins.join(", ")}. Ask your workspace
                administrator to update the permitted websites in the server
                configuration.
              </p>
            )}
            <p>
              The included Northstar fixture is available immediately. Public
              sites require your authorization. Capture blocks private
              addresses, cross-origin navigation, non-GET requests, downloads
              and challenges.
            </p>
            <h2>Storage</h2>
            <p>
              Sources, storyboard decisions and export versions stay attached to
              each production. Access requires your workspace session.
            </p>
            <h2>About this build</h2>
            <p>
              The local fixture test uses a deterministic script and a real
              browser/video pipeline. Bedrock mode uses Strands tools to inspect
              sources and save the storyboard. Export receipts identify the
              planner and voice used.
            </p>
          </div>
        ) : view === "projects" ? (
          <>
            <div className="lp-search">
              <input
                aria-label="Search projects"
                placeholder="Search your projects…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <span>{jobs.length} projects</span>
            </div>
            <div className="lp-projects">
              {jobs
                .filter((j) =>
                  j.request.title.toLowerCase().includes(search.toLowerCase()),
                )
                .map((j) => {
                  const a = j.artifacts.at(-1);
                  return (
                    <button
                      className="lp-project"
                      data-job-id={j.id}
                      key={j.id}
                      onClick={() => choose(j)}
                    >
                      <div className="lp-project-image">
                        {a ? (
                          <img
                            src={artifactURL(j, a, "poster.png")}
                            alt={j.request.title}
                          />
                        ) : (
                          <span>
                            <Glyph name="play" />
                            {human(j.state)}
                          </span>
                        )}
                      </div>
                      <div>
                        <h2>{j.request.title}</h2>
                        <p>
                          {human(j.request.format)} ·{" "}
                          {j.request.duration_seconds}s ·{" "}
                          {j.request.orientation} ·{" "}
                          {j.request.narration_mode === "silent"
                            ? "Silent export"
                            : `${human(j.request.narration_voice ?? "female")} voice`}
                        </p>
                        <span className="lp-status" data-state={j.state}>
                          {human(j.state)}
                        </span>
                      </div>
                    </button>
                  );
                })}
            </div>
            {jobs.length === 0 && (
              <Empty
                title="Your first story is waiting."
                text="Create a demo to start your project library."
              />
            )}
          </>
        ) : (
          <>
            {view === "jobs" && (
              <div className="lp-job-picker">
                <select
                  aria-label="Select production"
                  value={job?.id ?? ""}
                  onChange={(e) => {
                    setSelected(e.target.value);
                    setDraft(null);
                  }}
                >
                  <option value="" disabled>
                    Select a production
                  </option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.request.title} — {human(j.state)}
                    </option>
                  ))}
                </select>
                {job && (
                  <span className="lp-status" data-state={job.state}>
                    {human(job.state)}
                  </span>
                )}
              </div>
            )}
            {view === "jobs" && job && <JobReport job={job} />}
            {job?.plan && (job.artifacts.length > 0 || job.change_proposal) && (
              <WebsiteUpdates job={job} refresh={refresh} />
            )}
            <div
              className="lp-tabs"
              role="tablist"
              aria-label="Production views"
            >
              {(
                [
                  "preview",
                  "storyboard",
                  "claims",
                  "sources",
                  "trace",
                  "receipts",
                ] as const
              ).map((name) => (
                <button
                  role="tab"
                  aria-selected={tab === name}
                  key={name}
                  onClick={() => {
                    setTab(name);
                    setDraft(null);
                  }}
                >
                  {human(name)}
                  {name === "sources" && job?.evidence.length
                    ? ` (${job.evidence.length})`
                    : name === "claims" && job?.claim_ledger?.length
                      ? ` (${job.claim_ledger.length})`
                      : ""}
                </button>
              ))}
            </div>
            {tab === "preview" ? (
              <section className="lp-preview">
                {job && artifact ? (
                  <>
                    <div
                      className={`lp-video ${artifact.qa.height > artifact.qa.width ? "portrait" : ""}`}
                    >
                      <video
                        key={job.id + "-" + artifact.attempt}
                        controls
                        playsInline
                        preload="metadata"
                        poster={artifactURL(job, artifact, "poster.png")}
                        src={artifactURL(job, artifact, "export.mp4")}
                      />
                    </div>
                    <div className="lp-export-bar">
                      <div>
                        <strong>{job.request.title}</strong>
                        <span>
                          {Math.round(artifact.qa.duration_seconds)}s ·{" "}
                          {artifact.qa.width} × {artifact.qa.height} · Version{" "}
                          {artifact.attempt}
                        </span>
                      </div>
                      <a
                        className="lp-primary"
                        href={artifactURL(job, artifact, "export.mp4")}
                        download={`${job.request.title}.mp4`}
                      >
                        Download MP4 ↓
                      </a>
                    </div>
                    <div className="lp-export-versions">
                      <label>
                        Export version
                        <select
                          aria-label="Export version"
                          value={artifact.attempt}
                          onChange={(e) =>
                            setSelectedAttempt(Number(e.target.value))
                          }
                        >
                          {job.artifacts.map((a) => (
                            <option value={a.attempt} key={a.attempt}>
                              Version {a.attempt} · {a.qa.width} × {a.qa.height}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <p className="lp-origin">
                      {job.planner === "fixture"
                        ? "Local fixture production · deterministic script"
                        : "Bedrock storyboard"}{" "}
                      · {artifact.qa.voices[0]?.provider}
                      {artifact.qa.voices[0]?.voice
                        ? ` ${artifact.qa.voices[0].voice}`
                        : ""}
                      {artifact.qa.voices[0]?.engine
                        ? ` · ${human(artifact.qa.voices[0].engine)} voice`
                        : ""}{" "}
                      · {artifact.qa.captions}
                    </p>
                    {["ready_for_review", "approved", "blocked"].includes(
                      job.state,
                    ) && (
                      <div className="lp-revisions">
                        <button
                          disabled={busy}
                          onClick={() => revision("shorter")}
                        >
                          Make it shorter
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => revision("founder_cut")}
                        >
                          Concise founders cut
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => revision("social_cut")}
                        >
                          Vertical social cut
                        </button>
                        <button
                          disabled={busy}
                          onClick={() =>
                            revision(
                              job.request.orientation === "portrait"
                                ? "landscape"
                                : "portrait",
                            )
                          }
                        >
                          Change orientation
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => revision("rerender")}
                        >
                          Render saved storyboard
                        </button>
                        <button disabled={busy} onClick={toggleMonitoring}>
                          {job.monitor?.enabled
                            ? "Stop background checks"
                            : "Watch source daily"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() =>
                            revision(
                              artifact.qa.captions === "Disabled"
                                ? "captions_on"
                                : "captions_off",
                            )
                          }
                        >
                          {artifact.qa.captions === "Disabled"
                            ? "Add captions"
                            : "Remove captions"}
                        </button>
                        <select
                          aria-label="Change video format"
                          disabled={busy}
                          value=""
                          onChange={(e) => revision(e.target.value)}
                        >
                          <option value="" disabled>
                            Change format…
                          </option>
                          <option value="presentation">Presentation</option>
                          <option value="product">Product demo</option>
                          <option value="spotlight">Spotlight</option>
                          <option value="short">Short</option>
                        </select>
                        {job.state === "ready_for_review" && (
                          <button
                            disabled={busy}
                            onClick={() => action("approve_export")}
                          >
                            Approve export
                          </button>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <Empty
                    title={
                      job && activeStates.includes(job.state)
                        ? "Your production is underway."
                        : "From a working product to a finished story."
                    }
                    text={
                      job
                        ? "Progress appears in the activity panel. The finished video will appear here when it passes quality checks."
                        : "Choose a website, write a brief and select a format. Your agent brings the footage, story and narration together."
                    }
                  />
                )}
              </section>
            ) : tab === "storyboard" ? (
              <section className="lp-storyboard">
                {job?.plan ? (
                  <>
                    <div className="lp-section-heading">
                      <p>
                        {job.plan.scenes.length} scenes · edit narration and
                        copy before a revision
                      </p>
                      {draft && (
                        <button
                          className="lp-primary"
                          disabled={busy}
                          onClick={savePlan}
                        >
                          Save storyboard
                        </button>
                      )}
                    </div>
                    {(draft ?? job.plan.scenes).map((scene, i) => (
                      <article key={i}>
                        <div className="lp-scene-order">
                          {String(i + 1).padStart(2, "0")}
                          <button
                            aria-label={`Move scene ${i + 1} earlier`}
                            disabled={
                              i === 0 || activeStates.includes(job.state)
                            }
                            onClick={() => {
                              const scenes = structuredClone(
                                draft ?? job.plan!.scenes,
                              );
                              [scenes[i - 1], scenes[i]] = [
                                scenes[i],
                                scenes[i - 1],
                              ];
                              setDraft(scenes);
                            }}
                          >
                            ↑
                          </button>
                          <button
                            aria-label={`Move scene ${i + 1} later`}
                            disabled={
                              i === (draft ?? job.plan!.scenes).length - 1 ||
                              activeStates.includes(job.state)
                            }
                            onClick={() => {
                              const scenes = structuredClone(
                                draft ?? job.plan!.scenes,
                              );
                              [scenes[i + 1], scenes[i]] = [
                                scenes[i],
                                scenes[i + 1],
                              ];
                              setDraft(scenes);
                            }}
                          >
                            ↓
                          </button>
                        </div>
                        <div>
                          <label>
                            Scene title
                            <input
                              value={scene.title}
                              maxLength={75}
                              disabled={activeStates.includes(job.state)}
                              onChange={(e) =>
                                editScene(i, "title", e.target.value)
                              }
                            />
                          </label>
                          <label>
                            On-screen copy
                            <textarea
                              value={scene.on_screen_copy}
                              maxLength={180}
                              disabled={activeStates.includes(job.state)}
                              onChange={(e) =>
                                editScene(i, "on_screen_copy", e.target.value)
                              }
                            />
                          </label>
                          <label>
                            Narration
                            <textarea
                              value={scene.narration}
                              maxLength={600}
                              disabled={activeStates.includes(job.state)}
                              onChange={(e) =>
                                editScene(i, "narration", e.target.value)
                              }
                            />
                          </label>
                          <p>
                            Sources: {scene.source_ids.join(", ")} · Page:{" "}
                            {scene.page_id}
                          </p>
                        </div>
                      </article>
                    ))}
                  </>
                ) : (
                  <Empty
                    title="Storyboard"
                    text="The agent saves a structured scene plan here after it has inspected the sources."
                  />
                )}
              </section>
            ) : tab === "claims" ? (
              <section className="lp-claims">
                {job?.claim_ledger?.length ? (
                  <>
                    <div className="lp-section-heading">
                      <h2>Claim ledger</h2>
                      <p>
                        Exact wording is distinguished from paraphrases. A
                        citation is not proof that a claim is true. Review the
                        Sources tab before approval.
                      </p>
                    </div>
                    {job.claim_ledger.map((entry, index) => (
                      <article key={index}>
                        <div>
                          <span className="lp-status" data-state={entry.status}>
                            {entry.status === "source_matched"
                              ? "Source wording matched"
                              : "Needs human review"}
                          </span>
                          <p>
                            Scene {entry.scene} · {human(entry.kind)}
                          </p>
                        </div>
                        <blockquote>{entry.claim}</blockquote>
                        <p>{entry.explanation}</p>
                        <PrelineDisclosure
                          title="Review cited evidence"
                          className="lp-evidence-disclosure"
                        >
                          {entry.sources.map((source) => (
                            <section key={source.id}>
                              <h3>
                                {source.id}: {source.title}
                              </h3>
                              {source.url.startsWith("https://") && (
                                <a
                                  href={source.url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Open original source
                                </a>
                              )}
                              <blockquote>{source.excerpt}</blockquote>
                            </section>
                          ))}
                        </PrelineDisclosure>
                        <p>
                          {entry.sources
                            .map((source) => `${source.id}: ${source.title}`)
                            .join(" · ")}
                        </p>
                      </article>
                    ))}
                  </>
                ) : (
                  <Empty
                    title="Claim ledger"
                    text="The ledger is created when the storyboard passes source validation."
                  />
                )}
              </section>
            ) : tab === "sources" ? (
              <section className="lp-sources">
                {job?.evidence.length ? (
                  job.evidence.map((s) => (
                    <article key={s.id}>
                      <div className="lp-section-heading">
                        <h2>{s.title}</h2>
                        <span>{s.id}</span>
                      </div>
                      {s.fixture ? (
                        <p>Included owned demonstration source</p>
                      ) : (
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.url} ↗
                        </a>
                      )}
                      <blockquote>{s.excerpt}</blockquote>
                      <p className="lp-hash">SHA-256 {s.sha256}</p>
                    </article>
                  ))
                ) : (
                  <Empty
                    title="Every story starts with a source."
                    text="Inspected page excerpts and their hashes will appear here."
                  />
                )}
              </section>
            ) : tab === "trace" ? (
              <section className="lp-trace">
                {job ? (
                  <>
                    <div className="lp-section-heading">
                      <h2>Job trace</h2>
                      <p>
                        Correlation ID: <code>{job.id}</code>
                      </p>
                    </div>
                    <p className="lp-trace-note">
                      This trace uses the same job correlation ID carried
                      through planning, capture, render and QA.
                    </p>
                    <CloudTraceLinks trace={job.observability} />
                    <PolicyReview receipts={job.policy_receipts} />
                    <ol>
                      {(job.trace ?? [])
                        .slice()
                        .reverse()
                        .map((entry, index) => (
                          <li key={index}>
                            <time>
                              {new Date(entry.at * 1000).toLocaleTimeString(
                                [],
                                {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                },
                              )}
                            </time>
                            <div>
                              <strong>
                                {human(entry.component)} · {human(entry.event)}
                              </strong>
                              <p>{serviceMessage(entry.detail)}</p>
                            </div>
                          </li>
                        ))}
                    </ol>
                  </>
                ) : (
                  <Empty
                    title="Job trace"
                    text="Trace events appear as soon as a production is created."
                  />
                )}
              </section>
            ) : (
              <section className="lp-receipts">
                {job ? (
                  <>
                    <div className="lp-section-heading">
                      <h2>Production receipt</h2>
                      <a href={apiEndpoint(`jobs/${job.id}/receipt`)} download>
                        Download JSON ↓
                      </a>
                    </div>
                    <PolicyReview receipts={job.policy_receipts} />
                    <dl>
                      <dt>Job ID</dt>
                      <dd>{job.id}</dd>
                      <dt>Correlation ID</dt>
                      <dd>{job.id}</dd>
                      <dt>Planner</dt>
                      <dd>{job.planner ?? "Pending"}</dd>
                      {job.model && (
                        <>
                          <dt>Bedrock model</dt>
                          <dd>{job.model}</dd>
                        </>
                      )}
                      {job.model_usage && (
                        <>
                          <dt>Model tokens</dt>
                          <dd>
                            {job.model_usage.totalTokens.toLocaleString()} of{" "}
                            {job.budget?.planning_tokens.toLocaleString() ??
                              "45,000"}{" "}
                            planning-token budget
                          </dd>
                        </>
                      )}
                      <dt>Attempt</dt>
                      <dd>{job.attempt}</dd>
                      <dt>Narrator</dt>
                      <dd>
                        {job.request.narration_mode === "silent"
                          ? "None — silent export"
                          : (artifact?.qa.voices[0]?.voice ??
                            human(job.request.narration_voice ?? "female"))}
                        {artifact?.qa.voices[0]?.engine
                          ? ` · ${human(artifact.qa.voices[0].engine)}`
                          : ""}
                      </dd>
                    </dl>
                    {artifact && (
                      <>
                        <h3>Export checks</h3>
                        <p>
                          {artifact.qa.width} × {artifact.qa.height} ·{" "}
                          {artifact.qa.duration_seconds.toFixed(2)} seconds ·{" "}
                          {(artifact.qa.bytes / 1e6).toFixed(1)} MB
                        </p>
                        <p className="lp-hash">SHA-256 {artifact.qa.sha256}</p>
                      </>
                    )}
                    <h3>Agent tools</h3>
                    {job.tool_receipts.map((r, i) => (
                      <p key={i}>
                        <strong>{r.tool}</strong>
                        <br />
                        {serviceMessage(r.detail)}
                      </p>
                    ))}
                    <h3>Capture actions</h3>
                    {job.capture_events?.map((r, i) => (
                      <p key={i}>
                        {[`Scene ${r.scene}`, r.action, r.page_id ?? r.position]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    ))}
                  </>
                ) : (
                  <Empty
                    title="Production receipts"
                    text="Tool calls, capture actions and output checks appear after a job starts."
                  />
                )}
              </section>
            )}
          </>
        )}
      </section>

      {view !== "settings" && view !== "projects" && (
        <aside className="lp-activity">
          <header>
            <h2>Concierge activity</h2>
            <p>{job ? human(job.state) : "Ready when you are"}</p>
          </header>
          {job?.error && (
            <div className="lp-error" role="alert">
              {serviceMessage(job.error)}
            </div>
          )}
          {job && <JobProgress job={job} compact />}
          <ol>
            {stageNames
              .filter(
                (name) =>
                  name !== "narrating" ||
                  (job
                    ? job.request.narration_mode !== "silent"
                    : narrationChoice !== "silent"),
              )
              .map((name, i) => {
                const current = stageNames.indexOf(job?.state ?? "");
                const done =
                  job?.timeline.some((t) => t.stage === name) &&
                  (!activeStates.includes(job.state) ||
                    current > stageNames.indexOf(name));
                return (
                  <li
                    key={name}
                    className={
                      done ? "done" : job?.state === name ? "current" : ""
                    }
                  >
                    <span>{done ? "✓" : i + 1}</span>
                    <div>
                      <b>{human(name)}</b>
                      <p>
                        {name === "planning"
                          ? "Grounded script and scene direction"
                          : name === "capturing"
                            ? "Real product footage"
                            : name === "quality_check"
                              ? "Streams, dimensions and duration"
                              : name === "narrating"
                                ? "Voice synthesis and timing"
                                : name === "rendering"
                                  ? (
                                      job
                                        ? job.request.narration_mode ===
                                          "silent"
                                        : narrationChoice === "silent"
                                    )
                                    ? "Silent video composition"
                                    : "Video, captions and audio"
                                  : name === "researching"
                                    ? "Official source evidence"
                                    : "Authorized website"}
                      </p>
                    </div>
                  </li>
                );
              })}
          </ol>
          {job?.state === "awaiting_plan_approval" && (
            <div className="lp-approval">
              <h3>Your storyboard is ready</h3>
              <p>
                Review the copy and sources, then authorize recording.
                Paraphrases require your explicit review.
              </p>
              <button onClick={() => setTab("claims")}>
                Review claims and evidence
              </button>
              <label className="lp-check">
                <input
                  type="checkbox"
                  checked={reviewMark === JSON.stringify(job.plan)}
                  onChange={(e) =>
                    setReviewMark(
                      e.target.checked ? JSON.stringify(job.plan) : "",
                    )
                  }
                />
                I reviewed the claims against their cited sources.
              </label>
              <button onClick={() => setTab("storyboard")}>
                Review storyboard
              </button>
              <button
                className="lp-primary"
                disabled={
                  busy ||
                  !!draft ||
                  (job.claim_ledger?.some((c) => c.status === "needs_review") &&
                    reviewMark !== JSON.stringify(job.plan))
                }
                onClick={() => action("approve_plan")}
              >
                Approve & record
              </button>
              <button disabled={busy} onClick={() => action("reject_plan")}>
                Reject plan
              </button>
            </div>
          )}
          {job?.state === "awaiting_changes_approval" && (
            <p>
              Review the changed sources in the center panel. No video will be
              replaced without approval.
            </p>
          )}
          {job && ["blocked", "failed"].includes(job.state) && (
            <button disabled={busy} onClick={() => action("retry")}>
              Retry from saved work
            </button>
          )}
          {job && activeStates.includes(job.state) && (
            <button disabled={busy} onClick={() => action("cancel")}>
              Cancel production
            </button>
          )}
          <div className="lp-events">
            <h3>Latest updates</h3>
            {job?.timeline
              .slice(-5)
              .reverse()
              .map((t, i) => (
                <p key={i}>
                  <time>
                    {new Date(t.at * 1000).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                  {serviceMessage(t.detail)}
                </p>
              ))}
          </div>
        </aside>
      )}
    </main>
  );
}

function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="lp-empty">
      <span className="lp-empty-mark">
        <Glyph name="play" />
      </span>
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
