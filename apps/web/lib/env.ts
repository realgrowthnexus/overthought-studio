export const publicEnv = {
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
};

/** Server-only env; throws a clear message when something is missing. */
export function serverEnv() {
  // keys only use these characters; anything else is a paste artefact (CR, bracketed-paste bytes, spaces)
  const serviceRoleKey = (process.env.SUPABASE_SERVICE_ROLE_KEY ?? "").replace(/[^A-Za-z0-9_.-]/g, "");
  if (!serviceRoleKey) throw new Error("SUPABASE_SERVICE_ROLE_KEY is not set");
  return {
    serviceRoleKey,
    masterKey: process.env.MASTER_KEY ?? "",
    appUrl: (process.env.APP_URL ?? "http://localhost:3000").replace(/\/$/, ""),
    setupToken: process.env.SETUP_TOKEN ?? "",
  };
}

export function appUrl() {
  return (process.env.APP_URL ?? "http://localhost:3000").replace(/\/$/, "");
}

export function appDomain() {
  try {
    return new URL(appUrl()).hostname.replace(/^studio\./, "");
  } catch {
    return "example.com";
  }
}
