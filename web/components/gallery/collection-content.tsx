"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import {
  hinggiAnatomy,
  hinggiBands,
  hinggiColors,
  hinggiMotifs,
} from "@/lib/gallery";

export function HinggiAnatomy() {
  const [selected, setSelected] = useState<string>("padua");
  const part = hinggiAnatomy.find((item) => item.id === selected)!;
  return (
    <section className="hinggi-anatomy" aria-label="Anatomi kain Hinggi">
      <div
        className="hinggi-band-diagram"
        role="group"
        aria-label="Skema tujuh pita horizontal"
      >
        <button
          className="hinggi-boundary"
          aria-pressed={selected === "kabakil"}
          onClick={() => setSelected("kabakil")}
        >
          Kabakil <span>Batas ujung</span>
        </button>
        {hinggiBands.map((id, index) => {
          const item = hinggiAnatomy.find((entry) => entry.id === id)!;
          return (
            <button
              key={index}
              className={`hinggi-band hinggi-band-${id}`}
              aria-pressed={selected === id}
              aria-label={`${item.name}, pita ${index + 1}`}
              onClick={() => setSelected(id)}
            >
              <span>{index + 1}</span>
              {item.name}
            </button>
          );
        })}
        <button
          className="hinggi-boundary"
          aria-pressed={selected === "kabakil"}
          onClick={() => setSelected("kabakil")}
        >
          Kabakil <span>Sebelum rumbai</span>
        </button>
      </div>
      <div
        className="hinggi-part-description"
        aria-live="polite"
        aria-atomic="true"
      >
        <span>{part.location}</span>
        <h3>{part.name}</h3>
        {part.alternate && <p className="hinggi-alternate">{part.alternate}</p>}
        <p>{part.description}</p>
      </div>
    </section>
  );
}

export function HinggiMotifs() {
  return (
    <div className="hinggi-motifs">
      {hinggiMotifs.map((motif) => (
        <details key={motif.name}>
          <summary>
            {motif.name}
            <ChevronDown size={17} />
          </summary>
          <p>{motif.meaning}</p>
        </details>
      ))}
    </div>
  );
}

export function HinggiColors() {
  return (
    <div className="hinggi-colors">
      {hinggiColors.map((item) => (
        <section key={item.name}>
          <header>
            <span style={{ backgroundColor: item.color }} aria-hidden="true" />
            <div>
              <h3>{item.name}</h3>
              <p>{item.tone}</p>
            </div>
          </header>
          <dl>
            <div>
              <dt>Bahan pewarna</dt>
              <dd>{item.dye}</dd>
            </div>
          </dl>
          <p>{item.meaning}</p>
        </section>
      ))}
    </div>
  );
}
