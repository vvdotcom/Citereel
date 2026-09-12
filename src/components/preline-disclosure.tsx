"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { HSAccordion } from "preline/non-auto";

/** Each React-owned root gets exactly one Preline instance, destroyed on unmount. */
export function PrelineDisclosure({
  title,
  children,
  defaultOpen = false,
  className = "",
}: {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  const id = useId().replaceAll(":", "");
  const root = useRef<HTMLDivElement>(null);
  const instance = useRef<HSAccordion | null>(null);
  const [fallbackOpen, setFallbackOpen] = useState(defaultOpen);
  useEffect(() => {
    let disposed = false;
    import("preline/non-auto")
      .then(({ HSAccordion: Accordion }) => {
        if (disposed || !root.current) return;
        instance.current = new Accordion(root.current);
        root.current.dataset.prelineReady = "true";
      })
      .catch(() => {
        // The same button remains operable with React if the optional chunk fails.
      });
    return () => {
      disposed = true;
      instance.current?.destroy();
      instance.current = null;
    };
  }, []);
  return (
    <div className="hs-accordion-group" data-hs-accordion-always-open>
      <div
        ref={root}
        id={id}
        className={`hs-accordion pl-disclosure ${fallbackOpen ? "active" : ""} ${className}`}
      >
        <button
          type="button"
          id={id + "-toggle"}
          className="hs-accordion-toggle pl-disclosure-toggle"
          aria-expanded={fallbackOpen}
          aria-controls={id + "-panel"}
          onClick={() => {
            if (!instance.current) setFallbackOpen((value) => !value);
          }}
        >
          <span>{title}</span>
          <svg
            className="pl-chevron"
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
        <div
          id={id + "-panel"}
          className={`hs-accordion-content pl-disclosure-content ${fallbackOpen ? "" : "hidden"}`}
          role="region"
          aria-labelledby={id + "-toggle"}
        >
          <div className="pl-disclosure-body">{children}</div>
        </div>
      </div>
    </div>
  );
}
