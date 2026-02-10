import {
  Project,
  ProjectWithRole,
  Opinion,
  Invitation,
  CalculationResult,
  FuzzyNumber,
  Member,
  ProjectInvitation,
} from '@/types/api';

let projectCounter = 0;
let opinionCounter = 0;
let invitationCounter = 0;
let memberCounter = 0;
let projectInvitationCounter = 0;

/**
 * Creates a mock Project object with default values.
 */
export function createProject(overrides: Partial<Project> = {}): Project {
  projectCounter++;
  return {
    id: `project-${projectCounter}`,
    name: `Test Project ${projectCounter}`,
    description: 'Test project description',
    scale_min: 0,
    scale_max: 100,
    scale_unit: '%',
    admin_id: 'admin-1',
    created_at: '2024-01-01T00:00:00Z',
    member_count: 1,
    ...overrides,
  };
}

/**
 * Creates a mock ProjectWithRole object with default admin role.
 */
export function createProjectWithRole(
  overrides: Partial<ProjectWithRole> = {}
): ProjectWithRole {
  const project = createProject(overrides);
  return {
    ...project,
    role: 'admin',
    ...overrides,
  };
}

/**
 * Creates a mock Opinion object with default fuzzy triangle values.
 */
export function createOpinion(overrides: Partial<Opinion> = {}): Opinion {
  opinionCounter++;
  return {
    id: `opinion-${opinionCounter}`,
    user_id: `user-${opinionCounter}`,
    user_email: `expert${opinionCounter}@example.com`,
    user_first_name: 'Expert',
    user_last_name: `${opinionCounter}`,
    position: 'Expert',
    lower_bound: 30,
    peak: 50,
    upper_bound: 70,
    centroid: 50,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Creates a mock Invitation object.
 */
export function createInvitation(overrides: Partial<Invitation> = {}): Invitation {
  invitationCounter++;
  return {
    id: `invitation-${invitationCounter}`,
    project_id: `project-${invitationCounter}`,
    project_name: `Invited Project ${invitationCounter}`,
    project_description: 'Invitation project description',
    project_scale_min: 0,
    project_scale_max: 100,
    project_scale_unit: '%',
    inviter_email: 'inviter@example.com',
    inviter_first_name: 'Inviter',
    current_experts_count: 3,
    invited_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Creates a mock FuzzyNumber object.
 */
export function createFuzzyNumber(overrides: Partial<FuzzyNumber> = {}): FuzzyNumber {
  return {
    lower: 30,
    peak: 50,
    upper: 70,
    centroid: 50,
    ...overrides,
  };
}

/**
 * Creates a mock CalculationResult object.
 */
export function createCalculationResult(
  overrides: Partial<CalculationResult> = {}
): CalculationResult {
  return {
    best_compromise: createFuzzyNumber({ lower: 35, peak: 52, upper: 68, centroid: 51.67 }),
    arithmetic_mean: createFuzzyNumber({ lower: 32, peak: 50, upper: 70, centroid: 50.67 }),
    median: createFuzzyNumber({ lower: 38, peak: 54, upper: 66, centroid: 52.67 }),
    max_error: 12.5,
    num_experts: 5,
    likert_value: null,
    likert_decision: null,
    calculated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Creates a mock Member object.
 */
export function createMember(overrides: Partial<Member> = {}): Member {
  memberCounter++;
  return {
    user_id: `user-${memberCounter}`,
    email: `member${memberCounter}@example.com`,
    first_name: 'Member',
    last_name: `${memberCounter}`,
    photo_url: null,
    role: 'expert',
    joined_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Creates a mock ProjectInvitation object (pending invitation on project page).
 */
export function createProjectInvitation(overrides: Partial<ProjectInvitation> = {}): ProjectInvitation {
  projectInvitationCounter++;
  return {
    id: `proj-invitation-${projectInvitationCounter}`,
    invitee_email: `pending${projectInvitationCounter}@example.com`,
    invitee_first_name: 'Pending',
    invitee_last_name: `User ${projectInvitationCounter}`,
    invited_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Resets all counters for deterministic IDs in tests.
 */
export function resetProjectCounters() {
  projectCounter = 0;
  opinionCounter = 0;
  invitationCounter = 0;
  memberCounter = 0;
  projectInvitationCounter = 0;
}
