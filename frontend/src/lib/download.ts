/**
 * Trigger a browser download of a JSON-serializable value as a file.
 *
 * Builds a Blob from the data and clicks a temporary anchor, then revokes the
 * object URL. The fetch + Blob approach is required because the API authorizes
 * with a Bearer header, so a plain `<a href download>` cannot reach the
 * endpoint. Used for the GDPR data export download.
 *
 * @param data - Any JSON-serializable value.
 * @param filename - Suggested file name for the download.
 */
export function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  });
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
