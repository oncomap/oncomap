import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// Reset scroll to the top on every route change (path or query string). Without
// this, an SPA navigation keeps the previous scroll position - so a link low on
// the landing page (e.g. "Jump to verified datasets") opens the catalog scrolled
// to the bottom instead of at the top with its filters applied.
export default function ScrollToTop() {
  const { pathname, search, state } = useLocation();
  useEffect(() => {
    // Opening a record as a modal keeps the catalog mounted behind it, so the
    // background must stay where it was.
    if ((state as { background?: unknown } | null)?.background) return;
    window.scrollTo(0, 0);
  }, [pathname, search, state]);
  return null;
}
