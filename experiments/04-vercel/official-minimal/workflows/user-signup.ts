// Adapted from Vercel Workflow's signup example at commit e1e64e3de30e10cba6803907b789699e851d33e2.
// Licensed under Apache-2.0; see THIRD_PARTY_NOTICES.md for source and modifications.
import { FatalError, sleep } from "workflow";

export async function handleUserSignup(email: string) {
  "use workflow";

  const user = await createUser(email);
  await sendWelcomeEmail(user);
  await sleep("1s");
  await sendOnboardingEmail(user);

  return { userId: user.id, status: "onboarded" };
}

async function createUser(email: string) {
  "use step";

  console.log(`Creating user with email: ${email}`);
  return { id: crypto.randomUUID(), email };
}

async function sendWelcomeEmail(user: { id: string; email: string }) {
  "use step";

  console.log(`Sending welcome email to user: ${user.id}`);
}

async function sendOnboardingEmail(user: { id: string; email: string }) {
  "use step";

  if (!user.email.includes("@")) {
    throw new FatalError("Invalid Email");
  }

  console.log(`Sending onboarding email to user: ${user.id}`);
}
