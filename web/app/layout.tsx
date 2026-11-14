import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: { default: "Tenara — tenun Nusantara, dari cerita sampai baju", template: "%s · Tenara" },
  description:
    "Pelajari asal-usul kain tenun dari sumber yang dikurasi, bandingkan penjual terverifikasi, lalu beli kainnya atau jadikan baju bersama penjahit.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        <AuthProvider>
          {children}
          <Reveal />
        </AuthProvider>
      </body>
    </html>
  );
}
