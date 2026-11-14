"use client";

import { useMemo, useSyncExternalStore } from "react";

export const galleryFavoritesKey = "tenara.catalog.favorites";
const emptyFavorites = "[]";
let sessionFavorites = emptyFavorites;
let sessionOnly = false;

function snapshot() {
  if (sessionOnly) return sessionFavorites;
  try {
    return window.localStorage.getItem(galleryFavoritesKey) ?? emptyFavorites;
  } catch {
    return sessionFavorites;
  }
}

function parseFavorites(value: string): string[] {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === "string")
      : [];
  } catch {
    return [];
  }
}

function subscribe(callback: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === galleryFavoritesKey) callback();
  };
  window.addEventListener("storage", onStorage);
  return () => window.removeEventListener("storage", onStorage);
}

function toggleFavorite(traditionId: string) {
  const current = parseFavorites(snapshot());
  const next = current.includes(traditionId)
    ? current.filter((id) => id !== traditionId)
    : [...current, traditionId];
  sessionFavorites = JSON.stringify(next);
  try {
    window.localStorage.setItem(galleryFavoritesKey, sessionFavorites);
    sessionOnly = false;
  } catch {
    // Keep favorites available for this session when storage is unavailable.
    sessionOnly = true;
  }
  // Notify this document too, including the existing catalog's storage listener.
  window.dispatchEvent(
    new StorageEvent("storage", {
      key: galleryFavoritesKey,
      newValue: sessionFavorites,
    }),
  );
}

export function useGalleryFavorites() {
  const serialized = useSyncExternalStore(
    subscribe,
    snapshot,
    () => emptyFavorites,
  );
  const favorites = useMemo(() => parseFavorites(serialized), [serialized]);
  return { favorites, toggleFavorite };
}
