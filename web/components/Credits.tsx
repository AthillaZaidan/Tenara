const items: [string, string, string, string, string][] = [
  ["Katoenen ikatweefsel afkomstig uit Soemba, KITLV 5636", "https://commons.wikimedia.org/w/index.php?curid=105093343", "AnonymousUnknown author", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
  ["Ikatweefsel afkomstig uit Soemba, KITLV 5639", "https://commons.wikimedia.org/w/index.php?curid=105246648", "AnonymousUnknown author", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
  ["Laoe komboe ikatweefsel afkomstig uit Soemba, KITLV 5629", "https://commons.wikimedia.org/w/index.php?curid=105274791", "AnonymousUnknown author", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
  ["Ikatweefsel afkomstig uit Soemba, KITLV 5632", "https://commons.wikimedia.org/w/index.php?curid=105139211", "AnonymousUnknown author", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"],
  ["Indonesia, scialle kain songket limar (Palembang, abad XIX)", "https://commons.wikimedia.org/w/index.php?curid=179301266", "Francesco Bini", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"],
];

export function Credits() {
  return (
    <p className="max-w-3xl">
      Gambar:{" "}
      {items.map(([title, url, who, lic, licUrl], i) => (
        <span key={url}>
          <a href={url} className="underline">“{title}”</a> oleh {who}, <a href={licUrl} className="underline">{lic}</a>, via Wikimedia Commons{i < items.length - 1 ? "; " : "."}
        </span>
      ))}
    </p>
  );
}
