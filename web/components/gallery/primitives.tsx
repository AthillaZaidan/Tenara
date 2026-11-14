"use client";

// Private copies of the prototype primitives keep the museum's original DOM.
import Link from "next/link";
import { ArrowRight, ChevronRight } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link
      href="/"
      className={`brand ${light ? "brand-light" : ""}`}
      aria-label="Tenara — beranda"
    >
      <svg viewBox="0 0 36 36" fill="none" aria-hidden="true">
        <path
          d="M18 2 34 18 18 34 2 18Z"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <path
          d="m18 8 10 10-10 10L8 18Zm0 6 4 4-4 4-4-4ZM7 7l22 22M29 7 7 29"
          stroke="currentColor"
          strokeWidth="1.2"
        />
      </svg>
      <span>Tenara</span>
    </Link>
  );
}

export function Button({
  href,
  children,
  variant = "primary",
  className = "",
  arrow = false,
  ...props
}: {
  href?: string;
  children: ReactNode;
  variant?: "primary" | "secondary" | "text";
  className?: string;
  arrow?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const cls = `button button-${variant} ${className}`;
  return href ? (
    <Link href={href} className={cls}>
      {children}
      {arrow && <ArrowRight size={24} strokeWidth={1.5} />}
    </Link>
  ) : (
    <button className={cls} {...props}>
      {children}
      {arrow && <ArrowRight size={24} strokeWidth={1.5} />}
    </button>
  );
}

export function Breadcrumb({
  items,
}: {
  items: { label: string; href?: string }[];
}) {
  return (
    <nav className="breadcrumb" aria-label="Jejak navigasi">
      <Link href="/">Beranda</Link>
      {items.map((item, i) => (
        <span key={i}>
          <ChevronRight size={12} />
          {item.href ? (
            <Link href={item.href}>{item.label}</Link>
          ) : (
            <span aria-current="page">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
