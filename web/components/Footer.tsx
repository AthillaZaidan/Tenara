import Link from "next/link";

export function Footer({ credits }: { credits?: React.ReactNode }) {
  return (
    <footer className="site-footer on-field overflow-hidden bg-field text-field-ink">
      <div className="frame mx-auto grid w-full max-w-[1430px] gap-12 pt-14 pb-10 md:grid-cols-[minmax(0,1fr)_240px] md:gap-10 md:pt-20 md:pb-16">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-field-ink/60">
            Untuk pengrajin dan pelaku kriya
          </p>
          <h2 className="t-head m-0 max-w-[20ch]">Punya kain atau jarum?</h2>
          <Link href="/partner" className="btn mt-6 no-underline">
            Daftar sebagai mitra
          </Link>
        </div>

        <nav aria-label="Tautan footer" className="md:pt-1">
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-field-ink/60">
            Galeri
          </p>
          <ul className="m-0 grid list-none gap-2 p-0 text-sm">
            <li><Link className="underline-offset-4 transition-opacity hover:underline hover:opacity-70" href="/galeri">Galeri</Link></li>
            <li><Link className="underline-offset-4 transition-opacity hover:underline hover:opacity-70" href="/katalog">Katalog Kain</Link></li>
            <li><Link className="underline-offset-4 transition-opacity hover:underline hover:opacity-70" href="/login">Masuk</Link></li>
            <li><Link className="underline-offset-4 transition-opacity hover:underline hover:opacity-70" href="/register">Daftar</Link></li>
          </ul>
        </nav>
      </div>

      <div className="frame mx-auto grid w-full max-w-[1430px] gap-4 border-t border-field-ink/20 py-5 text-xs leading-relaxed text-field-ink/70 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start sm:gap-8">
        <p className="m-0">
          Pembayaran, pengiriman, dan komisi pada versi ini adalah simulasi demo.
        </p>
        {credits && (
          <details className="sm:justify-self-end">
            <summary className="cursor-pointer font-medium text-field-ink underline underline-offset-4">
              Kredit gambar
            </summary>
            <div className="mt-3 max-w-[70ch] text-field-ink/70 [&_p]:m-0 [&_a]:underline [&_a]:underline-offset-2">
              {credits}
            </div>
          </details>
        )}
      </div>

      <div className="frame mx-auto w-full max-w-[1430px] overflow-hidden pt-2">
        <p
          aria-hidden
          className="t-display m-0 select-none whitespace-nowrap leading-[0.78] tracking-[-0.07em] text-field-ink/10"
          style={{ fontSize: "clamp(4rem, 17vw, 15rem)" }}
        >
          Tenara
        </p>
      </div>
    </footer>
  );
}
