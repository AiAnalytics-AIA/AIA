/** DEVELOPMENT FIXTURE — artifacts have no HTTP route yet (registry: "stage-artifacts"). */
export type ArtifactType = "input_docx" | "input_xlsx" | "dataset" | "import_pack" | "sociomap" | "final_docx" | "final_pdf";

export type FixtureArtifact = {
  id: string;
  projectId: string;
  type: ArtifactType;
  filename: string;
  versionLabel: string;
  createdAt: string; // ISO
  note?: string;
};

export const fixtureArtifacts: FixtureArtifact[] = [
  { id: "art-001", projectId: "PRJ-00a1", type: "input_xlsx", filename: "kvoty_csu_2021.xlsx", versionLabel: "v1", createdAt: "2026-09-11T10:00:00Z" },
  { id: "art-002", projectId: "PRJ-00c2", type: "input_docx", filename: "zadani_scenare.docx", versionLabel: "v1", createdAt: "2026-09-10T14:30:00Z" },
];
