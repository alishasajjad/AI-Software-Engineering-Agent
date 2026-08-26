import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  ApiError,
  getCorrectionStatus,
  listTaskPatches,
  listVerifications,
} from '../api'

import type {
  CorrectionLoopResponse,
  PendingPatch,
  TaskRecord,
  VerificationRun,
} from '../types'

import StatusBadge from './StatusBadge'


type HistoryCategory =
  | 'all'
  | 'tasks'
  | 'patches'
  | 'verifications'
  | 'corrections'


type HistoryActivity = {
  id: string
  category: Exclude<
    HistoryCategory,
    'all'
  >
  title: string
  description: string
  timestamp: string
  taskId: string
  taskTitle: string
  repositoryPath: string
  status: string
}


type HistoryPageProps = {
  tasks: TaskRecord[]
  onOpenTask: (
    taskId: string,
  ) => void
}


function getErrorMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unable to load history.'
}


function formatTimestamp(
  value?: string | null,
): string {
  if (!value) {
    return '—'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}


function timestampValue(
  value?: string | null,
): number {
  if (!value) {
    return 0
  }

  const result =
    new Date(value).getTime()

  return Number.isNaN(result)
    ? 0
    : result
}


function patchTitle(
  patch: PendingPatch,
): string {
  if (patch.status === 'applied') {
    return 'Patch applied'
  }

  if (patch.status === 'approved') {
    return 'Patch approved'
  }

  if (patch.status === 'rejected') {
    return 'Patch rejected'
  }

  if (patch.status === 'stale') {
    return 'Patch became stale'
  }

  return 'Patch prepared'
}


function patchTimestamp(
  patch: PendingPatch,
): string {
  return (
    patch.applied_at ??
    patch.reviewed_at ??
    patch.updated_at ??
    patch.created_at
  )
}


function HistoryPage({
  tasks,
  onOpenTask,
}: HistoryPageProps) {
  const [activities, setActivities] =
    useState<HistoryActivity[]>([])

  const [patches, setPatches] =
    useState<PendingPatch[]>([])

  const [
    verifications,
    setVerifications,
  ] = useState<VerificationRun[]>([])

  const [
    corrections,
    setCorrections,
  ] = useState<
    CorrectionLoopResponse[]
  >([])

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const [category, setCategory] =
    useState<HistoryCategory>('all')

  const [search, setSearch] =
    useState('')

  const [refreshKey, setRefreshKey] =
    useState(0)

  useEffect(() => {
    let cancelled = false

    const loadHistory =
      async () => {
        setLoading(true)
        setError(null)

        try {
          const bundles =
            await Promise.all(
              tasks.map(
                async (task) => {
                  const [
                    taskPatches,
                    taskVerifications,
                  ] =
                    await Promise.all([
                      listTaskPatches(
                        task.id,
                      ),
                      listVerifications(
                        task.id,
                      ),
                    ])

                  const failedRuns =
                    taskVerifications.filter(
                      (run) =>
                        run.status ===
                        'failed',
                    )

                  const correctionResults =
                    await Promise.all(
                      failedRuns.map(
                        async (run) => {
                          try {
                            return await getCorrectionStatus(
                              task.id,
                              run.id,
                            )
                          } catch (
                            requestError
                          ) {
                            if (
                              requestError instanceof
                                ApiError &&
                              requestError.status ===
                                404
                            ) {
                              return null
                            }

                            throw requestError
                          }
                        },
                      ),
                    )

                  const taskCorrections =
                    correctionResults.filter(
                      (
                        item,
                      ): item is CorrectionLoopResponse =>
                        item !== null,
                    )

                  return {
                    task,
                    patches:
                      taskPatches,
                    verifications:
                      taskVerifications,
                    corrections:
                      taskCorrections,
                  }
                },
              ),
            )

          if (cancelled) {
            return
          }

          const nextActivities:
            HistoryActivity[] = []

          const allPatches:
            PendingPatch[] = []

          const allVerifications:
            VerificationRun[] = []

          const allCorrections:
            CorrectionLoopResponse[] = []

          for (const bundle of bundles) {
            const {
              task,
              patches:
                taskPatches,
              verifications:
                taskVerifications,
              corrections:
                taskCorrections,
            } = bundle

            nextActivities.push({
              id:
                `task:${task.id}`,
              category: 'tasks',
              title: 'Task created',
              description:
                task.description,
              timestamp:
                task.created_at ??
                task.updated_at ??
                '',
              taskId: task.id,
              taskTitle:
                task.title,
              repositoryPath:
                task.repository_path,
              status:
                task.status ??
                'created',
            })

            for (
              const patch
              of taskPatches
            ) {
              allPatches.push(
                patch,
              )

              nextActivities.push({
                id:
                  `patch:${patch.id}`,
                category:
                  'patches',
                title:
                  patchTitle(
                    patch,
                  ),
                description:
                  patch.path,
                timestamp:
                  patchTimestamp(
                    patch,
                  ),
                taskId:
                  task.id,
                taskTitle:
                  task.title,
                repositoryPath:
                  task.repository_path,
                status:
                  patch.status,
              })
            }

            for (
              const run
              of taskVerifications
            ) {
              allVerifications.push(
                run,
              )

              nextActivities.push({
                id:
                  `verification:${run.id}`,
                category:
                  'verifications',
                title:
                  'Verification run',
                description:
                  `${run.steps.length} verification step${run.steps.length === 1 ? '' : 's'}`,
                timestamp:
                  run.completed_at ??
                  run.created_at,
                taskId:
                  task.id,
                taskTitle:
                  task.title,
                repositoryPath:
                  task.repository_path,
                status:
                  run.status,
              })
            }

            for (
              const correction
              of taskCorrections
            ) {
              allCorrections.push(
                correction,
              )

              const session =
                correction
                  .active_session

              nextActivities.push({
                id:
                  `correction:${session.id}`,
                category:
                  'corrections',
                title:
                  'Self-correction workflow',
                description:
                  correction.message,
                timestamp:
                  session.completed_at ??
                  session.updated_at ??
                  session.created_at,
                taskId:
                  task.id,
                taskTitle:
                  task.title,
                repositoryPath:
                  task.repository_path,
                status:
                  session.status,
              })
            }
          }

          nextActivities.sort(
            (left, right) =>
              timestampValue(
                right.timestamp,
              ) -
              timestampValue(
                left.timestamp,
              ),
          )

          setActivities(
            nextActivities,
          )

          setPatches(
            allPatches,
          )

          setVerifications(
            allVerifications,
          )

          setCorrections(
            allCorrections,
          )
        } catch (
          requestError
        ) {
          if (!cancelled) {
            setError(
              getErrorMessage(
                requestError,
              ),
            )
          }
        } finally {
          if (!cancelled) {
            setLoading(false)
          }
        }
      }

    void loadHistory()

    return () => {
      cancelled = true
    }
  }, [
    tasks,
    refreshKey,
  ])

  const filteredActivities =
    useMemo(() => {
      const query =
        search.trim().toLowerCase()

      return activities.filter(
        (activity) => {
          if (
            category !== 'all' &&
            activity.category !==
              category
          ) {
            return false
          }

          if (!query) {
            return true
          }

          const haystack = [
            activity.title,
            activity.description,
            activity.taskTitle,
            activity.repositoryPath,
            activity.status,
          ]
            .join(' ')
            .toLowerCase()

          return haystack.includes(
            query,
          )
        },
      )
    }, [
      activities,
      category,
      search,
    ])

  const appliedPatches =
    patches.filter(
      (patch) =>
        patch.status ===
        'applied',
    ).length

  const passedVerifications =
    verifications.filter(
      (run) =>
        run.status ===
        'passed',
    ).length

  const failedVerifications =
    verifications.filter(
      (run) =>
        run.status ===
        'failed',
    ).length

  return (
    <div className="history-page">
      <header className="history-header">
        <div>
          <div className="breadcrumb">
            Engineering Control

            <span>/</span>

            History
          </div>

          <h1>
            Engineering History
          </h1>

          <p>
            Review task activity,
            human decisions,
            repository changes,
            verification runs and
            self-correction workflows.
          </p>
        </div>

        <button
          type="button"
          className="button button-secondary"
          disabled={loading}
          onClick={() =>
            setRefreshKey(
              (current) =>
                current + 1,
            )
          }
        >
          {loading
            ? 'Refreshing…'
            : '↻ Refresh history'}
        </button>
      </header>

      <section className="history-summary-grid">
        <article className="history-summary-card">
          <span>
            Total tasks
          </span>

          <strong>
            {tasks.length}
          </strong>

          <small>
            Engineering requests
          </small>
        </article>

        <article className="history-summary-card">
          <span>
            Applied patches
          </span>

          <strong>
            {appliedPatches}
          </strong>

          <small>
            Human-approved writes
          </small>
        </article>

        <article className="history-summary-card">
          <span>
            Verification passed
          </span>

          <strong>
            {passedVerifications}
          </strong>

          <small>
            {failedVerifications}
            {' '}
            failed run
            {failedVerifications === 1
              ? ''
              : 's'}
          </small>
        </article>

        <article className="history-summary-card">
          <span>
            Correction sessions
          </span>

          <strong>
            {corrections.length}
          </strong>

          <small>
            Bounded recovery workflows
          </small>
        </article>
      </section>

      <section className="history-toolbar">
        <div className="history-tabs">
          {(
            [
              [
                'all',
                'All activity',
              ],
              [
                'tasks',
                'Tasks',
              ],
              [
                'patches',
                'Patches',
              ],
              [
                'verifications',
                'Verifications',
              ],
              [
                'corrections',
                'Corrections',
              ],
            ] as const
          ).map(
            ([
              value,
              label,
            ]) => (
              <button
                key={value}
                type="button"
                className={
                  category ===
                  value
                    ? 'history-tab active'
                    : 'history-tab'
                }
                onClick={() =>
                  setCategory(
                    value,
                  )
                }
              >
                {label}
              </button>
            ),
          )}
        </div>

        <div className="history-search">
          <span>
            ⌕
          </span>

          <input
            value={search}
            onChange={(event) =>
              setSearch(
                event.target
                  .value,
              )
            }
            placeholder="Search history…"
          />
        </div>
      </section>

      {error && (
        <div className="global-message global-error">
          <span>
            !
          </span>

          <div>
            <strong>
              History unavailable
            </strong>

            <p>
              {error}
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="history-loading">
          <div className="loading-orbit" />

          <strong>
            Loading engineering history…
          </strong>
        </div>
      ) : filteredActivities.length ===
        0 ? (
          <div className="empty-state history-empty">
            <div className="empty-state-icon">
              ◷
            </div>

            <h3>
              No matching history
            </h3>

            <p>
              Activity will appear here
              after tasks, patches and
              verification runs are
              created.
            </p>
          </div>
        ) : (
          <div className="history-layout">
            <div className="history-timeline">
              {filteredActivities.map(
                (activity) => (
                  <article
                    key={
                      activity.id
                    }
                    className="history-item"
                  >
                    <div className="history-marker">
                      <span />
                    </div>

                    <div className="history-card">
                      <div className="history-card-top">
                        <div>
                          <span className="history-category">
                            {
                              activity.category
                            }
                          </span>

                          <h3>
                            {
                              activity.title
                            }
                          </h3>
                        </div>

                        <StatusBadge
                          status={
                            activity.status
                          }
                        />
                      </div>

                      <p>
                        {
                          activity.description
                        }
                      </p>

                      <div className="history-task-row">
                        <div>
                          <strong>
                            {
                              activity.taskTitle
                            }
                          </strong>

                          <code>
                            {
                              activity.repositoryPath
                            }
                          </code>
                        </div>

                        <button
                          type="button"
                          className="button button-ghost button-small"
                          onClick={() =>
                            onOpenTask(
                              activity.taskId,
                            )
                          }
                        >
                          Open task →
                        </button>
                      </div>

                      <time>
                        {formatTimestamp(
                          activity.timestamp,
                        )}
                      </time>
                    </div>
                  </article>
                ),
              )}
            </div>
          </div>
        )}
    </div>
  )
}

export default HistoryPage