// Nitro adaptation of Vercel Workflow's signup example at commit e1e64e3de30e10cba6803907b789699e851d33e2.
// Licensed under Apache-2.0; see THIRD_PARTY_NOTICES.md for source and modifications.
import { defineEventHandler } from "nitro/h3";
import { start } from "workflow/api";

import { handleUserSignup } from "../workflows/user-signup";

export default defineEventHandler(async ({ req }) => {
  const { email } = (await req.json()) as { email: string };
  const run = await start(handleUserSignup, [email]);

  return {
    message: "User signup workflow started",
    runId: run.runId,
  };
});
