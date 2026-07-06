/**
 * Central react-query key registry. Project-scoped mutations invalidate the
 * `project(id)` prefix, which covers every sub-resource key below it.
 */
export const queryKeys = {
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  projectOpinions: (id: string) => ["projects", id, "opinions"] as const,
  projectResult: (id: string) => ["projects", id, "result"] as const,
  projectMembers: (id: string) => ["projects", id, "members"] as const,
  projectInvitations: (id: string) => ["projects", id, "invitations"] as const,
  invitations: ["invitations"] as const,
};
