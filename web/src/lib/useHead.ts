import { useEffect } from "react";

const BASE_TITLE = "OncoMap";

// Minimal per-page <head> management without pulling in a helmet dependency.
// Sets document.title and the meta description, restoring neither on unmount
// (each page sets its own; the next navigation overwrites).
export function useHead(title: string, description?: string): void {
  useEffect(() => {
    document.title = title ? `${title} — ${BASE_TITLE}` : BASE_TITLE;
    if (description !== undefined) {
      let tag = document.querySelector<HTMLMetaElement>(
        'meta[name="description"]',
      );
      if (!tag) {
        tag = document.createElement("meta");
        tag.name = "description";
        document.head.appendChild(tag);
      }
      tag.content = description;
    }
  }, [title, description]);
}
