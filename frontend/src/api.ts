import type {
  CorrectionLoopResponse,
  CreateTaskPayload,
  JsonObject,
  PatchActionResponse,
  PatchPreparationResponse,
  PendingPatch,
  TaskRecord,
  VerificationRun,
} from './types'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

export const API_BASE_URL = configuredBaseUrl
  ? configuredBaseUrl.replace(/\/$/, '')
  : '/api/v1'

export class ApiError extends Error {
  status: number
  details: unknown

  constructor(
    message: string,
    status: number,
    details: unknown = null,
  ) {
    super(message)

    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)

  if (init.body !== undefined && init.body !== null) {
    headers.set('Content-Type', 'application/json')
  }

  headers.set('Accept', 'application/json')

  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...init,
      headers,
    },
  )

  const rawText = await response.text()

  let payload: unknown = null

  if (rawText) {
    try {
      payload = JSON.parse(rawText)
    } catch {
      payload = rawText
    }
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`

    if (
      payload &&
      typeof payload === 'object' &&
      'detail' in payload
    ) {
      const detail = (
        payload as {
          detail?: unknown
        }
      ).detail

      if (typeof detail === 'string') {
        message = detail
      } else if (detail !== undefined) {
        message = JSON.stringify(detail)
      }
    }

    throw new ApiError(
      message,
      response.status,
      payload,
    )
  }

  return payload as T
}

export function listTasks(): Promise<TaskRecord[]> {
  return request<TaskRecord[]>(
    '/tasks',
  )
}

export function getTask(
  taskId: string,
): Promise<TaskRecord> {
  return request<TaskRecord>(
    `/tasks/${taskId}`,
  )
}

export function createTask(
  payload: CreateTaskPayload,
): Promise<TaskRecord> {
  return request<TaskRecord>(
    '/tasks',
    {
      method: 'POST',
      body: JSON.stringify(
        payload,
      ),
    },
  )
}

export function generatePlan(
  taskId: string,
): Promise<JsonObject> {
  return request<JsonObject>(
    `/tasks/${taskId}/plan`,
    {
      method: 'POST',
    },
  )
}

export function prepareTaskPatches(
  taskId: string,
): Promise<PatchPreparationResponse> {
  return request<PatchPreparationResponse>(
    `/tasks/${taskId}/patches/prepare`,
    {
      method: 'POST',
    },
  )
}

export function listTaskPatches(
  taskId: string,
): Promise<PendingPatch[]> {
  return request<PendingPatch[]>(
    `/tasks/${taskId}/patches`,
  )
}

export function approvePatch(
  taskId: string,
  patchId: string,
): Promise<PatchActionResponse> {
  return request<PatchActionResponse>(
    `/tasks/${taskId}/patches/${patchId}/approve`,
    {
      method: 'POST',
    },
  )
}

export function rejectPatch(
  taskId: string,
  patchId: string,
): Promise<PatchActionResponse> {
  return request<PatchActionResponse>(
    `/tasks/${taskId}/patches/${patchId}/reject`,
    {
      method: 'POST',
    },
  )
}

export function applyPatch(
  taskId: string,
  patchId: string,
): Promise<PatchActionResponse> {
  return request<PatchActionResponse>(
    `/tasks/${taskId}/patches/${patchId}/apply`,
    {
      method: 'POST',
    },
  )
}

export function runVerification(
  taskId: string,
  pytestTargets: string[],
): Promise<VerificationRun> {
  return request<VerificationRun>(
    `/tasks/${taskId}/verifications`,
    {
      method: 'POST',
      body: JSON.stringify({
        pytest_targets: pytestTargets,
      }),
    },
  )
}

export function listVerifications(
  taskId: string,
): Promise<VerificationRun[]> {
  return request<VerificationRun[]>(
    `/tasks/${taskId}/verifications`,
  )
}

export function analyzeFailure(
  taskId: string,
  verificationId: string,
): Promise<JsonObject> {
  return request<JsonObject>(
    `/tasks/${taskId}/verifications/${verificationId}/corrections/analyze`,
    {
      method: 'POST',
    },
  )
}

export function proposeCorrection(
  taskId: string,
  verificationId: string,
): Promise<JsonObject> {
  return request<JsonObject>(
    `/tasks/${taskId}/verifications/${verificationId}/corrections/propose`,
    {
      method: 'POST',
    },
  )
}

export function prepareCorrectionPatches(
  taskId: string,
  verificationId: string,
): Promise<JsonObject> {
  return request<JsonObject>(
    `/tasks/${taskId}/verifications/${verificationId}/corrections/patches/prepare`,
    {
      method: 'POST',
    },
  )
}

export function getCorrectionStatus(
  taskId: string,
  verificationId: string,
): Promise<CorrectionLoopResponse> {
  return request<CorrectionLoopResponse>(
    `/tasks/${taskId}/verifications/${verificationId}/corrections/status`,
  )
}

export function advanceCorrection(
  taskId: string,
  verificationId: string,
): Promise<CorrectionLoopResponse> {
  return request<CorrectionLoopResponse>(
    `/tasks/${taskId}/verifications/${verificationId}/corrections/advance`,
    {
      method: 'POST',
    },
  )
}