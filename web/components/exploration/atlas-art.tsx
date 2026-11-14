/** Original, reusable illustration pieces for the Nusantara atlas.
 * Symbols use a ground anchor at (0, 0), allowing the scene to sort them by depth.
 */
export function AtlasArt() {
  return (
    <defs>
      <linearGradient id="atlas-land" x2=".3" y2="1">
        <stop stopColor="#c8cb6c" />
        <stop offset=".48" stopColor="#97b654" />
        <stop offset="1" stopColor="#779947" />
      </linearGradient>
      <linearGradient id="atlas-cliff" x2="0" y2="1">
        <stop stopColor="#f9df9b" />
        <stop offset=".5" stopColor="#e4b873" />
        <stop offset="1" stopColor="#be8c51" />
      </linearGradient>
      <linearGradient id="atlas-leaf" x1="0" y1="0" x2="1" y2="1">
        <stop stopColor="#bbca4b" />
        <stop offset=".42" stopColor="#7b9d34" />
        <stop offset="1" stopColor="#365e35" />
      </linearGradient>
      <linearGradient id="atlas-roof" x2=".2" y2="1">
        <stop stopColor="#f0b55d" />
        <stop offset=".55" stopColor="#bb6235" />
        <stop offset="1" stopColor="#733e2d" />
      </linearGradient>
      <linearGradient id="atlas-thatch" x2="1" y2="1">
        <stop stopColor="#f6d48d" />
        <stop offset=".45" stopColor="#c28e4b" />
        <stop offset="1" stopColor="#86613b" />
      </linearGradient>
      <linearGradient id="atlas-mountain-paint" x2="1" y2=".7">
        <stop stopColor="#e0d18b" />
        <stop offset=".4" stopColor="#9da15b" />
        <stop offset="1" stopColor="#486b48" />
      </linearGradient>
      <radialGradient id="atlas-cloud">
        <stop stopColor="#fffdf0" />
        <stop offset=".72" stopColor="#f9e9cb" />
        <stop offset="1" stopColor="#e6cda7" />
      </radialGradient>
      <pattern
        id="atlas-weave"
        width="44"
        height="44"
        patternUnits="userSpaceOnUse"
      >
        <rect width="44" height="44" fill="#943e32" />
        <path
          d="M22 2 40 22 22 42 4 22Z M22 11 32 22 22 33 12 22Z"
          fill="none"
          stroke="#f1ce86"
          strokeWidth="2"
        />
        <path
          d="M0 0 7 7M37 37 44 44M0 44 7 37M37 7 44 0M22 17 27 22 22 27 17 22Z"
          stroke="#e5ab64"
          fill="none"
        />
        <path
          d="M0 11H5M0 33H5M39 11H44M39 33H44"
          stroke="#edc585"
          strokeWidth="2"
        />
      </pattern>
      <pattern
        id="atlas-grass"
        width="27"
        height="23"
        patternUnits="userSpaceOnUse"
      >
        <path
          d="m4 17 2-4 1 4m13-8 2-3 1 3"
          fill="none"
          stroke="#526e36"
          strokeWidth=".6"
          opacity=".22"
        />
        <circle cx="13" cy="21" r=".7" fill="#f9dd8d" opacity=".55" />
      </pattern>
      <filter
        id="atlas-island-shadow"
        x="-10%"
        y="-20%"
        width="125%"
        height="155%"
      >
        <feDropShadow
          dx="2"
          dy="11"
          stdDeviation="8"
          floodColor="#245f58"
          floodOpacity=".28"
        />
      </filter>
      <filter
        id="atlas-object-shadow"
        x="-50%"
        y="-30%"
        width="200%"
        height="180%"
      >
        <feDropShadow
          dx="1"
          dy="3"
          stdDeviation="2"
          floodColor="#39562d"
          floodOpacity=".2"
        />
      </filter>
      <filter id="atlas-paper" x="0" y="0" width="100%" height="100%">
        <feTurbulence
          type="fractalNoise"
          baseFrequency=".65"
          numOctaves="3"
          stitchTiles="stitch"
        />
        <feColorMatrix type="saturate" values="0" />
        <feComponentTransfer>
          <feFuncA type="linear" slope=".13" />
        </feComponentTransfer>
        <feBlend in="SourceGraphic" mode="soft-light" />
      </filter>

      <g id="atlas-tree">
        <ellipse cy="1" rx="9" ry="3" fill="#365c35" opacity=".16" />
        <path d="M-1 0 0-25 3-25 2 0Z" fill="#916637" />
        <path d="m1-13-7-8m8 3 6-9" stroke="#9b7038" strokeWidth="1.6" />
        <path
          d="M-13-25c-4-6 1-13 7-13 0-8 11-12 16-5 8-2 15 8 10 14 3 6-3 12-10 10-3 5-12 5-15 0-6 2-11-1-8-6Z"
          fill="url(#atlas-leaf)"
        />
        <g fill="#c5cc55" opacity=".65">
          <ellipse cx="-6" cy="-33" rx="4" ry="3" />
          <ellipse cx="4" cy="-41" rx="4" ry="3" />
          <ellipse cx="12" cy="-33" rx="3" ry="2" />
        </g>
        <g fill="#355e35" opacity=".4">
          <ellipse cx="-6" cy="-24" rx="4" ry="3" />
          <ellipse cx="6" cy="-24" rx="4" ry="3" />
        </g>
      </g>
      <g id="atlas-flowering-tree">
        <use href="#atlas-tree" />
        <g fill="#dd6b36">
          <circle cx="-10" cy="-34" r="4" />
          <circle cx="1" cy="-41" r="4" />
          <circle cx="10" cy="-36" r="4.5" />
          <circle cx="-2" cy="-29" r="4" />
          <circle cx="15" cy="-28" r="3" />
        </g>
        <g fill="#f5af55">
          <circle cx="-11" cy="-36" r="1.6" />
          <circle cx="0" cy="-43" r="1.8" />
          <circle cx="9" cy="-38" r="1.5" />
          <circle cx="-3" cy="-31" r="1.5" />
        </g>
      </g>
      <g id="atlas-palm-frond-art">
        <path
          d="M3-43Q-11-62-24-45q18-5 27 2M3-43Q-20-47-22-28q13-14 25-15M3-43Q-2-66 8-66q-3 14-5 23M3-43q9-22 24-12Q13-54 3-43M3-43q21-8 27 9Q14-43 3-43M3-43q12 3 12 23Q9-35 3-43"
          fill="url(#atlas-leaf)"
          stroke="#8b9e38"
          strokeWidth=".65"
        />
        <g fill="#94703a">
          <circle cx="1" cy="-41" r="2.8" />
          <circle cx="5" cy="-40" r="2.6" />
        </g>
      </g>
      <g id="atlas-palm">
        <ellipse cy="1" rx="9" ry="2.5" fill="#365c35" opacity=".16" />
        <path d="M-2 0Q5-22 1-43L4-44Q9-19 2 0Z" fill="#aa783e" />
        <path
          d="M1-5 4-6M2-12 6-13M3-20 7-21M3-28 7-29M2-36 6-37"
          stroke="#ebca7c"
          strokeWidth="1"
        />
        <g className="atlas-palm-fronds">
          <use href="#atlas-palm-frond-art" />
        </g>
      </g>
      <g id="atlas-bush">
        <ellipse rx="12" ry="4" fill="#486d37" opacity=".17" />
        <path
          d="M-12 0q-3-10 5-11 0-10 8-9 8-2 9 8 9 0 7 12Z"
          fill="url(#atlas-leaf)"
        />
        <path
          d="m-7-3 1-4m7-2 1-4m7 8 1-3"
          stroke="#c4ca55"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
      <g id="atlas-mountain">
        <ellipse cy="-2" rx="42" ry="12" fill="#4f753d" opacity=".18" />
        <path
          d="M-49 0q17-25 26-41l18-23 11 7L43 0Z"
          fill="url(#atlas-mountain-paint)"
        />
        <path
          d="m-5-64 11 7L43 0 14-15 0-42-10-28-22-27Z"
          fill="#496c49"
          opacity=".65"
        />
        <path
          d="m-5-64-18 23-10 25 19-18L0-49 8-38Z"
          fill="#f1dc9b"
          opacity=".7"
        />
        <path
          d="m-38-6 10-12 6 5m30-3 10 9"
          fill="none"
          stroke="#bed079"
          strokeWidth="3"
        />
      </g>
      <g id="atlas-terraces">
        <path
          d="M-45 0q-10-12 2-25 12-10 16-28 28-19 56 0 5 17 18 29Q60-4 35 5Z"
          fill="#657d37"
        />
        <path
          d="M-27-48q23 16 56-1M-32-38q30 19 64 0M-38-26q41 20 77 0M-44-13q46 21 89 0M-44-1q46 18 84 2"
          fill="none"
          stroke="#ddcc55"
          strokeWidth="6"
        />
        <path
          d="M-27-51q23 16 54-1M-32-41q30 19 64 0M-38-29q41 20 77 0M-44-16q46 21 89 0M-44-4q46 18 84 2"
          fill="none"
          stroke="#b4bf42"
          strokeWidth="3"
        />
      </g>
      <g id="atlas-house-base">
        <ellipse cy="1" rx="33" ry="8" fill="#4c6035" opacity=".2" />
        <path d="m-22-27 27-8 23 11v22L2 6-22-5Z" fill="#d0a362" />
        <path d="M2-17 28-24v22L2 6Z" fill="#9e6b3e" />
        <path
          d="M-18-4V7M-7-1V10M7 2v9M23-3v9"
          stroke="#755338"
          strokeWidth="3"
        />
        <path d="m-13-12 7-2v11l-7 2Zm23-1 7-2v8l-7 2Z" fill="#5d4931" />
        <path
          d="m-23-10 25 9 28-9M-23-14 2-5l28-9"
          fill="none"
          stroke="#efcd8a"
          strokeWidth="1"
        />
      </g>
      <g id="atlas-house-joglo">
        <use href="#atlas-house-base" />
        <path
          d="m-36-26 14-12L0-66l15 8 12 21 15 9L4-15Z"
          fill="url(#atlas-roof)"
          stroke="#f0bd71"
          strokeWidth="1.2"
        />
        <path
          d="M0-66 4-34 42-28 4-15-36-26l40-8"
          fill="none"
          stroke="#f8ce83"
          strokeWidth="1.3"
        />
        <path
          d="m-17-39 19 9 23-7M-22-33 3-23l27-8M-7-54l5 18m11-21 4 22"
          fill="none"
          stroke="#d58d4c"
          strokeWidth="1"
        />
        <path
          d="M-3-67 2-70l5 6"
          fill="none"
          stroke="#8e4b2c"
          strokeWidth="2"
        />
      </g>
      <g id="atlas-house-batak">
        <use href="#atlas-house-base" />
        <path
          d="M-36-69q16 32 39 30 20 0 33-30l-6 42L4-14-28-27Z"
          fill="url(#atlas-roof)"
          stroke="#efbb74"
          strokeWidth="1.6"
        />
        <path
          d="M-36-69 4-23l32-46M-28-48 3-25l26-22M-23-36 3-20l24-16"
          stroke="#f6d196"
          fill="none"
          strokeWidth="1.2"
        />
        <path d="m-11-24 14-11 14 14L3-17Z" fill="#88412e" />
        <path d="m-5-24 8-6 8 7-8 3Z" fill="none" stroke="#f1d08f" />
      </g>
      <g id="atlas-house-minang">
        <use href="#atlas-house-base" />
        <path
          d="M-42-58q16 23 23-5 12 28 22-7 12 32 23 6 4 25 18 8L33-27 3-17-30-28Z"
          fill="#78432f"
          stroke="#f0bb72"
          strokeWidth="1.8"
        />
        <path
          d="m-32-35 34 10 32-9m-57-13 23 15 27-16M3-61v31"
          stroke="#cf7642"
          strokeWidth="2"
          fill="none"
        />
      </g>
      <g id="atlas-house-stilt">
        <use href="#atlas-house-base" />
        <path
          d="m-36-27 22-31 27-7 27 31-36 16Z"
          fill="url(#atlas-roof)"
          stroke="#f4cb85"
          strokeWidth="1.2"
        />
        <path
          d="m-14-58 18 40m9-47 27 31M-25-43 0-51m-29 15L4-44m9-13 18 24m-12-26 18 24"
          fill="none"
          stroke="#f2bb70"
        />
        <path
          d="m-9 1 0 14 16 5V5M-9 8 7 13M-9 13l16 5"
          stroke="#d7b17a"
          strokeWidth="2"
          fill="none"
        />
      </g>
      <g id="atlas-house-lumbung">
        <use href="#atlas-house-base" />
        <path
          d="M-32-25q-2-24 20-35Q1-75 15-57q19 15 22 32L3-14Z"
          fill="url(#atlas-thatch)"
          stroke="#f5d594"
          strokeWidth="1.2"
        />
        <path
          d="M-9-58Q-3-35 3-15M0-65Q12-45 18-21M7-62q18 21 24 36M-18-50l-6 24M-13-54l-2 30"
          stroke="#8f683c"
          strokeWidth="1"
          fill="none"
          opacity=".6"
        />
      </g>
      <g id="atlas-house-sumba">
        <use href="#atlas-house-base" />
        <path
          d="m-35-24 19-15 10-52 11-3 14 54 23 13L4-14Z"
          fill="url(#atlas-thatch)"
          stroke="#f2cc88"
          strokeWidth="1.4"
        />
        <path
          d="m-6-91 10 59 38 5M4-32-35-24M-1-87l10 53M-10-68l-4 31M8-82l12 48M-23-31l26 10 26-8"
          stroke="#a87a42"
          strokeWidth="1"
          fill="none"
        />
        <path d="M-5-92v-7m9 5 1-7" stroke="#73543a" strokeWidth="2" />
      </g>
      <g id="atlas-house-tambi">
        <ellipse cy="2" rx="30" ry="7" fill="#476333" opacity=".2" />
        <path d="m-20-18 23-8 23 10V2L1 9-20 0Z" fill="#b28049" />
        <path
          d="M-17-2v12M-5 3v10M11 4v9M22-1v10"
          stroke="#725536"
          strokeWidth="3"
        />
        <path
          d="m-34-16 29-66 12-3 32 65L2-5Z"
          fill="url(#atlas-thatch)"
          stroke="#f6d69a"
          strokeWidth="1.5"
        />
        <path
          d="M-5-82 2-5l37-15M-1-78l8 68M5-80l12 65M10-72l14 54M-10-66l-14 47M-16-50l-11 32"
          fill="none"
          stroke="#8a633c"
          strokeWidth="1"
          opacity=".65"
        />
        <path d="m-7-21 7-17 9 18-8 4Z" fill="#634b31" />
        <path d="m-8-84 14-4M-7-88l13 8" stroke="#815333" strokeWidth="2" />
      </g>
      <g id="atlas-house-toraja">
        <use href="#atlas-house-base" />
        <path
          d="M-46-72q25 32 50 24 22-4 40-34L31-28 4-14-31-28Z"
          fill="url(#atlas-roof)"
          stroke="#f0c887"
          strokeWidth="2"
        />
        <path
          d="M-46-72Q-15-34 4-23q23-5 40-59M-29-47q25 19 58-6M-23-35q22 12 48-4"
          fill="none"
          stroke="#f0c18a"
          strokeWidth="1.5"
        />
        <path
          d="M-13-17V0M-4-14V3M5-14V3M14-17v15"
          stroke="#e9c184"
          strokeWidth="1.5"
        />
      </g>
      <g id="atlas-house-honai">
        <ellipse cy="2" rx="27" ry="8" fill="#476333" opacity=".2" />
        <path d="M-20-18V0q20 14 40 0v-18Z" fill="#b28b54" stroke="#87633d" />
        <path
          d="M-15-17V2M-9-17V4M-3-17V5M3-17V5M9-17V4M15-17V2"
          stroke="#dcc28b"
          strokeWidth="1.3"
        />
        <path
          d="M-29-16q0-37 29-43 28 6 29 43-28 16-58 0Z"
          fill="url(#atlas-thatch)"
          stroke="#edce92"
          strokeWidth="1.4"
        />
        <path
          d="M0-59Q-6-38-8-10M0-59q12 23 14 47M-8-54q-12 15-14 37M8-54q14 16 16 35M-2-57l4 47"
          stroke="#947047"
          strokeWidth="1"
          opacity=".7"
          fill="none"
        />
        <path d="M-3 5V-5q5-10 10-1V5" fill="#5d4932" />
      </g>
      <g id="atlas-waterfall">
        <path d="m-23-44 20-12 25 6 9 43L5 4-25-5Z" fill="#64815a" />
        <path d="m-23-44 20-12 25 6L6-38Z" fill="#b6bd7b" />
        <path
          d="M-6-44Q2-27-4-5q2 12 15 9l10-8q-15-6-12-18l1-20Z"
          fill="#b8e2cc"
        />
        <path
          d="M-2-42Q5-25 1-7M6-42q-3 17 2 27"
          fill="none"
          stroke="#f8f7d9"
          strokeWidth="2"
        />
        <ellipse cx="7" cy="4" rx="23" ry="8" fill="#87c9b5" />
        <path
          d="M-9 4q15 8 32 0M-5 0q11 7 20 1"
          fill="none"
          stroke="#e6eac3"
          strokeWidth="1.5"
        />
        <path d="m-26-8 7-6 6 7-8 4m39-4 10-8 6 12-9 3" fill="#c2bc7e" />
      </g>
      <g id="atlas-meru">
        <ellipse cy="2" rx="27" ry="7" fill="#456036" opacity=".2" />
        <path d="m-20-5 20-7 24 7L3 5Z" fill="#d2aa6d" />
        <path
          d="M-10-9v-47H9v48"
          fill="#c78645"
          stroke="#835334"
          strokeWidth="2"
        />
        {[0, 1, 2, 3, 4].map((n) => (
          <g
            key={n}
            transform={`translate(0 ${-12 - n * 13}) scale(${1 - n * 0.13})`}
          >
            <path
              d="m-27 0 13-10L0-18 13-11 29 0 2 7Z"
              fill="#70472e"
              stroke="#dfaa60"
              strokeWidth="1.5"
            />
            <path d="m-22-1 23 4 23-4" fill="none" stroke="#edc783" />
          </g>
        ))}
        <path d="M0-85v-8" stroke="#e8ba67" strokeWidth="2" />
      </g>
      <g id="atlas-cloth">
        <path
          d="M-17 3v-38m37 38v-38m-41 2h45"
          stroke="#a37a42"
          strokeWidth="2.3"
        />
        <path d="M-13-32h28v34H-13Z" fill="url(#atlas-weave)" />
        <path d="M-13-29h28M-13-1h28" stroke="#f9dc9b" strokeWidth="2" />
        <path d="M-10 3v3m5-3v3m5-3v3m5-3v3m5-3v3" stroke="#e0b878" />
      </g>
      <g id="atlas-cloud-shape" fill="url(#atlas-cloud)">
        <ellipse cy="-6" rx="62" ry="15" opacity=".45" />
        <path d="M-64-13q-2-14 15-13 2-22 25-16 6-25 31-20 23-2 28 23 24-7 30 11 21-3 25 10 0 13-30 13H-40q-35 0-24-8Z" />
        <path
          d="M-36-26q6-15 19-7-4-20 13-23 25-6 30 13 6 18-12 22-16 2-18-9-2-10 8-11 9 0 7 7M-18-24q-7 17-25 8m66-17q16-11 27 5m-5 10q-18 11-32 3"
          fill="none"
          stroke="#e2c79f"
          strokeWidth="3"
          opacity=".65"
          strokeLinecap="round"
        />
        <path
          d="M-49-29q8-10 15-6M-9-53q19-11 28 6m18 14q9-3 14 4"
          stroke="#fffdf0"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
          opacity=".85"
        />
      </g>
      <g id="atlas-boat-shape">
        <ellipse cy="7" rx="39" ry="6" fill="#e5f0d2" opacity=".2" />
        <path
          d="M-39-1q35 12 79-5L24 9Q-6 17-31 7Z"
          fill="#835030"
          stroke="#e9bd75"
          strokeWidth="1.7"
        />
        <path
          d="M-30 4q30 10 61-4"
          stroke="#f0d99d"
          strokeWidth="2"
          fill="none"
        />
        <path d="M-2 3v-71" stroke="#875b36" strokeWidth="2.5" />
        <path
          d="m-5-64-31 48L-5-6Z"
          fill="url(#atlas-weave)"
          stroke="#f5d99d"
          strokeWidth="1.4"
        />
        <path
          d="M2-60 30-12 2-7Z"
          fill="#f4dfaa"
          stroke="#b77a46"
          strokeWidth="1.2"
        />
        <path d="M8-45 21-16 8-13Z" fill="#ba6b40" opacity=".8" />
        <path d="m-2-69 15 6-15 3" fill="#b95c36" />
      </g>
      <g
        id="atlas-wave-shape"
        fill="none"
        stroke="#e4e4b5"
        strokeLinecap="round"
      >
        <path
          d="M-38 0q18-12 38 0t38 0M-25 7q17-9 32 0t27 0M-12-7q14-7 27 0"
          strokeWidth="1.5"
        />
      </g>
      <g id="atlas-flower" fill="none" stroke="#b38337" strokeWidth="1.5">
        {[0, 60, 120, 180, 240, 300].map((a) => (
          <path
            key={a}
            transform={`rotate(${a})`}
            d="M0 0Q-15-14 0-25 15-14 0 0Zm0-7-4-7 4-6 4 6Z"
          />
        ))}
        <circle r="5" fill="#f3dfab" />
      </g>
    </defs>
  );
}

export function AtlasOrnaments() {
  return (
    <svg
      className="nx-atlas-ornaments"
      viewBox="0 0 1600 900"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <pattern
          id="atlas-border-weave"
          width="58"
          height="58"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(-12)"
        >
          <rect width="58" height="58" fill="#8c4034" />
          <path
            d="m29 3 24 26-24 26L5 29Zm0 11 14 15-14 15-14-15Zm0 9 5 6-5 6-5-6Z"
            fill="none"
            stroke="#edc47e"
            strokeWidth="2"
          />
          <path
            d="M0 0 9 9M49 49 58 58M0 58l9-9M49 9l9-9"
            stroke="#dba163"
            strokeWidth="3"
          />
        </pattern>
        <linearGradient id="atlas-border-light" x2=".3" y2="1">
          <stop stopColor="#ffd58e" stopOpacity=".3" />
          <stop offset=".6" stopColor="#71342e" stopOpacity="0" />
          <stop offset="1" stopColor="#512e28" stopOpacity=".5" />
        </linearGradient>
      </defs>
      <g fill="none" stroke="#eee1b2" opacity=".7" strokeWidth="1.7">
        <path d="M-30 177q35-33 69-7t69 0 69 0M-30 187q35-33 69-7t69 0 69 0M-30 198q35-33 69-7t69 0 69 0M1425 174q35-28 69-3t69 0 69 0M1425 185q35-28 69-3t69 0 69 0M1425 196q35-28 69-3t69 0 69 0" />
        {[0, 1, 2, 3].map((n) => (
          <path
            key={n}
            d={`m${n * 25 - 10} 213 12-10 12 10-12 10Zm${1450 + n * 25} 0 12-10 12 10-12 10Z`}
          />
        ))}
      </g>
      <g
        className="nx-atlas-corner-leaves"
        fill="#779443"
        stroke="#d5c56f"
        strokeWidth="1"
      >
        <path d="M0 738Q75 629 10 554q-32 96-10 184M0 754q125-87 91-156Q9 633 0 754M0 770q125-50 142-7Q81 798 0 770M0 746q55-119 4-171-17 89-4 171M1600 805q-104-109-164-53 57 55 164 53M1600 807q-48-143-103-111-8 71 103 111M1600 817q-136-42-149 19 79 23 149-19" />
        <path
          d="M0 756 72 626M0 767l108-2M1600 810l-137-50m137 46-88-100"
          fill="none"
        />
      </g>
      <path
        d="M-10 708C96 683 207 814 364 852Q460 887 558 916L479 942C302 876 214 855 93 823Q27 806-10 821Z"
        fill="url(#atlas-border-weave)"
        stroke="#eac580"
        strokeWidth="4"
      />
      <path
        d="M-10 708C96 683 207 814 364 852Q460 887 558 916L479 942C302 876 214 855 93 823Q27 806-10 821Z"
        fill="url(#atlas-border-light)"
      />
      <path
        d="M1083 918q134-101 249-84 134 19 278-91v83q-90 35-181 28-128-21-237 72Z"
        fill="url(#atlas-border-weave)"
        stroke="#eac580"
        strokeWidth="4"
      />
      <path
        d="M1083 918q134-101 249-84 134 19 278-91v83q-90 35-181 28-128-21-237 72Z"
        fill="url(#atlas-border-light)"
      />
      <g
        transform="translate(1510 785)"
        fill="#fff1cb"
        stroke="#e2c783"
        strokeWidth="1"
      >
        {[0, 72, 144, 216, 288].map((a) => (
          <ellipse key={a} cy="-13" rx="8" ry="16" transform={`rotate(${a})`} />
        ))}
        <circle r="5" fill="#dfae4b" />
      </g>
    </svg>
  );
}
