export type TaskRecord = {
  id: string
  title: string
  description: string
  repository_path: string
  status?: string | null
  created_at?: string
  updated_at?: string
}

export type CreateTaskPayload = {
  title: string
  description: string
  repository_path: string
}

export type PendingPatchStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'applied'
  | 'stale'

export type PendingPatch = {
  id: string
  task_id: string
  path: string
  original_content: string
  proposed_content: string
  diff: string
  original_sha256: string
  status: PendingPatchStatus
  created_at: string
  updated_at?: string | null
  reviewed_at?: string | null
  applied_at?: string | null
}

export type PatchActionResponse = {
  message: string
  patch: PendingPatch
}

export type PatchPreparationResponse = {
  task_id: string
  editor_summary: string
  patches: PendingPatch[]
}

export type VerificationStep = {
  id: string
  verification_run_id: string
  position: number
  command_type: string
  command: string[]
  exit_code: number | null
  stdout: string
  stderr: string
  timed_out: boolean
  duration_seconds: number
  succeeded: boolean
  created_at: string
}

export type VerificationRun = {
  id: string
  task_id: string
  status:
    | 'running'
    | 'passed'
    | 'failed'
    | 'error'
  error_message: string | null
  started_at: string
  completed_at: string | null
  created_at: string
  steps: VerificationStep[]
}

export type CorrectionPatchSummary = {
  id: string
  path: string
  status: PendingPatchStatus
}

export type CorrectionLoopSession = {
  id: string
  task_id: string
  source_verification_run_id: string
  parent_session_id: string | null
  last_verification_run_id: string | null
  status: string
  current_attempt: number
  max_attempts: number
  created_at: string
  updated_at: string
  completed_at: string | null
}

export type CorrectionLoopResponse = {
  root_session_id: string
  active_session: CorrectionLoopSession
  chain: CorrectionLoopSession[]
  terminal: boolean
  safe_stopped: boolean
  requires_human_action: boolean
  next_action:
    | 'generate_proposal'
    | 'prepare_patches'
    | 'review_patches'
    | 'apply_approved_patches'
    | 'reverify'
    | 'none'
  remaining_attempts: number
  stop_reason: string | null
  message: string
  patches: CorrectionPatchSummary[]
}

export type JsonObject = Record<
  string,
  unknown
>