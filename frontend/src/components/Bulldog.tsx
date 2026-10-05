interface Props {
  size?: number
  /** Gentle head tilt + blink (off automatically for prefers-reduced-motion). */
  animated?: boolean
  className?: string
  title?: string
}

/**
 * Handsome Dan, the Campus Customs shop bulldog, drawn in SVG: fawn face,
 * brindle eye patch, underbite, and a Yale-blue collar with a gold "Y" tag.
 */
export default function Bulldog({ size = 48, animated = false, className = '', title }: Props) {
  return (
    <svg
      className={`bulldog${animated ? ' animated' : ''} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <g className="dan-head">
        {/* ears */}
        <path d="M22 30 C10 22 8 46 18 54 C24 46 28 38 32 34 Z" fill="#6b4a33" stroke="#1d2340" strokeWidth="3" strokeLinejoin="round" />
        <path d="M98 30 C110 22 112 46 102 54 C96 46 92 38 88 34 Z" fill="#6b4a33" stroke="#1d2340" strokeWidth="3" strokeLinejoin="round" />
        {/* head */}
        <path
          d="M60 22 C88 22 104 40 104 64 C104 88 86 104 60 104 C34 104 16 88 16 64 C16 40 32 22 60 22 Z"
          fill="#f1dfc4"
          stroke="#1d2340"
          strokeWidth="3"
        />
        {/* brindle patch */}
        <path d="M70 34 C86 32 96 44 92 58 C84 60 74 56 68 48 C66 42 66 37 70 34 Z" fill="#c9925f" />
        {/* brow wrinkles */}
        <path d="M44 36 C52 32 60 32 66 35" fill="none" stroke="#b8865a" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M48 42 C54 39 60 39 64 41" fill="none" stroke="#b8865a" strokeWidth="2.5" strokeLinecap="round" />
        {/* eyes */}
        <g className="dan-eyes">
          <circle cx="42" cy="56" r="6" fill="#1d2340" />
          <circle cx="78" cy="56" r="6" fill="#1d2340" />
          <circle cx="44" cy="54" r="2" fill="#fff" />
          <circle cx="80" cy="54" r="2" fill="#fff" />
        </g>
        {/* muzzle + jowls */}
        <path
          d="M30 80 C30 66 44 62 60 62 C76 62 90 66 90 80 C90 94 76 98 60 98 C44 98 30 94 30 80 Z"
          fill="#fff7ea"
          stroke="#1d2340"
          strokeWidth="2.5"
        />
        <path d="M60 74 L60 84 M60 84 C54 90 44 90 40 84 M60 84 C66 90 76 90 80 84" fill="none" stroke="#1d2340" strokeWidth="2.5" strokeLinecap="round" />
        {/* underbite teeth */}
        <path d="M49 90 L50 84 L53 89 Z M71 90 L70 84 L67 89 Z" fill="#fff" stroke="#1d2340" strokeWidth="1.5" strokeLinejoin="round" />
        {/* nose */}
        <ellipse cx="60" cy="70" rx="11" ry="7" fill="#1d2340" />
        <ellipse cx="56" cy="68" rx="3" ry="1.6" fill="#5b6280" />
        {/* cheeks */}
        <circle cx="32" cy="74" r="5" fill="#f6b8c8" opacity="0.7" />
        <circle cx="88" cy="74" r="5" fill="#f6b8c8" opacity="0.7" />
      </g>
      {/* Yale-blue collar with a gold Y tag */}
      <path d="M28 100 C44 110 76 110 92 100 L94 108 C76 118 44 118 26 108 Z" fill="#00356b" stroke="#1d2340" strokeWidth="2" />
      <circle cx="60" cy="112" r="7" fill="#f4c542" stroke="#1d2340" strokeWidth="2" />
      <text x="60" y="115.5" textAnchor="middle" fontFamily="Georgia, serif" fontWeight="700" fontSize="9" fill="#00356b">
        Y
      </text>
    </svg>
  )
}
