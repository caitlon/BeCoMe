/**
 * Trigger a browser download of a Blob by clicking a temporary anchor.
 *
 * The fetch + Blob approach is required because authorized endpoints use a
 * Bearer header, so a plain `<a href download>` cannot reach them. Used for the
 * result export (PDF/CSV) and the GDPR data export.
 *
 * @param blob - The file contents.
 * @param filename - Suggested file name for the download.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Trigger a browser download of a JSON-serializable value as a file.
 *
 * @param data - Any JSON-serializable value.
 * @param filename - Suggested file name for the download.
 */
export function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  });
  downloadBlob(blob, filename);
}
