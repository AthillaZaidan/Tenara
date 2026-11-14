"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import {
  forwardRef,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";

type Variant = "region" | "toolbar" | "icon" | "menu" | "text" | "passport";
type ContentProps = {
  children?: ReactNode;
  icon?: ReactNode;
  trailing?: ReactNode;
  badge?: number;
  variant?: Variant;
  className?: string;
};
type ButtonProps = ContentProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className">;
type LinkProps = ContentProps &
  Omit<
    AnchorHTMLAttributes<HTMLAnchorElement>,
    "children" | "className" | "href"
  > & { href: string };

export function MapSurface() {
  return (
    <>
      <span className="map-control-surface" aria-hidden="true">
        <span className="map-control-wash" />
      </span>
      <span className="map-control-inlay" aria-hidden="true" />
    </>
  );
}

function MapButtonContent({
  children,
  icon,
  trailing,
  badge,
  variant,
}: ContentProps) {
  return (
    <>
      {variant !== "text" && <MapSurface />}
      <span className="map-control-content">
        {icon && <span className="map-control-leading">{icon}</span>}
        {children && <span className="map-control-label">{children}</span>}
        {badge !== undefined && (
          <span className="map-control-badge">{badge}</span>
        )}
        {trailing && <span className="map-control-trailing">{trailing}</span>}
      </span>
    </>
  );
}

/** Native buttons keep refs, accessible names and camera tracking on the root.
 * All visual feedback lives on inner HTML/CSS layers, with no image assets.
 */
export const MapButton = forwardRef<HTMLButtonElement, ButtonProps>(
  function MapButton(
    {
      children,
      icon,
      trailing,
      badge,
      variant = "toolbar",
      className = "",
      type = "button",
      ...props
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        type={type}
        className={`map-control map-control--${variant} ${className}`}
        {...props}
      >
        <MapButtonContent
          variant={variant}
          icon={icon}
          trailing={trailing}
          badge={badge}
        >
          {children}
        </MapButtonContent>
      </button>
    );
  },
);

export const MapButtonLink = forwardRef<HTMLAnchorElement, LinkProps>(
  function MapButtonLink(
    {
      children,
      icon,
      trailing,
      badge,
      variant = "toolbar",
      className = "",
      href,
      ...props
    },
    ref,
  ) {
    return (
      <Link
        ref={ref}
        href={href}
        className={`map-control map-control--${variant} ${className}`}
        {...props}
      >
        <MapButtonContent
          variant={variant}
          icon={icon}
          trailing={trailing}
          badge={badge}
        >
          {children}
        </MapButtonContent>
      </Link>
    );
  },
);

type IconName =
  | "catalog"
  | "book"
  | "settings"
  | "close"
  | "arrow"
  | "chevron"
  | "compass"
  | "display"
  | "gem"
  | "pin"
  | "check";
/** CSS pictograms and a standard vector arrow; no button/icon image assets. */
export function MapIcon({ name }: { name: IconName }) {
  if (name === "arrow")
    return (
      <ArrowUpRight
        className="map-icon map-icon--arrow"
        size={18}
        strokeWidth={1.75}
        aria-hidden="true"
      />
    );
  return (
    <span className={`map-icon map-icon--${name}`} aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}

export function MapPassport({
  visited,
  total,
  onClick,
}: {
  visited: number;
  total: number;
  onClick: () => void;
}) {
  return (
    <MapButton
      variant="passport"
      onClick={onClick}
      aria-label={`Buka daftar daerah, ${visited} dari ${total} dikunjungi`}
    >
      <span className="map-passport-book" aria-hidden="true">
        <span>PASPOR</span>
        <i />
      </span>
      <span className="map-passport-copy">
        <strong>Paspor Jelajah</strong>
        <small>
          {visited} / {total} daerah
          <span className="map-passport-extra"> dikunjungi</span>
        </small>
        <span
          className="map-passport-track"
          role="progressbar"
          aria-label="Daerah dikunjungi"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={visited}
        >
          <span style={{ width: `${total ? (visited / total) * 100 : 0}%` }} />
        </span>
      </span>
    </MapButton>
  );
}
