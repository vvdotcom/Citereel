"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { BrandMark } from "./brand-mark";
import "./landing.css";
import examples from "../../public/examples/manifest.json";
import { PrelineDisclosure } from "./preline-disclosure";
import { Testimonials } from "./testimonials";

const formats = [
  {
    id: "presentation",
    label: "Presentations",
    title: "Give the full picture.",
    description:
      "Walk through your product with a narrated story, readable captions and room for the details.",
    detail: "A guided product walkthrough",
  },
  {
    id: "product",
    label: "Product demos",
    title: "Show how it works.",
    description:
      "Put your product in motion with recorded browser footage, narration and focused scene-by-scene explanations.",
    detail: "Your product, in action",
  },
  {
    id: "spotlight",
    label: "Spotlights",
    title: "Make a feature the focus.",
    description:
      "Give one feature its own story. Keep the recording focused on what matters and the evidence behind it.",
    detail: "One feature. A closer look.",
  },
  {
    id: "short",
    label: "Shorts",
    title: "A smaller screen. A clear story.",
    description:
      "Turn a product moment into a vertical video, with highlighted captions and a format made for mobile viewing.",
    detail: "A story made for mobile",
  },
] as const;

type Example = (typeof examples)[keyof typeof examples];
const benchmarkRows: {
  label: string;
  value: (sample: Example) => string | number;
}[] = [
  {
    label: "Video duration",
    value: ({ qa }) => `${qa.duration_seconds.toFixed(2)} s`,
  },
  { label: "Resolution", value: ({ qa }) => `${qa.width} × ${qa.height}` },
  {
    label: "Orientation",
    value: ({ qa }) =>
      qa.width > qa.height ? "Landscape · 16:9" : "Portrait · 9:16",
  },
  { label: "Scenes", value: ({ qa }) => qa.scene_layouts.length },
  {
    label: "Download size",
    value: ({ qa }) => `${(qa.bytes / 1_000_000).toFixed(2)} MB`,
  },
  {
    label: "Video / audio",
    value: ({ qa }) =>
      `${qa.video_codec.toUpperCase()} / ${qa.audio_codec.toUpperCase()}`,
  },
  {
    label: "Sample planning",
    value: ({ planner }) =>
      planner === "bedrock" ? "Strands + Bedrock" : "Local fixture script",
  },
  { label: "Narration", value: ({ qa }) => qa.voices[0].provider },
];

export function Landing() {
  const [selected, setSelected] =
    useState<(typeof formats)[number]["id"]>("presentation");
  const [menuOpen, setMenuOpen] = useState(false);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const example = examples[selected];
  const format = formats.find((item) => item.id === selected)!;

  return (
    <div className="home-page">
      <a className="home-skip" href="#main-content">
        Skip to content
      </a>
      <header className="home-header">
        <div className="home-header-inner">
          <Link href="/" className="home-brand" aria-label="Citereel home">
            <BrandMark />citereel
          </Link>
          <button
            className="home-menu-toggle"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="home-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? "Close menu" : "Menu"}
          </button>
          <nav
            id="home-navigation"
            className={menuOpen ? "is-open" : ""}
            aria-label="Main navigation"
          >
            <a href="#examples" onClick={() => setMenuOpen(false)}>
              Video formats
            </a>
            <a href="#benchmarks" onClick={() => setMenuOpen(false)}>
              Benchmarks
            </a>
            <a href="#questions" onClick={() => setMenuOpen(false)}>
              FAQs
            </a>
            <Link href="/projects" className="home-projects-link">
              Your projects
            </Link>
            <Link className="home-button home-button-primary" href="/studio">
              Open workspace <span aria-hidden="true">↗</span>
            </Link>
          </nav>
        </div>
      </header>
      <main id="main-content">
        <section className="home-hero" aria-labelledby="home-title">
          <div className="home-announcement">
            Your product changed. Your video can, too.{" "}
            <a href="#questions">
              Learn about updates <span aria-hidden="true">→</span>
            </a>
          </div>
          <div className="home-intro">
            <h1 id="home-title">
              Your product has a story.
              <br />
              <span>Let people see it.</span>
            </h1>
            <p>
              Turn your website into a narrated product video.
              <br className="home-desktop-break" /> Planned by AI. Reviewed by
              you. Ready for your next launch.
            </p>
            <div className="home-actions">
              <Link className="home-button home-button-primary" href="/studio">
                Create your demo <span aria-hidden="true">↗</span>
              </Link>
              <a
                className="home-button home-button-outline"
                href="#watch-example"
              >
                Watch an example <span aria-hidden="true">▷</span>
              </a>
            </div>
          </div>
          <div
            className="home-format-gallery"
            id="examples"
            role="tablist"
            aria-label="Video examples"
          >
            {formats.map((item, index) => (
              <button
                key={item.id}
                ref={(element) => {
                  tabs.current[index] = element;
                }}
                type="button"
                role="tab"
                id={`format-${item.id}`}
                aria-controls="watch-example"
                aria-selected={selected === item.id}
                tabIndex={selected === item.id ? 0 : -1}
                onClick={() => setSelected(item.id)}
                onKeyDown={(event) => {
                  let next = index;
                  if (event.key === "ArrowRight")
                    next = (index + 1) % formats.length;
                  else if (event.key === "ArrowLeft")
                    next = (index + formats.length - 1) % formats.length;
                  else if (event.key === "Home") next = 0;
                  else if (event.key === "End") next = formats.length - 1;
                  else return;
                  event.preventDefault();
                  setSelected(formats[next].id);
                  tabs.current[next]?.focus();
                }}
                aria-label={item.label}
              >
                <span className="home-format-name">
                  {item.label}
                  <span aria-hidden="true">↗</span>
                </span>
                <span
                  className={`home-format-image ${item.id === "short" ? "is-portrait" : ""}`}
                >
                  <Image
                    src={`/examples/${item.id}.png?v=${examples[item.id].qa.sha256.slice(0, 12)}`}
                    alt=""
                    fill
                    sizes="(max-width: 760px) 45vw, 310px"
                  />
                </span>
                <span className="home-format-detail">{item.detail}</span>
              </button>
            ))}
          </div>
        </section>
        <section
          className="home-showcase home-container"
          id="watch-example"
          role="tabpanel"
          aria-labelledby={`format-${selected}`}
          tabIndex={0}
        >
          <div className="home-showcase-copy">
            <h2>{format.title}</h2>
            <p>{format.description}</p>
            <Link className="home-text-link" href="/studio">
              Make your own video <span aria-hidden="true">→</span>
            </Link>
            <p className="home-example-spec">
              {example.qa.width} × {example.qa.height}{" "}
              <span>Actual browser recording</span>
            </p>
          </div>
          <div className="home-example-media">
            <div
              className={
                "home-player " + (selected === "short" ? "vertical" : "")
              }
            >
              <video
                key={selected}
                controls
                playsInline
                preload="metadata"
                poster={`/examples/${selected}.png?v=${example.qa.sha256.slice(0, 12)}`}
                src={`/examples/${selected}.mp4?v=${example.qa.sha256.slice(0, 12)}`}
                aria-label={`${selected} example`}
              />
            </div>
            <p className="home-attribution">
              Original Northstar demo site.{" "}
              {example.planner === "bedrock"
                ? "Strands + Amazon Bedrock planning, " +
                  example.qa.voices[0].provider +
                  " narration."
                : "Local fixture script and " +
                  example.qa.voices[0].provider +
                  " narration; this example did not use Bedrock."}
            </p>
          </div>
        </section>
        <section
          className="home-workflow-section"
          id="benchmarks"
          aria-labelledby="benchmark-title"
        >
          <div className="home-container">
            <div className="home-section-heading">
              <h2 id="benchmark-title">Four modes. Real output benchmarks.</h2>
              <p>
                Compare the Northstar sample exports shown above. These are
                measured file results, not estimated performance.
              </p>
            </div>
            <p className="home-benchmark-scroll-hint">
              Swipe to compare all four modes.
            </p>
            <div
              className="home-benchmark-scroll"
              role="region"
              aria-label="Video mode benchmark comparison"
              tabIndex={0}
            >
              <table className="home-benchmarks">
                <caption>Recorded Northstar sample benchmarks</caption>
                <thead>
                  <tr>
                    <th scope="col">Sample output</th>
                    {formats.map((item) => (
                      <th scope="col" key={item.id}>
                        {item.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {benchmarkRows.map((row) => (
                    <tr key={row.label}>
                      <th scope="row">{row.label}</th>
                      {formats.map((item) => (
                        <td key={item.id}>{row.value(examples[item.id])}</td>
                      ))}
                    </tr>
                  ))}
                  <tr>
                    <th scope="row">View output</th>
                    {formats.map((item) => (
                      <td key={item.id}>
                        <a
                          href="#watch-example"
                          onClick={() => setSelected(item.id)}
                          aria-label={`Watch ${item.label.toLowerCase()} benchmark`}
                        >
                          Watch example <span aria-hidden="true">↗</span>
                        </a>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="home-technology">
              <span>Built with</span>
              <strong>Amazon Bedrock</strong>
              <span aria-hidden="true">+</span>
              <strong>Strands Agents</strong>
              <p>AI planning with a human approval step.</p>
            </div>
          </div>
        </section>
        <Testimonials />
        <section
          className="home-questions home-container"
          id="questions"
          aria-labelledby="questions-title"
        >
          <div>
            <h2 id="questions-title">
              Before you <br />
              press record.
            </h2>
            <p>A few details about sources, review and production.</p>
          </div>
          <div>
            <PrelineDisclosure title="Which websites can I use?">
              <p>
                Use a public page you are authorized to record, or an included
                demonstration site. The worker respects access restrictions.
                Sign-in, checkout and CAPTCHA workflows are not supported. Some
                websites are captured as static HTML rather than their
                interactive layout.
              </p>
            </PrelineDisclosure>
            <PrelineDisclosure title="What happens when my product changes?">
              <p>
                Choose Check website for changes in your production. Citereel
                compares inspected text, identifies affected scenes, and asks
                before requesting a Bedrock rewrite. You approve the updated
                storyboard before recording. Previous exports stay available.
              </p>
            </PrelineDisclosure>
            <PrelineDisclosure title="Are all claims automatically verified?">
              <p>
                No. The claim ledger distinguishes matching source wording from
                copy that needs review. A citation is not a truth guarantee. You
                remain responsible for checking claims and watching the final
                export.
              </p>
            </PrelineDisclosure>
          </div>
        </section>
      </main>
      <footer className="home-container">
        <Link href="/" className="home-brand">
          <BrandMark />citereel
        </Link>
        <span>Built with Strands Agents and Amazon Bedrock.</span>
        <Link href="/verification">Cloud verification</Link>
        <Link href="/studio">Open Studio ↗</Link>
      </footer>
    </div>
  );
}
