import { FaForward, FaPlay, FaStop } from 'react-icons/fa6'

interface TimelineControlsProps {
  minuteCount: number
  currentMinuteIndex: number
  playbackSpeed: 0 | 1 | 2 | 4
  isLoading: boolean
  onTogglePlayback: () => void
  onChangePlaybackSpeed: (speed: 1 | 2 | 4) => void
}

const PLAYBACK_SPEEDS: Array<{ speed: 1 | 2 | 4; label: string; title: string }> = [
  { speed: 1, label: '1x', title: 'Normal speed' },
  { speed: 2, label: '2x', title: 'Skip 2 minutes per step' },
  { speed: 4, label: '4x', title: 'Skip 4 minutes per step' },
]

function formatMinuteClock(minuteIndex: number): string {
  const safeMinute = Math.max(0, Math.min(1439, Math.floor(minuteIndex)))
  const hours = Math.floor(safeMinute / 60)
  const minutes = safeMinute % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

export function TimelineControls({
  minuteCount,
  currentMinuteIndex,
  playbackSpeed,
  isLoading,
  onTogglePlayback,
  onChangePlaybackSpeed,
}: TimelineControlsProps) {
  const areControlsDisabled = isLoading || minuteCount === 0
  const effectiveSpeed = playbackSpeed === 0 ? 1 : playbackSpeed

  return (
    <div className="timeline-controls" aria-label="24-hour interpolation timeline controls">
      <button
        type="button"
        className={`timeline-controls__play-toggle${playbackSpeed > 0 ? ' timeline-controls__play-toggle--active' : ''}`}
        onClick={onTogglePlayback}
        disabled={areControlsDisabled}
        title={playbackSpeed > 0 ? 'Stop playback' : 'Start playback'}
        aria-label={playbackSpeed > 0 ? 'Stop playback' : 'Start playback'}
      >
        {playbackSpeed > 0 ? <FaStop aria-hidden="true" /> : <FaPlay aria-hidden="true" />}
      </button>

      <div className="timeline-controls__speed-group" role="group" aria-label="Playback speed">
        {PLAYBACK_SPEEDS.map((item) => (
          <button
            key={item.speed}
            type="button"
            className={`timeline-controls__speed-button${playbackSpeed === item.speed ? ' timeline-controls__speed-button--active' : ''}`}
            onClick={() => onChangePlaybackSpeed(item.speed)}
            disabled={areControlsDisabled}
            title={item.title}
            aria-pressed={effectiveSpeed === item.speed}
          >
            <FaForward aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      <div className="timeline-controls__label" aria-live="polite">
        {formatMinuteClock(currentMinuteIndex)}
      </div>
    </div>
  )
}
