export type Entry = {
  id: string;
  slug: string;
  name: string;
  kind: string;
  aliases: string[];
  textile_type: string | null;
  technique: string | null;
  region: string | null;
  community: string | null;
  summary: string | null;
  status: string;
  revision: number;
};

export async function loadEntries(): Promise<Entry[]> {
  const { api } = await import("./api");
  try {
    const data = await api<{ items: Entry[] }>("/gallery?limit=100", { token: null });
    return data.items;
  } catch {
    return [];
  }
}
