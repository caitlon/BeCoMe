import { useEffect } from "react";

// A non-empty title gets " - BeCoMe" appended unless `suffix` is false;
// an empty title always gives "BeCoMe". The prerender reads the same rule through
// this function, so a page title in the shipped HTML cannot differ from the one
// the page sets.
export function documentTitle(title: string, suffix = true): string {
  if (!title) return "BeCoMe";
  return suffix ? `${title} - BeCoMe` : title;
}

export function useDocumentTitle(title: string, { suffix = true }: { suffix?: boolean } = {}) {
  useEffect(() => {
    document.title = documentTitle(title, suffix);
  }, [title, suffix]);
}
