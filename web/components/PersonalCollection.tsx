import Link from "next/link";
import { ArrowRight, ChevronRight, Heart, ShoppingBag } from "lucide-react";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import "./personal-collection.css";

export function PersonalCollection({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <>
    <Nav />
    <main className="personal-collection">
      <div className="personal-shell">
        <nav className="personal-breadcrumb" aria-label="Breadcrumb">
          <Link href="/account">Akun saya</Link><ChevronRight size={13} aria-hidden="true" /><span aria-current="page">{title}</span>
        </nav>
        <header className="personal-heading">
          <div><p className="personal-eyebrow">RUANG PRIBADI TENARA</p><h1>{title}</h1><p className="personal-description">{description}</p></div>
          <Link href="/katalog" className="personal-catalog-link">Jelajahi katalog <ArrowRight size={16} aria-hidden="true" /></Link>
        </header>
        {children}
      </div>
    </main>
    <Footer />
  </>;
}

export function CollectionEmptyState({ kind, title, description, href, action }: { kind: "designs" | "orders"; title: string; description: string; href?: string; action?: string }) {
  const Icon = kind === "designs" ? Heart : ShoppingBag;
  return <div className="personal-empty">
    <div className={`personal-illustration personal-illustration--${kind}`} aria-hidden="true">
      <svg viewBox="0 0 160 124" fill="none">
        <ellipse cx="80" cy="65" rx="55" ry="51" fill="#edf0e8" />
        <path d="m24 32 4-4 4 4-4 4-4-4Zm105 57 4-4 4 4-4 4-4-4Z" stroke="#9ba78e" />
        <path d="M127 28v10m-5-5h10M24 88v6m-3-3h6" stroke="#9ba78e" strokeLinecap="round" />
        {kind === "designs" ? <>
          <path d="m52 29 53 7-8 68-53-7 8-68Z" fill="#e0e6d9" stroke="#7d8e70" strokeWidth="1.5" />
          <path d="m61 22 51 14-17 64-51-14 17-64Z" fill="#fffefa" stroke="#3d5a33" strokeWidth="1.5" strokeLinejoin="round" />
          <path d="m60 43 39 10M56 57l39 10M52 71l39 10M69 35l-12 45m26-41L71 84m26-41L85 88" stroke="#b7c1aa" />
          <path d="m79 48 8 13-13 8-8-13 13-8Z" fill="#edf0e8" stroke="#3d5a33" strokeWidth="1.5" />
          <path d="m61 22 51 14-3 11-51-14 3-11Z" fill="#e0e6d9" stroke="#3d5a33" strokeWidth="1.5" />
        </> : <>
          <path d="m52 46-6 53h68l-6-53H52Z" fill="#fffefa" stroke="#3d5a33" strokeWidth="1.7" strokeLinejoin="round" />
          <path d="M66 48V37a14 14 0 0 1 28 0v11" stroke="#3d5a33" strokeWidth="1.7" strokeLinecap="round" />
          <path d="m80 61 12 12-12 12-12-12 12-12Z" fill="#edf0e8" stroke="#7d8e70" strokeWidth="1.3" />
          <path d="m80 68 5 5-5 5-5-5 5-5Z" stroke="#3d5a33" strokeWidth="1.3" />
          <path d="M53 92h54" stroke="#b7c1aa" strokeDasharray="3 4" />
        </>}
      </svg>
      <span className="personal-illustration-badge"><Icon size={15} strokeWidth={1.6} /></span>
    </div>
    <h2>{title}</h2>
    <p>{description}</p>
    {href && action && <Link href={href} className="btn">{action}<ArrowRight size={16} aria-hidden="true" /></Link>}
  </div>;
}

export function CollectionLoading({ children }: { children: React.ReactNode }) {
  return <div className="personal-loading" role="status"><span className="personal-loading-dot" />{children}</div>;
}
