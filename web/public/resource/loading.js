/**
 * Initialize the SVG logo shown on the first loading screen.
 * @param {string} id - Element selector.
 */
function initSvgLogo(id) {
  const svgStr = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" class="loading-svg" aria-label="FinWork">
      <defs>
        <linearGradient id="loading-fw-grad" x1="112" y1="108" x2="420" y2="402" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#2563EB"/>
          <stop offset=".52" stop-color="#06B6D4"/>
          <stop offset="1" stop-color="#22C55E"/>
        </linearGradient>
      </defs>
      <g fill="none" stroke="url(#loading-fw-grad)" stroke-width="48" stroke-linecap="round" stroke-linejoin="round">
        <path d="M142 386V126h190"/>
        <path d="M142 252h138"/>
        <path d="M224 316l50 70 54-94 50 94 46-142"/>
      </g>
      <circle cx="224" cy="316" r="12" fill="#FFFFFF"/>
      <circle cx="328" cy="292" r="12" fill="#FFFFFF"/>
      <circle cx="424" cy="244" r="12" fill="#FFFFFF"/>
    </svg>
  `
  const appEl = document.querySelector(id)
  const div = document.createElement('div')
  div.innerHTML = svgStr
  if (appEl) {
    appEl.appendChild(div)
  }
}

function addThemeColorCssVars() {
  const key = '__THEME_COLOR__'
  const defaultColor = '#2563EB'
  const themeColor = window.localStorage.getItem(key) || defaultColor
  const cssVars = `--primary-color: ${themeColor}`
  document.documentElement.style.cssText = cssVars
}

addThemeColorCssVars()

initSvgLogo('#loadingLogo')
