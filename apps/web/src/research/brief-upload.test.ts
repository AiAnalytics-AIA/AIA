import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { ATTACHMENT_MAX_BYTES, fileProblem, uploadProblem } from "./brief-upload";

describe("the Brief's upload, in Czech", () => {
  it("refuses an empty or too large file before sending it, at the server's own limit", () => {
    expect(fileProblem(0)).toBe("empty");
    expect(fileProblem(1)).toBeNull();
    expect(fileProblem(ATTACHMENT_MAX_BYTES)).toBeNull();
    expect(fileProblem(ATTACHMENT_MAX_BYTES + 1)).toBe("too_large");
  });

  it("says a refusal by its code, never the API's English message", () => {
    expect(uploadProblem("empty")).toBe("soubor je prázdný");
    expect(uploadProblem("too_large")).toBe("soubor je větší než 25 MB");
    const validation = new ApiError(422, "validation_error", "The request body or parameters are invalid.", null);
    // Never guessed: the request's schema refuses more than an empty file (a name over 255 too).
    expect(uploadProblem(validation)).toBe("AIA soubor nepřijala (kód validation_error)");
    const other = new ApiError(409, "not_saved", "Nothing saved yet.", null);
    expect(uploadProblem(other)).not.toContain("Nothing");
    expect(uploadProblem(other)).toContain("not_saved");
    expect(uploadProblem(new TypeError("Failed to fetch"))).not.toContain("Failed");
  });
});
