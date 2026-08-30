interface CompensarBrandProps {
  compact?: boolean
}

export function CompensarBrand({
  compact = false,
}: CompensarBrandProps) {
  return (
    <div
      className={
        compact
          ? 'compensar-brand compact'
          : 'compensar-brand'
      }
      aria-label="Compensar"
    >
      <span
        className="compensar-symbol"
        aria-hidden="true"
      >
        <i className="dot dot-1" />
        <i className="dot dot-2" />
        <i className="dot dot-3" />
        <i className="dot dot-4" />
        <i className="dot dot-5" />
        <i className="dot dot-6" />
      </span>

      {!compact && (
        <strong>compensar</strong>
      )}
    </div>
  )
}
