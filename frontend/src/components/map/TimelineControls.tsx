interface TimelineControlsProps {
  minuteCount: number
  currentMinuteIndex: number
  isPlaying: boolean
  isLoading: boolean
  error: string | null
  onSeek: (nextMinuteIndex: number) => void
  onTogglePlay: () => void
}

function formatMinuteClock(minuteIndex: number): string {
  const safeMinute = Math.max(0, Math.min(1439, Math.floor(minuteIndex)))
  const hours = Math.floor(safeMinute / 60)
  const minutes = safeMinute % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

export function TimelineControls({
  minuteCount,
  currentMinuteIndex,
  isPlaying,
  isLoading,
  error,
  onSeek,
  onTogglePlay,
}: TimelineControlsProps) {
  const safeMax = Math.max(0, minuteCount - 1)

  return (
    <div className="timeline-controls" aria-label="24-hour interpolation timeline controls">
      <div className="timeline-controls__header">
        <button
          type="button"
          className="timeline-controls__play"
          onClick={onTogglePlay}
          disabled={isLoading || minuteCount === 0}
        >
          {isPlaying ? 'Pause' : 'Play'}
        </button>

        <div className="timeline-controls__label">
          {formatMinuteClock(currentMinuteIndex)}
        </div>
      </div>

      <input
        className="timeline-controls__slider"
        type="range"
        min={0}
        max={safeMax}
        step={1}
        value={Math.min(currentMinuteIndex, safeMax)}
        onChange={(event) => onSeek(Number(event.target.value))}
        disabled={isLoading || minuteCount === 0}
        aria-label="Timeline minute index"
      />

      <div className="timeline-controls__meta" aria-live="polite">
        {isLoading && 'Loading timeline...'}
        {!isLoading && error}
        {!isLoading && !error && minuteCount > 0
          ? `Minute ${Math.min(currentMinuteIndex + 1, minuteCount)} / ${minuteCount}`
          : null}
        {!isLoading && !error && minuteCount === 0 ? 'Select a metric to load timeline.' : null}
      </div>
    </div>
  )
}
