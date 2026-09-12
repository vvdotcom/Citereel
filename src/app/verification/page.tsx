"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PolicyReview, type PolicyReceipt } from "@/components/policy-review";

type Report = {
  verified_at: string;
  job_id: string;
  runtime: string;
  model: string;
  duration_seconds: number;
  width: number;
  height: number;
  export_sha256: string;
  video_url: string;
  receipt_url: string;
  checks: { name: string; result: string; evidence: string }[];
  policy_receipts: PolicyReceipt[];
  public_example?: { job_id: string; source_url: string; video_url: string; qa: { width: number; height: number; duration_seconds: number; sha256: string } };
};

export default function Verification() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/verification/cloud-report.json").then((response) => {
      if (!response.ok) throw new Error("The cloud verification report has not been published yet.");
      return response.json();
    }).then(setReport).catch((reason: Error) => setError(reason.message));
  }, []);
  return <main className="cloud-verification" style={{ maxWidth: 1056, margin: "0 auto", padding: "32px 24px", lineHeight: 1.6, overflowWrap: "anywhere" }}>
    <Link href="/" style={{ color: "var(--aws)" }}>← Citereel</Link>
    <h1>Cloud verification</h1>
    <p>A recorded engineering test of Citereel’s deployed workflow. The Northstar demo business is fictional; the AWS execution and generated video are real.</p>
    {error && <p role="status">{error}</p>}
    {!report && !error && <p>Loading verification results…</p>}
    {report && <>
      <p>Verified {new Date(report.verified_at).toLocaleString()} · Production <code>{report.job_id}</code></p>
      <video src={report.video_url} controls playsInline preload="metadata" style={{ width: "100%", borderRadius: 8, background: "#000" }} />
      <p>{report.width} × {report.height} · {report.duration_seconds.toFixed(1)} seconds · {report.runtime} · {report.model}</p>
      <a href={report.receipt_url} style={{ color: "var(--aws)" }} download>Download the source, policy and export receipt</a>
      {report.public_example && <section style={{ marginTop: 32 }}>
        <h2>Public website example: Amazon Bedrock</h2>
        <p>Generated from <a href={report.public_example.source_url} style={{ color: "var(--aws)" }}>AWS documentation</a> through the same deployed workflow, with a reviewed script. Production <code>{report.public_example.job_id}</code>.</p>
        <video src={report.public_example.video_url} aria-label="Amazon Bedrock public website demo" controls playsInline preload="metadata" style={{ width: "100%", borderRadius: 8, background: "#000" }} />
        <p>{report.public_example.qa.width} × {report.public_example.qa.height} · {report.public_example.qa.duration_seconds.toFixed(1)} seconds · AgentCore, Strands, Bedrock and Polly</p>
      </section>}
      <h2>Verified behavior</h2>
      <ul style={{ paddingLeft: 20 }}>{report.checks.map((check) => <li key={check.name} style={{ margin: "16px 0" }}>
        <strong>{check.name}: {check.result}</strong><p>{check.evidence}</p>
      </li>)}</ul>
      <details><summary>Export SHA-256</summary><code style={{ overflowWrap: "anywhere" }}>{report.export_sha256}</code></details>
      <PolicyReview receipts={report.policy_receipts} />
    </>}
  </main>;
}
