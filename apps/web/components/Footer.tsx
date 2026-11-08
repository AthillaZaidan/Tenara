import Link from "next/link";

export function Footer({ credits }: { credits?: React.ReactNode }) {
  return (
    <footer className="on-field relative overflow-hidden bg-field text-field-ink">
      <div className="frame grid gap-10 pt-24 pb-6 md:grid-cols-12">
        <div className="md:col-span-7">
          <p className="t-head max-w-[20ch]">Punya kain atau jarum?</p>
          <Link href="/partner" className="btn mt-8 no-underline">Daftar sebagai mitra</Link>
        </div>
        <ul className="grid gap-2 text-base md:col-span-3 md:col-start-10 list-none p-0">
          <li><Link href="/gallery">Gallery</Link></li>
          <li><Link href="/login">Masuk</Link></li>
          <li><Link href="/register">Daftar</Link></li>
                  </ul>
      </div>
      <div className="frame t-small flex flex-wrap justify-between gap-x-8 gap-y-2 pb-3">
        <span>Pembayaran, pengiriman, dan komisi pada versi ini adalah simulasi demo.</span>
        {credits}
      </div>
      <p
        aria-hidden
        className="t-display select-none whitespace-nowrap leading-none"
        style={{ fontSize: "26vw", transform: "translateY(30%)", marginLeft: "-1vw" }}
      >
        Tenara
      </p>
    </footer>
  );
}
