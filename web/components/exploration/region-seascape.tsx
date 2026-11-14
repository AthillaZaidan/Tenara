/** Broad, screen-space cloud banks keep the ocean continuous behind every camera pose. */
export function RegionSeascape() {
  return (
    <div className="nx-region-seascape" aria-hidden="true">
      <div className="nx-sea-haze nx-sea-haze-far" />
      <div className="nx-sea-haze nx-sea-haze-near" />
      <svg
        className="nx-sea-glints"
        viewBox="0 0 1600 1000"
        preserveAspectRatio="xMidYMid slice"
      >
        <g fill="none" stroke="currentColor" strokeLinecap="round">
          <path d="m90 430 38-8m-2 11 17-4M1280 310l46-10m-14 14 24-5M170 760l50-11m-22 14 32-7M1320 735l54-12m-12 14 27-6M930 895l38-8" />
        </g>
      </svg>
    </div>
  );
}
