"use client";

import { useState } from "react";
import Link from "next/link";
import { BrandMark } from "./brand-mark";

const slides = [
  {
    label: "01",
    title: "Every launch deserves a clear story.",
    body: "Citereel turns an authorized product workspace into a reviewable product presentation—without recreating the research, capture, and edit loop from scratch.",
    kind: "opening",
  },
  {
    label: "02",
    title: "Start with evidence, not assumptions.",
    body: "The concierge keeps official source material attached to the scenes it proposes. Unsupported claims pause for a decision instead of slipping into the script.",
    kind: "evidence",
  },
  {
    label: "03",
    title: "Show the work in its real context.",
    body: "A bounded browser plan records only approved actions on an authorized origin. The resulting footage stays traceable from click to scene.",
    kind: "capture",
  },
  {
    label: "04",
    title: "Review a finished draft with receipts.",
    body: "Narration, captions, capture logs, source links, and output checks arrive together. Publishing is always a separate explicit approval.",
    kind: "review",
  },
] as const;

function Arrow({ direction }: { direction: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d={
          direction === "left" ? "m14 6-6 6 6 6M9 12h8" : "m10 6 6 6-6 6m5-6H7"
        }
      />
    </svg>
  );
}

export function DemoPresentation() {
  const [current, setCurrent] = useState(0);
  const slide = slides[current];
  const change = (offset: number) =>
    setCurrent((value) => (value + offset + slides.length) % slides.length);

  return (
    <main className="presentation-shell">
      <header className="presentation-header">
        <Link href="/" className="presentation-brand">
          <BrandMark />
          <strong>citereel</strong>
        </Link>
        <span>Design preview · illustrative screens</span>
        <span>4 slides</span>
      </header>
      <section
        className={`presentation-canvas ${slide.kind}`}
        aria-live="polite"
      >
        <div className="presentation-copy">
          <span>{slide.label} / 04</span>
          <h1>{slide.title}</h1>
          <p>{slide.body}</p>
        </div>
        <div className="presentation-visual" aria-hidden="true">
          {slide.kind === "opening" && (
            <div className="opening-visual">
              <div className="opening-site">
                <b>Northstar</b>
                <span>Research workspace</span>
                <h2>Evidence for the decisions ahead.</h2>
                <div className="opening-row">
                  <i />
                  <i />
                  <i />
                </div>
              </div>
              <div className="opening-script">
                <span>Scene 1</span>
                <b>Lead with the moment of clarity.</b>
                <p>Source: workspace overview</p>
              </div>
            </div>
          )}
          {slide.kind === "evidence" && (
            <div className="ledger-visual">
              <header>
                <b>Evidence ledger</b>
                <span>3 sources retained</span>
              </header>
              <article>
                <i>01</i>
                <div>
                  <b>Research workspace overview</b>
                  <span>Illustrative source · product page</span>
                </div>
                <em>Scene 1</em>
              </article>
              <article>
                <i>02</i>
                <div>
                  <b>Evidence review workflow</b>
                  <span>Illustrative source · workflow guide</span>
                </div>
                <em>Scene 2</em>
              </article>
              <article>
                <i>03</i>
                <div>
                  <b>Approval policy</b>
                  <span>Illustrative source · trust center</span>
                </div>
                <em>Scene 4</em>
              </article>
            </div>
          )}
          {slide.kind === "capture" && (
            <div className="capture-visual">
              <header>
                <span>● ● ●</span>
                <b>Citereel · illustrative workspace</b>
              </header>
              <div className="capture-body">
                <aside>
                  <b>Overview</b>
                  <span>Evidence</span>
                  <span>Projects</span>
                </aside>
                <section>
                  <p>Research workspace</p>
                  <h2>Decisions with the evidence attached.</h2>
                  <div className="capture-action">
                    <span>Click recorded</span>
                    <b>Open evidence review</b>
                  </div>
                </section>
              </div>
              <footer>
                <span>Approved action 02 / 04</span>
                <i />
              </footer>
            </div>
          )}
          {slide.kind === "review" && (
            <div className="review-visual">
              <div className="review-video">
                <div>
                  <span>Product presentation</span>
                  <b>00:45</b>
                </div>
                <h2>Evidence for the decisions ahead.</h2>
                <footer>
                  <i />
                  <span>Draft ready for review</span>
                </footer>
              </div>
              <div className="review-receipt">
                <span>Quality receipt</span>
                <b>Video and audio streams verified</b>
                <p>2560 × 1440 · 00:45 · SHA-256 recorded</p>
              </div>
            </div>
          )}
        </div>
      </section>
      <footer className="presentation-footer">
        <div className="slide-tabs">
          {slides.map((item, index) => (
            <button
              key={item.label}
              type="button"
              className={index === current ? "selected" : ""}
              onClick={() => setCurrent(index)}
              aria-label={`Show slide ${index + 1}`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="presentation-actions">
          <button
            type="button"
            onClick={() => change(-1)}
            aria-label="Previous slide"
          >
            <Arrow direction="left" />
          </button>
          <button
            type="button"
            onClick={() => change(1)}
            aria-label="Next slide"
          >
            <Arrow direction="right" />
          </button>
        </div>
      </footer>
    </main>
  );
}
