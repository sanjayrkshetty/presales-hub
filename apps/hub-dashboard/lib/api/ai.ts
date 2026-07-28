import { apiFetch } from "./client";

export type GenerateDocxResult = {
  proposal_id: string;
  mode: string;
  provider: string;
  model: string;
  retrieved_chunks: number;
  bu: string;
  scrub_flags: string[];
  sections: string[];
  bytes: number;
  docx_base64: string;
  filename: string;
};

export const aiApi = {
  generateDocx: (
    proposalId: string,
    opts: { brief?: string; bu?: string; sections?: string[] } = {},
  ) =>
    apiFetch<GenerateDocxResult>(`/api/ai/proposals/${proposalId}/generate-docx`, {
      method: "POST",
      body: JSON.stringify({
        brief: opts.brief ?? "",
        bu: opts.bu ?? "dfir",
        sections: opts.sections,
        as_json: true,
      }),
    }),
};
