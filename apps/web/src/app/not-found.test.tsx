// @vitest-environment jsdom
// An address Next cannot route says so in Czech and offers the way back, never Next's English 404.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import NotFoundPage from "./not-found";

afterEach(cleanup);

describe("not found", () => {
  it("says the page is not in AIA and links to the clients", () => {
    render(<NotFoundPage />);
    expect(screen.getByRole("heading", { name: t("pageNotFound.title") })).toBeTruthy();
    expect(screen.getByText(t("pageNotFound.text"))).toBeTruthy();
    expect(screen.getByRole("link", { name: t("pageNotFound.openClients") }).getAttribute("href")).toBe("/app/clients");
    expect(screen.queryByText(/could not be found/i)).toBeNull();
  });
});
