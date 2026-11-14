import { redirect } from "next/navigation";

type RegisterPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function RegisterPage({ searchParams }: RegisterPageProps) {
  const params = await searchParams;
  const next = Array.isArray(params.next) ? params.next[0] : params.next;
  const query = new URLSearchParams({ mode: "register" });
  if (next) query.set("next", next);

  redirect(`/login?${query.toString()}`);
}
