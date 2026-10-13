export type Role = "admin" | "officer" | "coordinator" | "recruiter" | "student";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  role_label: string;
  course: string | null;
  course_name: string | null;
  company_id: string | null;
  student_id: string | null;
  mfa_enabled: boolean;
  is_active: boolean;
}

export interface Course {
  code: string;
  name: string;
  short: string;
}

export interface Student {
  id: string;
  placement_id: string;
  full_name: string;
  email: string | null;
  mobile: string | null;
  course: string;
  course_name: string;
  course_short: string;
  batch: string;
  registration_status: string;
  registration_label: string;
  eligibility_status: string;
  eligibility_label: string;
  placement_status: string;
  placement_status_label: string;
  cgpa: number | null;
  remarks: string | null;
  exclusion_drives_remaining: number;
  archived: boolean;
}

export interface Offer {
  id: string;
  student_id: string;
  company_id: string;
  company_name: string;
  drive_id: string | null;
  offer_type: string;
  offer_type_label: string;
  category: string | null;
  ctc_lpa: number | null;
  stipend_amount: number | null;
  stipend_period: string | null;
  ppo_status: string;
  acceptance_status: string;
  joining_status: string;
  offer_date: string;
  acceptance_deadline: string | null;
  is_off_campus: boolean;
  noc_status: string;
  voided: boolean;
  void_reason: string | null;
  policy_verdict: string | null;
  remarks: string | null;
}

export interface Check {
  code: string;
  title: string;
  status: "pass" | "fail" | "review" | "info";
  detail: string;
}

export interface Evaluation {
  verdict: "allow" | "block" | "review";
  checks: Check[];
  governing_ctc: number | null;
  governing_category: string | null;
  placement_status: string;
  placement_status_label: string;
}

export interface Standing {
  placement_status: string;
  placement_status_label: string;
  governing_ctc: number | null;
  governing_category: string | null;
  further_allow: string[];
  further_review: string[];
  locks: string[];
}

export interface Drive {
  id: string;
  company_id: string;
  company_name: string;
  title: string;
  offer_type: string;
  offer_type_label: string;
  ctc_lpa: number | null;
  stipend_amount: number | null;
  stipend_period: string | null;
  acceptance_hours: number | null;
  courses: string[];
  min_cgpa: number | null;
  scheduled_on: string | null;
  eligible_count?: number;
  withheld_count?: number;
}

export interface Company {
  id: string;
  name: string;
  notes: string | null;
}

export interface StatPack {
  highest: number | null;
  average: number | null;
  median: number | null;
  count: number;
}

export interface Overview {
  scope: string;
  session: string;
  course_name?: string | null;
  company?: string;
  definitions: Record<string, string>;
  totals?: Record<string, number>;
  ctc?: StatPack;
  stipend_monthly?: StatPack;
  by_course?: Array<Record<string, string | number | null>>;
  by_batch?: Array<Record<string, string | number | null>>;
  by_company?: Array<Record<string, string | number | string[] | null>>;
  attention?: Array<{ student_id: string; student_name: string; placement_id: string; kind: string; message: string }>;
  drives?: Drive[];
}
