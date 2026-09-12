"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import "./testimonials.css";

const testimonials = [
  {
    name: "Mia Chen",
    role: "Founder, Orbit Notes",
    quote:
      "Seeing our product as a story helped everything click. I could review the script, adjust the details, and make the demo feel like us before recording.",
    portrait: "/testimonials/mia-chen-photo.png",
  },
  {
    name: "Rafael Cruz",
    role: "Product lead, Fieldwork",
    quote:
      "The storyboard gave our team something concrete to review. Having the source beside each claim made it easier to decide what belonged in our product demo.",
    portrait: "/testimonials/rafael-cruz-photo.png",
  },
  {
    name: "Nora Ellis",
    role: "Designer, Little North",
    quote:
      "I liked being able to shape the story before the video was made. The narration and captions brought the walkthrough together without losing the product details.",
    portrait: "/testimonials/nora-ellis-photo.png",
  },
  {
    name: "Devon Brooks",
    role: "Indie founder, Canvas Lane",
    quote:
      "Starting with our website made the first draft feel familiar. I could focus on the message, review each scene, and keep the parts that told our story best.",
    portrait: "/testimonials/devon-brooks-photo.png",
  },
  {
    name: "Asha Patel",
    role: "Marketing lead, Gatherly",
    quote:
      "A feature update gave us a reason to revisit the demo. Reviewing the changed scenes while keeping the rest made the update feel focused and manageable.",
    portrait: "/testimonials/asha-patel-photo.png",
  },
  {
    name: "Theo Park",
    role: "Co-founder, Pebble Studio",
    quote:
      "The different video formats helped me picture where our story could go. I could check the finished export with the team before choosing what to share.",
    portrait: "/testimonials/theo-park-photo.png",
  },
];

export function Testimonials() {
  const track = useRef<HTMLUListElement>(null);
  const [canGoBack, setCanGoBack] = useState(false);
  const [canGoForward, setCanGoForward] = useState(true);

  const updateControls = useCallback(() => {
    const element = track.current;
    if (!element) return;
    setCanGoBack(element.scrollLeft > 2);
    setCanGoForward(
      element.scrollLeft + element.clientWidth < element.scrollWidth - 2,
    );
  }, []);

  useEffect(() => {
    const element = track.current;
    if (!element) return;
    const observer = new ResizeObserver(updateControls);
    observer.observe(element);
    return () => observer.disconnect();
  }, [updateControls]);

  function browse(direction: number) {
    const element = track.current;
    if (!element) return;
    const gap = Number.parseFloat(getComputedStyle(element).columnGap) || 0;
    element.scrollBy({
      left: direction * (element.clientWidth + gap),
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  }

  return (
    <section
      className="home-testimonials"
      id="testimonials"
      aria-labelledby="testimonials-title"
      aria-describedby="testimonials-note"
    >
      <div className="home-container">
        <div className="home-testimonials-heading">
          <div>
            <p className="home-testimonials-label">Testimonials</p>
            <h2 id="testimonials-title">
              What our creators <em>say.</em>
            </h2>
            <p id="testimonials-note">
              Fictional characters, AI-generated portraits, and sample quotes
              for testing.
            </p>
          </div>
          <div
            className="home-testimonials-controls"
            aria-label="Testimonial controls"
          >
            <button
              type="button"
              aria-label="Previous testimonials"
              aria-controls="testimonials-track"
              disabled={!canGoBack}
              onClick={() => browse(-1)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m14 7-5 5 5 5M9 12h10" />
              </svg>
            </button>
            <button
              type="button"
              aria-label="Next testimonials"
              aria-controls="testimonials-track"
              disabled={!canGoForward}
              onClick={() => browse(1)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m10 7 5 5-5 5M5 12h10" />
              </svg>
            </button>
          </div>
        </div>
        <ul
          className="home-testimonials-track"
          id="testimonials-track"
          ref={track}
          onScroll={updateControls}
          tabIndex={0}
          aria-label="Fictional testimonials"
          onKeyDown={(event) => {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
            event.preventDefault();
            browse(event.key === "ArrowLeft" ? -1 : 1);
          }}
        >
          {testimonials.map((person) => (
            <li key={person.name}>
              <figure className="home-testimonial-card">
                <div className="home-testimonial-copy">
                  <div
                    className="home-testimonial-stars"
                    role="img"
                    aria-label="Sample rating: 5 out of 5 stars"
                  >
                    {[0, 1, 2, 3, 4].map((star) => (
                      <svg key={star} viewBox="0 0 24 24" aria-hidden="true">
                        <path d="m12 2 3 6.5 7 .9-5.1 5 1.3 7.1-6.2-3.4-6.2 3.4 1.3-7.1L2 9.4l7-.9Z" />
                      </svg>
                    ))}
                  </div>
                  <blockquote>{person.quote}</blockquote>
                </div>
                <figcaption>
                  <Image
                    className="home-testimonial-avatar"
                    src={person.portrait}
                    alt=""
                    width={48}
                    height={48}
                    sizes="48px"
                  />
                  <div>
                    <strong>{person.name}</strong>
                    <span>{person.role}</span>
                  </div>
                </figcaption>
              </figure>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
