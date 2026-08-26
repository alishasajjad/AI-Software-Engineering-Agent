import {
  useMemo,
  useState,
} from 'react'

import type {
  PendingPatch,
} from '../types'

import StatusBadge from './StatusBadge'


type PatchAction =
  | 'approve'
  | 'reject'
  | 'apply'


type PatchCardProps = {
  patch: PendingPatch
  busyAction: string | null
  onAction: (
    patch: PendingPatch,
    action: PatchAction,
  ) => Promise<void>
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


function PatchCard({
  patch,
  busyAction,
  onAction,
}: PatchCardProps) {
  const [diffOpen, setDiffOpen] =
    useState(true)

  const operationKey = (
    action: PatchAction,
  ) =>
    `${patch.id}:${action}`

  const isBusy = (
    action: PatchAction,
  ) =>
    busyAction ===
    operationKey(action)

  const pending =
    patch.status === 'pending'

  const approved =
    patch.status === 'approved'

  const diffStats =
    useMemo(() => {
      const lines =
        patch.diff.split('\n')

      const additions =
        lines.filter(
          (line) =>
            line.startsWith(
              '+',
            ) &&
            !line.startsWith(
              '+++',
            ),
        ).length

      const deletions =
        lines.filter(
          (line) =>
            line.startsWith(
              '-',
            ) &&
            !line.startsWith(
              '---',
            ),
        ).length

      return {
        additions,
        deletions,
      }
    }, [
      patch.diff,
    ])

  return (
    <article className="patch-card">
      <div className="patch-card-header">
        <div className="patch-heading-copy">
          <div className="eyebrow">
            Controlled file change
          </div>

          <h3 className="patch-path">
            {patch.path}
          </h3>
        </div>

        <StatusBadge
          status={patch.status}
        />
      </div>

      <div className="patch-meta">
        <span>
          Created
          {' '}
          <strong>
            {formatTimestamp(
              patch.created_at,
            )}
          </strong>
        </span>

        {patch.reviewed_at && (
          <span>
            Reviewed
            {' '}
            <strong>
              {formatTimestamp(
                patch.reviewed_at,
              )}
            </strong>
          </span>
        )}

        {patch.applied_at && (
          <span>
            Applied
            {' '}
            <strong>
              {formatTimestamp(
                patch.applied_at,
              )}
            </strong>
          </span>
        )}
      </div>

      <div className="patch-summary-row">
        <div className="patch-stat patch-stat-add">
          <span>
            +
          </span>

          <strong>
            {diffStats.additions}
          </strong>

          additions
        </div>

        <div className="patch-stat patch-stat-delete">
          <span>
            −
          </span>

          <strong>
            {diffStats.deletions}
          </strong>

          deletions
        </div>

        <div className="patch-hash">
          <span>
            Original SHA
          </span>

          <code>
            {patch.original_sha256.slice(
              0,
              12,
            )}
          </code>
        </div>
      </div>

      <div className="diff-shell">
        <div className="diff-toolbar">
          <div>
            <span className="diff-dot diff-dot-red" />
            <span className="diff-dot diff-dot-yellow" />
            <span className="diff-dot diff-dot-green" />

            <strong>
              Unified diff
            </strong>
          </div>

          <button
            type="button"
            className="diff-toggle"
            onClick={() =>
              setDiffOpen(
                (current) =>
                  !current,
              )
            }
          >
            {diffOpen
              ? 'Hide'
              : 'Show'}
          </button>
        </div>

        {diffOpen && (
          <pre className="diff-view">
            {patch.diff ||
              'No textual diff available.'}
          </pre>
        )}
      </div>

      {(pending ||
        approved) && (
        <div className="patch-review-gate">
          <div>
            <span className="review-gate-icon">
              ⛨
            </span>

            <div>
              <strong>
                Human approval gate
              </strong>

              <p>
                No repository write
                occurs until an approved
                patch is explicitly
                applied.
              </p>
            </div>
          </div>

          <div className="patch-actions">
            {pending && (
              <>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={
                    busyAction !==
                    null
                  }
                  onClick={() =>
                    void onAction(
                      patch,
                      'approve',
                    )
                  }
                >
                  {isBusy(
                    'approve',
                  )
                    ? 'Approving…'
                    : '✓ Approve patch'}
                </button>

                <button
                  type="button"
                  className="button button-danger"
                  disabled={
                    busyAction !==
                    null
                  }
                  onClick={() =>
                    void onAction(
                      patch,
                      'reject',
                    )
                  }
                >
                  {isBusy(
                    'reject',
                  )
                    ? 'Rejecting…'
                    : 'Reject'}
                </button>
              </>
            )}

            {approved && (
              <>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={
                    busyAction !==
                    null
                  }
                  onClick={() =>
                    void onAction(
                      patch,
                      'apply',
                    )
                  }
                >
                  {isBusy(
                    'apply',
                  )
                    ? 'Applying…'
                    : 'Apply approved patch'}
                </button>

                <button
                  type="button"
                  className="button button-danger"
                  disabled={
                    busyAction !==
                    null
                  }
                  onClick={() =>
                    void onAction(
                      patch,
                      'reject',
                    )
                  }
                >
                  {isBusy(
                    'reject',
                  )
                    ? 'Rejecting…'
                    : 'Reject'}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {patch.status ===
        'applied' && (
        <div className="callout callout-success">
          <strong>
            Safely applied.
          </strong>
          {' '}
          This approved patch has
          been written to the
          repository.
        </div>
      )}

      {patch.status ===
        'stale' && (
        <div className="callout callout-warning">
          Repository content changed
          after this patch was
          prepared. Generate a fresh
          patch before continuing.
        </div>
      )}

      {patch.status ===
        'rejected' && (
        <div className="callout callout-neutral">
          This patch was rejected and
          cannot be applied.
        </div>
      )}
    </article>
  )
}

export default PatchCard