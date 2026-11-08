import type { Metadata } from "next";
import { Hanken_Grotesk } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Reveal } from "@/components/Reveal";

const hanken = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"], weight: ["400", "500"] });

export const metadata: Metadata = {
  title: { default: "Tenara — tenun Nusantara, dari cerita sampai baju", template: "%s · Tenara" },
  description:
    "Pelajari asal-usul kain tenun dari sumber yang dikurasi, bandingkan penjual terverifikasi, lalu beli kainnya atau jadikan baju bersama penjahit.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className={hanken.variable}>
      <head>
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="" />
        <link href="https://api.fontshare.com/v2/css?f[]=zodiak@100,300&display=swap" rel="stylesheet" />
      </head>
      <body>
        <AuthProvider>
          {children}
          <Reveal />
        </AuthProvider>
      </body>
    </html>
  );
}
