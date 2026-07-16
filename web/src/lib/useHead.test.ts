import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useHead } from "./useHead";

describe("useHead", () => {
  it("sets document.title suffixed with the base title", () => {
    renderHook(() => useHead("Contact"));
    expect(document.title).toContain("Contact");
    expect(document.title).toContain("OncoMap");
  });

  it("falls back to the base title when title is empty", () => {
    renderHook(() => useHead(""));
    expect(document.title).toBe("OncoMap");
  });

  it("creates and sets the meta description when provided", () => {
    renderHook(() => useHead("Stats", "A description of the stats page."));
    const tag = document.querySelector<HTMLMetaElement>(
      'meta[name="description"]',
    );
    expect(tag).not.toBeNull();
    expect(tag!.content).toBe("A description of the stats page.");
  });

  it("does not touch the meta description when none is given", () => {
    // seed a description, then call useHead without one
    let tag = document.querySelector<HTMLMetaElement>(
      'meta[name="description"]',
    );
    if (!tag) {
      tag = document.createElement("meta");
      tag.name = "description";
      document.head.appendChild(tag);
    }
    tag.content = "seed";
    renderHook(() => useHead("NoDesc"));
    expect(
      document.querySelector<HTMLMetaElement>('meta[name="description"]')!
        .content,
    ).toBe("seed");
  });
});
