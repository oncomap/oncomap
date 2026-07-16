import { createContext, useContext } from "react";
import type { SiteData } from "./types";

// Same-origin payload: dev serves web/public/site.json, prod serves the copy
// build_site.sh drops next to index.html. The build-time pipeline
// (records/*.yaml -> build/compile.py) stays the source of truth.
//
// Root-relative on purpose: a nested route like /dataset/:id would resolve a
// bare "site.json" to /dataset/site.json, which the SPA fallback answers with
// index.html - breaking every deep link into a record.
export async function loadSiteData(): Promise<SiteData> {
  const res = await fetch("/site.json", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(
      "Could not load site.json. Run 'uv run python build/compile.py' first.",
    );
  }
  return (await res.json()) as SiteData;
}

export const SiteContext = createContext<SiteData | null>(null);

export function useSite(): SiteData {
  const data = useContext(SiteContext);
  if (!data) throw new Error("useSite used outside of a loaded SiteContext");
  return data;
}
