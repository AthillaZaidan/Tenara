export type GalleryVariant = {
  id: string;
  entry_id: string;
  name: string;
  description: string;
  images: { url: string; caption: string | null; credit: string | null; license: string | null }[];
};
