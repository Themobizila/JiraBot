"""
Ativos visuais do painel web do JiraBot: tema (CSS), efeitos e menu retratil (JS), dashboard analitico (JS) e logotipo (SVG).

Estes blocos sao injetados no HTML_PAGE de web_panel.py por meio de marcadores, mantendo o arquivo principal enxuto
e permitindo que o atualizador (que copia apenas .py/.bat/.ico/.png) distribua o logotipo e o tema sem arquivos extras.
"""

from __future__ import annotations

# ----------------------------------------------------------------------------------------------------------------------
# LOGOTIPO: hexagono dourado (hextech), anel de cronometro com gema e a letra J.
# ----------------------------------------------------------------------------------------------------------------------
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="JiraBot">'
    '<defs>'
    '<linearGradient id="jbGold" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#f6e6b4"/><stop offset="0.45" stop-color="#c8aa6e"/><stop offset="1" stop-color="#7a5a26"/>'
    '</linearGradient>'
    '<linearGradient id="jbDark" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#241b0d"/><stop offset="1" stop-color="#0a0705"/>'
    '</linearGradient>'
    '</defs>'
    '<polygon points="32,3 58,18 58,46 32,61 6,46 6,18" fill="url(#jbDark)" stroke="url(#jbGold)" '
    'stroke-width="2.6" stroke-linejoin="round"/>'
    '<polygon points="32,8.5 53,20.5 53,43.5 32,55.5 11,43.5 11,20.5" fill="none" stroke="url(#jbGold)" '
    'stroke-opacity="0.35" stroke-width="1"/>'
    '<path d="M32 12.5 A19.5 19.5 0 1 1 14.6 22.2" fill="none" stroke="url(#jbGold)" stroke-width="2.4" '
    'stroke-linecap="round"/>'
    '<path d="M32 8.6 L35 12.5 L32 16.4 L29 12.5 Z" fill="url(#jbGold)"/>'
    '<path d="M25.5 21 H40 V24.5 H37 V38 C37 43 33.8 45.6 29.4 45.6 C26.8 45.6 24.8 44.8 23.2 43.1 '
    'L25.7 40.5 C26.6 41.5 27.8 42 29.3 42 C31.9 42 33.5 40.5 33.5 37.7 V24.5 H25.5 Z" fill="url(#jbGold)"/>'
    '</svg>'
)

# ----------------------------------------------------------------------------------------------------------------------
# JS EARLY: aplica estado dos efeitos e do menu antes da primeira pintura (evita "piscar" ao recarregar).
# ----------------------------------------------------------------------------------------------------------------------
EARLY_JS = r"""
(function () {
  try {
    var root = document.documentElement;
    var fx = localStorage.getItem('jirabot_fx_paused');
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (fx === '1' || (fx === null && reduced)) root.classList.add('fx-paused');
    if (localStorage.getItem('jirabot_sidebar_collapsed') === '1') root.classList.add('sidebar-collapsed');
  } catch (e) {}
})();
"""

# ----------------------------------------------------------------------------------------------------------------------
# CSS DO TEMA
# ----------------------------------------------------------------------------------------------------------------------
THEME_CSS = r"""
/* ==========================================================================================
   TEMA JIRABOT - Obsidiana e Ouro (escuro) / Pergaminho e Bronze (claro)
   Inspirado na identidade hextech da Riot (League of Legends) e na atmosfera de Elden Ring.
   ========================================================================================== */
:root {
  color-scheme: light;
  --font-display: "Cinzel", "Trajan Pro", "Palatino Linotype", "Book Antiqua", Georgia, serif;
  --font-body: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
  --ease: cubic-bezier(0.22, 0.8, 0.26, 1);
  --sidebar-w: 272px;
  --sidebar-w-collapsed: 78px;

  /* Pergaminho (claro) */
  --bg-body: #ece3cf;
  --bg-solid: #fbf6e9;
  --bg-card: #fbf6e9;
  --bg-subtle: #f3ead6;
  --bg-input: #fffdf5;
  --bg-input-readonly: #f1e8d3;
  --text-main: #1d1710;
  --text-secondary: #40362a;
  --text-muted: #6d604a;
  --border-color: #ddd0b0;
  --border-strong: #c2b088;
  --primary: #8a6820;
  --primary-hover: #6e5217;
  --primary-light: rgba(138, 104, 32, 0.13);
  --primary-text: #76571a;
  --on-primary: #fff8e4;
  --gold: #9a7424;
  --gold-bright: #b98f33;
  --gold-deep: #6e5217;
  --success: #1c7a58;
  --success-bg: rgba(28, 122, 88, 0.14);
  --warning: #b25d10;
  --warning-bg: rgba(178, 93, 16, 0.14);
  --danger: #b2202f;
  --danger-bg: rgba(178, 32, 47, 0.12);
  --info: #23756a;
  --info-bg: rgba(35, 117, 106, 0.13);
  --radius: 4px;
  --shadow: 0 1px 2px rgba(60, 40, 10, 0.1), 0 6px 18px rgba(60, 40, 10, 0.07);
  --topbar-bg: #fbf6e9;
  --glow-1: rgba(205, 165, 70, 0.2);
  --glow-2: rgba(160, 90, 40, 0.08);
  --vignette: rgba(90, 60, 20, 0.07);
  --spot: rgba(190, 145, 50, 0.14);
  --glow-card: rgba(160, 120, 40, 0.16);
  --ember-rgb: 150, 100, 25;
  --btn-primary-from: #bd9336;
  --btn-primary-to: #8a6820;
  --chart-1: #9a7424;
  --chart-2: #b2202f;
  --chart-3: #1c7a58;
  --chart-4: #6d604a;
  --chart-5: #b25d10;

  /* Barra lateral (escura nos dois temas, como o cliente da Riot) */
  --bg-sidebar: #0a0806;
  --bg-sidebar-hover: #1a150e;
  --nav-text: #c9bb9c;
  --nav-text-hover: #f6e8c6;
  --side-gold: #c8aa6e;
  --side-border: rgba(200, 170, 110, 0.2);
}

[data-theme="dark"] {
  color-scheme: dark;
  --bg-body: #0a0907;
  --bg-solid: #15110b;
  --bg-card: #15110b;
  --bg-subtle: #1d1810;
  --bg-input: #100d08;
  --bg-input-readonly: #1a150e;
  --text-main: #f0e6d2;
  --text-secondary: #d4c8ae;
  --text-muted: #a39880;
  --border-color: #2b2418;
  --border-strong: #4b3f26;
  --primary: #c8aa6e;
  --primary-hover: #dcc287;
  --primary-light: rgba(200, 170, 110, 0.14);
  --primary-text: #e3c882;
  --on-primary: #1a1408;
  --gold: #c8aa6e;
  --gold-bright: #f0d9a0;
  --gold-deep: #785a28;
  --success: #34b58c;
  --success-bg: rgba(52, 181, 140, 0.16);
  --warning: #e8913a;
  --warning-bg: rgba(232, 145, 58, 0.16);
  --danger: #ef4a5f;
  --danger-bg: rgba(239, 74, 95, 0.16);
  --info: #5fb7a8;
  --info-bg: rgba(95, 183, 168, 0.16);
  --shadow: 0 6px 22px rgba(0, 0, 0, 0.5);
  --topbar-bg: #0c0a07;
  --glow-1: rgba(200, 170, 110, 0.11);
  --glow-2: rgba(190, 70, 40, 0.08);
  --vignette: rgba(0, 0, 0, 0.45);
  --spot: rgba(214, 178, 100, 0.09);
  --glow-card: rgba(200, 170, 110, 0.1);
  --ember-rgb: 232, 190, 110;
  --btn-primary-from: #f0d9a0;
  --btn-primary-to: #c8aa6e;
  --chart-1: #c8aa6e;
  --chart-2: #e0556a;
  --chart-3: #3cb996;
  --chart-4: #b3a789;
  --chart-5: #e0903a;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  scrollbar-color: var(--border-strong) transparent;
}

body {
  font-family: var(--font-body);
  background-color: var(--bg-body);
  color: var(--text-main);
  display: flex;
  min-height: 100vh;
  overflow-x: hidden;
  position: relative;
  transition: background-color 0.3s ease, color 0.3s ease;
}

::selection {
  background: rgba(200, 170, 110, 0.35);
  color: inherit;
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 6px;
  border: 2px solid transparent;
  background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--gold);
  background-clip: content-box;
}

input[type="checkbox"],
input[type="radio"] {
  accent-color: var(--primary);
}

/* ------------------------------------------------------------------------------------------
   Atmosfera: brilhos de fundo, brasas (canvas) e spotlight que segue o mouse
   ------------------------------------------------------------------------------------------ */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(1200px 620px at 80% -12%, var(--glow-1), transparent 62%),
    radial-gradient(900px 520px at 6% 112%, var(--glow-2), transparent 62%),
    linear-gradient(180deg, transparent 55%, var(--vignette));
}

#fx-canvas {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

.fx-spot {
  position: fixed;
  top: 0;
  left: 0;
  width: 560px;
  height: 560px;
  margin-left: -280px;
  margin-top: -280px;
  border-radius: 50%;
  z-index: 0;
  pointer-events: none;
  background: radial-gradient(circle, var(--spot) 0%, transparent 68%);
  transform: translate3d(-9999px, -9999px, 0);
  will-change: transform;
  transition: opacity 0.4s ease;
}

html.fx-paused .fx-spot {
  opacity: 0;
}

/* ------------------------------------------------------------------------------------------
   Barra lateral retratil
   ------------------------------------------------------------------------------------------ */
.sidebar {
  width: var(--sidebar-w);
  background: linear-gradient(180deg, #0e0b07 0%, #080605 60%, #060504 100%);
  color: var(--nav-text-hover);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 100;
  border-right: 1px solid var(--side-border);
  overflow: hidden;
  transition: width 0.38s var(--ease), transform 0.38s var(--ease);
}

.sidebar::after {
  content: "";
  position: absolute;
  top: 0;
  right: -1px;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent, var(--side-gold) 30%, var(--side-gold) 70%, transparent);
  opacity: 0.55;
  pointer-events: none;
}

.brand {
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 13px;
  position: relative;
  min-height: 78px;
}

.brand::after {
  content: "";
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--side-gold), transparent);
  opacity: 0.5;
}

.brand-logo {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: block;
  filter: drop-shadow(0 0 8px rgba(200, 170, 110, 0.4));
  will-change: transform, opacity;
}

.brand-logo svg {
  width: 100%;
  height: 100%;
  display: block;
}

html:not(.fx-paused) .brand-logo {
  animation: fx-logo-glow 4.8s ease-in-out infinite;
}

.brand-text {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  max-width: 190px;
  transition: max-width 0.3s var(--ease), opacity 0.25s ease;
}

.brand-text h1 {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: linear-gradient(180deg, #fbefc9 0%, #c8aa6e 55%, #8f6d30 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: #c8aa6e;
}

.brand-text span {
  font-size: 10.5px;
  color: #8f8368;
  display: block;
  margin-top: 3px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-menu {
  padding: 16px 12px 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-bottom {
  padding: 4px 12px 10px;
  position: relative;
}

.nav-bottom::before {
  content: "";
  position: absolute;
  left: 16px;
  right: 16px;
  top: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--side-gold), transparent);
  opacity: 0.35;
}

.nav-bottom .nav-btn {
  margin-top: 10px;
}

.nav-btn {
  width: 100%;
  background: transparent;
  border: none;
  color: var(--nav-text);
  padding: 11px 14px;
  border-radius: 3px;
  text-align: left;
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  overflow: hidden;
  transition: background-color 0.25s ease, color 0.25s ease, padding 0.3s var(--ease);
}

.nav-btn::before {
  content: "";
  position: absolute;
  left: 0;
  top: 18%;
  bottom: 18%;
  width: 3px;
  background: linear-gradient(180deg, #f0d9a0, #c8aa6e 50%, #785a28);
  border-radius: 0 2px 2px 0;
  transform: scaleY(0);
  transition: transform 0.3s var(--ease);
  box-shadow: 0 0 10px rgba(200, 170, 110, 0.7);
}

.nav-btn svg {
  width: 19px;
  height: 19px;
  stroke: currentColor;
  flex-shrink: 0;
  transition: transform 0.3s var(--ease), filter 0.3s ease;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  max-width: 210px;
  transition: max-width 0.3s var(--ease), opacity 0.25s ease;
}

.nav-btn:hover {
  background-color: var(--bg-sidebar-hover);
  color: var(--nav-text-hover);
}

.nav-btn:hover svg {
  transform: scale(1.12);
  filter: drop-shadow(0 0 5px rgba(200, 170, 110, 0.6));
}

.nav-btn:hover::before {
  transform: scaleY(0.55);
}

.nav-btn.active {
  background: linear-gradient(90deg, rgba(200, 170, 110, 0.2), rgba(200, 170, 110, 0.03));
  color: #f6e8c6;
  font-weight: 600;
}

.nav-btn.active::before {
  transform: scaleY(1);
}

.nav-btn.active svg {
  color: #f0d9a0;
  filter: drop-shadow(0 0 6px rgba(200, 170, 110, 0.7));
}

.sidebar-footer {
  padding: 14px 18px;
  font-size: 12px;
  color: #8f8368;
  position: relative;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-footer::before {
  content: "";
  position: absolute;
  left: 16px;
  right: 16px;
  top: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--side-gold), transparent);
  opacity: 0.5;
}

.daemon-pill {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 5px;
  font-weight: 600;
  color: #e9dcc0;
}

.footer-text {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
  transition: max-width 0.3s var(--ease), opacity 0.25s ease;
}

.dot {
  width: 9px;
  height: 9px;
  flex-shrink: 0;
  border-radius: 50%;
  background-color: #ef4a5f;
  box-shadow: 0 0 6px rgba(239, 74, 95, 0.5);
}

.dot.online {
  background-color: #34d6a0;
  box-shadow: 0 0 9px rgba(52, 214, 160, 0.7);
}

html:not(.fx-paused) .dot.online {
  animation: fx-pulse 2.2s ease-in-out infinite;
}

/* Estado recolhido (somente icones) - apenas em telas largas */
@media (min-width: 901px) {
  html.sidebar-collapsed .sidebar {
    width: var(--sidebar-w-collapsed);
  }
  html.sidebar-collapsed .main-wrapper {
    margin-left: var(--sidebar-w-collapsed);
    width: calc(100% - var(--sidebar-w-collapsed));
    max-width: calc(100% - var(--sidebar-w-collapsed));
  }
  html.sidebar-collapsed .brand {
    padding-left: 18px;
  }
  html.sidebar-collapsed .brand-text,
  html.sidebar-collapsed .nav-label,
  html.sidebar-collapsed .footer-text {
    max-width: 0;
    opacity: 0;
  }
  html.sidebar-collapsed .nav-btn {
    gap: 0;
    padding-left: 29px;
    padding-right: 0;
  }
  html.sidebar-collapsed .daemon-pill {
    gap: 0;
  }
  html.sidebar-collapsed .sidebar-footer {
    padding-left: 33px;
  }
}

#sidebar-backdrop {
  display: none;
}

/* ------------------------------------------------------------------------------------------
   Conteudo principal e barra superior
   ------------------------------------------------------------------------------------------ */
.main-wrapper {
  margin-left: var(--sidebar-w);
  width: calc(100% - var(--sidebar-w));
  max-width: calc(100% - var(--sidebar-w));
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  z-index: 1;
  transition: margin-left 0.38s var(--ease), width 0.38s var(--ease), max-width 0.38s var(--ease);
}

.topbar {
  background: var(--topbar-bg);
  border-bottom: 1px solid var(--border-color);
  padding: 11px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 50;
  gap: 12px;
  flex-wrap: wrap;
}

.topbar::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold) 20%, var(--gold) 80%, transparent);
  opacity: 0.45;
  pointer-events: none;
}

.topbar::before {
  content: "";
  position: absolute;
  left: 0;
  bottom: -1px;
  height: 2px;
  width: 25%;
  background: linear-gradient(90deg, transparent, var(--gold-bright), transparent);
  opacity: 0;
  pointer-events: none;
  will-change: transform;
}

html:not(.fx-paused) .topbar::before {
  opacity: 0.9;
  animation: fx-sweep 7s linear infinite;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  flex-wrap: wrap;
}

.topbar-title {
  font-family: var(--font-display);
  font-size: 15.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--text-main);
}

[data-theme="dark"] .topbar-title {
  background: linear-gradient(180deg, #fbefc9, #c8aa6e);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* Hamburguer animado */
.hamburger {
  width: 42px;
  height: 40px;
  flex-shrink: 0;
  position: relative;
  background: transparent;
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  cursor: pointer;
  transition: border-color 0.25s ease, background-color 0.25s ease, box-shadow 0.25s ease;
}

.hamburger:hover {
  border-color: var(--gold);
  background: var(--primary-light);
  box-shadow: 0 0 14px var(--glow-card);
}

.hb-bar {
  position: absolute;
  left: 11px;
  height: 2px;
  background: var(--gold);
  border-radius: 2px;
  transition: transform 0.38s var(--ease), opacity 0.2s ease, width 0.3s var(--ease), top 0.38s var(--ease);
}

.hb-bar:nth-child(1) { top: 12px; width: 20px; }
.hb-bar:nth-child(2) { top: 19px; width: 14px; }
.hb-bar:nth-child(3) { top: 26px; width: 20px; }

.hamburger:hover .hb-bar:nth-child(2) { width: 20px; }

.hamburger.is-open .hb-bar:nth-child(1) { top: 19px; transform: rotate(45deg); }
.hamburger.is-open .hb-bar:nth-child(2) { opacity: 0; width: 0; }
.hamburger.is-open .hb-bar:nth-child(3) { top: 19px; transform: rotate(-45deg); }

/* Botao de pausar efeitos */
.fx-btn .fx-ico-play { display: none; }
html.fx-paused .fx-btn .fx-ico-pause { display: none; }
html.fx-paused .fx-btn .fx-ico-play { display: inline; }
html.fx-paused .fx-btn {
  border-color: var(--gold);
  color: var(--primary-text);
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 4px 10px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
  line-height: 1.2;
  flex-shrink: 0;
  border: 1px solid transparent;
}

.badge-running { background: var(--success-bg); color: var(--success); border-color: rgba(52, 181, 140, 0.35); }
.badge-paused { background: var(--warning-bg); color: var(--warning); border-color: rgba(232, 145, 58, 0.35); }
.badge-completed { background: var(--info-bg); color: var(--info); border-color: rgba(95, 183, 168, 0.35); }
.badge-idle { background: var(--bg-subtle); color: var(--text-muted); border-color: var(--border-strong); }
.badge-danger { background: var(--danger-bg); color: var(--danger); border-color: rgba(239, 74, 95, 0.35); }

.content {
  padding: 22px 24px 40px;
  width: 100%;
  max-width: 1560px;
}

.tab-pane {
  display: none;
}

.tab-pane.active {
  display: block;
}

html:not(.fx-paused) .tab-pane.active > *,
html:not(.fx-paused) .tab-pane.active .grid-4 > *,
html:not(.fx-paused) .tab-pane.active .grid-2 > *,
html:not(.fx-paused) .tab-pane.active .grid-kpi > * {
  animation: fx-rise 0.7s var(--ease) backwards;
}

html:not(.fx-paused) .tab-pane.active > *:nth-child(2) { animation-delay: 70ms; }
html:not(.fx-paused) .tab-pane.active > *:nth-child(3) { animation-delay: 140ms; }
html:not(.fx-paused) .tab-pane.active > *:nth-child(4) { animation-delay: 210ms; }
html:not(.fx-paused) .tab-pane.active > *:nth-child(5) { animation-delay: 280ms; }
html:not(.fx-paused) .tab-pane.active > *:nth-child(n+6) { animation-delay: 340ms; }
html:not(.fx-paused) .tab-pane.active .grid-4 > *:nth-child(2),
html:not(.fx-paused) .tab-pane.active .grid-kpi > *:nth-child(2),
html:not(.fx-paused) .tab-pane.active .grid-2 > *:nth-child(2) { animation-delay: 110ms; }
html:not(.fx-paused) .tab-pane.active .grid-4 > *:nth-child(3),
html:not(.fx-paused) .tab-pane.active .grid-kpi > *:nth-child(3) { animation-delay: 190ms; }
html:not(.fx-paused) .tab-pane.active .grid-4 > *:nth-child(4),
html:not(.fx-paused) .tab-pane.active .grid-kpi > *:nth-child(4) { animation-delay: 270ms; }
html:not(.fx-paused) .tab-pane.active .grid-kpi > *:nth-child(5) { animation-delay: 340ms; }
html:not(.fx-paused) .tab-pane.active .grid-kpi > *:nth-child(6) { animation-delay: 410ms; }

/* ------------------------------------------------------------------------------------------
   Grades, cartoes e estatisticas (paineis com cantos ornamentais)
   ------------------------------------------------------------------------------------------ */
.grid-4 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.grid-kpi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow);
  margin-bottom: 20px;
  position: relative;
  transition: border-color 0.35s ease, box-shadow 0.35s ease;
}

.card::before,
.card::after {
  content: "";
  position: absolute;
  width: 14px;
  height: 14px;
  border: 1px solid var(--gold);
  opacity: 0.75;
  pointer-events: none;
  transition: width 0.35s var(--ease), height 0.35s var(--ease), opacity 0.35s ease;
}

.card::before {
  top: -1px;
  left: -1px;
  border-right: none;
  border-bottom: none;
}

.card::after {
  bottom: -1px;
  right: -1px;
  border-left: none;
  border-top: none;
}

.card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow), 0 0 30px var(--glow-card);
}

.card:hover::before,
.card:hover::after {
  width: 28px;
  height: 28px;
  opacity: 1;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 10px;
  position: relative;
}

.card-header::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: -1px;
  width: 64px;
  height: 1px;
  background: var(--gold);
  box-shadow: 0 0 8px var(--gold);
}

.card-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px 18px;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
  transition: transform 0.35s var(--ease), border-color 0.35s ease, box-shadow 0.35s ease;
}

.stat-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  height: 2px;
  width: 100%;
  background: linear-gradient(90deg, var(--gold-bright), var(--gold) 40%, transparent);
  transform-origin: left;
  transform: scaleX(0.3);
  transition: transform 0.6s var(--ease);
}

.stat-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow), 0 0 28px var(--glow-card);
}

.stat-card:hover::before {
  transform: scaleX(1);
}

.stat-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  margin-bottom: 9px;
}

.stat-value {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--text-main);
}

.stat-sub {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}

.progress-bar-wrap {
  width: 100%;
  height: 7px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 10px;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--gold-deep), var(--gold) 55%, var(--gold-bright));
  transition: width 0.6s var(--ease);
  position: relative;
  box-shadow: 0 0 10px var(--glow-card);
}

.progress-bar-fill::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 30%, rgba(255, 255, 255, 0.45) 50%, transparent 70%);
  transform: translateX(-100%);
}

html:not(.fx-paused) .progress-bar-fill::after {
  animation: fx-shine 3.2s ease-in-out infinite;
}

/* ------------------------------------------------------------------------------------------
   Botoes
   ------------------------------------------------------------------------------------------ */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 15px;
  border-radius: 3px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: pointer;
  border: 1px solid transparent;
  transition: transform 0.2s ease, box-shadow 0.3s ease, border-color 0.25s ease, background-color 0.25s ease, color 0.25s ease, filter 0.25s ease;
  text-decoration: none;
  white-space: nowrap;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}

.btn::after {
  content: "";
  position: absolute;
  top: 0;
  left: -90%;
  width: 55%;
  height: 100%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  transform: skewX(-20deg);
  transition: left 0.65s var(--ease);
  pointer-events: none;
}

.btn:hover::after {
  left: 140%;
}

.btn:active {
  transform: translateY(1px);
}

.btn svg {
  width: 15px;
  height: 15px;
  stroke: currentColor;
  flex-shrink: 0;
}

.btn-primary {
  background: linear-gradient(180deg, var(--btn-primary-from), var(--btn-primary-to));
  color: var(--on-primary);
  border-color: var(--gold-deep);
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.18);
}
.btn-primary:hover {
  filter: brightness(1.08);
  box-shadow: 0 0 18px var(--glow-card), 0 0 0 1px var(--gold-bright);
}

.btn-success {
  background: linear-gradient(180deg, #2f9a76, #1f7a5b);
  color: #f4fff9;
  border-color: #16634a;
}
.btn-success:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 16px rgba(52, 181, 140, 0.3);
}

.btn-warning {
  background: linear-gradient(180deg, #d98a33, #b86a1c);
  color: #fff7ea;
  border-color: #955514;
}
.btn-warning:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 16px rgba(232, 145, 58, 0.3);
}

.btn-danger {
  background: linear-gradient(180deg, #d6384d, #a8212f);
  color: #fff2f3;
  border-color: #861a26;
}
.btn-danger:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 16px rgba(239, 74, 95, 0.3);
}

.btn-outline {
  background-color: transparent;
  border-color: var(--border-strong);
  color: var(--text-secondary);
}
.btn-outline:hover {
  background-color: var(--primary-light);
  border-color: var(--gold);
  color: var(--primary-text);
  box-shadow: 0 0 14px var(--glow-card);
}

.btn-sm {
  padding: 5px 11px;
  font-size: 12px;
}

.btn-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

td .btn-group {
  flex-wrap: nowrap;
  white-space: nowrap;
}

/* ------------------------------------------------------------------------------------------
   Formularios
   ------------------------------------------------------------------------------------------ */
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;
}

.form-group label {
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.form-control {
  padding: 8px 11px;
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  font-size: 13px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-input);
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.form-control:hover {
  border-color: var(--gold-deep);
}

.form-control:focus {
  outline: none;
  border-color: var(--gold);
  box-shadow: 0 0 0 3px rgba(200, 170, 110, 0.2), 0 0 14px var(--glow-card);
}

.form-control[readonly] {
  background: var(--bg-input-readonly);
}

textarea.form-control {
  resize: vertical;
  min-height: 68px;
}

/* ------------------------------------------------------------------------------------------
   Caixa de horarios, tabelas, pilulas
   ------------------------------------------------------------------------------------------ */
.schedule-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  padding: 16px;
  margin-bottom: 14px;
  position: relative;
}

.schedule-box::before {
  content: "";
  position: absolute;
  left: -1px;
  top: -1px;
  width: 3px;
  height: 100%;
  background: linear-gradient(180deg, var(--gold-bright), var(--gold-deep));
  opacity: 0.8;
}

.schedule-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

@media (max-width: 900px) {
  .schedule-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.schedule-summary-bar {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  background-color: var(--bg-subtle);
  color: var(--text-muted);
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-strong);
  white-space: nowrap;
}

td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

tr {
  transition: background-color 0.2s ease;
}

tr:hover td {
  background-color: var(--primary-light);
}

tr.row-today td {
  background-color: var(--primary-light);
  box-shadow: inset 0 0 0 9999px transparent;
}

tr.row-today td:first-child {
  box-shadow: inset 3px 0 0 var(--gold);
}

.ticket-pill {
  display: inline-block;
  padding: 3px 8px;
  background-color: var(--primary-light);
  color: var(--primary-text);
  border: 1px solid rgba(200, 170, 110, 0.35);
  border-radius: 2px;
  font-weight: 700;
  font-size: 12px;
  font-family: Consolas, monospace;
  letter-spacing: 0.03em;
  white-space: nowrap;
  flex-shrink: 0;
}

.time-pill {
  display: inline-block;
  padding: 2px 7px;
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-strong);
  border-radius: 2px;
  font-family: Consolas, monospace;
  font-size: 12px;
  color: var(--text-main);
  white-space: nowrap;
}

.bulk-bar {
  background: var(--primary-light);
  border: 1px solid var(--gold);
  border-radius: 3px;
  padding: 12px 16px;
  margin-bottom: 16px;
  display: none;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.bulk-bar.active {
  display: flex;
}

/* ------------------------------------------------------------------------------------------
   Modal, toast e utilitarios
   ------------------------------------------------------------------------------------------ */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(6, 4, 2, 0.85);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 20px;
}

.modal-backdrop.open {
  display: flex;
}

html:not(.fx-paused) .modal-backdrop.open {
  animation: fx-fade 0.25s ease backwards;
}

html:not(.fx-paused) .modal-backdrop.open .modal-dialog {
  animation: fx-pop 0.4s var(--ease) backwards;
}

.modal-dialog {
  background: var(--bg-solid);
  color: var(--text-main);
  border: 1px solid var(--gold-deep);
  border-radius: var(--radius);
  width: 100%;
  max-width: 700px;
  max-height: 92vh;
  overflow-y: auto;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6), 0 0 40px var(--glow-card);
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 16px 22px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-header h3 {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.modal-body {
  padding: 20px 22px;
}

.modal-footer {
  padding: 14px 22px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-subtle);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

#toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 300;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.toast {
  background: #120e08;
  color: #f4e8cc;
  padding: 12px 18px;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(200, 170, 110, 0.12);
  border: 1px solid rgba(200, 170, 110, 0.3);
  border-left: 4px solid var(--side-gold);
  min-width: 280px;
  max-width: 460px;
}

html:not(.fx-paused) .toast {
  animation: fx-toast 0.45s var(--ease) backwards;
}

.toast.success { border-left-color: #34d6a0; }
.toast.error { border-left-color: #ef4a5f; }

pre.terminal-box {
  background: #070503;
  color: #e6dcc4;
  border: 1px solid var(--border-strong);
  padding: 16px;
  border-radius: 3px;
  font-family: Consolas, monospace;
  font-size: 12px;
  overflow-x: auto;
  line-height: 1.5;
}

.weekday-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 0;
}

.weekday-checks label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  cursor: pointer;
}

/* ------------------------------------------------------------------------------------------
   Dashboard Analitico
   ------------------------------------------------------------------------------------------ */
.an-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.section-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.seg {
  display: inline-flex;
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  overflow: hidden;
}

.seg-btn {
  background: transparent;
  border: none;
  border-right: 1px solid var(--border-strong);
  color: var(--text-secondary);
  padding: 6px 13px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: background-color 0.25s ease, color 0.25s ease;
}

.seg-btn:last-child {
  border-right: none;
}

.seg-btn:hover {
  background: var(--primary-light);
  color: var(--primary-text);
}

.seg-btn.active {
  background: linear-gradient(180deg, var(--btn-primary-from), var(--btn-primary-to));
  color: var(--on-primary);
}

.an-loading,
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 44px 20px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 20px;
  text-align: center;
  flex-wrap: wrap;
}

.spinner {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--border-strong);
  border-top-color: var(--gold);
  animation: fx-spin 0.9s linear infinite;
  flex-shrink: 0;
}

html.fx-paused .spinner {
  animation-play-state: running !important;
}

.empty-mini {
  padding: 22px 8px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

/* Barras horizontais */
.hbar {
  margin-bottom: 14px;
}

.hbar:last-child {
  margin-bottom: 0;
}

.hbar-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12.5px;
  margin-bottom: 6px;
}

.hbar-name {
  font-weight: 700;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.hbar-val {
  color: var(--text-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.hbar-track {
  height: 10px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.hbar-fill {
  height: 100%;
  width: var(--w, 0%);
  background: linear-gradient(90deg, var(--gold-deep), var(--gold) 60%, var(--gold-bright));
  box-shadow: 0 0 10px var(--glow-card);
  transform-origin: left;
}

.hbar.alt .hbar-fill {
  background: linear-gradient(90deg, #7d2431, var(--chart-2));
}

html:not(.fx-paused) .hbar-fill {
  animation: fx-grow 0.9s var(--ease) backwards;
  animation-delay: calc(var(--i, 0) * 90ms + 150ms);
}

/* Rosca de descricao */
.donut-wrap {
  display: flex;
  align-items: center;
  gap: 26px;
  flex-wrap: wrap;
}

.donut {
  width: 170px;
  height: 170px;
  flex-shrink: 0;
  position: relative;
}

.donut svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.donut-track {
  fill: none;
  stroke: var(--bg-subtle);
  stroke-width: 4.2;
}

.donut-seg {
  fill: none;
  stroke-width: 4.2;
  stroke-linecap: butt;
}

html:not(.fx-paused) .donut-seg {
  animation: fx-donut 1.1s var(--ease) backwards;
}

.donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.donut-center strong {
  font-family: var(--font-display);
  font-size: 26px;
  color: var(--text-main);
}

.donut-center span {
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  margin-top: 2px;
}

.legend-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-width: 220px;
}

.legend-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
}

.legend-swatch {
  width: 12px;
  height: 12px;
  margin-top: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}

.legend-item strong {
  display: block;
  color: var(--text-main);
}

.legend-item small {
  color: var(--text-muted);
  font-size: 12px;
}

.mini-split {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-strong);
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.mini-split div {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 9px 10px;
  font-size: 12px;
  color: var(--text-muted);
}

.mini-split b {
  display: block;
  font-family: var(--font-display);
  font-size: 17px;
  color: var(--text-main);
  margin-bottom: 2px;
}

/* Top tickets */
.top-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 12.5px;
}

.top-row:last-child {
  border-bottom: none;
}

.top-sum {
  min-width: 0;
}

.top-sum .t-title {
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.top-sum .t-meta {
  color: var(--text-muted);
  font-size: 11.5px;
}

.top-time {
  font-family: var(--font-display);
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
}

/* Grafico de linhas */
.chart-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 11px;
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  background: transparent;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.25s ease, color 0.25s ease, border-color 0.25s ease, opacity 0.25s ease;
}

.chip.on {
  color: var(--text-main);
  border-color: var(--gold);
  background: var(--primary-light);
}

.chip:not(.on) {
  opacity: 0.6;
}

.chip-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.lc-wrap {
  position: relative;
  width: 100%;
}

.lc-svg {
  width: 100%;
  height: auto;
  display: block;
  overflow: visible;
}

.lc-grid {
  stroke: var(--border-color);
  stroke-width: 1;
  stroke-dasharray: 3 5;
}

.lc-axis-text {
  fill: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-body);
}

.lc-line {
  fill: none;
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 1;
  stroke-dashoffset: 0;
  filter: drop-shadow(0 0 4px var(--glow-card));
}

html:not(.fx-paused) .lc-line {
  animation: fx-draw 1.4s var(--ease) backwards;
}

.lc-area {
  opacity: 0.9;
}

html:not(.fx-paused) .lc-area {
  animation: fx-fade 1.6s ease backwards;
}

.lc-dot {
  stroke: var(--bg-solid);
  stroke-width: 1.5;
}

.lc-cursor {
  stroke: var(--gold);
  stroke-width: 1;
  stroke-dasharray: 3 3;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.lc-hover-dot {
  opacity: 0;
  pointer-events: none;
  stroke: var(--bg-solid);
  stroke-width: 2;
  transition: opacity 0.15s ease;
}

.s1 { --c: var(--chart-1); }
.s2 { --c: var(--chart-2); }
.s3 { --c: var(--chart-3); }
.s4 { --c: var(--chart-4); }
.s5 { --c: var(--chart-5); }
.lc-line.s1, .lc-line.s2, .lc-line.s3, .lc-line.s4, .lc-line.s5 { stroke: var(--c); }
.lc-dot.s1, .lc-dot.s2, .lc-dot.s3, .lc-dot.s4, .lc-dot.s5 { fill: var(--c); }
.lc-hover-dot.s1, .lc-hover-dot.s2, .lc-hover-dot.s3, .lc-hover-dot.s4, .lc-hover-dot.s5 { fill: var(--c); }
.chip-dot.s1, .chip-dot.s2, .chip-dot.s3, .chip-dot.s4, .chip-dot.s5 { background: var(--c); box-shadow: 0 0 8px var(--c); }

.lc-tip {
  position: absolute;
  top: 0;
  left: 0;
  transform: translate(-50%, 6px);
  background: #120e08;
  color: #f4e8cc;
  border: 1px solid rgba(200, 170, 110, 0.4);
  border-radius: 3px;
  padding: 8px 11px;
  font-size: 12px;
  line-height: 1.55;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
  white-space: nowrap;
  z-index: 5;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.5);
}

.lc-tip b {
  display: block;
  color: #e3c882;
  margin-bottom: 2px;
  font-family: var(--font-display);
  letter-spacing: 0.04em;
}

/* ------------------------------------------------------------------------------------------
   Animacoes (todas protegidas por html:not(.fx-paused) ou pausadas pelo botao de efeitos)
   ------------------------------------------------------------------------------------------ */
@keyframes fx-rise {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fx-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes fx-pop {
  from { opacity: 0; transform: translateY(14px) scale(0.97); }
  to { opacity: 1; transform: none; }
}

@keyframes fx-toast {
  from { opacity: 0; transform: translateX(32px); }
  to { opacity: 1; transform: none; }
}

@keyframes fx-grow {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

@keyframes fx-draw {
  from { stroke-dashoffset: 1; }
  to { stroke-dashoffset: 0; }
}

@keyframes fx-donut {
  from { stroke-dasharray: 0 100; }
}

@keyframes fx-sweep {
  from { transform: translate3d(-100%, 0, 0); }
  to { transform: translate3d(500%, 0, 0); }
}

@keyframes fx-shine {
  0% { transform: translateX(-100%); }
  55%, 100% { transform: translateX(100%); }
}

@keyframes fx-pulse {
  0%, 100% { box-shadow: 0 0 6px rgba(52, 214, 160, 0.5); }
  50% { box-shadow: 0 0 14px rgba(52, 214, 160, 0.95); }
}

@keyframes fx-logo-glow {
  0%, 100% { opacity: 0.88; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.025); }
}

@keyframes fx-spin {
  to { transform: rotate(360deg); }
}

/* Modo efeitos pausados: congela animacoes ambiente e remove transicoes de movimento */
html.fx-paused *,
html.fx-paused *::before,
html.fx-paused *::after {
  animation-play-state: paused !important;
  transition-duration: 0.01ms !important;
  transition-delay: 0s !important;
}

/* ------------------------------------------------------------------------------------------
   Responsivo: menu lateral vira gaveta em telas estreitas
   ------------------------------------------------------------------------------------------ */
@media (max-width: 900px) {
  .sidebar {
    transform: translateX(-104%);
    width: var(--sidebar-w);
    box-shadow: none;
  }
  html.sidebar-open .sidebar {
    transform: none;
    box-shadow: 0 0 60px rgba(0, 0, 0, 0.7);
  }
  .main-wrapper {
    margin-left: 0;
    width: 100%;
    max-width: 100%;
  }
  #sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 90;
    background: rgba(6, 4, 2, 0.7);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
  }
  html.sidebar-open #sidebar-backdrop {
    opacity: 1;
    pointer-events: auto;
  }
  .grid-2 {
    grid-template-columns: 1fr;
  }
  .content {
    padding: 16px 14px 32px;
  }
}
"""

# ----------------------------------------------------------------------------------------------------------------------
# JS DE EFEITOS, MENU RETRATIL E FONTE
# ----------------------------------------------------------------------------------------------------------------------
UI_FX_JS = r"""
/* ==================== EFEITOS VISUAIS (BRASAS, SPOTLIGHT) E BOTAO DE PAUSA ==================== */
function fxPaused() {
  return document.documentElement.classList.contains('fx-paused');
}

const Embers = (function () {
  let canvas = null;
  let ctx = null;
  let w = 0;
  let h = 0;
  let particles = [];
  let raf = 0;
  let running = false;
  let last = 0;
  let sprite = null;
  let cachedRgb = '';

  function makeSprite(rgb) {
    if (sprite && cachedRgb === rgb) return sprite;
    cachedRgb = rgb;
    const s = 48;
    const off = document.createElement('canvas');
    off.width = s;
    off.height = s;
    const octx = off.getContext('2d');
    const c = s / 2;
    const g = octx.createRadialGradient(c, c, 1, c, c, c);
    g.addColorStop(0, 'rgba(' + rgb + ',1)');
    g.addColorStop(0.22, 'rgba(' + rgb + ',0.75)');
    g.addColorStop(0.55, 'rgba(' + rgb + ',0.25)');
    g.addColorStop(1, 'rgba(' + rgb + ',0)');
    octx.fillStyle = g;
    octx.fillRect(0, 0, s, s);
    sprite = off;
    return sprite;
  }

  function spawn(initial) {
    return {
      x: Math.random() * w,
      y: initial ? Math.random() * h : h + 14,
      r: 0.7 + Math.random() * 1.8,
      vy: 12 + Math.random() * 30,
      vx: (Math.random() - 0.5) * 8,
      ph: Math.random() * Math.PI * 2,
      sw: 0.4 + Math.random() * 1.1,
      a: 0.35 + Math.random() * 0.55,
      tw: Math.random() * Math.PI * 2
    };
  }

  function resize() {
    if (!canvas) return;
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = w;
    canvas.height = h;
    const target = Math.max(22, Math.min(65, Math.floor((w * h) / 32000)));
    while (particles.length < target) particles.push(spawn(true));
    if (particles.length > target) particles.length = target;
    if (!running) draw(0);
  }

  function draw(dt) {
    if (!ctx) return;
    const rgb = (getComputedStyle(document.documentElement).getPropertyValue('--ember-rgb') || '232,190,110').trim();
    const dark = document.documentElement.getAttribute('data-theme') !== 'light';
    const spr = makeSprite(rgb);
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = dark ? 'lighter' : 'source-over';
    const mult = dark ? 1 : 0.65;
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      if (dt > 0) {
        p.ph += dt * p.sw;
        p.tw += dt * 2.6;
        p.y -= p.vy * dt;
        p.x += (p.vx + Math.sin(p.ph) * 14) * dt;
        if (p.y < -16 || p.x < -20 || p.x > w + 20) particles[i] = spawn(false);
      }
      const edge = Math.min(1, Math.max(0, p.y / (h * 0.25)), Math.max(0, (h - p.y) / (h * 0.12)) + 0.35);
      const alpha = p.a * (0.55 + 0.45 * Math.sin(p.tw)) * Math.min(1, edge) * mult;
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      const size = p.r * 6.5;
      ctx.drawImage(spr, p.x - size * 0.5, p.y - size * 0.5, size, size);
    }
  }

  function frame(ts) {
    if (!running) return;
    const dt = Math.min(0.05, (ts - last) / 1000);
    last = ts;
    draw(dt);
    raf = requestAnimationFrame(frame);
  }

  return {
    init: function () {
      canvas = document.getElementById('fx-canvas');
      if (!canvas) return;
      ctx = canvas.getContext('2d');
      resize();
      window.addEventListener('resize', resize);
    },
    start: function () {
      if (!ctx || running || document.hidden) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    },
    stop: function () {
      running = false;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    },
    redraw: function () {
      sprite = null;
      if (!running) draw(0);
    }
  };
})();

function updateFxButton() {
  const paused = fxPaused();
  const btn = document.getElementById('fx-toggle-btn');
  const lbl = document.getElementById('fx-toggle-label');
  if (lbl) lbl.textContent = paused ? 'Retomar Efeitos' : 'Pausar Efeitos';
  if (btn) {
    btn.setAttribute('aria-pressed', paused ? 'true' : 'false');
    btn.title = paused ? 'Retomar animações e efeitos visuais' : 'Pausar animações e efeitos visuais';
  }
}

function setFxPaused(paused, persist) {
  document.documentElement.classList.toggle('fx-paused', paused);
  if (persist) {
    try { localStorage.setItem('jirabot_fx_paused', paused ? '1' : '0'); } catch (e) {}
  }
  if (paused) Embers.stop(); else Embers.start();
  updateFxButton();
}

function toggleFx() {
  const next = !fxPaused();
  setFxPaused(next, true);
  showToast(next ? 'Animações e efeitos pausados.' : 'Animações e efeitos retomados.', 'info');
}

/* ==================== MENU LATERAL RETRATIL (HAMBURGUER ANIMADO) ==================== */
function isMobileNav() {
  return window.matchMedia('(max-width: 900px)').matches;
}

function syncHamburger() {
  const root = document.documentElement;
  const open = isMobileNav() ? root.classList.contains('sidebar-open') : !root.classList.contains('sidebar-collapsed');
  const btn = document.getElementById('hamburger-btn');
  if (btn) {
    btn.classList.toggle('is-open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
}

function toggleSidebar() {
  const root = document.documentElement;
  if (isMobileNav()) {
    root.classList.toggle('sidebar-open');
  } else {
    const collapsed = root.classList.toggle('sidebar-collapsed');
    try { localStorage.setItem('jirabot_sidebar_collapsed', collapsed ? '1' : '0'); } catch (e) {}
  }
  syncHamburger();
}

function closeMobileSidebar() {
  document.documentElement.classList.remove('sidebar-open');
  syncHamburger();
}

/* ==================== INICIALIZACAO DA INTERFACE ==================== */
(function initUiFx() {
  function boot() {
    // Fonte de exibicao carregada de forma assincrona para nao bloquear a pintura (fallback serifado local)
    try {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&display=swap';
      document.head.appendChild(link);
    } catch (e) {}

    Embers.init();
    if (!fxPaused()) Embers.start();
    updateFxButton();
    syncHamburger();

    const spotEl = document.querySelector('.fx-spot');
    let spotX = 0, spotY = 0, spotTick = false;
    window.addEventListener('mousemove', function (ev) {
      spotX = ev.clientX;
      spotY = ev.clientY;
      if (spotTick || fxPaused()) return;
      spotTick = true;
      requestAnimationFrame(function () {
        if (spotEl) {
          spotEl.style.transform = 'translate3d(' + spotX + 'px,' + spotY + 'px,0)';
        }
        spotTick = false;
      });
    }, { passive: true });

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) Embers.stop(); else if (!fxPaused()) Embers.start();
    });

    window.addEventListener('resize', function () {
      if (!isMobileNav()) document.documentElement.classList.remove('sidebar-open');
      syncHamburger();
    });

    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closeMobileSidebar();
    });

    // Recolore as brasas ao trocar de tema
    const obs = new MutationObserver(function () { Embers.redraw(); });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
"""

# ----------------------------------------------------------------------------------------------------------------------
# JS DO DASHBOARD ANALITICO
# ----------------------------------------------------------------------------------------------------------------------
ANALYTICS_JS = r"""
/* ==================== DASHBOARD ANALITICO ==================== */
let analyticsDays = 30;
let analyticsData = null;
let analyticsLoading = false;
let analyticsGran = 'day';
const analyticsSeriesOn = { tickets: true, completed: true, cumulative: false, hours: false };
const SERIES_DEFS = {
  tickets: { label: 'Tickets trabalhados', cls: 's1', axis: 'count' },
  completed: { label: 'Tickets finalizados', cls: 's3', axis: 'count' },
  cumulative: { label: 'Finalizados acumulados', cls: 's2', axis: 'count' },
  hours: { label: 'Horas lançadas', cls: 's5', axis: 'hours' }
};

function anFmtNumber(value, decimals) {
  return Number(value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: decimals });
}

function anFmtDate(iso) {
  if (!iso || iso.length < 10) return '-';
  return iso.slice(8, 10) + '/' + iso.slice(5, 7) + '/' + iso.slice(0, 4);
}

function anAnimateNumber(el, target, decimals) {
  if (!el) return;
  const final = Number(target || 0);
  if (fxPaused() || final === 0) {
    el.textContent = anFmtNumber(final, decimals);
    return;
  }
  const t0 = performance.now();
  const dur = 900;
  function step(now) {
    const k = Math.min(1, (now - t0) / dur);
    const eased = 1 - Math.pow(1 - k, 3);
    el.textContent = anFmtNumber(final * eased, decimals);
    if (k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function setAnalyticsPeriod(days) {
  analyticsDays = days;
  loadAnalytics(false);
}

function updatePeriodButtons() {
  document.querySelectorAll('.seg-btn[data-days]').forEach(b => {
    b.classList.toggle('active', Number(b.dataset.days) === analyticsDays);
  });
}

async function loadAnalytics(force) {
  if (analyticsLoading) return;
  analyticsLoading = true;
  updatePeriodButtons();
  const stateEl = document.getElementById('an-state');
  const contentEl = document.getElementById('an-content');
  stateEl.style.display = '';
  stateEl.innerHTML = '<div class="an-loading"><span class="spinner"></span><span>Consultando o Jira e consolidando seus lançamentos...</span></div>';
  try {
    const data = await apiCall('/api/analytics?days=' + analyticsDays + (force ? '&refresh=1' : ''));
    analyticsData = data;
    if (!data.available) {
      contentEl.style.display = 'none';
      stateEl.innerHTML = '<div class="empty-state"><span>' + escapeHtml(data.message || 'Dados indisponíveis no momento.') + '</span>'
        + '<button class="btn btn-outline btn-sm" onclick="switchTab(\'tab-settings\')">Abrir Configurações</button></div>';
      return;
    }
    stateEl.style.display = 'none';
    stateEl.innerHTML = '';
    contentEl.style.display = '';
    renderAnalytics(data);
  } catch (err) {
    contentEl.style.display = 'none';
    stateEl.innerHTML = '<div class="empty-state"><span>Não foi possível carregar o dashboard: ' + escapeHtml(err.message) + '</span>'
      + '<button class="btn btn-outline btn-sm" onclick="loadAnalytics(true)">Tentar novamente</button></div>';
  } finally {
    analyticsLoading = false;
  }
}

function renderAnalytics(d) {
  const t = d.totals;
  const c = d.completion;
  const tp = d.time_per_ticket;

  document.getElementById('an-subtitle').textContent =
    'Período de ' + anFmtDate(d.start_date) + ' a ' + anFmtDate(d.end_date)
    + ' - dados reais do Jira (atualizado em ' + (d.generated_at || '-') + ')';

  document.getElementById('an-kpi-hours').textContent = t.formatted;
  document.getElementById('an-kpi-hours-sub').textContent =
    t.worklogs + ' lançamento(s) em ' + t.days_with_logs + ' dia(s) com registro';
  anAnimateNumber(document.getElementById('an-kpi-tickets'), t.tickets, 0);
  document.getElementById('an-kpi-tickets-sub').textContent = 'Tickets distintos com horas suas no período';
  anAnimateNumber(document.getElementById('an-kpi-done'), c.total, 0);
  document.getElementById('an-kpi-done-sub').textContent = 'Concluídos no Jira por você (status de categoria Concluído)';
  anAnimateNumber(document.getElementById('an-kpi-done-avg'), c.avg_per_week, 2);
  document.getElementById('an-kpi-done-avg-sub').textContent =
    'Por semana (' + anFmtNumber(c.avg_per_month, 1) + ' por mês)';
  document.getElementById('an-kpi-avg').textContent = tp.avg_formatted;
  document.getElementById('an-kpi-avg-sub').textContent = 'Mediana: ' + tp.median_formatted + ' por ticket';
  document.getElementById('an-kpi-avg-done').textContent = c.total ? tp.avg_completed_formatted : '-';
  document.getElementById('an-kpi-avg-done-sub').textContent =
    c.total ? 'Tempo seu lançado nos tickets finalizados' : 'Nenhum ticket finalizado por você no período';

  renderTypeBars('an-bars-time', d.by_type_time, 'seconds', r => r.formatted + ' (' + anFmtNumber(r.percent_time, 1) + '%)', false);
  renderTypeBars('an-bars-count', d.by_type_count, 'worklogs', r => r.worklogs + ' lançamento(s) (' + anFmtNumber(r.percent_worklogs, 1) + '%)', true);
  renderDescriptionDonut(d.description);
  renderTopTickets(d.top_tickets);
  renderEvolutionControls();
  renderEvolutionChart();
}

function renderTypeBars(containerId, rows, valueKey, labelFn, alt) {
  const el = document.getElementById(containerId);
  if (!rows || !rows.length) {
    el.innerHTML = '<div class="empty-mini">Sem lançamentos no período selecionado.</div>';
    return;
  }
  const max = Math.max.apply(null, rows.map(r => r[valueKey])) || 1;
  el.innerHTML = rows.slice(0, 8).map((r, i) =>
    '<div class="hbar' + (alt ? ' alt' : '') + '" style="--i:' + i + '">'
    + '<div class="hbar-head"><span class="hbar-name" title="' + escapeHtml(r.type) + '">' + escapeHtml(r.type) + '</span>'
    + '<span class="hbar-val">' + labelFn(r) + '</span></div>'
    + '<div class="hbar-track"><div class="hbar-fill" style="--w:' + ((r[valueKey] / max) * 100).toFixed(1) + '%"></div></div>'
    + '</div>'
  ).join('');
}

function renderDescriptionDonut(desc) {
  const el = document.getElementById('an-desc');
  if (!desc || !desc.worklogs_total) {
    el.innerHTML = '<div class="empty-mini">Sem lançamentos no período selecionado.</div>';
    return;
  }
  const withPct = desc.worklogs_with_pct;
  const withoutPct = desc.worklogs_without_pct;
  el.innerHTML =
    '<div class="donut-wrap">'
    + '<div class="donut"><svg viewBox="0 0 42 42">'
    + '<circle class="donut-track" cx="21" cy="21" r="15.9155"></circle>'
    + '<circle class="donut-seg" cx="21" cy="21" r="15.9155" stroke="var(--chart-1)" stroke-dasharray="' + withPct + ' ' + (100 - withPct) + '" stroke-dashoffset="0"></circle>'
    + '<circle class="donut-seg" cx="21" cy="21" r="15.9155" stroke="var(--chart-2)" stroke-dasharray="' + withoutPct + ' ' + (100 - withoutPct) + '" stroke-dashoffset="-' + withPct + '"></circle>'
    + '</svg><div class="donut-center"><strong>' + anFmtNumber(withPct, 1) + '%</strong><span>com descrição</span></div></div>'
    + '<div class="legend-list">'
    + '<div class="legend-item"><span class="legend-swatch" style="background:var(--chart-1)"></span><div><strong>Com descrição: ' + desc.worklogs_with + ' lançamento(s)</strong><small>' + anFmtNumber(withPct, 1) + '% do total de ' + desc.worklogs_total + '</small></div></div>'
    + '<div class="legend-item"><span class="legend-swatch" style="background:var(--chart-2)"></span><div><strong>Sem descrição: ' + desc.worklogs_without + ' lançamento(s)</strong><small>' + anFmtNumber(withoutPct, 1) + '% do total de ' + desc.worklogs_total + '</small></div></div>'
    + '</div></div>'
    + '<div class="mini-split">'
    + '<div><b>' + desc.tickets_with + '</b>Tickets totalmente descritos (' + anFmtNumber(desc.tickets_with_pct, 1) + '%)</div>'
    + '<div><b>' + desc.tickets_partial + '</b>Parcialmente descritos (' + anFmtNumber(desc.tickets_partial_pct, 1) + '%)</div>'
    + '<div><b>' + desc.tickets_without + '</b>Sem nenhuma descrição (' + anFmtNumber(desc.tickets_without_pct, 1) + '%)</div>'
    + '</div>';
}

function renderTopTickets(rows) {
  const el = document.getElementById('an-top');
  if (!rows || !rows.length) {
    el.innerHTML = '<div class="empty-mini">Sem lançamentos no período selecionado.</div>';
    return;
  }
  el.innerHTML = rows.map(r =>
    '<div class="top-row">'
    + '<span class="ticket-pill">' + escapeHtml(r.key) + '</span>'
    + '<div class="top-sum"><span class="t-title" title="' + escapeHtml(r.summary) + '">' + escapeHtml(r.summary || 'Sem resumo') + '</span>'
    + '<span class="t-meta">' + escapeHtml(r.type) + ' - ' + r.worklogs + ' lançamento(s)' + (r.completed ? ' - finalizado por você' : '') + '</span></div>'
    + '<span class="top-time">' + r.formatted + '</span>'
    + '</div>'
  ).join('');
}

function renderEvolutionControls() {
  const chips = document.getElementById('an-chips');
  chips.innerHTML = Object.keys(SERIES_DEFS).map(k =>
    '<button class="chip' + (analyticsSeriesOn[k] ? ' on' : '') + '" onclick="toggleSeries(\'' + k + '\')">'
    + '<i class="chip-dot ' + SERIES_DEFS[k].cls + '"></i>' + SERIES_DEFS[k].label + '</button>'
  ).join('');
  document.querySelectorAll('.seg-btn[data-gran]').forEach(b => {
    b.classList.toggle('active', b.dataset.gran === analyticsGran);
  });
}

function toggleSeries(key) {
  const onCount = Object.keys(analyticsSeriesOn).filter(k => analyticsSeriesOn[k]).length;
  if (analyticsSeriesOn[key] && onCount === 1) return;
  analyticsSeriesOn[key] = !analyticsSeriesOn[key];
  renderEvolutionControls();
  renderEvolutionChart();
}

function setAnalyticsGranularity(g) {
  analyticsGran = g;
  renderEvolutionControls();
  renderEvolutionChart();
}

function isoLocal(d) {
  const p = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}

function evolutionRows() {
  const base = (analyticsData && analyticsData.evolution) || [];
  if (analyticsGran !== 'week') {
    return base.map(r => ({
      label: r.date.slice(8, 10) + '/' + r.date.slice(5, 7),
      full: anFmtDate(r.date),
      tickets: r.tickets,
      completed: r.completed,
      cumulative: r.completed_cumulative,
      hours: r.hours
    }));
  }
  const weeks = new Map();
  base.forEach(r => {
    const d = new Date(r.date + 'T00:00:00');
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const key = isoLocal(monday);
    if (!weeks.has(key)) weeks.set(key, { start: key, keys: new Set(), completed: 0, cumulative: 0, hours: 0 });
    const w = weeks.get(key);
    (r.keys || []).forEach(k => w.keys.add(k));
    w.completed += r.completed;
    w.cumulative = r.completed_cumulative;
    w.hours += r.hours;
  });
  return Array.from(weeks.values()).map(w => ({
    label: w.start.slice(8, 10) + '/' + w.start.slice(5, 7),
    full: 'Semana de ' + anFmtDate(w.start),
    tickets: w.keys.size,
    completed: w.completed,
    cumulative: w.cumulative,
    hours: Math.round(w.hours * 100) / 100
  }));
}

function niceCeil(v) {
  if (v <= 4) return Math.max(1, Math.ceil(v));
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

function smoothPath(pts, top, bottom) {
  if (pts.length === 1) return 'M' + pts[0][0] + ',' + pts[0][1];
  let d = 'M' + pts[0][0].toFixed(1) + ',' + pts[0][1].toFixed(1);
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const clampY = y => Math.min(bottom, Math.max(top, y));
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = clampY(p1[1] + (p2[1] - p0[1]) / 6);
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = clampY(p2[1] - (p3[1] - p1[1]) / 6);
    d += ' C' + c1x.toFixed(1) + ',' + c1y.toFixed(1) + ' ' + c2x.toFixed(1) + ',' + c2y.toFixed(1) + ' ' + p2[0].toFixed(1) + ',' + p2[1].toFixed(1);
  }
  return d;
}

function renderEvolutionChart() {
  const host = document.getElementById('an-chart');
  const rows = evolutionRows();
  if (!rows.length) {
    host.innerHTML = '<div class="empty-mini">Sem dados para o período selecionado.</div>';
    return;
  }
  const active = Object.keys(analyticsSeriesOn).filter(k => analyticsSeriesOn[k]);
  const countKeys = active.filter(k => SERIES_DEFS[k].axis === 'count');
  const hasHours = active.includes('hours');
  const W = 960, H = 330, padL = 44, padR = hasHours ? 48 : 18, padT = 18, padB = 36;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const leftMax = niceCeil(Math.max(1, ...countKeys.flatMap(k => rows.map(r => r[k]))));
  const rightMax = niceCeil(Math.max(1, ...rows.map(r => r.hours)));
  const xAt = i => padL + (rows.length === 1 ? innerW / 2 : (i * innerW) / (rows.length - 1));
  const yAt = (v, max) => padT + innerH - (v / max) * innerH;

  let svg = '<svg class="lc-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">';
  svg += '<defs>' + active.map(k =>
    '<linearGradient id="lc-grad-' + k + '" x1="0" y1="0" x2="0" y2="1">'
    + '<stop offset="0" style="stop-color:var(--chart-' + SERIES_DEFS[k].cls.slice(1) + ');stop-opacity:0.28"/>'
    + '<stop offset="1" style="stop-color:var(--chart-' + SERIES_DEFS[k].cls.slice(1) + ');stop-opacity:0"/></linearGradient>'
  ).join('') + '</defs>';

  for (let g = 0; g <= 4; g++) {
    const y = padT + (innerH * g) / 4;
    svg += '<line class="lc-grid" x1="' + padL + '" x2="' + (W - padR) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '"/>';
    if (countKeys.length) {
      svg += '<text class="lc-axis-text" x="' + (padL - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + anFmtNumber(leftMax - (leftMax * g) / 4, 1) + '</text>';
    }
    if (hasHours) {
      svg += '<text class="lc-axis-text" x="' + (W - padR + 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="start">' + anFmtNumber(rightMax - (rightMax * g) / 4, 1) + 'h</text>';
    }
  }

  const step = Math.max(1, Math.ceil(rows.length / 9));
  rows.forEach((r, i) => {
    if (i % step === 0 || i === rows.length - 1) {
      svg += '<text class="lc-axis-text" x="' + xAt(i).toFixed(1) + '" y="' + (H - 12) + '" text-anchor="middle">' + r.label + '</text>';
    }
  });

  active.forEach((k, idx) => {
    const def = SERIES_DEFS[k];
    const max = def.axis === 'hours' ? rightMax : leftMax;
    const pts = rows.map((r, i) => [xAt(i), yAt(r[k], max)]);
    const line = smoothPath(pts, padT, padT + innerH);
    const baseY = (padT + innerH).toFixed(1);
    if (rows.length > 1) {
      svg += '<path class="lc-area" d="' + line + ' L' + pts[pts.length - 1][0].toFixed(1) + ',' + baseY + ' L' + pts[0][0].toFixed(1) + ',' + baseY + ' Z" fill="url(#lc-grad-' + k + ')"/>';
    }
    svg += '<path class="lc-line ' + def.cls + '" pathLength="1" d="' + line + '" style="animation-delay:' + (idx * 120) + 'ms"/>';
    if (rows.length <= 45) {
      pts.forEach(p => { svg += '<circle class="lc-dot ' + def.cls + '" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="2.6"/>'; });
    }
  });

  svg += '<line class="lc-cursor" id="lc-cursor" y1="' + padT + '" y2="' + (padT + innerH) + '" x1="0" x2="0"/>';
  active.forEach(k => { svg += '<circle class="lc-hover-dot ' + SERIES_DEFS[k].cls + '" id="lc-hd-' + k + '" r="5" cx="0" cy="0"/>'; });
  svg += '<rect id="lc-hit" x="' + padL + '" y="' + padT + '" width="' + innerW + '" height="' + innerH + '" fill="transparent"/>';
  svg += '</svg><div class="lc-tip" id="lc-tip"></div>';
  host.innerHTML = '<div class="lc-wrap" id="lc-wrap">' + svg + '</div>';

  const hit = document.getElementById('lc-hit');
  const tip = document.getElementById('lc-tip');
  const cursor = document.getElementById('lc-cursor');
  const wrap = document.getElementById('lc-wrap');
  const svgEl = wrap.querySelector('svg');

  function hide() {
    tip.style.opacity = 0;
    cursor.style.opacity = 0;
    active.forEach(k => { document.getElementById('lc-hd-' + k).style.opacity = 0; });
  }

  hit.addEventListener('mousemove', function (ev) {
    const box = svgEl.getBoundingClientRect();
    const scale = W / box.width;
    const px = (ev.clientX - box.left) * scale;
    let i = rows.length === 1 ? 0 : Math.round(((px - padL) / innerW) * (rows.length - 1));
    i = Math.max(0, Math.min(rows.length - 1, i));
    const r = rows[i];
    const x = xAt(i);
    cursor.setAttribute('x1', x);
    cursor.setAttribute('x2', x);
    cursor.style.opacity = 1;
    let html = '<b>' + escapeHtml(r.full) + '</b>';
    active.forEach(k => {
      const def = SERIES_DEFS[k];
      const max = def.axis === 'hours' ? rightMax : leftMax;
      const dot = document.getElementById('lc-hd-' + k);
      dot.setAttribute('cx', x);
      dot.setAttribute('cy', yAt(r[k], max));
      dot.style.opacity = 1;
      html += def.label + ': <strong>' + anFmtNumber(r[k], 2) + (def.axis === 'hours' ? 'h' : '') + '</strong><br>';
    });
    tip.innerHTML = html;
    const tipHalf = (tip.offsetWidth || 160) / 2 + 4;
    tip.style.left = Math.max(tipHalf, Math.min(box.width - tipHalf, x / scale)) + 'px';
    tip.style.top = (padT / scale) + 'px';
    tip.style.opacity = 1;
  });
  hit.addEventListener('mouseleave', hide);
}
"""
