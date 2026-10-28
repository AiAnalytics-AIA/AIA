import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { errorTechnical, errorText, errorWords } from "./error-words";

describe("error words", () => {
  it("says a refusal in Czech by its status, never the API's English", () => {
    const e = new ApiError(404, "not_found", "Not found, or not accessible", "req-1");
    expect(errorWords(e)).toBe("Tady nic není, nebo k tomu nemáte přístup.");
    expect(errorWords(new ApiError(503, "x", "upstream", null))).toMatch(/^AIA teď neodpovídá/);
    expect(errorWords(new ApiError(409, "stale", "stale", null))).toMatch(/^Mezitím se tu něco změnilo/);
    expect(errorWords(new ApiError(418, "teapot", "x", null))).toBe("Nepovedlo se to. Zkuste to prosím znovu.");
  });

  it("tells a dropped connection apart", () => {
    expect(errorWords(new TypeError("Failed to fetch"))).toMatch(/^Nepodařilo se spojit s AIA/);
  });

  it("keeps the technical detail, labelled, after the sentence", () => {
    const e = new ApiError(403, "insufficient_role", "Your role on this study", "req-9");
    expect(errorTechnical(e)).toBe("HTTP 403 · insufficient_role: Your role on this study (req-9)");
    expect(errorText(e)).toBe("K tomu nemáte oprávnění. O změnu požádejte vlastníka nebo správce organizace. (Technické údaje: HTTP 403 · insufficient_role: Your role on this study (req-9))");
    expect(errorText(null)).toBe("Nepovedlo se to. Zkuste to prosím znovu.");
    // What this client raised itself is already in Czech and is said as written.
    expect(errorText(new Error("Konfiguraci nasazení se nepodařilo načíst."))).toBe("Konfiguraci nasazení se nepodařilo načíst.");
  });
});
