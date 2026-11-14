import { AccountData } from "@/components/AccountData";
import { Page, RequireAuth } from "@/components/ui";

export const metadata = { title: "Akun dan privasi" };

export default function AccountPage() {
  return <Page><h1 className="t-head mb-4 mt-8">Akun dan privasi</h1><p className="mb-10 max-w-2xl">Kelola alamat pengiriman dan kendali atas foto badan Anda.</p><RequireAuth><AccountData /></RequireAuth></Page>;
}
