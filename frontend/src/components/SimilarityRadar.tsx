import { useId } from 'react'

const AXES = [
  { key: 'weight_title', label: 'Title / Role' },
  { key: 'weight_skills', label: 'Tech & Skills' },
  { key: 'weight_seniority', label: 'Seniority' },
  { key: 'weight_sector', label: 'Sector & Type' },
] as const

type WeightKey = (typeof AXES)[number]['key']

interface Props {
  weights: Record<WeightKey, number>
  onChange: (key: WeightKey, value: number) => void
  size?: number
}

function polarToCart(angle: number, r: number, cx: number, cy: number) {
  const rad = (angle - 90) * (Math.PI / 180)
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

export default function SimilarityRadar({ weights, onChange, size = 220 }: Props) {
  const id = useId()
  const cx = size / 2
  const cy = size / 2
  const maxR = size * 0.38
  const n = AXES.length
  const angleStep = 360 / n

  const gridLevels = [0.25, 0.5, 0.75, 1.0]

  const axisPoints = AXES.map((_, i) => polarToCart(i * angleStep, maxR, cx, cy))
  const dataPoints = AXES.map(({ key }, i) => polarToCart(i * angleStep, maxR * (weights[key] ?? 0), cx, cy))
  const dataPath = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') + ' Z'

  return (
    <div className="flex flex-col items-center gap-6">
      {/* SVG radar */}
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-label="Similarity weight radar chart"
        role="img"
      >
        <defs>
          <radialGradient id={`${id}-fill`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0.10" />
          </radialGradient>
        </defs>

        {/* Grid rings */}
        {gridLevels.map((lvl) => {
          const pts = AXES.map((_, i) => polarToCart(i * angleStep, maxR * lvl, cx, cy))
          const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') + ' Z'
          return (
            <path
              key={lvl}
              d={path}
              fill="none"
              stroke="var(--color-outline-variant)"
              strokeOpacity="0.35"
              strokeWidth="1"
            />
          )
        })}

        {/* Axis spokes */}
        {axisPoints.map((pt, i) => (
          <line
            key={i}
            x1={cx} y1={cy}
            x2={pt.x.toFixed(1)} y2={pt.y.toFixed(1)}
            stroke="var(--color-outline-variant)"
            strokeOpacity="0.4"
            strokeWidth="1"
          />
        ))}

        {/* Data polygon */}
        <path
          d={dataPath}
          fill={`url(#${id}-fill)`}
          stroke="var(--color-primary)"
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {/* Axis labels */}
        {AXES.map(({ label }, i) => {
          const pt = polarToCart(i * angleStep, maxR + 18, cx, cy)
          const anchor = pt.x < cx - 4 ? 'end' : pt.x > cx + 4 ? 'start' : 'middle'
          return (
            <text
              key={i}
              x={pt.x.toFixed(1)}
              y={pt.y.toFixed(1)}
              textAnchor={anchor}
              dominantBaseline="middle"
              fontSize="10"
              fontWeight="600"
              fill="var(--color-on-surface-variant)"
            >
              {label}
            </text>
          )
        })}

        {/* Data point dots */}
        {dataPoints.map((pt, i) => (
          <circle key={i} cx={pt.x.toFixed(1)} cy={pt.y.toFixed(1)} r="3.5" fill="var(--color-primary)" />
        ))}
      </svg>

      {/* Per-axis sliders */}
      <div className="w-full space-y-3 max-w-xs">
        {AXES.map(({ key, label }) => (
          <div key={key} className="space-y-1">
            <div className="flex justify-between text-xs font-semibold text-on-surface-variant">
              <span>{label}</span>
              <span className="text-primary">{((weights[key] ?? 0) * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={weights[key] ?? 0}
              onChange={(e) => onChange(key, parseFloat(e.target.value))}
              className="w-full h-1.5 rounded-full accent-primary bg-surface-container cursor-pointer"
              aria-label={`${label} weight`}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
