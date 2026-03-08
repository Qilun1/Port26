import type { ViewMode } from '../../features/sensors/model/viewMode'

interface ViewModeToggleProps {
  value: ViewMode
  onChange: (nextMode: ViewMode) => void
  disabled?: boolean
}

export function ViewModeToggle({ value, onChange, disabled = false }: ViewModeToggleProps) {
  return (
    <div className="view-mode-toggle" role="group" aria-label="View mode selector">
      <button
        type="button"
        className={`view-mode-toggle__button${value === '2d' ? ' view-mode-toggle__button--active' : ''}`}
        onClick={() => onChange('2d')}
        disabled={disabled}
      >
        2D Heatmap
      </button>
      <button
        type="button"
        className={`view-mode-toggle__button${value === '3d' ? ' view-mode-toggle__button--active' : ''}`}
        onClick={() => onChange('3d')}
        disabled={disabled}
      >
        3D Surface
      </button>
    </div>
  )
}
