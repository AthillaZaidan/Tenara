"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, ChevronRight, CircleHelp, Leaf, type LucideIcon } from "lucide-react";
import { Nav } from "@/components/Nav";
import { MerchantSidebar, type WorkspaceSection } from "@/components/MerchantSidebar";
import { Notice, Page } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import "@/app/merchant/merchant.css";
import "./partner-workspace.css";

export type PartnerRole = "merchant" | "tailor";

export function useWorkspaceRole() {
  const { has } = useAuth();
  const requested = useSearchParams().get("as");
  const roles = (["buyer", "merchant", "tailor", "admin"] as const).filter((role) => has(role));
  return roles.find((role) => role === requested) ?? roles[0] ?? "buyer";
}

export function WorkspacePage({ role, active = "overview", title, description, action, back, children }: {
  role: PartnerRole; active?: WorkspaceSection; title: string; description: string; action?: React.ReactNode;
  back?: { href: string; label: string }; children: React.ReactNode;
}) {
  const home = role === "tailor" ? "/tailor" : "/merchant";
  return <div className={`merchant-dashboard partner-workspace ${role === "tailor" ? "tailor-dashboard" : ""}`}>
    <Nav />
    <main className="layout">
      <MerchantSidebar active={active} role={role} />
      <div className="content">
        <nav className="breadcrumb" aria-label="Breadcrumb"><Link href={home}>{role === "tailor" ? "Ruang penjahit" : "Ruang penjual"}</Link><ChevronRight size={13} aria-hidden="true" />{back && <><Link href={back.href}>{back.label}</Link><ChevronRight size={13} aria-hidden="true" /></>}<span aria-current="page">{title}</span></nav>
        <header className="heading"><div><p className="eyebrow">RUANG KARYA TENARA</p><h1>{title}</h1><p>{description}</p></div>{action}</header>
        <div className="workspace-body">{children}</div>
        <footer className="footer"><span><Leaf size={13} aria-hidden="true" />Tenara · Merawat cerita, menghubungkan karya.</span><span><CircleHelp size={14} aria-hidden="true" />Pembayaran & pengiriman dalam simulasi demo.</span></footer>
      </div>
    </main>
  </div>;
}

/** Keeps the selected partner workspace when opening shared order, request, and chat routes. */
export function WorkspaceRoute({ active, title, description, back, children }: {
  active: WorkspaceSection; title: string; description: string; back?: { href: string; label: string }; children: React.ReactNode;
}) {
  const role = useWorkspaceRole();
  if (role === "merchant" || role === "tailor") {
    return <WorkspacePage role={role} active={active} title={title} description={description} back={back && { ...back, href: `${back.href}${back.href.includes("?") ? "&" : "?"}as=${role}` }}>{children}</WorkspacePage>;
  }
  return <Page>{back && <Link href={back.href} className="link my-6 inline-flex items-center gap-2 text-sm"><ArrowLeft size={15} />{back.label}</Link>}<h1 className="t-head mb-4 mt-6">{title}</h1><p className="mb-8 max-w-2xl text-base text-muted">{description}</p>{children}</Page>;
}

export function WorkspacePanel({ title, description, icon: Icon, children, className = "", id }: { title: string; description?: string; icon?: LucideIcon; children: React.ReactNode; className?: string; id?: string }) {
  return <section className={`workspace-panel ${className}`} id={id}>
    <div className="workspace-panel-heading">{Icon && <span className="workspace-panel-icon"><Icon size={18} strokeWidth={1.5} aria-hidden="true" /></span>}<div><h2>{title}</h2>{description && <p>{description}</p>}</div></div>
    <div className="workspace-panel-body">{children}</div>
  </section>;
}

export function WorkspaceEmpty({ icon: Icon, title, description, href, action, onReset }: { icon: LucideIcon; title: string; description: string; href?: string; action?: string; onReset?: () => void }) {
  return <div className="workspace-empty"><span className="workspace-empty-art" aria-hidden="true"><Icon size={34} strokeWidth={1.1} /><span /></span><h3>{title}</h3><p>{description}</p>{href && action && <Link href={href} className="btn">{action}<ArrowRight size={15} aria-hidden="true" /></Link>}{onReset && <button type="button" className="btn btn-quiet" onClick={onReset}>Hapus filter</button>}</div>;
}

export function WorkspaceLoading({ children = "Menyiapkan ruang karya Anda…" }: { children?: React.ReactNode }) {
  return <div className="workspace-loading" role="status"><span />{children}</div>;
}

export function WorkspaceError({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="workspace-error"><Notice tone="error">{message}</Notice>{retry && <button type="button" className="btn btn-quiet" onClick={retry}>Coba lagi</button>}</div>;
}
