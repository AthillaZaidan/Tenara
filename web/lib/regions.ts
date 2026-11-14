import type { Entry } from "@/lib/types";
import type { RegionId } from "@/lib/exploration";

export type Region = { id: RegionId; name: string; position: [number, number]; aliases: string[] };

// Locations describe the illustrated navigation only. Cultural text is supplied by the API.
export const regions: Region[] = [
  { id: "sumatera-utara", name: "Sumatera Utara", position: [13, 24], aliases: ["sumatera utara", "batak", "ulos"] },
  { id: "sumatera-barat", name: "Sumatera Barat", position: [17, 40], aliases: ["sumatera barat", "minangkabau", "pandai sikek"] },
  { id: "sumatera-selatan", name: "Sumatera Selatan", position: [23, 52], aliases: ["sumatera selatan", "palembang"] },
  { id: "jawa-tengah", name: "Jawa Tengah", position: [36, 73], aliases: ["jawa tengah", "jepara", "troso"] },
  { id: "bali", name: "Bali", position: [43, 75], aliases: ["bali", "endek", "gringsing"] },
  { id: "lombok", name: "Lombok", position: [48, 74], aliases: ["lombok", "sasak"] },
  { id: "sumba", name: "Sumba", position: [54, 85], aliases: ["sumba", "hinggi"] },
  { id: "flores", name: "Sikka · Flores", position: [60, 75], aliases: ["sikka", "flores"] },
  { id: "sulawesi-tengah", name: "Sulawesi Tengah", position: [56, 38], aliases: ["sulawesi tengah", "donggala"] },
];

export function regionExploreHrefForTerms(terms: (string | null | undefined)[]): string {
  const text = terms.filter(Boolean).join(" ").toLocaleLowerCase("id");
  const region = regions.find((item) => item.aliases.some((alias) => {
    const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(?:^|[^a-z])${escaped}(?:$|[^a-z])`, "i").test(text);
  }));
  return region ? `/galeri/daerah/${region.id}` : "/galeri";
}

export function regionExploreHrefForEntry(entry: Pick<Entry, "name" | "aliases" | "textile_type" | "region" | "community">): string {
  return regionExploreHrefForTerms([
    entry.name,
    entry.region,
    entry.community,
    entry.textile_type,
    ...entry.aliases,
  ]);
}

export function entriesForRegion(entries: Entry[], region: Region): Entry[] {
  return entries.filter((entry) => {
    const text = [entry.name, entry.region, entry.community, entry.textile_type, ...entry.aliases].filter(Boolean).join(" ").toLocaleLowerCase("id");
    return region.aliases.some((alias) => {
      const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return new RegExp(`(?:^|[^a-z])${escaped}(?:$|[^a-z])`, "i").test(text);
    });
  });
}
