from pathlib import Path
import re
import shutil
import gzip
import brotli

SCHEMA_PATH = Path('/code/apps/organizations_ext/schema.py')
SETTINGS_PATH = Path('/code/glitchtip/settings.py')
DIST_INDEX_PATH = Path('/code/dist/index.html')
EMAIL_TEMPLATE_DIR = Path('/code/templates/account/email')
DIST_IMAGE_DIR = Path('/code/dist/assets/images')
STATIC_IMAGE_DIR = Path('/code/static/assets/images')
STATIC_EMAIL_IMAGE_PATH = Path('/code/static/images/logo.png')
DIST_FAVICON_PATH = Path('/code/dist/favicon.ico')
STATIC_FAVICON_PATH = Path('/code/static/favicon.ico')
IKTARA_ASSET_DIRS = [
    Path('/opt/iktara-assets'),
    Path('/tmp/iktara-assets'),
]


BRAND_NAME = 'YantrAI'
BRAND_SHORT = 'YantrAI'
BRAND_ACCOUNT_NAME = 'YantrAI Account'
BRAND_SUBJECT_PREFIX = '[YantrAI]'


# ── YantrAI-style expanded logo ──
# Matches the new UI sidebar brand: Navy rounded square mark + wordmark
PRIMARY_LOGO_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="40" viewBox="0 0 200 40" role="img" aria-label="{BRAND_SHORT}">
  <!-- Mark: navy square with white glyph -->
  <rect width="32" height="32" x="0" y="4" rx="8" fill="#002c5d"/>
  <g stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(6,10) scale(0.9)">
    <path d="M4 2 L10 10 L16 2"/>
    <line x1="10" y1="10" x2="10" y2="18"/>
    <circle cx="10" cy="10" r="1.4" fill="#ffffff" stroke="none"/>
  </g>
  <!-- Wordmark: YantrAI -->
  <text x="42" y="27" fill="currentColor" font-size="20" font-family="Fraunces, Georgia, serif" font-weight="400" letter-spacing="-0.3">Yantr<tspan font-style="italic" fill="#002c5d">AI</tspan></text>
</svg>
"""


# ── YantrAI-style collapsed sidebar mark ──
# Matches the standalone mark in the design system
COLLAPSED_LOGO_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36" role="img" aria-label="{BRAND_SHORT}">
  <rect width="32" height="32" x="2" y="2" rx="8" fill="#002c5d"/>
  <g stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(8,8) scale(0.9)">
    <path d="M4 2 L10 10 L16 2"/>
    <line x1="10" y1="10" x2="10" y2="18"/>
    <circle cx="10" cy="10" r="1.4" fill="#ffffff" stroke="none"/>
  </g>
</svg>
"""


# ── Inline SVG favicon data URI (YantrAI mark, no image file needed) ──
FAVICON_SVG_DATA_URI = (
    'data:image/svg+xml,'
    '%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2232%22%20height%3D%2232%22'
    '%20viewBox%3D%220%200%2032%2032%22%3E'
    '%3Crect%20width%3D%2232%22%20height%3D%2232%22%20rx%3D%228%22%20fill%3D%22%23002c5d%22%2F%3E'
    '%3Cg%20stroke%3D%22%23ffffff%22%20stroke-width%3D%221.9%22%20stroke-linecap%3D%22round%22'
    '%20stroke-linejoin%3D%22round%22%20fill%3D%22none%22%20transform%3D%22translate(6%2C6)%22%3E'
    '%3Cpath%20d%3D%22M4%202%20L10%2010%20L16%202%22%2F%3E'
    '%3Cline%20x1%3D%2210%22%20y1%3D%2210%22%20x2%3D%2210%22%20y2%3D%2218%22%2F%3E'
    '%3Ccircle%20cx%3D%2210%22%20cy%3D%2210%22%20r%3D%221.4%22%20fill%3D%22%23ffffff%22%20stroke%3D%22none%22%2F%3E'
    '%3C%2Fg%3E'
    '%3C%2Fsvg%3E'
)


# ── Brand text replacements ──────────────────────────────────────────
# Order matters: longer/more-specific patterns first to avoid partial matches.
BRAND_REPLACEMENTS = {
    # ── Fix already-patched Iktara strings ──
    'Iktara Observability Account': BRAND_ACCOUNT_NAME,
    'Iktara Observability': BRAND_NAME,
    'Iktara Monitoring Services': BRAND_NAME,
    'Iktara monitoring services': BRAND_NAME,
    '"Iktara"': f'"{BRAND_SHORT}"',
    "'Iktara'": f"'{BRAND_SHORT}'",
    'Iktara ': f'{BRAND_SHORT} ',
    'support@yantrai.ai': 'info@iktara.ai',
    'info@yantrai.ai': 'info@iktara.ai',
    'support@iktara.ai': 'info@iktara.ai',
    'static/assets/images/iktara-logo-wide.png': 'static/assets/images/glitchtip-logo-v1.svg',
    'static/assets/images/iktara-logo.png': 'static/assets/images/glitchtip-logo-collasped.svg',
    'href="static/assets/images/iktara-favicon.png"': 'href="favicon.ico"',

    # ── Color Branding (GlitchTip Red → YantrAI Navy) ──
    '#e94056': '#002c5d',
    '#E94056': '#002c5d',

    # ── Email / account templates ──
    'Verify Your GlitchTip Account Email': f'Verify Your {BRAND_ACCOUNT_NAME} Email',
    'Add Email to GlitchTip Account': f'Add Email to {BRAND_ACCOUNT_NAME}',
    'Password Reset For Your GlitchTip Account': f'Password Reset For Your {BRAND_ACCOUNT_NAME}',
    'GlitchTip Account': BRAND_ACCOUNT_NAME,
    'GlitchTip user account': f'{BRAND_NAME} user account',
    'on GlitchTip</title>': f'on {BRAND_NAME}</title>',

    # ── Invitations ──
    'You are invited to GlitchTip': f'You are invited to {BRAND_NAME}',
    'is using GlitchTip': f'is using {BRAND_NAME}',
    "Visit GlitchTip's homepage": f"Visit {BRAND_NAME}'s homepage",
    'Join the team on GlitchTip': f'Join the team on {BRAND_NAME}',

    # ── Alerts & Monitoring ──
    'GlitchTip Alerts': f'{BRAND_NAME} Alerts',
    'GlitchTip Test Notification': f'{BRAND_NAME} Test Notification',
    'GlitchTip Uptime Alert': f'{BRAND_NAME} Uptime Alert',
    'GlitchTip Alert': f'{BRAND_NAME} Alert',
    'View on GlitchTip': f'View on {BRAND_NAME}',
    'View at GlitchTip:': f'View at {BRAND_NAME}:',
    'GlitchTip: {{ object.monitor }}': f'{BRAND_NAME}: {{{{ object.monitor }}}}',

    # ── Compiled JS: subscription / billing text (chunk-DRWB3P6T) ──
    'subscription to GlitchTip': f'subscription to {BRAND_NAME}',
    'an account with GlitchTip': f'an account with {BRAND_NAME}',

    # ── Compiled JS: onboarding / help text ──
    'Connect your project to GlitchTip': f'Connect your project to {BRAND_NAME}',
    'connects your project to GlitchTip': f'connects your project to {BRAND_NAME}',
    'reported to GlitchTip': f'reported to {BRAND_NAME}',
    'get started with GlitchTip': f'get started with {BRAND_NAME}',
    'instance of GlitchTip': f'instance of {BRAND_NAME}',
    # Angular $localize interpolated variant (chunk-RCGJVQVN)
    'project to GlitchTip': f'project to {BRAND_NAME}',

    # ── Compiled JS: sidebar / nav ──
    'Support GlitchTip': f'Support {BRAND_NAME}',
    'Hosted GlitchTip': f'Hosted {BRAND_NAME}',

    # ── Compiled JS: settings / version ──
    'GlitchTip version': f'{BRAND_NAME} version',
    'GlitchTip instance name': f'{BRAND_NAME} instance name',

    # ── Compiled JS: misc UI labels ──
    "In order to use GlitchTip, you'll need to create an organization.": (
        f"In order to use {BRAND_NAME}, you'll need to create an organization."
    ),
    'New to GlitchTip?': f'New to {BRAND_NAME}?',
    'GlitchTip requires JavaScript': f'{BRAND_NAME} requires JavaScript',
    '<title>GlitchTip</title>': f'<title>{BRAND_NAME}</title>',
    'GlitchTip does not support session tracking.': f'{BRAND_NAME} does not support session tracking.',
    'GlitchTip installation and configuration docs': f'{BRAND_NAME} installation and configuration docs',
    'GlitchTip CLI': f'{BRAND_NAME} CLI',
    'GlitchTip, you need to:': f'{BRAND_NAME}, you need to:',
    "GlitchTip, you'll need to create an organization.": f"{BRAND_NAME}, you'll need to create an organization.",
    'Enable GlitchTip': f'Enable {BRAND_NAME}',
    'GlitchTip under project settings.': f'{BRAND_NAME} under project settings.',
    'GlitchTip will send': f'{BRAND_NAME} will send',
    'title="GlitchTip"': f'title="{BRAND_NAME}"',
    '<div>Powered by</div>': f'<div>{BRAND_NAME}</div>',
    'Crash reports powered by <a href="https://glitchtip.com">GlitchTip</a>': f'Crash reports by {BRAND_NAME}',

    # ── Compiled JS: alt text on logo images in sidebar/login/reset ──
    '"alt","GlitchTip"': f'"alt","{BRAND_SHORT}"',
    "'alt','GlitchTip'": f"'alt','{BRAND_SHORT}'",
    'alt="alt_text"': f'alt="{BRAND_SHORT}"',
    'alt width=': f'alt="{BRAND_SHORT}" width=',

    # ── Compiled JS: fallback document.title (main JS) ──
    'document.title="GlitchTip"': f'document.title="{BRAND_NAME}"',
    "document.title='GlitchTip'": f"document.title='{BRAND_NAME}'",

    # ── Compiled JS: external GlitchTip links (sidebar support CTA) ──
    'https://liberapay.com/GlitchTip/donate': '#',
    'https://app.glitchtip.com/register?utm_medium=website&utm_source=glitchtip&utm_campaign=selfhost_nagware': '#',
    'https://glitchtip.com': 'https://iktara.ai',
    'sales@glitchtip.com?subject=Purchase support inquiry': 'info@iktara.ai',
    'sales@glitchtip.com': 'info@iktara.ai',

    # ── Compiled JS: logo src paths → use Iktara PNGs ──
    # 'src","static/assets/images/glitchtip-logo-v1.svg"': 'src","static/assets/images/iktara-logo-wide.png"',
    # 'src","static/assets/images/glitchtip-logo-collasped.svg"': 'src","static/assets/images/iktara-logo.png"',

    # ── Misc UI text cleanup ──
    'Create New Organization': 'Create Organization',
    'Return to login': 'Return to sign in',

    # ── Inject display:none directly into Angular's scoped component CSS ──
    # This overrides the ViewEncapsulation by modifying the CSS rules in-place.
    '.support-cta-divider{border-color:var(--mat-sys-outline-variant)}':
        '.support-cta-divider{display:none!important;height:0;overflow:hidden}',
    '.support-cta-container{margin:15px 0 0 26px}':
        '.support-cta-container{display:none!important;height:0;overflow:hidden;margin:0}',

    # ── Catch-all: remaining "GlitchTip " with trailing space ──
    # This is intentionally last so it doesn't interfere with more-specific rules above.
    'GlitchTip ': f'{BRAND_NAME} ',
}

THEME_CSS = """
/* ═══════════════════════════════════════════════════════════════
   YantrAI — Design System v4 (Blue & White)
   Aligned to ds.css: clean white · navy #002c5d · blue #1d5fa8
   Fonts: Fraunces (display) · Geist (body) · JetBrains Mono
   ═══════════════════════════════════════════════════════════════ */

:root {
  --ik-bg:           #ffffff;
  --ik-bg-card:      #ffffff;
  --ik-bg-sunken:    #f8f9fb;
  --ik-navy:         #002c5d;
  --ik-navy-700:     #00407e;
  --ik-navy-100:     #e3eaf3;
  --ik-navy-50:      #f0f4f9;
  --ik-accent:       #1d5fa8;
  --ik-accent-soft:  rgba(29, 95, 168, 0.10);
  --ik-accent-hover: #164d8a;
  --ik-ink:          #14181f;
  --ik-ink-2:        #3a4250;
  --ik-ink-3:        #6b7585;
  --ik-ink-4:        #9da6b3;
  --ik-line:         #e3eaf3;
  --ik-line-2:       #d8dee9;
  --ik-ok:     #1f7a3a; --ik-ok-bg:   #e8f3ec;
  --ik-warn:   #a86a00; --ik-warn-bg: #f7eede;
  --ik-err:    #a82a1d; --ik-err-bg:  #f7e5e3;
  --ik-info:   #1d5fa8; --ik-info-bg: #e3edf7;
  --ik-shadow-1: 0 1px 2px rgba(0,0,0,0.05);
  --ik-shadow-2: 0 4px 12px rgba(0,0,0,0.05);
  --ik-shadow-3: 0 12px 32px rgba(0,0,0,0.08);
  --ik-r-sm: 4px; --ik-r-md: 6px; --ik-r-lg: 10px; --ik-r-xl: 14px;
  --ik-tr: 0.15s cubic-bezier(0.4,0,0.2,1);
  /* Keep Angular Material primary pointing to accent (Blue) for YantrAI style */
  --mat-sys-primary: var(--ik-accent) !important;
  --mat-sys-on-primary: #fff !important;
}

:root.dark {
  --ik-bg:           #101418;
  --ik-bg-card:      #181c22;
  --ik-bg-sunken:    #0c1014;
  --ik-navy:         #7da3d8;
  --ik-navy-700:     #2a4d7a;
  --ik-navy-100:     rgba(125,163,216,0.18);
  --ik-navy-50:      rgba(125,163,216,0.10);
  --ik-accent:       #6ea3d9;
  --ik-accent-soft:  rgba(110, 163, 217, 0.10);
  --ik-accent-hover: #4a6fa0;
  --ik-ink:          #e6e8ec;
  --ik-ink-2:        #b8bdc6;
  --ik-ink-3:        #8d94a0;
  --ik-ink-4:        #6a727e;
  --ik-line:         #232830;
  --ik-line-2:       #2f353f;
  --ik-ok:     #5ec787; --ik-ok-bg:   rgba(94,199,135,0.14);
  --ik-warn:   #d99a45; --ik-warn-bg: rgba(217,154,69,0.14);
  --ik-err:    #e87266; --ik-err-bg:  rgba(232,114,102,0.14);
  --ik-info:   #6ea3d9; --ik-info-bg: rgba(110,163,217,0.14);
  --ik-shadow-1: 0 1px 2px rgba(0,0,0,0.4);
  --ik-shadow-2: 0 1px 3px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.3);
  --ik-shadow-3: 0 2px 8px rgba(0,0,0,0.5), 0 16px 40px rgba(0,0,0,0.5);
}

/* ── Global typography: Geist body · Fraunces display · JetBrains Mono ── */
body, html, input, select, textarea, button,
.mat-mdc-card, .mat-mdc-table, mat-sidenav-content,
.mdc-list-item__primary-text, .mdc-button__label {
  font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4, .mat-mdc-dialog-title,
gt-top-app-bar h1, .l-body h1 {
  font-family: 'Fraunces', Georgia, serif !important;
  letter-spacing: -0.02em !important;
}
code, pre, [class*="mono"] {
  font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace !important;
}

/* ── Page background: white/dark ── */
.mat-sidenav-content, mat-sidenav-content {
  background: var(--ik-bg) !important;
  color: var(--ik-ink) !important;
}
body { background: var(--ik-bg) !important; color: var(--ik-ink) !important; }

/* ═══ SIDEBAR: light/dark matching --bg-sunken in ds.css ═══ */
mat-sidenav, .mat-drawer {
  background: var(--ik-bg-sunken) !important;
  border-right: 1px solid var(--ik-line) !important;
  box-shadow: none !important;
}
.logo-toolbar {
  background: var(--ik-bg-sunken) !important;
  padding: 18px 14px 14px !important;
  border-bottom: 1px solid var(--ik-line) !important;
}
.logo-toolbar .main-logo {
  max-height: 32px; width: auto; filter: none !important;
  transition: opacity var(--ik-tr);
  color: var(--ik-ink) !important;
}
/* Ensure logo elements use themed variables */
.logo-toolbar .main-logo rect { fill: var(--ik-navy) !important; }
.logo-toolbar .main-logo text { fill: var(--ik-ink) !important; }
.logo-toolbar .main-logo tspan { fill: var(--ik-navy) !important; }
.logo-toolbar .main-logo g[stroke] { stroke: #ffffff !important; }
.logo-toolbar .main-logo circle { fill: #ffffff !important; }

.logo-toolbar .main-logo:hover { opacity: 0.85; }
.logo-toolbar .collapsed-logo { max-height: 28px; width: auto; filter: none !important; }
.logo-toolbar .collapsed-logo rect { fill: var(--ik-navy) !important; }
.logo-toolbar .collapsed-logo g[stroke] { stroke: #ffffff !important; }
.logo-toolbar .collapsed-logo circle { fill: #ffffff !important; }

/* Nav items */
mat-sidenav .mdc-list-item__primary-text,
mat-sidenav .nav-text {
  color: var(--ik-ink-2) !important;
  font-family: 'Geist', sans-serif !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  transition: color var(--ik-tr);
}
mat-sidenav mat-icon {
  color: var(--ik-ink-3) !important;
  transition: color var(--ik-tr);
}
mat-sidenav mat-icon[matlistitemicon],
mat-sidenav mat-icon[matListItemIcon] {
  color: var(--ik-ink-4) !important;
  font-size: 19px !important;
}

/* Sidebar collapse responsiveness */
mat-sidenav.collapsed .nav-text,
mat-sidenav.collapsed .mdc-list-item__primary-text,
mat-sidenav.collapsed .logo-toolbar .main-logo {
  display: none !important;
}
mat-sidenav:not(.collapsed) .logo-toolbar .collapsed-logo {
  display: none !important;
}

/* Nav hover */
mat-sidenav mat-list-item:hover,
mat-sidenav button[mat-list-item]:hover {
  background: var(--ik-bg-card) !important;
  border-radius: var(--ik-r-md) !important;
  box-shadow: var(--ik-shadow-1) !important;
}

/* Active nav item */
.active-section {
  background: var(--ik-navy) !important;
  border-left: none !important;
  border-radius: var(--ik-r-md) !important;
  margin: 0 8px !important;
}
.active-section .mdc-list-item__primary-text,
.active-section .nav-text,
.active-section mat-icon {
  color: #ffffff !important;
  font-weight: 600 !important;
}
:root.dark .active-section .mdc-list-item__primary-text,
:root.dark .active-section .nav-text,
:root.dark .active-section mat-icon {
  color: #101418 !important;
}

.active-menu-item { background: var(--ik-navy-50) !important; }
.mdc-list-item--activated {
  background: var(--ik-navy) !important;
  border-radius: var(--ik-r-md) !important;
}
.mdc-list-item--activated .mdc-list-item__primary-text,
.mdc-list-item--activated mat-icon { color: #ffffff !important; }
:root.dark .mdc-list-item--activated .mdc-list-item__primary-text,
:root.dark .mdc-list-item--activated mat-icon { color: #101418 !important; }

/* Dividers */
mat-sidenav .nav-section-divider,
mat-sidenav hr { border-color: var(--ik-line) !important; margin: 10px 0 !important; }
mat-sidenav .collapse-toggle mat-icon { color: var(--ik-ink-4) !important; }
mat-sidenav .collapse-toggle:hover mat-icon { color: var(--ik-navy) !important; }
mat-sidenav .arrow-icon { color: var(--ik-ink-4) !important; }

/* Org dropdown */
.org-dropdown-container .mat-mdc-text-field-wrapper {
  background: var(--ik-bg-card) !important; border-radius: var(--ik-r-md) !important;
  border: 1px solid var(--ik-line) !important;
}
.org-dropdown-container .mat-mdc-select-value-text,
.org-dropdown-container .mdc-floating-label,
.org-dropdown-container .mat-mdc-select-arrow { color: var(--ik-ink-2) !important; }

/* Org create button */
.org-create-button {
  border-color: var(--ik-line) !important;
  color: var(--ik-ink-2) !important;
  background: var(--ik-bg-card) !important;
  border-radius: var(--ik-r-md) !important; font-weight: 500 !important;
  transition: all var(--ik-tr) !important;
}
.org-create-button:hover {
  background: var(--ik-bg-sunken) !important; border-color: var(--ik-line-strong) !important; color: var(--ik-ink) !important;
}

/* ═══ COMPLETELY HIDE Support CTA + Version ═══ */
.support-cta-container,
.support-cta-divider,
.support-cta-list {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
  max-height: 0 !important;
  opacity: 0 !important;
}
.version, .version a {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
  max-height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* ═══ TOP BAR ═══ */
gt-top-app-bar .mat-toolbar,
.mat-toolbar.mat-primary {
  background: var(--ik-bg-card) !important;
  color: var(--ik-ink) !important;
  border-bottom: 1px solid var(--ik-line) !important;
  box-shadow: none !important;
}
gt-top-app-bar h1, .l-body h1,
gt-top-app-bar .mat-toolbar h1 {
  font-size: 20px !important; font-weight: 400 !important;
  font-family: 'Fraunces', Georgia, serif !important;
  color: var(--ik-ink) !important; letter-spacing: -0.02em !important;
}

/* ═══ BUTTONS: navy primary · warm-outlined secondary ═══ */
.mat-mdc-raised-button.mat-primary,
.mat-mdc-unelevated-button.mat-primary,
button[color="primary"].mat-mdc-raised-button,
.mdc-button--raised.mat-primary {
  background-color: var(--ik-navy) !important;
  color: #fff !important;
  border-radius: var(--ik-r-md) !important;
  font-weight: 500 !important; text-transform: none !important; letter-spacing: 0 !important;
  box-shadow: var(--ik-shadow-1) !important;
  transition: all var(--ik-tr) !important;
}
:root.dark .mat-mdc-raised-button.mat-primary,
:root.dark .mat-mdc-unelevated-button.mat-primary,
:root.dark button[color="primary"].mat-mdc-raised-button,
:root.dark .mdc-button--raised.mat-primary {
  color: #101418 !important;
}
.mat-mdc-raised-button.mat-primary:hover,
.mat-mdc-unelevated-button.mat-primary:hover {
  background-color: var(--ik-navy-700) !important;
  box-shadow: var(--ik-shadow-2) !important;
}
.mat-mdc-outlined-button, .mdc-button--outlined {
  border-color: var(--ik-line-2) !important;
  color: var(--ik-ink-2) !important;
  border-radius: var(--ik-r-md) !important;
  font-weight: 500 !important; text-transform: none !important;
  background: var(--ik-bg-card) !important;
}
.mat-mdc-outlined-button:hover {
  background: var(--ik-bg-sunken) !important;
  border-color: #b8b0a0 !important;
  color: var(--ik-ink) !important;
}
.mat-mdc-icon-button { transition: background var(--ik-tr) !important; }
.mat-mdc-icon-button:hover { background: var(--ik-bg-sunken) !important; }

/* ═══ CARDS: warm card bg with warm border ═══ */
.mat-mdc-card, mat-card {
  background: var(--ik-bg-card) !important;
  border-radius: var(--ik-r-lg) !important;
  border: 1px solid var(--ik-line) !important;
  box-shadow: var(--ik-shadow-1) !important;
  transition: box-shadow var(--ik-tr), transform var(--ik-tr) !important;
  overflow: hidden !important;
}
.mat-mdc-card:hover, mat-card:hover {
  box-shadow: var(--ik-shadow-2) !important;
  transform: translateY(-1px) !important;
}

/* ═══ TABLES ═══ */
.mat-mdc-table {
  background: var(--ik-bg-card) !important;
  border-radius: var(--ik-r-lg) !important;
  overflow: hidden !important;
  border: 1px solid var(--ik-line) !important;
}
.mat-mdc-header-row, .mat-mdc-header-cell {
  background: var(--ik-bg-sunken) !important;
  font-weight: 500 !important; font-size: 11px !important;
  text-transform: uppercase !important; letter-spacing: 0.08em !important;
  color: var(--ik-ink-3) !important;
  border-bottom: 1px solid var(--ik-line) !important;
}
.mat-mdc-row { transition: background var(--ik-tr) !important; }
.mat-mdc-row:hover { background: var(--ik-navy-50) !important; }

/* Issue list rows */
.issue-list-item, [class*="issue-list"] {
  border-radius: 0 !important;
  border-left: 2px solid transparent !important;
  transition: all var(--ik-tr) !important;
}
.issue-list-item:hover, [class*="issue-list"]:hover {
  background: var(--ik-navy-50) !important;
  border-left-color: var(--ik-navy) !important;
}

/* ═══ FORM FIELDS ═══ */
.mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline__leading,
.mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline__notch,
.mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline__trailing {
  border-color: var(--ik-line) !important;
}
.mat-mdc-form-field.mat-focused .mdc-notched-outline__leading,
.mat-mdc-form-field.mat-focused .mdc-notched-outline__notch,
.mat-mdc-form-field.mat-focused .mdc-notched-outline__trailing {
  border-color: var(--ik-navy) !important;
}
.mat-mdc-form-field .mdc-floating-label--float-above {
  color: var(--ik-navy) !important;
}

/* ═══ CHIPS / BADGES ═══ */
.mat-mdc-chip {
  border-radius: 6px !important;
  font-weight: 500 !important;
  font-size: 12px !important;
}

/* ═══ TABS ═══ */
.mat-mdc-tab.mdc-tab--active .mdc-tab__text-label {
  color: var(--ik-accent) !important;
  font-weight: 600 !important;
}
.mat-mdc-tab-header .mdc-tab-indicator__content--underline {
  border-color: var(--ik-accent) !important;
}

/* ═══ PROGRESS / LOADING ═══ */
.mat-mdc-progress-bar .mdc-linear-progress__bar-inner {
  border-color: var(--ik-accent) !important;
}
.mat-mdc-progress-spinner circle {
  stroke: var(--ik-accent) !important;
}

/* ═══ CHECKBOX / RADIO / TOGGLE ═══ */
.mat-mdc-checkbox .mdc-checkbox__native-control:checked ~ .mdc-checkbox__background {
  background-color: var(--ik-accent) !important;
  border-color: var(--ik-accent) !important;
}
.mat-mdc-slide-toggle .mdc-switch--selected .mdc-switch__handle::after {
  background: var(--ik-accent) !important;
}
.mat-mdc-radio-button .mdc-radio__native-control:checked + .mdc-radio__background .mdc-radio__outer-circle {
  border-color: var(--ik-accent) !important;
}
.mat-mdc-radio-button .mdc-radio__native-control:checked + .mdc-radio__background .mdc-radio__inner-circle {
  background-color: var(--ik-accent) !important;
  border-color: var(--ik-accent) !important;
}

/* ═══ PAGINATOR ═══ */
.mat-mdc-paginator {
  background: transparent !important;
  border-top: 1px solid var(--ik-line) !important;
}

/* ═══ SNACKBAR / TOAST ═══ */
.mat-mdc-snack-bar-container .mdc-snackbar__surface {
  background: var(--ik-ink) !important;
  border-radius: var(--ik-r-md) !important;
  box-shadow: var(--ik-shadow-3) !important;
}

/* ═══ DIALOGS ═══ */
.mat-mdc-dialog-container .mdc-dialog__surface {
  border-radius: 14px !important;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15) !important;
}

/* ═══ SCROLLBAR (webkit) ═══ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(0,44,93,0.18);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(0,44,93,0.3); }
mat-sidenav ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); }
mat-sidenav ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }

/* ═══ LINKS ═══ */
a:not([class]) {
  color: var(--ik-navy) !important;
  text-decoration: none !important;
  transition: color var(--ik-tr) !important;
}
a:not([class]):hover { color: var(--ik-accent) !important; }

/* ═══ MOBILE NAV TOOLBAR ═══ */
gt-mobile-nav-toolbar .mat-toolbar {
  background: var(--ik-navy) !important;
  color: rgba(255,255,255,0.82) !important;
}

/* ═══ SELECTION / FOCUS RINGS ═══ */
*:focus-visible {
  outline: 2px solid var(--ik-accent) !important;
  outline-offset: 2px !important;
}

/* ═══ UPTIME MONITOR STATUS BARS ═══ */
[class*="monitor-check"].up, [style*="background-color: green"],
[style*="background: green"] {
  background-color: var(--ik-ok) !important;
  border-radius: 2px !important;
}
[class*="monitor-check"].down, [style*="background-color: red"],
[style*="background: red"] {
  background-color: var(--ik-err) !important;
  border-radius: 2px !important;
}

/* ═══ SETTINGS LINK COLOR ═══ */
a[routerlink*="settings"], a[href*="settings"] {
  color: var(--ik-accent) !important;
}

/* ═══ DROPDOWN / SELECT OVERLAY FIX ═══ */
.mat-mdc-select-panel,
.cdk-overlay-pane .mat-mdc-select-panel {
  background: var(--ik-bg-card) !important;
  border: 1px solid var(--ik-line) !important;
  border-radius: var(--ik-r-md) !important;
  box-shadow: var(--ik-shadow-3) !important;
}
.mat-mdc-option .mdc-list-item__primary-text {
  color: var(--ik-ink) !important; font-size: 13px !important; font-weight: 500 !important;
}
.mat-mdc-option:hover:not(.mdc-list-item--disabled),
.mat-mdc-option.mdc-list-item--selected { background: var(--ik-navy-50) !important; }
.mat-mdc-option.mdc-list-item--selected .mdc-list-item__primary-text {
  color: var(--ik-navy) !important; font-weight: 600 !important;
}

/* ═══ LOGIN / AUTH: blue gradient bg · white card · Fraunces heading ═══ */
.mat-sidenav-content:has(.auth-form-wrapper),
mat-sidenav-content:has(.auth-form-wrapper) {
  background: linear-gradient(140deg, #001a3a 0%, var(--ik-navy) 60%, #00407e 100%) !important;
}
:root.dark .mat-sidenav-content:has(.auth-form-wrapper),
:root.dark mat-sidenav-content:has(.auth-form-wrapper) {
  background: linear-gradient(140deg, #000000 0%, #0c1014 60%, #101418 100%) !important;
}
.auth-form-wrapper {
  display: flex !important; justify-content: center !important;
  align-items: center !important; min-height: 100vh !important; padding: 24px !important;
}
.auth-form {
  background: var(--ik-bg-card) !important;
  border-radius: var(--ik-r-xl) !important;
  padding: 40px 36px 32px !important;
  box-shadow: var(--ik-shadow-3) !important;
  max-width: 420px !important; width: 100% !important;
  border: 1px solid var(--ik-line) !important;
}
.auth-form .logo-container {
  text-align: center !important; margin-bottom: 28px !important;
}
.auth-form .logo-container img {
  background: var(--ik-navy) !important; padding: 10px 20px !important;
  border-radius: var(--ik-r-lg) !important; width: 180px !important; height: auto !important;
}
.auth-form h2 {
  font-family: 'Fraunces', Georgia, serif !important;
  font-size: 26px !important; font-weight: 400 !important; letter-spacing: -0.02em !important;
  color: var(--ik-navy) !important; text-align: center !important; margin-bottom: 24px !important;
}

/* Login form fields */
.auth-form .mat-mdc-form-field {
  width: 100% !important;
}

/* Login submit button */
.auth-form .mat-mdc-raised-button,
.auth-form .mat-mdc-unelevated-button {
  width: 100% !important;
  height: 48px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
  border-radius: 8px !important;
  margin-top: 8px !important;
}

/* Links below the form */
.auth-form a {
  color: var(--ik-accent) !important;
  font-weight: 600 !important;
}
.auth-form a { color: var(--ik-accent) !important; font-weight: 600 !important; }
.auth-form a:hover { color: var(--ik-accent-hover) !important; }
.auth-form .caption-text {
  color: var(--ik-ink-3) !important; font-family: 'JetBrains Mono', monospace !important;
  font-size: 11px !important; margin-top: 16px !important; text-align: center !important;
}

/* ═══ UPTIME MONITORS ═══ */
gt-monitor-list .mat-elevation-z2,
gt-monitor-list .mat-mdc-card,
gt-monitor-list .mat-card {
  background: var(--ik-bg-card) !important; border: 1px solid var(--ik-line) !important;
  border-radius: var(--ik-r-lg) !important; box-shadow: var(--ik-shadow-2) !important; overflow: hidden !important;
}
gt-monitor-list .mat-table,
gt-monitor-list .mat-mdc-table { background: var(--ik-bg-card) !important; border: none !important; }
gt-monitor-list .mat-header-row,
gt-monitor-list .mat-mdc-header-row {
  background: var(--ik-bg-sunken) !important; border-bottom: 1px solid var(--ik-line) !important;
}
gt-monitor-list .mat-header-cell,
gt-monitor-list .mat-mdc-header-cell {
  color: var(--ik-ink-3) !important; font-size: 11px !important; font-weight: 500 !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important; padding: 12px 16px !important;
}
gt-monitor-list .mat-row,
gt-monitor-list .mat-mdc-row {
  border-bottom: 1px solid var(--ik-line) !important; transition: background var(--ik-tr) !important;
}
gt-monitor-list .mat-row:hover,
gt-monitor-list .mat-mdc-row:hover { background: var(--ik-navy-50) !important; }
gt-monitor-list .mat-cell,
gt-monitor-list .mat-mdc-cell { color: var(--ik-ink) !important; font-size: 13px !important; padding: 12px 16px !important; }
gt-monitor-list .mat-cell a,
gt-monitor-list .mat-mdc-cell a {
  color: var(--ik-navy) !important; font-weight: 500 !important;
  text-decoration: none !important; transition: color var(--ik-tr) !important;
}
gt-monitor-list .mat-cell a:hover,
gt-monitor-list .mat-mdc-cell a:hover { color: var(--ik-accent) !important; }
gt-monitor-list .add-monitor-button,
gt-monitor-list button.add-monitor-button,
gt-monitor-list .mat-mdc-raised-button,
gt-monitor-list .mat-raised-button {
  background: var(--ik-navy) !important; color: #fff !important;
  border: 0 !important; border-radius: var(--ik-r-md) !important; font-weight: 500 !important;
  box-shadow: var(--ik-shadow-1) !important;
  transition: background var(--ik-tr), transform var(--ik-tr), box-shadow var(--ik-tr) !important;
}
gt-monitor-list .add-monitor-button:hover,
gt-monitor-list button.add-monitor-button:hover,
gt-monitor-list .mat-mdc-raised-button:hover,
gt-monitor-list .mat-raised-button:hover {
  background: var(--ik-navy-700) !important; transform: translateY(-1px) !important; box-shadow: var(--ik-shadow-2) !important;
}

/* ═══ EMBEDDED MODE OVERRIDES ═══ */
/* Keep gt-top-app-bar visible on all tabs to display page titles and action buttons */
html.is-embedded mat-sidenav,
html.is-embedded .mat-drawer {
  display: none !important;
  visibility: hidden !important;
  width: 0 !important;
  height: 0 !important;
  overflow: hidden !important;
}
html.is-embedded mat-sidenav-content,
html.is-embedded .mat-sidenav-content {
  margin-left: 0 !important;
  margin-right: 0 !important;
  padding-top: 0 !important;
}
html.is-embedded .l-body--flex {
  height: 100vh !important;
  padding-top: 0 !important;
}
"""


def resolve_asset(asset_name: str) -> Path | None:
    for root in IKTARA_ASSET_DIRS:
        candidate = root / asset_name
        if candidate.exists():
            return candidate
    return None


def replace_in_text(content: str) -> str:
    updated = content

    # ── Robust Logo Patching (Before other replacements) ──
    # Target <img> tags referencing logo.png (emails)
    updated = re.sub(
        r'<img[^>]+(?:src|style)="[^"]*(?:logo\.png|display:none)[^"]*"[^>]*>',
        (
            '<div style="font-family: \'Fraunces\', Georgia, serif; font-size: 28px; font-weight: 500; color: #14181f; letter-spacing: -0.01em; line-height: 1; text-decoration: none;">'
            'Yantr<em style="font-style: italic; color: #002c5d; font-weight: 500; text-decoration: none;">AI</em></div>'
        ),
        updated,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Target <object> tags referencing logo.png (status pages)
    updated = re.sub(
        r'<object[^>]+data="[^"]+logo\.png[^"]*"[^>]*>.*?</object>',
        (
            '<span style="font-family: \'Fraunces\', Georgia, serif; font-size: 22px; font-weight: 500; color: #14181f; letter-spacing: -0.01em; line-height: 1; text-decoration: none;">'
            'Yantr<em style="font-style: italic; color: #002c5d; font-weight: 500; text-decoration: none;">AI</em></span>'
        ),
        updated,
        flags=re.IGNORECASE | re.DOTALL
    )

    for source, target in BRAND_REPLACEMENTS.items():
        updated = updated.replace(source, target)
    # Fix double-static path bug
    updated = updated.replace('static/static/', 'static/')
    updated = re.sub(r'(?<!:)//static/', '/static/', updated)
    return updated


def patch_text_file(path: Path) -> bool:
    if not path.exists():
        return False

    try:
        original = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError, OSError):
        return False

    updated = replace_in_text(original)
    if updated == original:
        return False

    try:
        path.write_text(updated, encoding='utf-8')
        remove_precompressed_variants(path)
    except (PermissionError, OSError):
        return False
    return True


def patch_tree_files(root: Path, patterns):
    changed = 0
    if not root.exists():
        return changed

    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file():
                try:
                    if patch_text_file(path):
                        changed += 1
                except UnicodeDecodeError:
                    continue
    return changed


def patch_text_with_extra_replacements(path: Path, replacements: dict) -> bool:
    if not path.exists():
        return False
    try:
        original = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError, OSError):
        return False
    updated = replace_in_text(original)
    for source, target in replacements.items():
        updated = updated.replace(source, target)
    if updated == original:
        return False
    try:
        path.write_text(updated, encoding='utf-8')
        remove_precompressed_variants(path)
    except (PermissionError, OSError):
        return False
    return True


def copy_if_changed(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src_bytes = src.read_bytes()
        dst_bytes = dst.read_bytes() if dst.exists() else b''
        if src_bytes == dst_bytes:
            return False
        dst.write_bytes(src_bytes)
        return True
    except (PermissionError, OSError):
        return False


def remove_precompressed_variants(path: Path):
    # Clean up existing variants first
    for suffix in ['.br', '.gz']:
        compressed = Path(str(path) + suffix)
        if compressed.exists():
            try:
                compressed.unlink()
            except (PermissionError, OSError):
                pass

    # Only compress if it is a text-based static asset (JS, CSS, HTML, SVG, JSON)
    if path.suffix not in ['.js', '.css', '.html', '.svg', '.json']:
        return

    try:
        data = path.read_bytes()
        # Compress with Gzip
        gz_path = Path(str(path) + '.gz')
        with gzip.open(gz_path, 'wb', compresslevel=9) as f:
            f.write(data)

        # Compress with Brotli
        br_path = Path(str(path) + '.br')
        compressed_data = brotli.compress(data, mode=brotli.MODE_TEXT)
        br_path.write_bytes(compressed_data)
    except Exception as e:
        print(f"Failed to re-compress {path}: {e}")


def patch_dist_html():
    changed = False
    embed_script = (
        '<script nonce="{{ csp_nonce }}">'
        'try{if(window.self!==window.top){document.documentElement.classList.add("is-embedded");}}'
        'catch(e){document.documentElement.classList.add("is-embedded");}'
        '</script>'
    )
    # Use inline SVG data URI for favicon — no external file dependency
    html_replacements = {
        'type="image/x-icon" href="favicon.ico"': f'type="image/svg+xml" href="{FAVICON_SVG_DATA_URI}"',
        "type='image/x-icon' href='favicon.ico'": f"type='image/svg+xml' href='{FAVICON_SVG_DATA_URI}'",
        'rel="icon" href="favicon.ico"': f'rel="icon" type="image/svg+xml" href="{FAVICON_SVG_DATA_URI}"',
        "rel='icon' href='favicon.ico'": f"rel='icon' type='image/svg+xml' href='{FAVICON_SVG_DATA_URI}'",
    }
    async_font_links = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,300;1,9..144,400;1,9..144,500&family=Geist:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" media="print" onload="this.media=\'all\'">\n'
    )
    try:
        if patch_text_with_extra_replacements(DIST_INDEX_PATH, html_replacements):
            changed = True
        if DIST_INDEX_PATH.exists():
            original = DIST_INDEX_PATH.read_text(encoding='utf-8')
            updated = original
            if 'https://fonts.googleapis.com' not in updated and '</head>' in updated:
                updated = updated.replace('</head>', f'{async_font_links}</head>')
            if 'window.self !== window.top' not in updated and '</head>' in updated:
                updated = updated.replace('</head>', f'{embed_script}\n</head>')
            updated = re.sub(
                r'<style id="iktara-brand-theme" nonce="\{\{ csp_nonce \}\}">.*?</style>',
                f'<style id="iktara-brand-theme" nonce="{{{{ csp_nonce }}}}">{THEME_CSS}</style>',
                updated,
                flags=re.DOTALL,
            )
            if 'id="iktara-brand-theme"' not in updated and '</head>' in updated:
                style_block = f'<style id="iktara-brand-theme" nonce="{{{{ csp_nonce }}}}">{THEME_CSS}</style>\n</head>'
                updated = updated.replace('</head>', style_block)
            if updated != original:
                DIST_INDEX_PATH.write_text(updated, encoding='utf-8')
                changed = True
        static_indexes = list(Path('/code/static').glob('index*.html'))
        for static_index in static_indexes:
            if patch_text_with_extra_replacements(static_index, html_replacements):
                changed = True
            try:
                original = static_index.read_text(encoding='utf-8')
                updated = original
                if 'https://fonts.googleapis.com' not in updated and '</head>' in updated:
                    updated = updated.replace('</head>', f'{async_font_links}</head>')
                if 'window.self !== window.top' not in updated and '</head>' in updated:
                    updated = updated.replace('</head>', f'{embed_script}\n</head>')
                updated = re.sub(
                    r'<style id="iktara-brand-theme" nonce="\{\{ csp_nonce \}\}">.*?</style>',
                    f'<style id="iktara-brand-theme" nonce="{{{{ csp_nonce }}}}">{THEME_CSS}</style>',
                    updated,
                    flags=re.DOTALL,
                )
                if 'id="iktara-brand-theme"' not in updated and '</head>' in updated:
                    style_block = f'<style id="iktara-brand-theme" nonce="{{{{ csp_nonce }}}}">{THEME_CSS}</style>\n</head>'
                    updated = updated.replace('</head>', style_block)
                if updated != original:
                    static_index.write_text(updated, encoding='utf-8')
                    changed = True
            except (UnicodeDecodeError, PermissionError, OSError):
                pass
            remove_precompressed_variants(static_index)
        remove_precompressed_variants(DIST_INDEX_PATH)
        if changed:
            print('glitchtip index html patched')
        else:
            print('glitchtip index html unchanged or not writable')
    except Exception as exc:
        print(f'glitchtip index html patch skipped: {exc}')


def patch_email_templates():
    # Patch main templates and app templates (alerts, organizations, uptime)
    dirs = [
        EMAIL_TEMPLATE_DIR,
        Path('/code/templates'),
        Path('/code/apps/alerts/templates'),
        Path('/code/apps/organizations_ext/templates'),
        Path('/code/apps/uptime/templates'),
        Path('/code/apps/oauth/templates'),
    ]
    changed = 0
    for d in dirs:
        changed += patch_tree_files(d, ['*.html', '*.txt'])

    if changed:
        print(f'glitchtip email/app templates patched: {changed}')
    else:
        print('glitchtip email/app templates already patched')


def patch_fallback_pages():
    changed = False
    fallback_paths = [
        Path('/code/templates/404.html'),
    ]
    for path in fallback_paths:
        if patch_text_file(path):
            changed = True
    if changed:
        print('glitchtip fallback templates patched')
    else:
        print('glitchtip fallback templates already patched')


def write_logo_assets():
    changed = 0
    # Keep the svg targets for dist/static references that are wired in compiled JS chunks.
    targets = [
        (DIST_IMAGE_DIR / 'glitchtip-logo-v1.svg', PRIMARY_LOGO_SVG),
        (DIST_IMAGE_DIR / 'glitchtip-logo-collasped.svg', COLLAPSED_LOGO_SVG),
        (STATIC_IMAGE_DIR / 'glitchtip-logo-v1.svg', PRIMARY_LOGO_SVG),
        (STATIC_IMAGE_DIR / 'glitchtip-logo-collasped.svg', COLLAPSED_LOGO_SVG),
    ]

    for target, content in targets:
        if not target.parent.exists():
            continue
        try:
            previous = target.read_text(encoding='utf-8') if target.exists() else ''
            if previous != content:
                target.write_text(content, encoding='utf-8')
                changed += 1
            remove_precompressed_variants(target)
        except (PermissionError, OSError):
            continue

    # Hashed/static copies used by prebuilt assets.
    for folder in [DIST_IMAGE_DIR, STATIC_IMAGE_DIR]:
        for path in folder.glob('glitchtip-logo-v1*.svg'):
            try:
                if path.read_text(encoding='utf-8') != PRIMARY_LOGO_SVG:
                    path.write_text(PRIMARY_LOGO_SVG, encoding='utf-8')
                    changed += 1
                remove_precompressed_variants(path)
            except (PermissionError, OSError, UnicodeDecodeError):
                continue
        for path in folder.glob('glitchtip-logo-collasped*.svg'):
            try:
                if path.read_text(encoding='utf-8') != COLLAPSED_LOGO_SVG:
                    path.write_text(COLLAPSED_LOGO_SVG, encoding='utf-8')
                    changed += 1
                remove_precompressed_variants(path)
            except (PermissionError, OSError, UnicodeDecodeError):
                continue

    # Copy Iktara image assets if mounted; these are used for favicon and email artwork.
    iktara_wide_logo_path = resolve_asset('iktara-img.png')
    iktara_logo_path = resolve_asset('iktara-logo.png')
    iktara_favicon_path = resolve_asset('favicon.png')

    image_targets = [
        (iktara_wide_logo_path, DIST_IMAGE_DIR / 'iktara-logo-wide.png'),
        (iktara_wide_logo_path, STATIC_IMAGE_DIR / 'iktara-logo-wide.png'),
        (iktara_logo_path, DIST_IMAGE_DIR / 'iktara-logo.png'),
        (iktara_logo_path, STATIC_IMAGE_DIR / 'iktara-logo.png'),
        (iktara_favicon_path, DIST_IMAGE_DIR / 'iktara-favicon.png'),
        (iktara_favicon_path, STATIC_IMAGE_DIR / 'iktara-favicon.png'),
        (iktara_logo_path, STATIC_EMAIL_IMAGE_PATH),
        (iktara_favicon_path, DIST_FAVICON_PATH),
        (iktara_favicon_path, STATIC_FAVICON_PATH),
    ]
    for src, dst in image_targets:
        if src is not None and copy_if_changed(src, dst):
            changed += 1
        remove_precompressed_variants(dst)

    if changed:
        print(f'glitchtip logo assets patched: {changed}')
    else:
        print('glitchtip logo assets already patched')


def patch_runtime_ui_strings():
    # Keep this scoped to text-bearing runtime assets to avoid touching binary files.
    # Expand scope to cover /code/apps for backend logic that sends emails/webhooks.
    changed = 0
    changed += patch_tree_files(Path('/code/dist'), ['*.html', '*.js', '*.json', '*.md', '*.css'])
    changed += patch_tree_files(Path('/code/static'), ['*.js', '*.json', '*.md', '*.css'])
    changed += patch_tree_files(Path('/code/apps'), ['*.py', '*.html', '*.txt'])
    if changed:
        print(f'glitchtip runtime ui strings patched: {changed}')
    else:
        print('glitchtip runtime ui strings already patched')


def patch_frontend_csrf():
    import re
    changed = 0
    for root in [Path('/code/dist'), Path('/code/static')]:
        for js_file in root.glob('**/*.js'):
            try:
                content = js_file.read_text(encoding='utf-8')
                updated = re.sub(
                    r'([a-zA-Z0-9_$]+)\("csrftoken"\)',
                    r'(\1("glitchtip_csrftoken")||\1("csrftoken"))',
                    content
                )
                if updated != content:
                    js_file.write_text(updated, encoding='utf-8')
                    remove_precompressed_variants(js_file)
                    changed += 1
            except (PermissionError, OSError, UnicodeDecodeError):
                pass
    if changed:
        print(f'glitchtip frontend csrf patched in {changed} files')


def ensure_all_compressed():
    print("Ensuring all text static files are pre-compressed...")
    import gzip
    import brotli
    for folder in [Path('/code/dist'), Path('/code/static')]:
        if not folder.exists():
            continue
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix in ['.js', '.css', '.html', '.svg', '.json']:
                gz_path = Path(str(path) + '.gz')
                br_path = Path(str(path) + '.br')
                if not gz_path.exists() or not br_path.exists():
                    try:
                        data = path.read_bytes()
                        if not gz_path.exists():
                            with gzip.open(gz_path, 'wb', compresslevel=9) as f:
                                f.write(data)
                        if not br_path.exists():
                            compressed_data = brotli.compress(data, mode=brotli.MODE_TEXT)
                            br_path.write_bytes(compressed_data)
                    except Exception as e:
                        print(f"Failed to compress {path} in verify phase: {e}")


def patch_branding():
    try:
        patch_frontend_csrf()
        patch_dist_html()
        patch_email_templates()
        patch_fallback_pages()
        patch_runtime_ui_strings()
        write_logo_assets()
        ensure_all_compressed()
    except Exception as exc:
        # Never block container startup on branding patches.
        print(f'glitchtip branding patch skipped: {exc}')


def patch_schema():
    if not SCHEMA_PATH.exists():
        print('schema file not found, skipping')
        return

    text = SCHEMA_PATH.read_text(encoding='utf-8')
    updated = text

    if 'from glitchtip.schema import CamelSchema, to_camel' not in updated:
        updated = updated.replace(
            'from glitchtip.schema import CamelSchema',
            'from glitchtip.schema import CamelSchema, to_camel'
        )

    updated = updated.replace(
        '    model_config = ConfigDict(coerce_numbers_to_str=True)',
        """    model_config = ConfigDict(
        coerce_numbers_to_str=True,
        alias_generator=to_camel,
        populate_by_name=True,
        validate_by_alias=True,
        validate_by_name=True,
        from_attributes=True,
    )"""
    )

    updated = updated.replace('    is_owner: bool', '    isOwner: bool = False')
    updated = updated.replace('    def resolve_is_owner(obj):', '    def resolve_isOwner(obj):')

    if 'def resolve_isOwner(obj):' not in updated:
        marker = '        return False\n\n\nclass OrganizationUserDetailSchema'
        extra = (
            '        return False\n\n'
            '    @staticmethod\n'
            '    def resolve_isOwner(obj):\n'
            '        if owner := obj.organization.owner:\n'
            '            return owner.organization_user_id == obj.id\n'
            '        return False\n\n\nclass OrganizationUserDetailSchema'
        )
        if marker in updated:
            updated = updated.replace(marker, extra)

    if updated != text:
        SCHEMA_PATH.write_text(updated, encoding='utf-8')
        print('glitchtip schema patched')
    else:
        print('glitchtip schema already patched')


def patch_settings_cookie_names():
    if not SETTINGS_PATH.exists():
        print('settings file not found, skipping')
        return

    text = SETTINGS_PATH.read_text(encoding='utf-8')
    updated = text

    marker = 'SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", global_settings.SESSION_COOKIE_AGE)'
    desired = (
        'SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", global_settings.SESSION_COOKIE_AGE)\n'
        'SESSION_COOKIE_NAME = env.str("SESSION_COOKIE_NAME", global_settings.SESSION_COOKIE_NAME)\n'
        'CSRF_COOKIE_NAME = env.str("CSRF_COOKIE_NAME", global_settings.CSRF_COOKIE_NAME)'
    )

    if marker in updated and 'SESSION_COOKIE_NAME = env.str("SESSION_COOKIE_NAME"' not in updated:
        updated = updated.replace(marker, desired)

    if updated != text:
        SETTINGS_PATH.write_text(updated, encoding='utf-8')
        print('glitchtip settings cookie names patched')
    else:
        print('glitchtip settings cookie names already patched')


def patch_settings_iframe_embed():
    if not SETTINGS_PATH.exists():
        print('settings file not found, skipping')
        return

    text = SETTINGS_PATH.read_text(encoding='utf-8')
    updated = text

    # ── Force Branding Overrides ──
    # Ensure even if env vars are "Iktara", we use "YantrAI" in the code.
    branding_overrides = (
        f'\n# ── YantrAI Branding Overrides ──\n'
        f'GLITCHTIP_INSTANCE_NAME = "{BRAND_NAME} Observability"\n'
        f'ACCOUNT_EMAIL_SUBJECT_PREFIX = "{BRAND_SUBJECT_PREFIX} "\n'
    )
    if 'YantrAI Branding Overrides' not in updated:
        updated += branding_overrides

    middleware_marker = 'if "GRANIAN_STATIC_PATH_MOUNT" in os.environ:'
    middleware_block = (
        'if env.bool("GLITCHTIP_IFRAME_EMBED_ENABLED", False):\n'
        '    MIDDLEWARE = [\n'
        '        middleware\n'
        '        for middleware in MIDDLEWARE\n'
        '        if middleware != "django.middleware.clickjacking.XFrameOptionsMiddleware"\n'
        '    ]\n\n'
    )
    if middleware_marker in updated and 'GLITCHTIP_IFRAME_EMBED_ENABLED' not in updated:
        updated = updated.replace(middleware_marker, middleware_block + middleware_marker)

    csp_marker = 'if csp_report_only:'
    legacy_csp_block = (
        'iframe_ancestors = env.list("GLITCHTIP_IFRAME_ANCESTORS", str, [])\n'
        'if iframe_ancestors:\n'
        '    SECURE_CSP_DIRECTIVES["frame-ancestors"] = iframe_ancestors\n\n'
    )
    csp_block = (
        'iframe_ancestors = env.list("GLITCHTIP_IFRAME_ANCESTORS", str, [])\n'
        'if env.bool("GLITCHTIP_IFRAME_EMBED_ENABLED", False):\n'
        '    if iframe_ancestors:\n'
        '        SECURE_CSP_DIRECTIVES["frame-ancestors"] = [CSP.SELF] + iframe_ancestors\n'
        '    else:\n'
        '        SECURE_CSP_DIRECTIVES["frame-ancestors"] = [CSP.SELF]\n\n'
    )
    updated = updated.replace(legacy_csp_block, csp_block)
    if csp_marker in updated and 'GLITCHTIP_IFRAME_ANCESTORS' not in updated:
        updated = updated.replace(csp_marker, csp_block + csp_marker)

    # ── FIX: Angular Material Overlay CSP Block ──
    # GlitchTip unconditionally adds `[CSP.NONCE]` to `style-src`, which causes browsers to ignore
    # `'unsafe-inline'` and strictly block `style="..."` attributes. This breaks Angular Material overlays.
    style_src_marker = '"style-src": env.list("CSP_STYLE_SRC", str, [CSP.SELF]) + [CSP.NONCE],'
    style_src_fixed = '"style-src": env.list("CSP_STYLE_SRC", str, [CSP.SELF]),'
    if style_src_marker in updated:
        updated = updated.replace(style_src_marker, style_src_fixed)

    # ── FIX: CSP img-src to allow data: URIs (required for inline SVG favicon) ──
    img_src_marker = '"img-src": env.list("CSP_IMG_SRC", str, [CSP.SELF]),'
    img_src_fixed = '"img-src": env.list("CSP_IMG_SRC", str, [CSP.SELF, "data:"]),'
    if img_src_marker in updated:
        updated = updated.replace(img_src_marker, img_src_fixed)

    cookie_marker = 'SESSION_COOKIE_SAMESITE = env.str("SESSION_COOKIE_SAMESITE", "Lax")'
    cookie_block = (
        'SESSION_COOKIE_SAMESITE = env.str("SESSION_COOKIE_SAMESITE", "Lax")\n'
        'CSRF_COOKIE_SAMESITE = env.str("CSRF_COOKIE_SAMESITE", "Lax")\n'
        'CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", False)'
    )
    if cookie_marker in updated and 'CSRF_COOKIE_SAMESITE = env.str("CSRF_COOKIE_SAMESITE"' not in updated:
        updated = updated.replace(cookie_marker, cookie_block)

    csrf_marker = 'CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", str, [])'
    csrf_block = (
        'CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", str, [])\n'
        'iframe_csrf_origins = env.list("GLITCHTIP_IFRAME_CSRF_TRUSTED_ORIGINS", str, [])\n'
        'if iframe_csrf_origins:\n'
        '    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS + iframe_csrf_origins))'
    )
    if csrf_marker in updated and 'GLITCHTIP_IFRAME_CSRF_TRUSTED_ORIGINS' not in updated:
        updated = updated.replace(csrf_marker, csrf_block)

    if updated != text:
        SETTINGS_PATH.write_text(updated, encoding='utf-8')
        print('glitchtip iframe settings patched')
    else:
        print('glitchtip iframe settings already patched')


def load_runtime_map():
    path = Path('/tmp/glitchtip_runtime_map.yaml')
    if not path.exists():
        print(f"Runtime map not found at {path}, skipping database seed.")
        return {}

    services = {}
    current_service = None
    in_services = False

    try:
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith('#'):
                    continue

                raw_line = line.rstrip('\r\n')
                indent = len(raw_line) - len(raw_line.lstrip(' '))

                if indent == 0:
                    if line_str.startswith('services:'):
                        in_services = True
                    else:
                        in_services = False
                    continue

                if in_services:
                    if indent == 2 and line_str.endswith(':'):
                        current_service = line_str[:-1].strip()
                        services[current_service] = {}
                    elif indent == 4 and current_service and ':' in line_str:
                        k, v = line_str.split(':', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        services[current_service][k] = v
    except Exception as exc:
        print(f"Error parsing runtime map: {exc}")
        return {}

    return services


def seed_database():
    import os
    import time
    import sys
    if '/code' not in sys.path:
        sys.path.insert(0, '/code')
    from django.db import OperationalError, ProgrammingError
    from django.contrib.auth import get_user_model

    # Check if database is ready by attempting to query user model
    max_retries = 30
    retry_interval = 2
    db_ready = False
    
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "glitchtip.settings")
    import django
    django.setup()

    User = get_user_model()
    for attempt in range(max_retries):
        try:
            User.objects.filter(is_superuser=True).first()
            db_ready = True
            print("Database is ready and migrated.")
            break
        except (OperationalError, ProgrammingError, Exception) as e:
            print(f"Database not ready yet (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(retry_interval)

    if not db_ready:
        print("Database not ready after waiting, skipping database seed.")
        return

    services = load_runtime_map()
    if not services:
        return

    from apps.organizations_ext.models import Organization, OrganizationUser
    from apps.projects.models import Project, ProjectKey
    import uuid

    # 1. Create Organization
    org, _ = Organization.objects.get_or_create(slug="iktara", defaults={"name": "iktara"})

    # 2. Check/Create Superuser
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@iktara.ai")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "adminadmin")
        admin_user = User.objects.create_superuser(
            email=email,
            password=password
        )
        print(f"Created default superuser '{username}' ({email})")

    # 3. Associate admin with organization as owner
    OrganizationUser.objects.get_or_create(organization=org, user=admin_user, defaults={"role": 3})

    # Create cPlatform integration token
    from apps.api_tokens.models import APIToken
    token_str = "gt_whEhIEhw5qaoRPxS_bFIM279WeTZQD7zwsP0uyMOrXU8NeWC"
    api_token, token_created = APIToken.objects.get_or_create(
        token=token_str,
        defaults={
            "user": admin_user,
            "label": "cPlatform Integration Token",
        }
    )
    if token_created or not api_token.scopes:
        scopes_list = [
            "project:read", "project:write", "project:admin", "project:releases",
            "team:read", "team:write", "team:admin",
            "event:read", "event:write", "event:admin",
            "org:read", "org:write", "org:admin",
            "member:read", "member:write", "member:admin"
        ]
        api_token.add_permissions(scopes_list)
        print("Seeded API integration token")

    # 4. Seed all projects and keys
    for service_name, details in services.items():
        slug = details.get("project_slug")
        dsn = details.get("dsn")
        if not slug or not dsn:
            continue

        try:
            parts = dsn.split("@")
            pub_key_str = parts[0].split("//")[1]
            project_id = int(dsn.split("/")[-1])
            pub_key_uuid = uuid.UUID(pub_key_str)
        except Exception as e:
            print(f"Failed to parse DSN for {service_name}: {e}")
            continue

        project, proj_created = Project.objects.get_or_create(
            id=project_id,
            defaults={"name": slug, "slug": slug, "organization": org}
        )
        if not proj_created and project.slug != slug:
            project.slug = slug
            project.name = slug
            project.save()

        ProjectKey.objects.get_or_create(
            project=project,
            public_key=pub_key_uuid,
            defaults={"name": "Default"}
        )
        print(f"Seeded project {slug} with ID {project_id} and key {pub_key_uuid}")


def patch_uptime_checks_limit():
    api_path = Path('/code/apps/uptime/api.py')
    if not api_path.exists():
        print('apps/uptime/api.py not found, skipping')
        return

    text = api_path.read_text(encoding='utf-8')
    updated = text

    # Change limit: int = 60 to limit: int = 120 in attach_checks_to_monitors
    target_def = 'async def attach_checks_to_monitors(\n    monitors: list[Monitor], limit: int = 60\n)'
    replacement_def = 'async def attach_checks_to_monitors(\n    monitors: list[Monitor], limit: int = 120\n)'
    
    if target_def in updated:
        updated = updated.replace(target_def, replacement_def)
    else:
        # Fallback if whitespace or previous limit differs
        updated = re.sub(
            r'async def attach_checks_to_monitors\(\s*monitors:\s*list\[Monitor\],\s*limit:\s*int\s*=\s*\d+\s*\)',
            'async def attach_checks_to_monitors(\n    monitors: list[Monitor], limit: int = 120\n)',
            updated
        )

    if updated != text:
        api_path.write_text(updated, encoding='utf-8')
        print('glitchtip uptime checks limit patched to 120')
    else:
        print('glitchtip uptime checks limit already patched or not found')


if __name__ == '__main__':
    patch_schema()
    patch_settings_cookie_names()
    patch_settings_iframe_embed()
    patch_branding()
    patch_uptime_checks_limit()
    try:
        seed_database()
    except Exception as exc:
        print(f'glitchtip database seed failed: {exc}')
