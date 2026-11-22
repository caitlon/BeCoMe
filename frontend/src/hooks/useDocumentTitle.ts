import { useEffect } from "react";

// A non-empty title gets " - BeCoMe" appended unless `suffix` is false;
// an empty title always gives "BeCoMe".
export function useDocumentTitle(title: string, { suffix = true }: { suffix?: boolean } = {}) {
  useEffect(() => {
    if (!title) {
      document.title = "BeCoMe";
    } else {
      document.title = suffix ? `${title} - BeCoMe` : title;
    }
  }, [title, suffix]);
}
