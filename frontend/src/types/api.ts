// BeCoMe API Types

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string | null;
  photo_url: string | null;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  scale_min: number;
  scale_max: number;
  scale_unit: string;
  admin_id: string;
  created_at: string;
  member_count: number;
}

export interface FuzzyNumber {
  lower: number;
  peak: number;
  upper: number;
  centroid: number;
}

export interface Opinion {
  id: string;
  user_id: string;
  user_email: string;
  user_first_name: string;
  user_last_name: string | null;
  position: string;
  lower_bound: number;
  peak: number;
  upper_bound: number;
  centroid: number;
  created_at: string;
  updated_at: string;
}

export interface CalculationResult {
  best_compromise: FuzzyNumber;
  arithmetic_mean: FuzzyNumber;
  median: FuzzyNumber;
  max_error: number;
  num_experts: number;
  likert_value: number | null;
  likert_decision: string | null;
  calculated_at: string;
}

export interface Invitation {
  id: string;
  project_id: string;
  project_name: string;
  project_description: string | null;
  project_scale_min: number;
  project_scale_max: number;
  project_scale_unit: string;
  inviter_email: string;
  inviter_first_name: string;
  current_experts_count: number;
  invited_at: string;
}

export interface Member {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string | null;
  photo_url: string | null;
  role: 'admin' | 'expert';
  joined_at: string;
}

export interface ProjectInvitation {
  id: string;
  invitee_email: string;
  invitee_first_name: string;
  invitee_last_name: string | null;
  invited_at: string;
}

export interface ProjectWithRole extends Project {
  role: 'admin' | 'expert';
}

export interface CreateProjectInput {
  name: string;
  description?: string;
  scale_min: number;
  scale_max: number;
  scale_unit: string;
}

export interface UpdateProjectInput {
  name?: string;
  description?: string;
  scale_min?: number;
  scale_max?: number;
  scale_unit?: string;
}

export interface CreateOpinionInput {
  position: string;
  lower_bound: number;
  peak: number;
  upper_bound: number;
}

export interface RegisterInput {
  email: string;
  password: string;
  first_name: string;
  last_name?: string;
}

export interface UpdateUserInput {
  first_name?: string;
  last_name?: string;
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export interface ApiError {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}
