import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import './App.css'

import {
  ApiError,
  advanceCorrection,
  analyzeFailure,
  applyPatch,
  approvePatch,
  createTask,
  generatePlan,
  getCorrectionStatus,
  getTask,
  listTaskPatches,
  listTasks,
  listVerifications,
  prepareCorrectionPatches,
  prepareTaskPatches,
  proposeCorrection,
  rejectPatch,
  runVerification,
} from './api'

import CorrectionPanel from './components/CorrectionPanel'
import HistoryPage from './components/HistoryPage'
import PatchCard from './components/PatchCard'
import StatusBadge from './components/StatusBadge'
import VerificationPanel from './components/VerificationPanel'

import type {
  CorrectionLoopResponse,
  JsonObject,
  PendingPatch,
  TaskRecord,
  VerificationRun,
} from './types'


type AppView =
  | 'workspace'
  | 'history'


type TaskFilter =
  | 'all'
  | 'normal'
  | 'evaluation'


const SIDEBAR_RECENT_TASK_LIMIT = 15


function getErrorMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'An unexpected error occurred.'
}


function formatTimestamp(
  value?: string | null,
): string {
  if (!value) {
    return '—'
  }

  const date =
    new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
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

  const date =
    new Date(value)

  const timestamp =
    date.getTime()

  return Number.isNaN(
    timestamp,
  )
    ? 0
    : timestamp
}


function isEvaluationTask(
  task: TaskRecord,
): boolean {
  const title =
    task.title.toLowerCase()

  const repositoryPath =
    task.repository_path.toLowerCase()

  return (
    title.startsWith(
      '[eval',
    ) ||
    title.includes(
      'eval task_',
    ) ||
    repositoryPath.includes(
      '\\evaluation\\workspaces\\',
    ) ||
    repositoryPath.includes(
      '/evaluation/workspaces/',
    )
  )
}


function App() {
  const [view, setView] =
    useState<AppView>(
      'workspace',
    )

  const [tasks, setTasks] =
    useState<TaskRecord[]>([])

  const [
    selectedTaskId,
    setSelectedTaskId,
  ] =
    useState<string | null>(
      null,
    )

  const [task, setTask] =
    useState<TaskRecord | null>(
      null,
    )

  const [
    taskLoading,
    setTaskLoading,
  ] = useState(false)

  const [plan, setPlan] =
    useState<JsonObject | null>(
      null,
    )

  const [patches, setPatches] =
    useState<PendingPatch[]>([])

  const [
    verifications,
    setVerifications,
  ] =
    useState<VerificationRun[]>(
      [],
    )

  const [
    selectedVerificationId,
    setSelectedVerificationId,
  ] =
    useState<string | null>(
      null,
    )

  const [
    correction,
    setCorrection,
  ] =
    useState<CorrectionLoopResponse | null>(
      null,
    )

  const [
    correctionVerificationId,
    setCorrectionVerificationId,
  ] =
    useState<string | null>(
      null,
    )

  const [
    correctionLoading,
    setCorrectionLoading,
  ] = useState(false)

  const [
    pageLoading,
    setPageLoading,
  ] = useState(true)

  const [
    apiOnline,
    setApiOnline,
  ] = useState(false)

  const [
    busyAction,
    setBusyAction,
  ] =
    useState<string | null>(
      null,
    )

  const [error, setError] =
    useState<string | null>(
      null,
    )

  const [notice, setNotice] =
    useState<string | null>(
      null,
    )

  const [
    newTaskOpen,
    setNewTaskOpen,
  ] = useState(false)

  const [
    newTaskTitle,
    setNewTaskTitle,
  ] = useState('')

  const [
    newTaskDescription,
    setNewTaskDescription,
  ] = useState('')

  const [
    newRepositoryPath,
    setNewRepositoryPath,
  ] = useState('')

  const [
    pytestTargetsInput,
    setPytestTargetsInput,
  ] = useState('')

  const [
    taskSearch,
    setTaskSearch,
  ] = useState('')

  const [
    taskFilter,
    setTaskFilter,
  ] =
    useState<TaskFilter>(
      'all',
    )

  const [
    showAllTasks,
    setShowAllTasks,
  ] = useState(false)

  const selectedVerification =
    useMemo(
      () =>
        verifications.find(
          (run) =>
            run.id ===
            selectedVerificationId,
        ) ??
        verifications[0] ??
        null,
      [
        verifications,
        selectedVerificationId,
      ],
    )

  const correctionSource =
    useMemo(() => {
      if (
        selectedVerification?.status ===
        'failed'
      ) {
        return selectedVerification
      }

      return (
        verifications.find(
          (run) =>
            run.status ===
            'failed',
        ) ?? null
      )
    }, [
      selectedVerification,
      verifications,
    ])

  const visibleCorrection =
    correctionSource &&
    correctionVerificationId ===
      correctionSource.id
      ? correction
      : null

  const pendingPatchCount =
    patches.filter(
      (patch) =>
        patch.status ===
        'pending',
    ).length

  const approvedPatchCount =
    patches.filter(
      (patch) =>
        patch.status ===
        'approved',
    ).length

  const appliedPatchCount =
    patches.filter(
      (patch) =>
        patch.status ===
        'applied',
    ).length

  const latestVerification =
    verifications[0] ?? null

  const hasHistoricalPlanningEvidence =
    Boolean(
      patches.length > 0 ||
      verifications.length > 0 ||
      correctionSource ||
      visibleCorrection,
    )

  const implementationPlanState =
    plan
      ? 'available'
      : hasHistoricalPlanningEvidence
        ? 'historical'
        : 'empty'

  const workflowSteps =
    useMemo(() => {
      const planDone =
        Boolean(
          plan ||
          hasHistoricalPlanningEvidence,
        )

      const reviewDone =
        appliedPatchCount > 0

      const reviewStarted =
        patches.length > 0

      const verifyDone =
        latestVerification?.status ===
        'passed'

      const verifyStarted =
        Boolean(
          latestVerification,
        )

      const correctionDone =
        Boolean(
          visibleCorrection?.terminal,
        )

      return [
        {
          label: 'Plan',
          description:
            plan
              ? 'Plan available'
              : hasHistoricalPlanningEvidence
                ? 'Previous planning completed'
                : 'Inspect repository',
          state: planDone
            ? 'done'
            : 'active',
        },
        {
          label: 'Review',
          description:
            'Approve changes',
          state: reviewDone
            ? 'done'
            : reviewStarted ||
                planDone
              ? 'active'
              : 'waiting',
        },
        {
          label: 'Verify',
          description:
            'Run checks',
          state: verifyDone
            ? 'done'
            : verifyStarted ||
                reviewDone
              ? 'active'
              : 'waiting',
        },
        {
          label: 'Correct',
          description:
            'Recover safely',
          state: correctionDone
            ? 'done'
            : correctionSource
              ? 'active'
              : 'waiting',
        },
      ]
    }, [
      appliedPatchCount,
      correctionSource,
      hasHistoricalPlanningEvidence,
      latestVerification,
      patches.length,
      plan,
      visibleCorrection,
    ])

  const taskCounts =
    useMemo(() => {
      let normal = 0
      let evaluation = 0

      for (const item of tasks) {
        if (
          isEvaluationTask(
            item,
          )
        ) {
          evaluation += 1
        } else {
          normal += 1
        }
      }

      return {
        all: tasks.length,
        normal,
        evaluation,
      }
    }, [
      tasks,
    ])

  const filteredTasks =
    useMemo(() => {
      const query =
        taskSearch
          .trim()
          .toLowerCase()

      return tasks
        .map(
          (
            item,
            index,
          ) => ({
            item,
            index,
          }),
        )
        .filter(
          ({
            item,
          }) => {
            const evaluation =
              isEvaluationTask(
                item,
              )

            if (
              taskFilter ===
                'normal' &&
              evaluation
            ) {
              return false
            }

            if (
              taskFilter ===
                'evaluation' &&
              !evaluation
            ) {
              return false
            }

            if (!query) {
              return true
            }

            const haystack = [
              item.title,
              item.description,
              item.repository_path,
              item.status ?? '',
            ]
              .join(' ')
              .toLowerCase()

            return haystack.includes(
              query,
            )
          },
        )
        .sort(
          (
            left,
            right,
          ) => {
            const rightTime =
              timestampValue(
                right.item.updated_at ??
                  right.item.created_at,
              )

            const leftTime =
              timestampValue(
                left.item.updated_at ??
                  left.item.created_at,
              )

            if (
              rightTime !==
              leftTime
            ) {
              return (
                rightTime -
                leftTime
              )
            }

            return (
              left.index -
              right.index
            )
          },
        )
        .map(
          ({
            item,
          }) => item,
        )
    }, [
      taskFilter,
      taskSearch,
      tasks,
    ])

  const taskSearchActive =
    taskSearch.trim().length > 0

  const sidebarTasks =
    useMemo(() => {
      if (
        showAllTasks ||
        taskSearchActive
      ) {
        return filteredTasks
      }

      return filteredTasks.slice(
        0,
        SIDEBAR_RECENT_TASK_LIMIT,
      )
    }, [
      filteredTasks,
      showAllTasks,
      taskSearchActive,
    ])

  const hiddenTaskCount =
    Math.max(
      filteredTasks.length -
        sidebarTasks.length,
      0,
    )

  const clearMessages = () => {
    setError(null)
    setNotice(null)
  }

  const showError = (
    value: unknown,
  ) => {
    setError(
      getErrorMessage(
        value,
      ),
    )
  }

  const handleSelectTask = (
    taskId: string,
  ) => {
    clearMessages()

    setView(
      'workspace',
    )

    setTaskLoading(
      true,
    )

    setPlan(null)
    setCorrection(null)

    setCorrectionVerificationId(
      null,
    )

    setSelectedVerificationId(
      null,
    )

    setSelectedTaskId(
      taskId,
    )
  }

  const refreshTaskList =
    useCallback(async () => {
      const result =
        await listTasks()

      setTasks(result)
      setApiOnline(true)

      return result
    }, [])

  const refreshTaskData =
    useCallback(
      async (
        taskId: string,
      ) => {
        const [
          taskResult,
          patchResult,
          verificationResult,
        ] =
          await Promise.all([
            getTask(taskId),
            listTaskPatches(
              taskId,
            ),
            listVerifications(
              taskId,
            ),
          ])

        setTask(
          taskResult,
        )

        setPatches(
          patchResult,
        )

        setVerifications(
          verificationResult,
        )

        setApiOnline(
          true,
        )

        setSelectedVerificationId(
          (current) => {
            if (
              current &&
              verificationResult.some(
                (run) =>
                  run.id ===
                  current,
              )
            ) {
              return current
            }

            return (
              verificationResult[0]
                ?.id ?? null
            )
          },
        )
      },
      [],
    )

  const refreshCorrection =
    useCallback(async () => {
      if (
        !selectedTaskId ||
        !correctionSource
      ) {
        return
      }

      setCorrectionLoading(
        true,
      )

      try {
        const result =
          await getCorrectionStatus(
            selectedTaskId,
            correctionSource.id,
          )

        setCorrection(
          result,
        )

        setCorrectionVerificationId(
          correctionSource.id,
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
          setCorrection(
            null,
          )

          setCorrectionVerificationId(
            correctionSource.id,
          )
        } else {
          showError(
            requestError,
          )
        }
      } finally {
        setCorrectionLoading(
          false,
        )
      }
    }, [
      correctionSource,
      selectedTaskId,
    ])

  useEffect(() => {
    let cancelled = false

    const initialize =
      async () => {
        try {
          const result =
            await listTasks()

          if (cancelled) {
            return
          }

          setTasks(
            result,
          )

          setApiOnline(
            true,
          )

          if (
            result.length > 0
          ) {
            setTaskLoading(
              true,
            )

            setSelectedTaskId(
              result[0].id,
            )
          }
        } catch (
          requestError
        ) {
          if (!cancelled) {
            setApiOnline(
              false,
            )

            setError(
              getErrorMessage(
                requestError,
              ),
            )
          }
        } finally {
          if (!cancelled) {
            setPageLoading(
              false,
            )
          }
        }
      }

    void initialize()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedTaskId) {
      return
    }

    let cancelled = false

    const loadTask =
      async () => {
        try {
          const [
            taskResult,
            patchResult,
            verificationResult,
          ] =
            await Promise.all([
              getTask(
                selectedTaskId,
              ),
              listTaskPatches(
                selectedTaskId,
              ),
              listVerifications(
                selectedTaskId,
              ),
            ])

          if (cancelled) {
            return
          }

          setTask(
            taskResult,
          )

          setPatches(
            patchResult,
          )

          setVerifications(
            verificationResult,
          )

          setApiOnline(
            true,
          )

          setSelectedVerificationId(
            verificationResult[0]
              ?.id ?? null,
          )
        } catch (
          requestError
        ) {
          if (!cancelled) {
            setTask(
              null,
            )

            setError(
              getErrorMessage(
                requestError,
              ),
            )
          }
        } finally {
          if (!cancelled) {
            setTaskLoading(
              false,
            )
          }
        }
      }

    void loadTask()

    return () => {
      cancelled = true
    }
  }, [
    selectedTaskId,
  ])

  useEffect(() => {
    if (
      !selectedTaskId ||
      !correctionSource
    ) {
      return
    }

    let cancelled = false

    const loadCorrection =
      async () => {
        try {
          const result =
            await getCorrectionStatus(
              selectedTaskId,
              correctionSource.id,
            )

          if (cancelled) {
            return
          }

          setCorrection(
            result,
          )

          setCorrectionVerificationId(
            correctionSource.id,
          )
        } catch (
          requestError
        ) {
          if (cancelled) {
            return
          }

          if (
            requestError instanceof
              ApiError &&
            requestError.status ===
              404
          ) {
            setCorrection(
              null,
            )

            setCorrectionVerificationId(
              correctionSource.id,
            )

            return
          }

          setError(
            getErrorMessage(
              requestError,
            ),
          )
        }
      }

    void loadCorrection()

    return () => {
      cancelled = true
    }
  }, [
    correctionSource,
    selectedTaskId,
  ])

  const handleCreateTask =
    async (
      event: FormEvent<HTMLFormElement>,
    ) => {
      event.preventDefault()

      const title =
        newTaskTitle.trim()

      const description =
        newTaskDescription.trim()

      const repositoryPath =
        newRepositoryPath.trim()

      if (
        !title ||
        !description ||
        !repositoryPath
      ) {
        setError(
          'Task title, description and repository path are required.',
        )

        return
      }

      clearMessages()

      setBusyAction(
        'create-task',
      )

      try {
        const created =
          await createTask({
            title,
            description,
            repository_path:
              repositoryPath,
          })

        await refreshTaskList()

        setPlan(null)
        setCorrection(null)

        setCorrectionVerificationId(
          null,
        )

        setSelectedVerificationId(
          null,
        )

        setTaskLoading(
          true,
        )

        setSelectedTaskId(
          created.id,
        )

        setView(
          'workspace',
        )

        setNewTaskTitle(
          '',
        )

        setNewTaskDescription(
          '',
        )

        setNewRepositoryPath(
          '',
        )

        setNewTaskOpen(
          false,
        )

        setNotice(
          'Task created successfully.',
        )
      } catch (
        requestError
      ) {
        showError(
          requestError,
        )
      } finally {
        setBusyAction(
          null,
        )
      }
    }

  const handleGeneratePlan =
    async () => {
      if (!selectedTaskId) {
        return
      }

      clearMessages()

      setBusyAction(
        'plan',
      )

      try {
        const result =
          await generatePlan(
            selectedTaskId,
          )

        setPlan(
          result,
        )

        setNotice(
          'Implementation plan generated.',
        )
      } catch (
        requestError
      ) {
        showError(
          requestError,
        )
      } finally {
        setBusyAction(
          null,
        )
      }
    }

  const handlePreparePatches =
    async () => {
      if (!selectedTaskId) {
        return
      }

      clearMessages()

      setBusyAction(
        'prepare-patches',
      )

      try {
        const result =
          await prepareTaskPatches(
            selectedTaskId,
          )

        setNotice(
          result.editor_summary ||
            'Pending patches prepared.',
        )

        await refreshTaskData(
          selectedTaskId,
        )

        await refreshCorrection()
      } catch (
        requestError
      ) {
        showError(
          requestError,
        )
      } finally {
        setBusyAction(
          null,
        )
      }
    }

  const handlePatchAction =
    async (
      patch: PendingPatch,
      action:
        | 'approve'
        | 'reject'
        | 'apply',
    ) => {
      if (!selectedTaskId) {
        return
      }

      const operationKey =
        `${patch.id}:${action}`

      clearMessages()

      setBusyAction(
        operationKey,
      )

      try {
        let response

        if (
          action ===
          'approve'
        ) {
          response =
            await approvePatch(
              selectedTaskId,
              patch.id,
            )
        } else if (
          action ===
          'reject'
        ) {
          response =
            await rejectPatch(
              selectedTaskId,
              patch.id,
            )
        } else {
          response =
            await applyPatch(
              selectedTaskId,
              patch.id,
            )
        }

        setNotice(
          response.message,
        )

        await refreshTaskData(
          selectedTaskId,
        )

        await refreshCorrection()
      } catch (
        requestError
      ) {
        showError(
          requestError,
        )
      } finally {
        setBusyAction(
          null,
        )
      }
    }

  const parsePytestTargets =
    (): string[] =>
      pytestTargetsInput
        .split(/[\n,]/)
        .map(
          (item) =>
            item.trim(),
        )
        .filter(Boolean)

  const handleRunVerification =
    async () => {
      if (!selectedTaskId) {
        return
      }

      clearMessages()

      setBusyAction(
        'verification',
      )

      try {
        const result =
          await runVerification(
            selectedTaskId,
            parsePytestTargets(),
          )

        setNotice(
          `Verification finished with status "${result.status}".`,
        )

        await refreshTaskData(
          selectedTaskId,
        )

        setSelectedVerificationId(
          result.id,
        )
      } catch (
        requestError
      ) {
        showError(
          requestError,
        )
      } finally {
        setBusyAction(
          null,
        )
      }
    }

  const runCorrectionAction =
    async (
      action:
        | 'analyze'
        | 'propose'
        | 'prepare-correction'
        | 'advance',
    ) => {
      if (
        !selectedTaskId ||
        !correctionSource
      ) {
        return
      }

      clearMessages()

      setBusyAction(
        action,
      )

      try {
        if (
          action ===
          'analyze'
        ) {
          await analyzeFailure(
            selectedTaskId,
            correctionSource.id,
          )

          setNotice(
            'Failure analysis completed.',
          )
        } else if (
          action ===
          'propose'
        ) {
          await proposeCorrection(
            selectedTaskId,
            correctionSource.id,
          )

          setNotice(
            'Correction proposal generated.',
          )
        } else if (
          action ===
          'prepare-correction'
        ) {
          await prepareCorrectionPatches(
            selectedTaskId,
            correctionSource.id,
          )

          setNotice(
            'Correction patches prepared for human review.',
          )
        } else {
          const result =
            await advanceCorrection(
              selectedTaskId,
              correctionSource.id,
            )

          setCorrection(
            result,
          )

          setCorrectionVerificationId(
            correctionSource.id,
          )

          setNotice(
            result.message,
          )
        }

        await refreshTaskData(
          selectedTaskId,
        )

        await refreshCorrection()
      } catch (
        requestError
      ) {
        showError(
          requestError,
        )
      } finally {
        setBusyAction(
          null,
        )
      }
    }

  if (pageLoading) {
    return (
      <div className="app-loading">
        <div className="loading-brand">
          {'</>'}
        </div>

        <div className="loading-orbit" />

        <div>
          <strong>
            Loading engineering workspace
          </strong>

          <span>
            Connecting to agent control plane…
          </span>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark">
              {'</>'}
            </div>

            <div>
              <strong>
                AI Software Agent
              </strong>

              <span>
                Engineering Control
              </span>
            </div>
          </div>

          <nav className="primary-navigation">
            <button
              type="button"
              className={
                view === 'workspace'
                  ? 'primary-nav-item active'
                  : 'primary-nav-item'
              }
              onClick={() =>
                setView(
                  'workspace',
                )
              }
            >
              <span>
                ◫
              </span>

              <div>
                <strong>
                  Workspace
                </strong>

                <small>
                  Agent control
                </small>
              </div>
            </button>

            <button
              type="button"
              className={
                view === 'history'
                  ? 'primary-nav-item active'
                  : 'primary-nav-item'
              }
              onClick={() =>
                setView(
                  'history',
                )
              }
            >
              <span>
                ◷
              </span>

              <div>
                <strong>
                  History
                </strong>

                <small>
                  Audit activity
                </small>
              </div>
            </button>
          </nav>

          <button
            type="button"
            className="button button-primary new-task-button"
            onClick={() =>
              setNewTaskOpen(
                true,
              )
            }
          >
            <span className="button-icon">
              +
            </span>

            New task
          </button>

          <div className="sidebar-heading">
            <span>
              Tasks
            </span>

            <b>
              {tasks.length}
            </b>
          </div>

          <div className="task-manager">
            <div className="task-search">
              <span>
                ⌕
              </span>

              <input
                value={
                  taskSearch
                }
                onChange={(
                  event,
                ) =>
                  setTaskSearch(
                    event.target
                      .value,
                  )
                }
                placeholder="Search tasks…"
                aria-label="Search tasks"
              />

              {taskSearch && (
                <button
                  type="button"
                  className="task-search-clear"
                  aria-label="Clear task search"
                  onClick={() =>
                    setTaskSearch(
                      '',
                    )
                  }
                >
                  ×
                </button>
              )}
            </div>

            <div className="task-filter-tabs">
              <button
                type="button"
                className={
                  taskFilter ===
                  'all'
                    ? 'task-filter-tab active'
                    : 'task-filter-tab'
                }
                onClick={() => {
                  setTaskFilter(
                    'all',
                  )
                  setShowAllTasks(
                    false,
                  )
                }}
              >
                All
                <span>
                  {taskCounts.all}
                </span>
              </button>

              <button
                type="button"
                className={
                  taskFilter ===
                  'normal'
                    ? 'task-filter-tab active'
                    : 'task-filter-tab'
                }
                onClick={() => {
                  setTaskFilter(
                    'normal',
                  )
                  setShowAllTasks(
                    false,
                  )
                }}
              >
                Normal
                <span>
                  {
                    taskCounts.normal
                  }
                </span>
              </button>

              <button
                type="button"
                className={
                  taskFilter ===
                  'evaluation'
                    ? 'task-filter-tab active'
                    : 'task-filter-tab'
                }
                onClick={() => {
                  setTaskFilter(
                    'evaluation',
                  )
                  setShowAllTasks(
                    false,
                  )
                }}
              >
                Eval
                <span>
                  {
                    taskCounts.evaluation
                  }
                </span>
              </button>
            </div>

            <div className="task-manager-meta">
              <span>
                {taskSearchActive
                  ? `${filteredTasks.length} matching task${filteredTasks.length === 1 ? '' : 's'}`
                  : showAllTasks
                    ? `Showing all ${filteredTasks.length}`
                    : `Recent ${Math.min(SIDEBAR_RECENT_TASK_LIMIT, filteredTasks.length)} of ${filteredTasks.length}`}
              </span>

              {!taskSearchActive &&
                filteredTasks.length >
                  SIDEBAR_RECENT_TASK_LIMIT && (
                  <button
                    type="button"
                    onClick={() =>
                      setShowAllTasks(
                        (current) =>
                          !current,
                      )
                    }
                  >
                    {showAllTasks
                      ? `Show recent ${SIDEBAR_RECENT_TASK_LIMIT}`
                      : `Show all`}
                  </button>
                )}
            </div>
          </div>

          <nav className="task-list">
            {sidebarTasks.length ===
              0 && (
              <div className="sidebar-empty">
                <div>
                  {taskSearchActive
                    ? '⌕'
                    : '</>'}
                </div>

                <span>
                  {taskSearchActive
                    ? 'No matching tasks'
                    : taskFilter ===
                        'normal'
                      ? 'No normal tasks'
                      : taskFilter ===
                          'evaluation'
                        ? 'No evaluation tasks'
                        : 'No tasks yet'}
                </span>

                <small>
                  {taskSearchActive
                    ? 'Try another title or repository path.'
                    : 'Create a task to begin.'}
                </small>
              </div>
            )}

            {sidebarTasks.map(
              (taskItem) => (
                <button
                  key={
                    taskItem.id
                  }
                  type="button"
                  title={
                    `${taskItem.title}\n${taskItem.repository_path}`
                  }
                  className={
                    selectedTaskId ===
                    taskItem.id &&
                    view ===
                      'workspace'
                      ? 'task-nav-item active'
                      : 'task-nav-item'
                  }
                  onClick={() =>
                    handleSelectTask(
                      taskItem.id,
                    )
                  }
                >
                  <span className="task-nav-icon">
                    {'</>'}
                  </span>

                  <span className="task-nav-copy">
                    <strong>
                      {
                        taskItem.title
                      }
                    </strong>

                    <small>
                      {
                        taskItem.repository_path
                      }
                    </small>
                  </span>

                  {isEvaluationTask(
                    taskItem,
                  ) && (
                    <span className="task-type-badge">
                      EVAL
                    </span>
                  )}
                </button>
              ),
            )}
          </nav>

          {hiddenTaskCount >
            0 &&
            !taskSearchActive && (
              <button
                type="button"
                className="sidebar-more-tasks"
                onClick={() =>
                  setShowAllTasks(
                    true,
                  )
                }
              >
                +
                {' '}
                {hiddenTaskCount}
                {' '}
                more task
                {hiddenTaskCount ===
                1
                  ? ''
                  : 's'}
              </button>
            )}

          <div className="sidebar-footer">
            <div
              className={
                apiOnline
                  ? 'system-online'
                  : 'system-online system-offline'
              }
            >
              <span className="online-dot" />

              <strong>
                {apiOnline
                  ? 'API connected'
                  : 'API unavailable'}
              </strong>
            </div>

            <span>
              Human approval enabled
            </span>

            <span>
              Safe execution controls active
            </span>
          </div>
        </aside>

        <main className="main-content">
          {error && (
            <div className="global-message global-error">
              <span>
                !
              </span>

              <div>
                <strong>
                  Action failed
                </strong>

                <p>
                  {error}
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setError(
                    null,
                  )
                }
              >
                ×
              </button>
            </div>
          )}

          {notice && (
            <div className="global-message global-success">
              <span>
                ✓
              </span>

              <div>
                <strong>
                  Completed
                </strong>

                <p>
                  {notice}
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setNotice(
                    null,
                  )
                }
              >
                ×
              </button>
            </div>
          )}

          {view ===
          'history' ? (
            <HistoryPage
              tasks={
                tasks
              }
              onOpenTask={
                handleSelectTask
              }
            />
          ) : taskLoading &&
            selectedTaskId ? (
              <div className="workspace-loader">
                <div className="loading-orbit" />

                <strong>
                  Loading task workspace…
                </strong>
              </div>
            ) : !task ? (
              <div className="welcome-state">
                <div className="welcome-glow" />

                <div className="welcome-mark">
                  {'</>'}
                </div>

                <div className="welcome-kicker">
                  Autonomous engineering
                  with human control
                </div>

                <h1>
                  AI Software Engineering
                  Agent
                </h1>

                <p>
                  Inspect repositories,
                  prepare controlled code
                  changes, verify results
                  and recover from failures
                  without bypassing human
                  approval.
                </p>

                <div className="welcome-features">
                  <span>
                    Repository-aware
                  </span>

                  <span>
                    Human-in-the-loop
                  </span>

                  <span>
                    Safe verification
                  </span>

                  <span>
                    Self-correction
                  </span>
                </div>

                <button
                  type="button"
                  className="button button-primary welcome-button"
                  onClick={() =>
                    setNewTaskOpen(
                      true,
                    )
                  }
                >
                  <span>
                    +
                  </span>

                  Create your first task
                </button>
              </div>
            ) : (
              <>
                <header className="page-header">
                  <div className="page-header-copy">
                    <div className="breadcrumb">
                      Engineering Control

                      <span>
                        /
                      </span>

                      Task Workspace
                    </div>

                    <h1>
                      {task.title}
                    </h1>

                    <p className="task-description">
                      {task.description}
                    </p>

                    <div className="repository-path">
                      <span>
                        Repository
                      </span>

                      <code
                        title={
                          task.repository_path
                        }
                      >
                        {
                          task.repository_path
                        }
                      </code>
                    </div>
                  </div>

                  <div className="page-header-actions">
                    <div className="header-api-status">
                      <span className="online-dot" />

                      API online
                    </div>

                    <button
                      type="button"
                      className="button button-secondary"
                      disabled={
                        busyAction !==
                        null
                      }
                      onClick={() => {
                        if (
                          selectedTaskId
                        ) {
                          void refreshTaskData(
                            selectedTaskId,
                          )
                        }
                      }}
                    >
                      ↻ Refresh
                    </button>
                  </div>
                </header>

                <section className="workflow-strip">
                  {workflowSteps.map(
                    (
                      step,
                      index,
                    ) => (
                      <div
                        key={
                          step.label
                        }
                        className={
                          `workflow-step workflow-${step.state}`
                        }
                      >
                        <span className="workflow-step-index">
                          {step.state ===
                          'done'
                            ? '✓'
                            : index +
                              1}
                        </span>

                        <div>
                          <strong>
                            {
                              step.label
                            }
                          </strong>

                          <small>
                            {
                              step.description
                            }
                          </small>
                        </div>
                      </div>
                    ),
                  )}
                </section>

                <section className="overview-grid">
                  <article className="overview-card">
                    <div className="overview-top">
                      <span className="overview-label">
                        Pending review
                      </span>

                      <span className="overview-icon">
                        ◇
                      </span>
                    </div>

                    <strong className="overview-value">
                      {
                        pendingPatchCount
                      }
                    </strong>

                    <small>
                      Patches awaiting
                      human decision
                    </small>
                  </article>

                  <article className="overview-card">
                    <div className="overview-top">
                      <span className="overview-label">
                        Approved
                      </span>

                      <span className="overview-icon">
                        ✓
                      </span>
                    </div>

                    <strong className="overview-value">
                      {
                        approvedPatchCount
                      }
                    </strong>

                    <small>
                      Patches ready to
                      apply
                    </small>
                  </article>

                  <article className="overview-card">
                    <div className="overview-top">
                      <span className="overview-label">
                        Latest verification
                      </span>

                      <span className="overview-icon">
                        ✓/
                      </span>
                    </div>

                    <div className="overview-status">
                      {latestVerification ? (
                        <StatusBadge
                          status={
                            latestVerification.status
                          }
                        />
                      ) : (
                        <span className="muted">
                          Not run
                        </span>
                      )}
                    </div>

                    <small>
                      {latestVerification
                        ? formatTimestamp(
                            latestVerification.completed_at ??
                              latestVerification.created_at,
                          )
                        : 'No execution history'}
                    </small>
                  </article>

                  <article className="overview-card">
                    <div className="overview-top">
                      <span className="overview-label">
                        Self-correction
                      </span>

                      <span className="overview-icon">
                        ↻
                      </span>
                    </div>

                    <div className="overview-status">
                      {visibleCorrection ? (
                        <StatusBadge
                          status={
                            visibleCorrection
                              .active_session
                              .status
                          }
                        />
                      ) : (
                        <span className="muted">
                          Idle
                        </span>
                      )}
                    </div>

                    <small>
                      Human approval
                      protected
                    </small>
                  </article>
                </section>

                <section className="workspace-section">
                  <div className="section-header">
                    <div>
                      <div className="section-number">
                        01
                      </div>

                      <div>
                        <h2>
                          Implementation Plan
                        </h2>

                        <p>
                          Inspect the
                          repository and
                          generate an
                          evidence-based
                          implementation
                          strategy.
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="button button-primary"
                      disabled={
                        busyAction !==
                        null
                      }
                      onClick={() =>
                        void handleGeneratePlan()
                      }
                    >
                      {busyAction ===
                      'plan'
                        ? 'Generating…'
                        : plan
                          ? 'Regenerate plan'
                          : implementationPlanState ===
                              'historical'
                            ? 'Generate current plan'
                            : 'Generate plan'}
                    </button>
                  </div>

                  {plan ? (
                    <div className="json-panel">
                      <div className="json-panel-header">
                        <span>
                          Agent plan
                        </span>

                        <span>
                          Current session · JSON
                        </span>
                      </div>

                      <pre>
                        {JSON.stringify(
                          plan,
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  ) : implementationPlanState ===
                    'historical' ? (
                      <div className="historical-plan-state">
                        <div className="historical-plan-icon">
                          ✓
                        </div>

                        <div className="historical-plan-copy">
                          <div className="historical-plan-heading">
                            <h3>
                              Previous planning completed
                            </h3>

                            <span>
                              Historical task
                            </span>
                          </div>

                          <p>
                            This task already
                            has downstream
                            engineering activity,
                            such as patches,
                            verification runs or
                            self-correction.
                            The current API does
                            not expose the
                            original plan payload
                            when an existing task
                            is reopened.
                          </p>

                          <div className="historical-plan-evidence">
                            {patches.length >
                              0 && (
                              <span>
                                ✓
                                {' '}
                                {patches.length}
                                {' '}
                                patch
                                {patches.length ===
                                1
                                  ? ''
                                  : 'es'}
                              </span>
                            )}

                            {verifications.length >
                              0 && (
                              <span>
                                ✓
                                {' '}
                                {
                                  verifications.length
                                }
                                {' '}
                                verification
                                {verifications.length ===
                                1
                                  ? ''
                                  : 's'}
                              </span>
                            )}

                            {correctionSource && (
                              <span>
                                ✓ Self-correction activity
                              </span>
                            )}
                          </div>

                          <small>
                            Generate a current
                            plan only if you want
                            the repository
                            inspected again.
                          </small>
                        </div>
                      </div>
                    ) : (
                      <div className="empty-state horizontal-empty">
                        <div className="empty-state-icon">
                          ◇
                        </div>

                        <div>
                          <h3>
                            No implementation
                            plan yet
                          </h3>

                          <p>
                            Generate a plan
                            before preparing
                            repository
                            changes.
                          </p>
                        </div>
                      </div>
                    )}
                </section>

                <section className="workspace-section">
                  <div className="section-header">
                    <div>
                      <div className="section-number">
                        02
                      </div>

                      <div>
                        <h2>
                          Patch Review
                        </h2>

                        <p>
                          Review AI-generated
                          diffs and control
                          every repository
                          write through
                          explicit human
                          approval.
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="button button-secondary"
                      disabled={
                        busyAction !==
                        null
                      }
                      onClick={() =>
                        void handlePreparePatches()
                      }
                    >
                      {busyAction ===
                      'prepare-patches'
                        ? 'Preparing…'
                        : 'Prepare changes'}
                    </button>
                  </div>

                  {patches.length ===
                  0 ? (
                    <div className="empty-state horizontal-empty">
                      <div className="empty-state-icon">
                        ±
                      </div>

                      <div>
                        <h3>
                          No reviewable
                          changes
                        </h3>

                        <p>
                          Prepare changes to
                          create controlled
                          diffs without
                          writing directly
                          to disk.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="patch-list">
                      {patches.map(
                        (patch) => (
                          <PatchCard
                            key={
                              patch.id
                            }
                            patch={
                              patch
                            }
                            busyAction={
                              busyAction
                            }
                            onAction={
                              handlePatchAction
                            }
                          />
                        ),
                      )}
                    </div>
                  )}
                </section>

                <section className="workspace-section">
                  <div className="section-header verification-section-header">
                    <div>
                      <div className="section-number">
                        03
                      </div>

                      <div>
                        <h2>
                          Automated Verification
                        </h2>

                        <p>
                          Execute compileall,
                          Ruff and pytest
                          inside the
                          controlled
                          verification
                          workflow.
                        </p>
                      </div>
                    </div>

                    <div className="verification-controls">
                      <textarea
                        value={
                          pytestTargetsInput
                        }
                        onChange={(
                          event,
                        ) =>
                          setPytestTargetsInput(
                            event.target
                              .value,
                          )
                        }
                        placeholder={
                          'Optional pytest targets\nExample: tests/test_api.py'
                        }
                        rows={2}
                      />

                      <button
                        type="button"
                        className="button button-primary"
                        disabled={
                          busyAction !==
                          null
                        }
                        onClick={() =>
                          void handleRunVerification()
                        }
                      >
                        {busyAction ===
                        'verification'
                          ? 'Running…'
                          : 'Run verification'}
                      </button>
                    </div>
                  </div>

                  <VerificationPanel
                    runs={
                      verifications
                    }
                    selectedId={
                      selectedVerificationId
                    }
                    onSelect={
                      setSelectedVerificationId
                    }
                  />
                </section>

                <section className="workspace-section">
                  <div className="section-header">
                    <div>
                      <div className="section-number">
                        04
                      </div>

                      <div>
                        <h2>
                          Self-Correction Control
                        </h2>

                        <p>
                          Diagnose failures,
                          create bounded
                          correction attempts
                          and stop at every
                          protected human
                          approval gate.
                        </p>
                      </div>
                    </div>
                  </div>

                  <CorrectionPanel
                    sourceVerification={
                      correctionSource
                    }
                    correction={
                      visibleCorrection
                    }
                    loading={
                      correctionLoading
                    }
                    busyAction={
                      busyAction
                    }
                    onRefresh={
                      refreshCorrection
                    }
                    onAnalyze={() =>
                      runCorrectionAction(
                        'analyze',
                      )
                    }
                    onPropose={() =>
                      runCorrectionAction(
                        'propose',
                      )
                    }
                    onPrepare={() =>
                      runCorrectionAction(
                        'prepare-correction',
                      )
                    }
                    onAdvance={() =>
                      runCorrectionAction(
                        'advance',
                      )
                    }
                  />
                </section>

                <footer className="workspace-footer">
                  <span>
                    AI Software Engineering
                    Agent
                  </span>

                  <span>
                    Safe execution · Human
                    approval · Audit history
                  </span>
                </footer>
              </>
            )}
        </main>
      </div>

      {newTaskOpen && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={() =>
            setNewTaskOpen(
              false,
            )
          }
        >
          <div
            className="task-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Create engineering task"
            onMouseDown={(
              event,
            ) =>
              event.stopPropagation()
            }
          >
            <div className="modal-header">
              <div>
                <div className="modal-icon">
                  {'</>'}
                </div>

                <div>
                  <h2>
                    Create engineering task
                  </h2>

                  <p>
                    Give the agent a
                    repository and a clear,
                    verifiable software
                    change.
                  </p>
                </div>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setNewTaskOpen(
                    false,
                  )
                }
              >
                ×
              </button>
            </div>

            <form
              className="task-modal-form"
              onSubmit={
                handleCreateTask
              }
            >
              <label>
                <span>
                  Task title
                </span>

                <input
                  autoFocus
                  value={
                    newTaskTitle
                  }
                  onChange={(
                    event,
                  ) =>
                    setNewTaskTitle(
                      event.target
                        .value,
                    )
                  }
                  placeholder="Update sample value"
                />
              </label>

              <label>
                <span>
                  Description
                </span>

                <textarea
                  value={
                    newTaskDescription
                  }
                  onChange={(
                    event,
                  ) =>
                    setNewTaskDescription(
                      event.target
                        .value,
                    )
                  }
                  placeholder="Describe exactly what should change and what behavior must remain valid."
                  rows={5}
                />
              </label>

              <label>
                <span>
                  Repository path
                </span>

                <input
                  value={
                    newRepositoryPath
                  }
                  onChange={(
                    event,
                  ) =>
                    setNewRepositoryPath(
                      event.target
                        .value,
                    )
                  }
                  placeholder="C:\projects\my-repository"
                />
              </label>

              <div className="modal-safety-note">
                <span>
                  ⛨
                </span>

                <p>
                  Preparing changes does
                  not write to disk.
                  Repository writes still
                  require explicit human
                  approval and apply.
                </p>
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="button button-ghost"
                  disabled={
                    busyAction !== null
                  }
                  onClick={() =>
                    setNewTaskOpen(
                      false,
                    )
                  }
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="button button-primary"
                  disabled={
                    busyAction !== null
                  }
                >
                  {busyAction ===
                  'create-task'
                    ? 'Creating task…'
                    : 'Create task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}

export default App