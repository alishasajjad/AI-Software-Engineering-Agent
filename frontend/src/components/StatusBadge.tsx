type StatusBadgeProps = {
  status: string
}


function normalizeStatus(
  status: string,
): string {
  return status
    .toLowerCase()
    .replace(
      /[^a-z0-9_-]/g,
      '-',
    )
}


function humanizeStatus(
  status: string,
): string {
  return status
    .replaceAll(
      '_',
      ' ',
    )
    .replaceAll(
      '-',
      ' ',
    )
}


function StatusBadge({
  status,
}: StatusBadgeProps) {
  const normalized =
    normalizeStatus(
      status,
    )

  return (
    <span
      className={
        `status-badge status-${normalized}`
      }
      title={
        humanizeStatus(
          status,
        )
      }
    >
      <span className="status-dot" />

      {humanizeStatus(
        status,
      )}
    </span>
  )
}

export default StatusBadge