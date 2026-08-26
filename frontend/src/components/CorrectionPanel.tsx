import type {
  CorrectionLoopResponse,
  VerificationRun,
} from '../types'

import StatusBadge from './StatusBadge'


type CorrectionPanelProps = {
  sourceVerification: VerificationRun | null
  correction: CorrectionLoopResponse | null
  loading: boolean
  busyAction: string | null
  onRefresh: () => Promise<void>
  onAnalyze: () => Promise<void>
  onPropose: () => Promise<void>
  onPrepare: () => Promise<void>
  onAdvance: () => Promise<void>
}


const FLOW_STEPS = [
  'Analyze',
  'Propose',
  'Review',
  'Reverify',
]


function flowIndex(
  status: string,
): number {
  const mapping:
    Record<string, number> = {
      analysis_ready: 0,
      proposal_ready: 1,
      patch_ready: 2,
      patches_approved: 2,
      patches_applied: 3,
      retry_created: 3,
      completed: 4,
    }

  return mapping[status] ?? 0
}


function CorrectionPanel({
  sourceVerification,
  correction,
  loading,
  busyAction,
  onRefresh,
  onAnalyze,
  onPropose,
  onPrepare,
  onAdvance,
}: CorrectionPanelProps) {
  if (!sourceVerification) {
    return (
      <div className="empty-state compact-empty correction-empty">
        <div className="empty-state-icon">
          ↻
        </div>

        <h3>
          Self-correction is idle
        </h3>

        <p>
          A failed verification will
          unlock the bounded
          self-correction workflow.
        </p>

        <div className="safety-note">
          <span>
            ⛨
          </span>

          Human approval is required
          before repository writes.
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="loading-state correction-loading">
        <div className="loading-orbit" />

        Loading correction state…
      </div>
    )
  }

  if (!correction) {
    return (
      <div className="correction-start">
        <div className="correction-failure-card">
          <div className="correction-failure-icon">
            !
          </div>

          <div>
            <span>
              Failed verification detected
            </span>

            <strong className="mono break-anywhere">
              {
                sourceVerification.id
              }
            </strong>

            <p>
              Start diagnosis to
              determine the likely cause
              before any corrective
              patch is prepared.
            </p>
          </div>
        </div>

        <button
          type="button"
          className="button button-primary"
          disabled={
            busyAction !== null
          }
          onClick={() =>
            void onAnalyze()
          }
        >
          {busyAction ===
          'analyze'
            ? 'Analyzing failure…'
            : 'Analyze failure'}
        </button>
      </div>
    )
  }

  const session =
    correction.active_session

  const activeFlowIndex =
    flowIndex(
      session.status,
    )

  const attemptProgress =
    session.max_attempts > 0
      ? Math.min(
          100,
          (
            session.current_attempt /
            session.max_attempts
          ) * 100,
        )
      : 0

  return (
    <div className="correction-panel">
      <div className="correction-heading">
        <div>
          <div className="eyebrow">
            Bounded recovery workflow
          </div>

          <div className="correction-title-row">
            <StatusBadge
              status={
                session.status
              }
            />

            {correction.terminal && (
              <span className="terminal-label-inline">
                Terminal state
              </span>
            )}

            {correction.requires_human_action && (
              <span className="human-gate-label">
                ⛨ Human gate
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          className="button button-ghost button-small"
          disabled={
            busyAction !== null
          }
          onClick={() =>
            void onRefresh()
          }
        >
          ↻ Refresh
        </button>
      </div>

      <div className="correction-flow">
        {FLOW_STEPS.map(
          (
            label,
            index,
          ) => {
            const completed =
              activeFlowIndex >
              index

            const active =
              activeFlowIndex ===
              index &&
              !correction.terminal

            return (
              <div
                key={label}
                className={
                  completed
                    ? 'correction-flow-step completed'
                    : active
                      ? 'correction-flow-step active'
                      : 'correction-flow-step'
                }
              >
                <span>
                  {completed
                    ? '✓'
                    : index + 1}
                </span>

                <strong>
                  {label}
                </strong>
              </div>
            )
          },
        )}
      </div>

      <p className="correction-message">
        {correction.message}
      </p>

      <div className="correction-stats">
        <div className="metric-card">
          <span>
            Attempt
          </span>

          <strong>
            {
              session.current_attempt
            }
            {' '}
            /
            {' '}
            {
              session.max_attempts
            }
          </strong>
        </div>

        <div className="metric-card">
          <span>
            Remaining
          </span>

          <strong>
            {
              correction.remaining_attempts
            }
          </strong>
        </div>

        <div className="metric-card">
          <span>
            Next action
          </span>

          <strong>
            {correction.next_action.replaceAll(
              '_',
              ' ',
            )}
          </strong>
        </div>
      </div>

      <div className="attempt-progress">
        <div
          className="attempt-progress-value"
          style={{
            width:
              `${attemptProgress}%`,
          }}
        />
      </div>

      {correction.requires_human_action && (
        <div className="callout callout-warning">
          <strong>
            Human action required.
          </strong>
          {' '}
          The agent is paused at a
          protected approval boundary
          and cannot cross it
          automatically.
        </div>
      )}

      {correction.safe_stopped && (
        <div className="callout callout-danger">
          <strong>
            Safe stop.
          </strong>
          {' '}
          {correction.stop_reason
            ? correction.stop_reason.replaceAll(
                '_',
                ' ',
              )
            : 'The correction loop stopped safely.'}
        </div>
      )}

      <div className="correction-actions">
        {session.status ===
          'analysis_ready' && (
          <>
            <button
              type="button"
              className="button button-primary"
              disabled={
                busyAction !==
                null
              }
              onClick={() =>
                void onPropose()
              }
            >
              {busyAction ===
              'propose'
                ? 'Generating…'
                : 'Generate correction proposal'}
            </button>

            <button
              type="button"
              className="button button-secondary"
              disabled={
                busyAction !==
                null
              }
              onClick={() =>
                void onAdvance()
              }
            >
              Advance safely
            </button>
          </>
        )}

        {session.status ===
          'proposal_ready' && (
          <>
            <button
              type="button"
              className="button button-primary"
              disabled={
                busyAction !==
                null
              }
              onClick={() =>
                void onPrepare()
              }
            >
              {busyAction ===
              'prepare-correction'
                ? 'Preparing…'
                : 'Prepare correction patches'}
            </button>

            <button
              type="button"
              className="button button-secondary"
              disabled={
                busyAction !==
                null
              }
              onClick={() =>
                void onAdvance()
              }
            >
              Advance safely
            </button>
          </>
        )}

        {session.status ===
          'patches_applied' && (
          <button
            type="button"
            className="button button-primary"
            disabled={
              busyAction !== null
            }
            onClick={() =>
              void onAdvance()
            }
          >
            {busyAction ===
            'advance'
              ? 'Re-verifying…'
              : 'Reverify correction'}
          </button>
        )}
      </div>

      {session.status ===
        'patch_ready' && (
        <div className="callout callout-neutral">
          Review the generated
          correction diff in Patch
          Review. The correction cannot
          proceed until a human approves
          or rejects it.
        </div>
      )}

      {session.status ===
        'patches_approved' && (
        <div className="callout callout-neutral">
          Correction patch approved.
          Apply it manually from Patch
          Review before re-verification.
        </div>
      )}

      <div className="correction-lineage">
        <div className="section-mini-header">
          Retry lineage
        </div>

        <div className="lineage-list">
          {correction.chain.map(
            (
              item,
              index,
            ) => (
              <div
                key={
                  item.id
                }
                className="lineage-row"
              >
                <div className="lineage-index">
                  {index + 1}
                </div>

                <div className="lineage-content">
                  <span className="mono">
                    {
                      item.id
                    }
                  </span>

                  <small>
                    Attempt
                    {' '}
                    {
                      item.current_attempt
                    }
                    {' '}
                    /
                    {' '}
                    {
                      item.max_attempts
                    }
                  </small>
                </div>

                <StatusBadge
                  status={
                    item.status
                  }
                />
              </div>
            ),
          )}
        </div>
      </div>
    </div>
  )
}

export default CorrectionPanel