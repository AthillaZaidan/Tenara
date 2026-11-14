"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Eye, EyeOff, LockKeyhole } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import { Notice, useAction } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { catalogSamples, type CatalogSample } from "@/lib/catalog-data";

const loginFabricCodes = ["SUM-01", "SIK-01", "JTG-01", "PLB-01", "DGL-01"];
const loginFabrics = loginFabricCodes
  .map((code) => catalogSamples.find((sample) => sample.code === code))
  .filter((sample): sample is CatalogSample => sample !== undefined);

type AuthMode = "login" | "register";

function AuthPanel() {
  const { login, register } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/orders";
  const { busy, error, run, setError } = useAction();
  const [mode, setMode] = useState<AuthMode>(searchParams.get("mode") === "register" ? "register" : "login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const selectMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setError(null);
    setPassword("");
    setConfirmPassword("");
    setShowPassword(false);
  };

  return (
    <>
      <h1 className="login-heading" id="login-title">
        {mode === "login" ? <>Selamat datang <em>kembali.</em></> : <>Buat akun <em>Tenara.</em></>}
      </h1>
      <p className="login-intro">
        {mode === "login"
          ? "Masuk untuk melanjutkan perjalananmu bersama kain dan cerita dari Nusantara."
          : "Bergabung untuk menyimpan kain, desain, dan cerita favoritmu."}
      </p>
      <div className="login-mode-switch" role="group" aria-label="Pilih mode akun">
        <button type="button" aria-pressed={mode === "login"} onClick={() => selectMode("login")}>Masuk</button>
        <button type="button" aria-pressed={mode === "register"} onClick={() => selectMode("register")}>Daftar</button>
      </div>
      <form
        className="login-form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (mode === "register" && password !== confirmPassword) {
            setError("Konfirmasi kata sandi belum sama.");
            return;
          }
          const user = await run(() => mode === "login" ? login(email, password) : register(email, password, displayName));
          if (user) router.replace(next.startsWith("/") ? next : "/orders");
        }}
      >
        {mode === "register" && (
          <label className="login-field" htmlFor="register-name">
            <span>Nama</span>
            <input
              className="field"
              id="register-name"
              type="text"
              placeholder="Nama lengkap"
              required
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </label>
        )}
        <label className="login-field" htmlFor="auth-email">
          <span>Email</span>
          <input
            className="field"
            id="auth-email"
            type="email"
            placeholder="nama@email.com"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <div className="login-field">
          <label htmlFor="auth-password">Kata sandi</label>
          <div className="login-password-wrap">
            <input
              className="field"
              id="auth-password"
              type={showPassword ? "text" : "password"}
              placeholder="Masukkan kata sandi"
              required
              minLength={mode === "register" ? 8 : undefined}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              className="login-password-toggle"
              type="button"
              aria-label={showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((shown) => !shown)}
            >
              {showPassword ? <EyeOff size={18} strokeWidth={1.7} /> : <Eye size={18} strokeWidth={1.7} />}
            </button>
          </div>
          {mode === "register" && <span className="login-field-hint">Minimal 8 karakter.</span>}
        </div>
        {mode === "register" && (
          <label className="login-field" htmlFor="register-confirm-password">
            <span>Konfirmasi kata sandi</span>
            <input
              className="field"
              id="register-confirm-password"
              type={showPassword ? "text" : "password"}
              placeholder="Ulangi kata sandi"
              required
              minLength={8}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </label>
        )}
        {error && <Notice tone="error">{error}</Notice>}
        <button className="btn login-submit" disabled={busy}>
          <span>{busy ? mode === "login" ? "Memeriksa akun…" : "Membuat akun…" : mode === "login" ? "Masuk ke akun" : "Buat akun"}</span>
          <ArrowRight size={18} strokeWidth={1.8} aria-hidden="true" />
        </button>
      </form>
      <div className="login-register">
        <span>{mode === "login" ? "Belum punya akun?" : "Sudah punya akun?"}</span>
        <button className="login-register-toggle" type="button" onClick={() => selectMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Daftar" : "Masuk"}
        </button>
      </div>
    </>
  );
}

export default function LoginPage() {
  const [activeFabricIndex, setActiveFabricIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const [isFocusWithin, setIsFocusWithin] = useState(false);

  useEffect(() => {
    if (isHovered || isFocusWithin || loginFabrics.length < 2) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const interval = window.setInterval(() => {
      setActiveFabricIndex((index) => (index + 1) % loginFabrics.length);
    }, 5000);

    return () => window.clearInterval(interval);
  }, [isHovered, isFocusWithin]);

  return (
    <>
      <Nav />
      <main className="login-main">
        <div className="login-layout">
          <section className="login-copy" aria-labelledby="login-title">
            <div className="login-copy-inner">
              <p className="login-eyebrow"><span aria-hidden="true" /> RUANG PERSONAL TENARA</p>
              <Suspense fallback={<div className="login-form-skeleton" aria-label="Memuat formulir masuk" />}>
                <AuthPanel />
              </Suspense>
              <p className="login-note"><LockKeyhole size={15} strokeWidth={1.7} aria-hidden="true" /> Pesanan, desain, dan kain favoritmu tersimpan di satu tempat.</p>
            </div>
          </section>

          <aside
            className="login-art"
            aria-label="Pratinjau kain tenun Nusantara"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onFocusCapture={() => setIsFocusWithin(true)}
            onBlurCapture={(event) => {
              const nextTarget = event.relatedTarget;
              if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
                setIsFocusWithin(false);
              }
            }}
          >
            {loginFabrics.map((fabric, index) => (
              <Image
                key={fabric.code}
                className={`login-art-photo${index === activeFabricIndex ? " is-active" : ""}`}
                src={fabric.images.utama}
                alt={index === activeFabricIndex ? `Kain tenun bermotif ${fabric.label} dari koleksi Nusantara` : ""}
                fill
                priority={index === 0}
                aria-hidden={index !== activeFabricIndex}
                sizes="(max-width: 780px) 100vw, 52vw"
              />
            ))}
            <div className="login-art-overlay">
              <div className="login-art-caption">
                <p className="login-art-kicker">SATU HELAI, BANYAK CERITA</p>
                <h2>Warisan yang terus <em>ditenun.</em></h2>
                <p>Jelajahi kain, kisah budaya, dan perajin yang menjaganya.</p>
              </div>
              <div className="login-art-controls">
                <span className="login-art-index">
                  {String(activeFabricIndex + 1).padStart(2, "0")} <span aria-hidden="true">/</span> {String(loginFabrics.length).padStart(2, "0")} <span aria-hidden="true">·</span> NUSANTARA
                </span>
                <div className="login-art-dots" role="group" aria-label="Pilih pratinjau kain">
                  {loginFabrics.map((fabric, index) => (
                    <button
                      key={fabric.code}
                      className={`login-art-dot${index === activeFabricIndex ? " is-active" : ""}`}
                      type="button"
                      aria-label={`Tampilkan pratinjau kain ${index + 1}`}
                      aria-pressed={index === activeFabricIndex}
                      onClick={() => setActiveFabricIndex(index)}
                    />
                  ))}
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>
      <Footer />
    </>
  );
}
