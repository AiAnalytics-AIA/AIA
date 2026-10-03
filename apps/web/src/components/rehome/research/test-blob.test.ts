// @vitest-environment jsdom
import { Blob as NodeBlob } from "node:buffer";
import { expect, it } from "vitest";
import { blobText } from "./test-blob";

it("reads the jsdom Blob used by browser code", async () => {
  expect(await blobText(new Blob(["příloha"]))).toBe("příloha");
});

it("reads the Node Blob returned by native fetch", async () => {
  expect(await blobText(new NodeBlob(["příloha"]) as Blob)).toBe("příloha");
});
