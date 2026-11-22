import { useEffect } from "react";

interface DocumentTitleOptions {
  /** Append " - BeCoMe" to the title. Set to false for a title that already names the product. */
  suffix?: boolean;
}

export function useDocumentTitle(title: string, { suffix = true }: DocumentTitleOptions = {}) {
  useEffect(() => {
    if (!title) {
      document.title = "BeCoMe";
    } else {
      document.title = suffix ? `${title} - BeCoMe` : title;
    }
  }, [title, suffix]);
}
