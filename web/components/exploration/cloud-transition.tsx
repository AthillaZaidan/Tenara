import type { CSSProperties } from "react";
import {
  CLOUD_CLOSE_MS,
  CLOUD_OPEN_MS,
  type WorldTransition,
} from "./use-world-navigation";

export function CloudTransition({
  transition,
}: {
  transition: WorldTransition;
}) {
  if (transition.phase === "idle" || transition.kind === "slide") return null;
  return (
    <div
      key={transition.sequence}
      className="nx-cloud-transition"
      data-phase={transition.phase}
      style={
        {
          "--cloud-close": `${CLOUD_CLOSE_MS}ms`,
          "--cloud-open": `${CLOUD_OPEN_MS}ms`,
        } as CSSProperties
      }
      aria-hidden="true"
    >
      <div className="nx-cloud-transition-veil" />
      {["left", "right"].map((side) => (
        <div key={side} className={`nx-cloud-bank nx-cloud-bank-${side}`}>
          <svg viewBox="0 0 600 1000" preserveAspectRatio="none">
            <path
              fill="#d3e9e7"
              d="M0 0H410C505-20 565 45 520 115C610 135 610 250 525 275C590 340 575 435 510 455C605 510 600 600 520 630C595 695 575 790 505 810C580 880 555 965 440 1000H0Z"
            />
            <path
              fill="#f0f7f2"
              d="M0 0H350C460-20 510 65 465 130C555 155 550 245 465 280C530 345 525 425 450 460C550 520 540 600 465 640C535 710 520 785 445 820C515 885 495 965 380 1000H0Z"
            />
            <path
              fill="#fcfcf1"
              opacity=".65"
              d="M0 0H200C320-10 385 65 340 150C440 180 430 280 350 310C415 385 400 470 325 500C435 570 420 660 340 695C425 770 390 865 315 885C360 945 305 1000 240 1000H0Z"
            />
          </svg>
        </div>
      ))}
    </div>
  );
}
