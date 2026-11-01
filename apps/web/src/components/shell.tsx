"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ArrowUpRight, ChartCandlestick, FlaskConical, LayoutDashboard, LockKeyhole,
  ShieldCheck, Swords, Wallet, Workflow, Menu, X, BookOpen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

const navigation = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/history", label: "Dados históricos", icon: BookOpen },
  { href: "/arena", label: "Arena", icon: Swords },
  { href: "/backtesting", label: "Backtesting", icon: FlaskConical },
  { href: "/signals", label: "Sinais", icon: Workflow },
  { href: "/paper", label: "Paper Trading", icon: ChartCandlestick },
  { href: "/wallet", label: "Carteira Bybit", icon: Wallet },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const closeWithEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && open) { setOpen(false); menuRef.current?.focus(); }
    };
    window.addEventListener("keydown", closeWithEscape);
    return () => window.removeEventListener("keydown", closeWithEscape);
  }, [open]);
  const current = navigation.find(n => n.href === pathname)?.label ?? "Execução real";
  return <div className="app-shell">
    {open && <button className="sidebar-scrim" aria-label="Fechar navegação" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Navegação principal">
      <Link className="brand" href="/" onClick={() => setOpen(false)}><span className="brand-mark"><Activity size={23} /></span><span>Crypto<span className="brand-light">Lab</span><small>ESCRYPTORIO</small></span></Link>
      <div className="workspace"><span className="workspace-dot" /><span>Workspace pessoal<small>Local · Bybit Spot</small></span><LockKeyhole size={13} /></div>
      <span className="nav-label">PESQUISA</span>
      <nav>{navigation.map(item => <Link key={item.href} href={item.href} aria-current={pathname === item.href ? "page" : undefined}
        className={`nav-item ${pathname === item.href ? "nav-active" : ""}`} onClick={() => setOpen(false)}>
        <item.icon size={17} /><span>{item.label}</span>{item.href === "/" && <span className="nav-dot" />}
      </Link>)}</nav>
      <div className="nav-divider" /><span className="nav-label">CONTROLE</span>
      <Link href="/execution" className={`nav-item ${pathname === "/execution" ? "nav-active" : ""}`} onClick={() => setOpen(false)}><ShieldCheck size={17} /><span>Execução real</span><LockKeyhole size={13} /></Link>
      <Link href="/roadmap" className="nav-item" onClick={() => setOpen(false)}><BookOpen size={17} /><span>Roteiro do projeto</span><ArrowUpRight size={13} /></Link>
      <div className="sidebar-bottom"><div className="safe-mode"><ShieldCheck size={18} /><div>Ambiente de pesquisa<small>Execução real desativada</small></div></div>
      <div className="profile"><span>HG</span><div>Workspace privado<small>Usuário único</small></div><LockKeyhole size={14} /></div></div>
    </aside>
    <div className="main-shell"><header className="topbar">
      <div className="breadcrumb"><Button ref={menuRef} variant="ghost" size="icon" className="mobile-menu" aria-label={open ? "Fechar menu" : "Abrir menu"} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X size={20} /> : <Menu size={20} />}</Button><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{current}</strong></div>
      <div className="topbar-right"><span className="public-mode"><LockKeyhole size={12} /> Somente leitura pública</span><span className="version">v0.1</span></div>
    </header>{children}<footer className="app-footer"><span>CryptoLab · Inteligência para pesquisar com método.</span><span>Mercado Spot <span className="footer-dot">·</span> Horários em Brasília (UTC−3)</span></footer></div>
  </div>;
}
