import { useEffect, useState } from "react";

const LETTERS = "INSIGNIA".split("");
const LETTER_DELAY = 0.08; // seconds between each letter
const HOLD_MS = 900;        // pause after all letters appear
const FADE_MS = 600;        // fade-out duration

export default function SplashScreen({ onComplete }) {
  const [fading, setFading] = useState(false);

  // Total time for all letters to appear
  const revealDuration = LETTERS.length * LETTER_DELAY * 1000;

  useEffect(() => {
    const holdTimer = setTimeout(() => setFading(true), revealDuration + HOLD_MS);
    const doneTimer = setTimeout(onComplete, revealDuration + HOLD_MS + FADE_MS);
    return () => { clearTimeout(holdTimer); clearTimeout(doneTimer); };
  }, []);

  return (
    <>
      <style>{`
        @keyframes letterIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "var(--bg)",
        display: "flex", alignItems: "center", justifyContent: "center",
        opacity: fading ? 0 : 1,
        transition: `opacity ${FADE_MS}ms ease`,
        pointerEvents: "none",
      }}>
        <div style={{ display: "flex", gap: 2 }}>
          {LETTERS.map((letter, i) => (
            <span
              key={i}
              style={{
                fontSize: 34,
                fontWeight: 300,
                letterSpacing: "0.18em",
                color: "var(--text)",
                fontFamily: "system-ui, sans-serif",
                opacity: 0,
                animation: `letterIn 0.4s ease forwards`,
                animationDelay: `${i * LETTER_DELAY}s`,
              }}
            >
              {letter}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}
