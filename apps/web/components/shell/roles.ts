export type MemberRole = "viewer" | "ap_clerk" | "ap_manager" | "controller" | "admin";

export const ROLE_LABEL: Record<MemberRole, string> = {
  viewer: "Viewer",
  ap_clerk: "AP clerk",
  ap_manager: "AP manager",
  controller: "Controller",
  admin: "Admin",
};

const RANK: Record<MemberRole, number> = { viewer: 0, ap_clerk: 1, ap_manager: 2, controller: 3, admin: 4 };

/** True when `role` is at least `required` (admin ⊇ controller ⊇ ap_manager ⊇ ap_clerk ⊇ viewer). */
export function hasRole(role: MemberRole, required: MemberRole): boolean {
  return RANK[role] >= RANK[required];
}

/**
 * Tooltip text for a disabled action (03-screens §1), or undefined when allowed.
 * <Button disabledReason={needsRole(role, "controller")}>Release hold</Button>
 */
export function needsRole(role: MemberRole, required: MemberRole): string | undefined {
  if (hasRole(role, required)) return undefined;
  if (role === "viewer") return "Read-only access";
  if (required === "controller" || required === "admin") return "Needs controller";
  return "Needs AP manager";
}
