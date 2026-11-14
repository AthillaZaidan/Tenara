/** Decorative nine-slice artwork. Labels and interaction remain ordinary HTML. */
export function OrnateFrame({
  square = false,
  variant = "label",
}: {
  square?: boolean;
  variant?: "label" | "toolbar" | "panel" | "passport" | "display";
}) {
  return (
    <span
      className={`nx-ornate-frame nx-ornate-frame-${square ? "square" : variant}`}
      aria-hidden="true"
    >
      <span className="nx-ornate-wash" />
    </span>
  );
}

export function OrnateGem() {
  return <HudIcon name="gem" className="nx-ornate-gem" />;
}

export function HudIcon({
  name,
  className = "",
}: {
  name:
    | "gem"
    | "catalog"
    | "book"
    | "arrow"
    | "settings"
    | "close"
    | "compass"
    | "display"
    | "chevron";
  className?: string;
}) {
  return (
    <img
      className={`nx-hud-icon nx-hud-icon-${name} ${className}`}
      src={`/assets/exploration/hud-icon-${name}.svg`}
      alt=""
      aria-hidden="true"
      width="20"
      height="20"
      draggable={false}
    />
  );
}
