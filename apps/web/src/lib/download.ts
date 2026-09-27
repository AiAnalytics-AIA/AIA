"use client";

// Save bytes the API served as a file on the person's machine. A download that
// needs the bearer token cannot be a plain <a href> (lib/api.ts): the bytes are
// fetched, given an object URL, and a temporary anchor is clicked.

export function saveBlob(blob: Blob, filename: string): void {
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 0);
}
