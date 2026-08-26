import {
  useMemo,
} from 'react'

import type {
  VerificationRun,
} from '../types'

import StatusBadge from './StatusBadge'


type VerificationPanelProps = {
  runs: VerificationRun[]
  selectedId: string | null
  onSelect: (
    verificationId: string,
  ) => void
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


function VerificationPanel({
  runs,
  selectedId,
  onSelect,
}: VerificationPanelProps) {
  const selected =
    runs.find(
      (run) =>
        run.id === selectedId,
    ) ??
    runs[0] ??
    null

  const summary =
    useMemo(() => {
      if (!selected) {
        return {
          passed: 0,
          failed: 0,
          duration: 0,
        }
      }

      return {
        passed:
          selected.steps.filter(
            (step) =>
              step.succeeded,
          ).length,

        failed:
          selected.steps.filter(
            (step) =>
              !step.succeeded,
          ).length,

        duration:
          selected.steps.reduce(
            (
              total,
              step,
            ) =>
              total +
              step.duration_seconds,
            0,
          ),
      }
    }, [
      selected,
    ])

  if (
    runs.length === 0 ||
    !selected
  ) {
    return (
      <div className="empty-state verification-empty">
        <div className="empty-state-icon">
          ✓/
        </div>

        <h3>
          No verification runs yet
        </h3>

        <p>
          Run the controlled
          verification pipeline to
          execute compileall, Ruff and
          pytest.
        </p>
      </div>
    )
  }

  return (
    <div className="verification-layout">
      <aside className="verification-list">
        <div className="verification-list-heading">
          <span>
            Execution history
          </span>

          <strong>
            {runs.length}
          </strong>
        </div>

        {runs.map(
          (run, index) => (
            <button
              key={run.id}
              type="button"
              className={
                run.id ===
                selected.id
                  ? 'verification-list-item active'
                  : 'verification-list-item'
              }
              onClick={() =>
                onSelect(
                  run.id,
                )
              }
            >
              <div className="verification-list-top">
                <div>
                  <small>
                    Run
                    {' '}
                    #
                    {runs.length -
                      index}
                  </small>

                  <StatusBadge
                    status={
                      run.status
                    }
                  />
                </div>

                <span className="verification-date">
                  {formatTimestamp(
                    run.created_at,
                  )}
                </span>
              </div>

              <span className="mono verification-id">
                {run.id}
              </span>
            </button>
          ),
        )}
      </aside>

      <div className="verification-detail">
        <div className="verification-detail-header">
          <div>
            <div className="eyebrow">
              Verification run
            </div>

            <h3 className="mono break-anywhere">
              {selected.id}
            </h3>

            <span className="verification-started">
              Started
              {' '}
              {formatTimestamp(
                selected.started_at,
              )}
            </span>
          </div>

          <StatusBadge
            status={
              selected.status
            }
          />
        </div>

        <div className="verification-summary-grid">
          <div className="verification-summary-card">
            <span>
              Steps
            </span>

            <strong>
              {selected.steps.length}
            </strong>

            <small>
              controlled commands
            </small>
          </div>

          <div className="verification-summary-card">
            <span>
              Passed
            </span>

            <strong className="summary-success">
              {summary.passed}
            </strong>

            <small>
              successful checks
            </small>
          </div>

          <div className="verification-summary-card">
            <span>
              Failed
            </span>

            <strong
              className={
                summary.failed > 0
                  ? 'summary-danger'
                  : ''
              }
            >
              {summary.failed}
            </strong>

            <small>
              failed checks
            </small>
          </div>

          <div className="verification-summary-card">
            <span>
              Runtime
            </span>

            <strong>
              {summary.duration.toFixed(
                2,
              )}
              s
            </strong>

            <small>
              total execution
            </small>
          </div>
        </div>

        {selected.error_message && (
          <div className="callout callout-danger">
            <strong>
              Verification error:
            </strong>
            {' '}
            {
              selected.error_message
            }
          </div>
        )}

        <div className="verification-pipeline-heading">
          <div>
            <strong>
              Pipeline execution
            </strong>

            <span>
              Sandboxed command history
            </span>
          </div>

          <time>
            Completed
            {' '}
            {formatTimestamp(
              selected.completed_at,
            )}
          </time>
        </div>

        <div className="step-list">
          {selected.steps.map(
            (step) => (
              <article
                key={step.id}
                className={
                  step.succeeded
                    ? 'verification-step verification-step-success'
                    : 'verification-step verification-step-failed'
                }
              >
                <div className="verification-step-header">
                  <div className="step-number">
                    {
                      step.position
                    }
                  </div>

                  <div className="step-title-group">
                    <strong>
                      {
                        step.command_type
                      }
                    </strong>

                    <span className="mono muted">
                      {step.command.join(
                        ' ',
                      )}
                    </span>
                  </div>

                  <StatusBadge
                    status={
                      step.succeeded
                        ? 'passed'
                        : step.timed_out
                          ? 'timeout'
                          : 'failed'
                    }
                  />
                </div>

                <div className="step-metrics">
                  <span>
                    Exit code
                    {' '}
                    <strong>
                      {step.exit_code ??
                        '—'}
                    </strong>
                  </span>

                  <span>
                    Duration
                    {' '}
                    <strong>
                      {step.duration_seconds.toFixed(
                        3,
                      )}
                      s
                    </strong>
                  </span>
                </div>

                {(step.stdout ||
                  step.stderr) && (
                  <details
                    className="terminal-details"
                    open={
                      !step.succeeded
                    }
                  >
                    <summary>
                      View command output
                    </summary>

                    <div className="terminal-output">
                      {step.stdout && (
                        <div>
                          <div className="terminal-label">
                            stdout
                          </div>

                          <pre>
                            {
                              step.stdout
                            }
                          </pre>
                        </div>
                      )}

                      {step.stderr && (
                        <div>
                          <div className="terminal-label terminal-label-error">
                            stderr
                          </div>

                          <pre>
                            {
                              step.stderr
                            }
                          </pre>
                        </div>
                      )}
                    </div>
                  </details>
                )}
              </article>
            ),
          )}
        </div>
      </div>
    </div>
  )
}

export default VerificationPanel