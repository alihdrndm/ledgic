import "server-only";

export type DemoPersona = "viewer" | "elena";

/** Demo credentials live only in server env; they are never sent to the client. */
export function demoCredentials(persona: DemoPersona): { email: string; password: string } | null {
  const email = persona === "elena" ? process.env.DEMO_ELENA_EMAIL : process.env.DEMO_VIEWER_EMAIL;
  const password = persona === "elena" ? process.env.DEMO_ELENA_PASSWORD : process.env.DEMO_VIEWER_PASSWORD;
  return email && password ? { email, password } : null;
}

export function isDemoElena(email: string | null | undefined): boolean {
  const elena = process.env.DEMO_ELENA_EMAIL;
  return Boolean(email && elena && email.toLowerCase() === elena.toLowerCase());
}
