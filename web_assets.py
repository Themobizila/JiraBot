"""
Ativos visuais do painel web do JiraBot: tema (CSS), efeitos e menu retratil (JS), dashboard analitico (JS) e logotipo (SVG).

Estes blocos sao injetados no HTML_PAGE de web_panel.py por meio de marcadores, mantendo o arquivo principal enxuto
e permitindo que o atualizador (que copia apenas .py/.bat/.ico/.png) distribua o logotipo e o tema sem arquivos extras.
"""

from __future__ import annotations

import base64
import os

# Carrega avatar oficial da Lofi Girl em base64 data URI para renderizacao instantanea sem requisicoes extras
_lofigirl_path = os.path.join(os.path.dirname(__file__), "assets", "lofigirl.png")
if os.path.exists(_lofigirl_path):
    with open(_lofigirl_path, "rb") as _f:
        LOFI_GIRL_AVATAR_DATA_URI = "data:image/png;base64," + base64.b64encode(_f.read()).decode("ascii")
else:
    LOFI_GIRL_AVATAR_DATA_URI = "/assets/lofigirl.png"

# ----------------------------------------------------------------------------------------------------------------------
# LOGOTIPOS TEMATICOS COMPLETOS (VETORIAIS SVG SEM EMOJIS)
# ----------------------------------------------------------------------------------------------------------------------
LOGO_DEFAULT_SVG = (
    '''<svg class="theme-logo logo-default" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="JiraBot Padrao">
  <defs>
    <linearGradient id="jbGold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f6e6b4"/><stop offset="0.45" stop-color="#c8aa6e"/><stop offset="1" stop-color="#7a5a26"/>
    </linearGradient>
    <linearGradient id="jbDark" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#241b0d"/><stop offset="1" stop-color="#0a0705"/>
    </linearGradient>
  </defs>
  <polygon points="32,3 58,18 58,46 32,61 6,46 6,18" fill="url(#jbDark)" stroke="url(#jbGold)" stroke-width="2.6" stroke-linejoin="round"/>
  <polygon points="32,8.5 53,20.5 53,43.5 32,55.5 11,43.5 11,20.5" fill="none" stroke="url(#jbGold)" stroke-opacity="0.35" stroke-width="1"/>
  <path d="M32 12.5 A19.5 19.5 0 1 1 14.6 22.2" fill="none" stroke="url(#jbGold)" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M32 8.6 L35 12.5 L32 16.4 L29 12.5 Z" fill="url(#jbGold)"/>
  <path d="M25.5 21 H40 V24.5 H37 V38 C37 43 33.8 45.6 29.4 45.6 C26.8 45.6 24.8 44.8 23.2 43.1 L25.7 40.5 C26.6 41.5 27.8 42 29.3 42 C31.9 42 33.5 40.5 33.5 37.7 V24.5 H25.5 Z" fill="url(#jbGold)"/>
</svg>'''
)

LOGO_HALLOWEEN_SVG = (
    '''<svg class="theme-logo logo-halloween" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="JiraBot Halloween">
  <defs>
    <linearGradient id="hwOrange" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffa34d"/><stop offset="0.5" stop-color="#ff7518"/><stop offset="1" stop-color="#b84300"/>
    </linearGradient>
    <linearGradient id="hwGlow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff275"/><stop offset="0.6" stop-color="#ff9900"/><stop offset="1" stop-color="#ff4400"/>
    </linearGradient>
    <linearGradient id="hwDark" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#220b33"/><stop offset="1" stop-color="#0e0417"/>
    </linearGradient>
    <linearGradient id="hwStem" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="#4a6b22"/><stop offset="1" stop-color="#70a332"/>
    </linearGradient>
  </defs>
  <polygon points="32,4 58,19 58,45 32,60 6,45 6,19" fill="url(#hwDark)" stroke="url(#hwOrange)" stroke-width="2.6" stroke-linejoin="round"/>
  <path d="M32 4 C44 4 55 16 55 32 C55 48 44 60 32 60 C20 60 9 48 9 32 C9 16 20 4 32 4 Z" fill="none" stroke="url(#hwOrange)" stroke-opacity="0.3" stroke-width="1.2"/>
  <path d="M32 4 C38 4 45 16 45 32 C45 48 38 60 32 60 C26 60 19 48 19 32 C19 16 26 4 32 4 Z" fill="none" stroke="url(#hwOrange)" stroke-opacity="0.45" stroke-width="1.2"/>
  <path d="M32 7 C31 3 33 0 35 0 C37 0 36 3 34 7 Z" fill="url(#hwStem)" stroke="#304712" stroke-width="0.8"/>
  <circle cx="32" cy="7" r="2.2" fill="#ff7518" stroke="#ffa34d" stroke-width="0.8"/>
  <polygon points="21,21 28,26 21,28" fill="url(#hwGlow)"/>
  <polygon points="43,21 36,26 43,28" fill="url(#hwGlow)"/>
  <path d="M25 31 H39 V35 H36 V43 C36 47.5 33 49.5 29 49.5 C26 49.5 24 48.5 22.5 47 L24.5 44.5 C25.5 45.5 26.8 46 28.5 46 C30.8 46 32 44.8 32 42.5 V35 H25 Z" fill="url(#hwGlow)"/>
  <polygon points="37,38 41,39 37,42" fill="url(#hwGlow)"/>
</svg>'''
)

LOGO_NATAL_SVG = (
    '''<svg class="theme-logo logo-natal" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="JiraBot Natal">
  <defs>
    <linearGradient id="ntGold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fff2a8"/><stop offset="0.5" stop-color="#ffd166"/><stop offset="1" stop-color="#c48f21"/>
    </linearGradient>
    <linearGradient id="ntRed" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ff6b78"/><stop offset="0.6" stop-color="#e63946"/><stop offset="1" stop-color="#9e1b26"/>
    </linearGradient>
    <linearGradient id="ntPine" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0f2e20"/><stop offset="1" stop-color="#040f0a"/>
    </linearGradient>
  </defs>
  <polygon points="32,3 58,18 58,46 32,61 6,46 6,18" fill="url(#ntPine)" stroke="url(#ntGold)" stroke-width="2.4" stroke-linejoin="round"/>
  <circle cx="32" cy="33" r="21" fill="none" stroke="#2ec4b6" stroke-opacity="0.3" stroke-width="1.5" stroke-dasharray="3,3"/>
  <circle cx="32" cy="33" r="18" fill="none" stroke="#1f694a" stroke-width="2.5"/>
  <path d="M6 18 Q16 12 32 3 Q48 12 58 18 Q48 16 32 9 Q16 16 6 18 Z" fill="#f0fff4" opacity="0.95"/>
  <circle cx="16" cy="24" r="2.2" fill="url(#ntRed)"/>
  <circle cx="48" cy="24" r="2.2" fill="url(#ntRed)"/>
  <circle cx="14" cy="40" r="2.2" fill="url(#ntRed)"/>
  <circle cx="50" cy="40" r="2.2" fill="url(#ntRed)"/>
  <polygon points="32,7 33.5,11 38,12 34,14.5 35.5,19 32,16 28.5,19 30,14.5 26,12 30.5,11" fill="url(#ntGold)"/>
  <path d="M25.5 23 H40 V26.5 H37 V38.5 C37 43 33.8 45.6 29.4 45.6 C26.8 45.6 24.8 44.8 23.2 43.1 L25.7 40.5 C26.6 41.5 27.8 42 29.3 42 C31.9 42 33.5 40.5 33.5 37.7 V26.5 H25.5 Z" fill="url(#ntGold)"/>
  <path d="M25 56 C28 53 32 54 32 56 C32 54 36 53 39 56 C37 59 34 58 32 60 C30 58 27 59 25 56 Z" fill="url(#ntRed)"/>
  <circle cx="32" cy="56" r="2" fill="url(#ntGold)"/>
</svg>'''
)

LOGO_ANO_NOVO_SVG = (
    '''<svg class="theme-logo logo-ano_novo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="JiraBot Ano Novo">
  <defs>
    <linearGradient id="nyGold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffffff"/><stop offset="0.3" stop-color="#fff275"/><stop offset="0.7" stop-color="#ffd700"/><stop offset="1" stop-color="#b39200"/>
    </linearGradient>
    <linearGradient id="nyNight" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#101938"/><stop offset="1" stop-color="#050814"/>
    </linearGradient>
  </defs>
  <polygon points="32,3 58,18 58,46 32,61 6,46 6,18" fill="url(#nyNight)" stroke="url(#nyGold)" stroke-width="2.6" stroke-linejoin="round"/>
  <circle cx="32" cy="33" r="20" fill="none" stroke="url(#nyGold)" stroke-width="1.4" stroke-opacity="0.8"/>
  <circle cx="32" cy="33" r="23" fill="none" stroke="#38bdf8" stroke-width="0.8" stroke-opacity="0.4" stroke-dasharray="2,4"/>
  <circle cx="32" cy="15" r="1.6" fill="#ffffff"/>
  <circle cx="50" cy="33" r="1.4" fill="url(#nyGold)"/>
  <circle cx="32" cy="51" r="1.4" fill="url(#nyGold)"/>
  <circle cx="14" cy="33" r="1.4" fill="url(#nyGold)"/>
  <line x1="32" y1="33" x2="32" y2="17" stroke="url(#nyGold)" stroke-width="2" stroke-linecap="round"/>
  <line x1="32" y1="33" x2="32" y2="21" stroke="#ffffff" stroke-width="1.4" stroke-linecap="round"/>
  <circle cx="32" cy="33" r="2.8" fill="url(#nyGold)"/>
  <polygon points="32,4 33.5,8 37,9 33.5,10 32,14 30.5,10 27,9 30.5,8" fill="#ffffff"/>
  <path d="M25.5 22 H40 V25.5 H37 V38.5 C37 43 33.8 45.6 29.4 45.6 C26.8 45.6 24.8 44.8 23.2 43.1 L25.7 40.5 C26.6 41.5 27.8 42 29.3 42 C31.9 42 33.5 40.5 33.5 37.7 V25.5 H25.5 Z" fill="url(#nyGold)"/>
</svg>'''
)

LOGO_PASCOA_SVG = (
    '''<svg class="theme-logo logo-pascoa" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="JiraBot Pascoa">
  <defs>
    <linearGradient id="psGold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#faf089"/><stop offset="0.5" stop-color="#ecc94b"/><stop offset="1" stop-color="#b7791f"/>
    </linearGradient>
    <linearGradient id="psGreen" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#163826"/><stop offset="1" stop-color="#0a1a11"/>
    </linearGradient>
    <linearGradient id="psLilac" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#e9d8fd"/><stop offset="1" stop-color="#b794f4"/>
    </linearGradient>
  </defs>
  <polygon points="32,3 58,18 58,46 32,61 6,46 6,18" fill="url(#psGreen)" stroke="url(#psGold)" stroke-width="2.4" stroke-linejoin="round"/>
  <path d="M32 8 C44 8 52 20 52 38 C52 48 43 56 32 56 C21 56 12 48 12 38 C12 20 20 8 32 8 Z" fill="none" stroke="url(#psGold)" stroke-width="1.2" stroke-opacity="0.45"/>
  <path d="M32 9 C30 5 28 3 25 3 C25 6 28 8 32 9 Z" fill="#68d391"/>
  <path d="M32 9 C34 5 36 3 39 3 C39 6 36 8 32 9 Z" fill="#48bb78"/>
  <circle cx="32" cy="9" r="1.8" fill="url(#psGold)"/>
  <circle cx="17" cy="30" r="2" fill="url(#psLilac)"/>
  <circle cx="47" cy="30" r="2" fill="url(#psLilac)"/>
  <path d="M25.5 22 H40 V25.5 H37 V38 C37 42.6 33.8 45.2 29.4 45.2 C26.8 45.2 24.8 44.4 23.2 42.7 L25.7 40.1 C26.6 41.1 27.8 41.6 29.3 41.6 C31.9 41.6 33.5 40.1 33.5 37.3 V25.5 H25.5 Z" fill="url(#psGold)"/>
  <path d="M25.5 22 C24 19 22 20 21 21 C22 23 24 23 25.5 22 Z" fill="#68d391"/>
</svg>'''
)

LOGO_SVG = LOGO_DEFAULT_SVG

THEME_LOGOS_HTML = (
    LOGO_DEFAULT_SVG + "\n" +
    LOGO_HALLOWEEN_SVG + "\n" +
    LOGO_NATAL_SVG + "\n" +
    LOGO_ANO_NOVO_SVG + "\n" +
    LOGO_PASCOA_SVG
)

# Adornos vetoriais tematicos para o escudo (mantidos para retrocompatibilidade)
THEME_BADGES_HTML = (
    '<div class="brand-theme-badge badge-halloween" title="Halloween">'
    '<svg viewBox="0 0 24 24" fill="none" stroke="#ff7518" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 2v3M4.5 9c0 6 3 11 7.5 11s7.5-5 7.5-11c0-2-1.5-4-3.5-4-1.5 0-2.8 1-4 1s-2.5-1-4-1c-2 0-3.5 2-3.5 4z" fill="#ff7518" fill-opacity="0.35"/>'
    '<polygon points="8,10 10,12 8,13" fill="#ff7518"/><polygon points="16,10 14,12 16,13" fill="#ff7518"/>'
    '<path d="M9 16c1.5 1 4.5 1 6 0" stroke="#150a24" stroke-width="1.8"/>'
    '</svg></div>'
    '<div class="brand-theme-badge badge-natal" title="Natal">'
    '<svg viewBox="0 0 24 24" fill="none" stroke="#e63946" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M3 17h18c0-5-5-12-9-14-3 2-6 7-6 10" fill="#e63946" fill-opacity="0.9"/>'
    '<rect x="2" y="17" width="20" height="4" rx="2" fill="#f0fff4" stroke="#c6f6d5" stroke-width="1.2"/>'
    '<circle cx="12" cy="3" r="2.5" fill="#f0fff4" stroke="#c6f6d5" stroke-width="1.2"/>'
    '</svg></div>'
    '<div class="brand-theme-badge badge-ano_novo" title="Ano Novo">'
    '<svg viewBox="0 0 24 24" fill="none" stroke="#ffd700" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    '<polygon points="12,1 15,9 23,12 15,15 12,23 9,15 1,12 9,9" fill="#ffd700" fill-opacity="0.9"/>'
    '<circle cx="12" cy="12" r="2.5" fill="#ffffff"/>'
    '</svg></div>'
    '<div class="brand-theme-badge badge-pascoa" title="Pascoa">'
    '<svg viewBox="0 0 24 24" fill="none" stroke="#48bb78" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M7 19c-1-6 0-14 3-17 2 3 2 9 0 17" fill="#48bb78" fill-opacity="0.4"/>'
    '<path d="M17 19c1-6 0-14-3-17-2 3-2 9 0 17" fill="#48bb78" fill-opacity="0.4"/>'
    '<ellipse cx="12" cy="18" rx="7" ry="5" fill="#b794f4" fill-opacity="0.45" stroke="#b794f4" stroke-width="1.4"/>'
    '</svg></div>'
)

# Icones vetoriais tematicos ao lado do titulo JiraBot
BRAND_TITLE_ICONS_HTML = (
    '''<svg class="brand-title-icon title-icon-halloween" viewBox="0 0 24 24" fill="none" aria-hidden="true" title="Halloween (Sazonal)">
  <path d="M12 2C13 1 15 1.5 15.5 3.5" stroke="#557a2b" stroke-width="2.2" stroke-linecap="round"/>
  <ellipse cx="12" cy="14" rx="10.5" ry="8.5" fill="#ff7518" stroke="#d94f00" stroke-width="1.5"/>
  <ellipse cx="12" cy="14" rx="6.5" ry="8.2" fill="#ffa34d" opacity="0.6"/>
  <polygon points="7,12 9.5,13.5 7,15" fill="#fff599"/>
  <polygon points="17,12 14.5,13.5 17,15" fill="#fff599"/>
  <polygon points="12,12.5 10.5,14.5 13.5,14.5" fill="#fff599"/>
  <path d="M7 17 Q12 21 17 17 Q14 19.5 12 19.2 Q10 19.5 7 17 Z" fill="#fff599"/>
</svg>
<svg class="brand-title-icon title-icon-natal" viewBox="0 0 24 24" fill="none" aria-hidden="true" title="Natal (Sazonal)">
  <polygon points="12,1 13.5,4.5 17,5 14,7.5 15,11 12,9 9,11 10,7.5 7,5 10.5,4.5" fill="#ffd166"/>
  <polygon points="12,4 17,10 7,10" fill="#2ec4b6" stroke="#c6f6d5" stroke-width="0.8"/>
  <polygon points="12,8 19,15 5,15" fill="#1f694a" stroke="#2ec4b6" stroke-width="0.8"/>
  <polygon points="12,12 21,20 3,20" fill="#144d34" stroke="#1f694a" stroke-width="0.8"/>
  <rect x="10.5" y="20" width="3" height="3.5" fill="#8d5b28"/>
  <circle cx="12" cy="10" r="1.3" fill="#e63946"/>
  <circle cx="9" cy="14" r="1.3" fill="#ffd166"/>
  <circle cx="15" cy="14" r="1.3" fill="#e63946"/>
  <circle cx="8" cy="18.5" r="1.4" fill="#ffd166"/>
  <circle cx="16" cy="18.5" r="1.4" fill="#e63946"/>
</svg>
<svg class="brand-title-icon title-icon-ano_novo" viewBox="0 0 24 24" fill="none" aria-hidden="true" title="Ano Novo (Sazonal)">
  <polygon points="12,1 14.5,8.5 22,12 14.5,15.5 12,23 9.5,15.5 2,12 9.5,8.5" fill="#ffd700"/>
  <polygon points="12,4 13.5,9.5 19,12 13.5,14.5 12,20 10.5,14.5 5,12 10.5,9.5" fill="#ffffff"/>
  <circle cx="12" cy="12" r="2.2" fill="#fff599"/>
  <line x1="6" y1="6" x2="18" y2="18" stroke="#ffe082" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="18" y1="6" x2="6" y2="18" stroke="#ffe082" stroke-width="1.2" stroke-linecap="round"/>
</svg>
<svg class="brand-title-icon title-icon-pascoa" viewBox="0 0 24 24" fill="none" aria-hidden="true" title="Páscoa (Sazonal)">
  <path d="M12 22 V11" stroke="#38a169" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M12 16 C8 16 6 13 6 10 C9 10 12 13 12 16 Z" fill="#68d391" stroke="#38a169" stroke-width="1"/>
  <path d="M12 13 C16 13 18 10 18 7 C15 7 12 10 12 13 Z" fill="#48bb78" stroke="#38a169" stroke-width="1"/>
  <circle cx="12" cy="7" r="4.2" fill="#b794f4" stroke="#9f7aea" stroke-width="1"/>
  <circle cx="12" cy="7" r="1.8" fill="#ecc94b"/>
</svg>''')

# Cenarios Aconchegantes Animados Estilo Lofi Girl para o menu lateral
LOFI_SCENES_HTML = (
    '''<div class="lofi-scene scene-halloween">
  <svg class="lofi-canvas-svg" viewBox="0 0 240 135" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Cenario Halloween Lofi">
    <defs>
      <linearGradient id="hwSkyReal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#080211"/>
        <stop offset="50%" stop-color="#140624"/>
        <stop offset="100%" stop-color="#260b3d"/>
      </linearGradient>
      <radialGradient id="hwMoonHalo" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#fff8d6" stop-opacity="0.95"/>
        <stop offset="35%" stop-color="#ffd580" stop-opacity="0.45"/>
        <stop offset="70%" stop-color="#ff9933" stop-opacity="0.15"/>
        <stop offset="100%" stop-color="#260b3d" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="hwPumpGlowReal" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#fff9b3" stop-opacity="0.95"/>
        <stop offset="40%" stop-color="#ff9900" stop-opacity="0.75"/>
        <stop offset="80%" stop-color="#ff5500" stop-opacity="0.3"/>
        <stop offset="100%" stop-color="#ff3300" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="hwMistGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#3d145c" stop-opacity="0"/>
        <stop offset="50%" stop-color="#4d1b70" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#190629" stop-opacity="0.8"/>
      </linearGradient>
      <linearGradient id="hwWoodPost" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#1d0d29"/>
        <stop offset="50%" stop-color="#3b1d4f"/>
        <stop offset="100%" stop-color="#14081c"/>
      </linearGradient>
    </defs>
    <!-- Ceu Noturno -->
    <rect width="240" height="135" fill="url(#hwSkyReal)"/>
    <!-- Estrelas distantes cintilantes -->
    <g class="lofi-stars">
      <circle cx="18" cy="14" r="0.7" fill="#ffffff" opacity="0.8"/>
      <circle cx="45" cy="22" r="0.9" fill="#ffe0b2" opacity="0.9"/>
      <circle cx="78" cy="10" r="0.6" fill="#ffffff" opacity="0.7"/>
      <circle cx="108" cy="20" r="0.8" fill="#fff3e0" opacity="0.85"/>
      <circle cx="138" cy="8" r="0.7" fill="#ffffff" opacity="0.75"/>
      <circle cx="218" cy="12" r="0.8" fill="#ffd580" opacity="0.8"/>
      <circle cx="232" cy="24" r="0.6" fill="#ffffff" opacity="0.6"/>
    </g>
    <!-- Lua Cheia da Colheita com Halo Atmosferico -->
    <circle cx="182" cy="36" r="32" fill="url(#hwMoonHalo)"/>
    <circle cx="182" cy="36" r="18" fill="#fff5cc"/>
    <!-- Crateras realistas da Lua -->
    <ellipse cx="176" cy="31" rx="3.5" ry="2.8" fill="#e8cf90" opacity="0.5"/>
    <ellipse cx="188" cy="42" rx="4.5" ry="3.5" fill="#e8cf90" opacity="0.45"/>
    <ellipse cx="190" cy="29" rx="2.2" ry="1.8" fill="#e8cf90" opacity="0.4"/>
    <circle cx="181" cy="45" r="2.2" fill="#e8cf90" opacity="0.4"/>
    <!-- Colinas ao Longe (3 Camadas de Profundidade) -->
    <path d="M0 90 Q65 72 135 84 Q195 94 240 78 L240 135 L0 135 Z" fill="#140624"/>
    <path d="M0 98 Q85 86 165 96 Q205 102 240 92 L240 135 L0 135 Z" fill="#1c0a30"/>
    <rect x="0" y="82" width="240" height="28" fill="url(#hwMistGrad)"/>
    <!-- Cerca de Madeira Rustica -->
    <line x1="0" y1="98" x2="240" y2="98" stroke="#250f38" stroke-width="2.5"/>
    <line x1="0" y1="110" x2="240" y2="110" stroke="#250f38" stroke-width="2.5"/>
    <rect x="32" y="90" width="6" height="34" rx="1" fill="url(#hwWoodPost)"/>
    <rect x="108" y="90" width="6" height="34" rx="1" fill="url(#hwWoodPost)"/>
    <rect x="188" y="90" width="6" height="34" rx="1" fill="url(#hwWoodPost)"/>
    <!-- Reflexo de madeira -->
    <line x1="33" y1="90" x2="33" y2="124" stroke="#4d2866" stroke-width="0.8"/>
    <line x1="109" y1="90" x2="109" y2="124" stroke="#4d2866" stroke-width="0.8"/>
    <line x1="189" y1="90" x2="189" y2="124" stroke="#4d2866" stroke-width="0.8"/>
    <!-- Espantalho Detalhado (Centro-Esquerda) -->
    <g class="lofi-scarecrow" transform="translate(68, 42)">
      <!-- Poste de sustentacao -->
      <rect x="7" y="18" width="4.5" height="66" fill="#2d160b"/>
      <rect x="-18" y="32" width="55" height="3.5" fill="#2d160b"/>
      <!-- Fibras de palha nos punhos e gola -->
      <path d="M-18 34 L-26 38 M-18 32 L-27 30 M-18 35 L-25 33" stroke="#e0a943" stroke-width="1.3"/>
      <path d="M37 34 L45 38 M37 32 L46 30 M37 35 L44 33" stroke="#e0a943" stroke-width="1.3"/>
      <path d="M6 24 L2 19 M12 24 L16 19 M9 25 L9 18" stroke="#e0a943" stroke-width="1.2"/>
      <!-- Casaco com dobras realistas -->
      <path d="M-4 32 L22 32 L26 64 L-8 64 Z" fill="#221130" stroke="#3d1e54" stroke-width="1"/>
      <path d="M-4 32 L8 46 L22 32" stroke="#13081c" stroke-width="1.2" fill="none"/>
      <line x1="9" y1="32" x2="9" y2="64" stroke="#15091f" stroke-width="1.5"/>
      <circle cx="9" cy="40" r="1" fill="#c8aa6e"/>
      <circle cx="9" cy="48" r="1" fill="#c8aa6e"/>
      <!-- Luz quente projetada no peito pela abobora -->
      <ellipse class="lofi-pumpkin-glow-chest" cx="9" cy="30" rx="14" ry="7" fill="url(#hwPumpGlowReal)" opacity="0.5"/>
      <!-- Cabeca de Abobora Esculpida (3D Jack-o'-lantern) -->
      <g transform="translate(9, 14)">
        <!-- Gomos externos -->
        <ellipse cx="0" cy="0" rx="14.5" ry="12.5" fill="#e65c00"/>
        <ellipse cx="0" cy="0" rx="11.5" ry="12.2" fill="#ff7518"/>
        <ellipse cx="0" cy="0" rx="6.5" ry="11.8" fill="#ffa34d"/>
        <!-- Talo de madeira e folha -->
        <path d="M0 -12 C1 -16 4 -18 6 -18" stroke="#557a2b" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <!-- Cavidades entalhadas com luz de vela interna -->
        <g class="lofi-pumpkin-glow">
          <polygon points="-7,-3 -2,1 -6,3" fill="#fff599"/>
          <polygon points="7,-3 2,1 6,3" fill="#fff599"/>
          <polygon points="0,-1 -2,2 2,2" fill="#fff599"/>
          <path d="M-7 5 Q0 11 7 5 Q4 8 0 8 Q-4 8 -7 5 Z" fill="#fff599"/>
        </g>
        <!-- Chapeu de bruxo rustico com remendo -->
        <ellipse cx="0" cy="-11" rx="19" ry="4.5" fill="#170824"/>
        <polygon points="-11,-11 11,-11 2,-32" fill="#220c36"/>
        <rect x="-8" y="-14" width="16" height="3" fill="#ff7518"/>
        <polygon points="4,-24 8,-22 6,-18 2,-20" fill="#3b1d4f" stroke="#e0a943" stroke-width="0.6"/>
      </g>
    </g>
    <!-- Gato Preto Realista Sentado na Cerca (Direita) -->
    <g class="lofi-cat" transform="translate(182, 78)">
      <!-- Sombra do gato na cerca -->
      <ellipse cx="10" cy="24" rx="9" ry="3" fill="#08020d" opacity="0.7"/>
      <!-- Corpo com anatomia organica -->
      <g class="lofi-cat-body">
        <!-- Patas e peito -->
        <ellipse cx="10" cy="18" rx="6.5" ry="8.5" fill="#0c0414"/>
        <circle cx="10" cy="8" r="5.5" fill="#0c0414"/>
        <polygon points="6,5 8,0 10.5,5" fill="#0c0414"/>
        <polygon points="10,5 12.5,0 14.5,5" fill="#0c0414"/>
        <!-- Luz suave da lua na silhueta do gato -->
        <path d="M15 12 Q17 18 15 24" stroke="#7a42a0" stroke-width="0.8" fill="none" opacity="0.6"/>
        <!-- Olhos felinos amendoados com pupilas -->
        <g class="lofi-cat-eyes">
          <ellipse cx="8.2" cy="7.5" rx="1.3" ry="1.8" fill="#ffd166"/>
          <ellipse cx="12.2" cy="7.5" rx="1.3" ry="1.8" fill="#ffd166"/>
          <line x1="8.2" y1="6" x2="8.2" y2="9" stroke="#0c0414" stroke-width="0.7"/>
          <line x1="12.2" y1="6" x2="12.2" y2="9" stroke="#0c0414" stroke-width="0.7"/>
        </g>
      </g>
      <!-- Cauda felina longa e ondulante -->
      <g class="lofi-cat-tail-wrap">
        <path class="lofi-cat-tail" d="M15 22 C22 25 24 16 26 12" fill="none" stroke="#0c0414" stroke-width="2.6" stroke-linecap="round"/>
      </g>
    </g>
    <!-- Campo de Trigo em Camadas com Espigas Detalhadas -->
    <!-- Camada de fundo de trigo -->
    <g class="lofi-wheat lofi-wheat-back" opacity="0.75">
      <path d="M5 135 Q10 112 8 96 M12 135 Q16 116 14 100 M24 135 Q20 110 26 94 M38 135 Q44 114 40 98" stroke="#a66e1e" stroke-width="1.3" fill="none"/>
      <path d="M115 135 Q120 114 116 96 M128 135 Q124 110 130 94 M140 135 Q146 116 142 100" stroke="#a66e1e" stroke-width="1.3" fill="none"/>
      <path d="M205 135 Q212 115 208 96 M220 135 Q216 110 224 92 M232 135 Q236 116 234 98" stroke="#a66e1e" stroke-width="1.3" fill="none"/>
    </g>
    <!-- Camada frontal de trigo iluminada -->
    <g class="lofi-wheat lofi-wheat-1">
      <path d="M8 135 Q12 108 6 88 M16 135 Q22 112 18 92 M28 135 Q24 106 32 86 M45 135 Q50 110 46 90" stroke="#e0a943" stroke-width="1.6" fill="none"/>
      <!-- Graos de trigo na ponta -->
      <circle cx="6" cy="88" r="1.4" fill="#ffd580"/>
      <circle cx="18" cy="92" r="1.4" fill="#ffd580"/>
      <circle cx="32" cy="86" r="1.4" fill="#ffd580"/>
      <circle cx="46" cy="90" r="1.4" fill="#ffd580"/>
    </g>
    <g class="lofi-wheat lofi-wheat-2">
      <path d="M120 135 Q116 108 124 88 M132 135 Q138 112 134 92 M148 135 Q144 106 152 86" stroke="#e0a943" stroke-width="1.6" fill="none"/>
      <circle cx="124" cy="88" r="1.4" fill="#ffd580"/>
      <circle cx="134" cy="92" r="1.4" fill="#ffd580"/>
      <circle cx="152" cy="86" r="1.4" fill="#ffd580"/>
      <path d="M200 135 Q208 110 204 90 M215 135 Q210 106 218 86 M228 135 Q234 112 230 92" stroke="#e0a943" stroke-width="1.6" fill="none"/>
      <circle cx="204" cy="90" r="1.4" fill="#ffd580"/>
      <circle cx="218" cy="86" r="1.4" fill="#ffd580"/>
      <circle cx="230" cy="92" r="1.4" fill="#ffd580"/>
    </g>
    <!-- Vaga-lumes e Brasas Flutuantes Sutis -->
    <circle class="lofi-ember lofi-ember-1" cx="74" cy="65" r="1.3" fill="#ffe082"/>
    <circle class="lofi-ember lofi-ember-2" cx="88" cy="74" r="1" fill="#ffb74d"/>
    <circle class="lofi-ember lofi-ember-3" cx="165" cy="88" r="1.2" fill="#ffe082"/>
    <circle class="lofi-ember lofi-ember-4" cx="140" cy="78" r="0.9" fill="#ff9800"/>
  </svg>
  <div class="lofi-caption">Noite de Outono | Lofi Chill</div>
</div>
<div class="lofi-scene scene-natal">
  <svg class="lofi-canvas-svg" viewBox="0 0 240 135" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Cenario Natal Lofi">
    <defs>
      <linearGradient id="ntWallReal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#120806"/>
        <stop offset="50%" stop-color="#1f0d09"/>
        <stop offset="100%" stop-color="#2a120d"/>
      </linearGradient>
      <radialGradient id="ntHearthGlowReal" cx="42%" cy="78%" r="68%">
        <stop offset="0%" stop-color="#ff9933" stop-opacity="0.6"/>
        <stop offset="40%" stop-color="#e63946" stop-opacity="0.25"/>
        <stop offset="75%" stop-color="#991b1b" stop-opacity="0.08"/>
        <stop offset="100%" stop-color="#120806" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="ntWinterNight" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#030814"/>
        <stop offset="60%" stop-color="#081830"/>
        <stop offset="100%" stop-color="#122a4a"/>
      </linearGradient>
      <linearGradient id="ntWoodPlank" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#1c0f0a"/>
        <stop offset="50%" stop-color="#29160e"/>
        <stop offset="100%" stop-color="#140a06"/>
      </linearGradient>
      <clipPath id="ntWindowArchClip">
        <path d="M148 18 Q182 10 216 18 L216 88 L148 88 Z"/>
      </clipPath>
    </defs>
    <!-- Parede de Tijolos Rústicos -->
    <rect width="240" height="135" fill="url(#ntWallReal)"/>
    <!-- Linhas e juntas de argamassa da alvenaria -->
    <g stroke="#3d1b14" stroke-width="0.7" opacity="0.4">
      <line x1="0" y1="18" x2="142" y2="18"/><line x1="0" y1="32" x2="142" y2="32"/><line x1="0" y1="46" x2="142" y2="46"/>
      <line x1="0" y1="60" x2="20" y2="60"/><line x1="122" y1="60" x2="142" y2="60"/>
      <line x1="28" y1="18" x2="28" y2="32"/><line x1="68" y1="18" x2="68" y2="32"/><line x1="108" y1="18" x2="108" y2="32"/>
      <line x1="48" y1="32" x2="48" y2="46"/><line x1="88" y1="32" x2="88" y2="46"/><line x1="128" y1="32" x2="128" y2="46"/>
    </g>
    <!-- Assoalho de Madeira Nobre com Tabuas -->
    <rect x="0" y="118" width="240" height="17" fill="url(#ntWoodPlank)"/>
    <line x1="0" y1="118" x2="240" y2="118" stroke="#3d2116" stroke-width="1.2"/>
    <line x1="0" y1="126" x2="240" y2="126" stroke="#26130b" stroke-width="0.8"/>
    <!-- Brilho aconchegante da lareira refletido na sala e piso -->
    <rect class="lofi-hearth-glow" x="0" y="15" width="165" height="120" fill="url(#ntHearthGlowReal)"/>
    <!-- JANELA EM ARCO COM VISTA PARA A NEVASCA DE INVERNO (Direita) -->
    <g class="lofi-window-wrap">
      <!-- Moldura chanfrada de madeira macica -->
      <path d="M145 16 Q182 8 219 16 L219 90 L145 90 Z" fill="#26140e" stroke="#42251a" stroke-width="2.2"/>
      <!-- Ceu noturno de inverno atras da janela -->
      <rect x="148" y="18" width="68" height="70" fill="url(#ntWinterNight)" clip-path="url(#ntWindowArchClip)"/>
      <!-- Pinheiros cobertos de neve ao fundo -->
      <polygon points="172,68 180,48 188,68" fill="#061324" clip-path="url(#ntWindowArchClip)"/>
      <polygon points="170,82 180,62 190,82" fill="#061324" clip-path="url(#ntWindowArchClip)"/>
      <polygon points="196,75 204,58 212,75" fill="#07172b" clip-path="url(#ntWindowArchClip)"/>
      <!-- Neve caindo la fora (Camada lenta e Camada rapida 3D) -->
      <g class="lofi-window-snow-back" clip-path="url(#ntWindowArchClip)">
        <circle cx="156" cy="24" r="0.8" fill="#e2f1ff" opacity="0.7"/>
        <circle cx="172" cy="38" r="0.9" fill="#e2f1ff" opacity="0.65"/>
        <circle cx="192" cy="26" r="0.8" fill="#e2f1ff" opacity="0.7"/>
        <circle cx="210" cy="44" r="0.9" fill="#e2f1ff" opacity="0.65"/>
        <circle cx="166" cy="58" r="0.8" fill="#e2f1ff" opacity="0.7"/>
        <circle cx="186" cy="68" r="0.9" fill="#e2f1ff" opacity="0.65"/>
      </g>
      <g class="lofi-window-snow-front" clip-path="url(#ntWindowArchClip)">
        <circle cx="162" cy="28" r="1.4" fill="#ffffff" opacity="0.95"/>
        <circle cx="180" cy="42" r="1.3" fill="#ffffff" opacity="0.9"/>
        <circle cx="204" cy="32" r="1.5" fill="#ffffff" opacity="0.95"/>
        <circle cx="174" cy="62" r="1.3" fill="#ffffff" opacity="0.9"/>
        <circle cx="198" cy="66" r="1.4" fill="#ffffff" opacity="0.9"/>
      </g>
      <!-- Divisoes da vidraca (mullions) -->
      <line x1="182" y1="12" x2="182" y2="90" stroke="#361c14" stroke-width="2"/>
      <line x1="148" y1="50" x2="216" y2="50" stroke="#361c14" stroke-width="1.8"/>
      <!-- Peitoril da Janela com Neve Acumulada -->
      <rect x="142" y="88" width="80" height="6" rx="1.5" fill="#361c14" stroke="#4a271c" stroke-width="1"/>
      <path d="M144 88 Q182 85 220 88 L218 89.5 Q182 87.5 144 89.5 Z" fill="#ebf8ff"/>
    </g>
    <!-- LAREIRA RUSTICA DE PEDRA E TIJOLOS (Centro-Esquerda) -->
    <g class="lofi-fireplace">
      <!-- Estrutura de pedras chanfradas -->
      <path d="M18 42 Q70 34 122 42 L122 118 L18 118 Z" fill="#2b1913" stroke="#472a20" stroke-width="2"/>
      <!-- Cavidade interna do fogo com fuligem escura -->
      <path d="M30 60 Q70 52 110 60 L110 118 L30 118 Z" fill="#0a0403"/>
      <!-- Leito de brasas incandescentes e lenha de vidoeiro -->
      <rect x="38" y="108" width="64" height="8" rx="2" fill="#210c06"/>
      <ellipse cx="70" cy="112" rx="30" ry="5" fill="#9e1b26"/>
      <ellipse cx="70" cy="112" rx="22" ry="3.5" fill="#e63946"/>
      <ellipse cx="70" cy="112" rx="14" ry="2" fill="#ffd166"/>
      <!-- LABAREDAS VIVAS DE FOGO EM 3 CAMADAS ORGANICAS -->
      <g class="lofi-fire-flames">
        <!-- Chamas externas carmesim -->
        <path d="M46 112 Q54 84 62 94 Q70 74 76 92 Q84 82 94 112 Z" fill="#e63946" opacity="0.85"/>
        <!-- Chamas intermediarias alaranjadas vibrantes -->
        <path d="M50 112 Q58 88 66 98 Q71 78 77 96 Q85 88 90 112 Z" fill="#ff7518"/>
        <!-- Chamas centrais incandescentes douradas/amarelas -->
        <path d="M58 112 Q64 94 70 102 Q73 86 77 100 Q82 94 82 112 Z" fill="#fff599"/>
      </g>
      <!-- Fagulhas que sobem da lareira -->
      <circle class="lofi-spark lofi-spark-1" cx="66" cy="80" r="1" fill="#fff599"/>
      <circle class="lofi-spark lofi-spark-2" cx="74" cy="74" r="0.8" fill="#ffd166"/>
      <!-- Aparador / Prateleira de Carvalho Macico -->
      <rect x="12" y="38" width="116" height="7" rx="1.5" fill="#3d2116" stroke="#573121" stroke-width="1.2"/>
      <!-- Guirlanda de Pinheiro e Azevinho com Lacos Vermelhos -->
      <path d="M14 45 Q42 54 70 46 Q98 54 126 45" stroke="#1f694a" stroke-width="3" fill="none" stroke-linecap="round"/>
      <circle cx="42" cy="51" r="1.8" fill="#e63946"/><circle cx="98" cy="51" r="1.8" fill="#e63946"/>
      <circle cx="70" cy="48" r="1.5" fill="#ffd166"/>
      <!-- Meias de La Aconchegantes Penduradas -->
      <path d="M36 45 L36 56 L30 58 L30 63 L39 63 L40 56 L40 45 Z" fill="#e63946"/>
      <rect x="34" y="44" width="8" height="2.5" rx="1" fill="#f0fff4"/>
      <path d="M96 45 L96 56 L90 58 L90 63 L99 63 L100 56 L100 45 Z" fill="#e63946"/>
      <rect x="94" y="44" width="8" height="2.5" rx="1" fill="#f0fff4"/>
      <!-- Caneca de Ceramica de Chocolate Quente com Fumaca Ondulante -->
      <rect x="64" y="30" width="8" height="9" rx="1.5" fill="#9e1b26" stroke="#c72030" stroke-width="0.8"/>
      <path d="M72 32 Q76 34.5 72 37" stroke="#9e1b26" stroke-width="1.2" fill="none"/>
      <!-- Fumaca ondulante subindo suavemente da caneca -->
      <g class="lofi-steam">
        <path d="M66 28 Q63 22 67 16" stroke="#ffffff" stroke-width="1" fill="none" opacity="0.65" stroke-linecap="round"/>
        <path d="M70 28 Q73 21 69 14" stroke="#ffffff" stroke-width="1" fill="none" opacity="0.65" stroke-linecap="round"/>
      </g>
    </g>
  </svg>
  <div class="lofi-caption">Lareira Acolhedora | Noite de Inverno</div>
</div>
<div class="lofi-scene scene-ano_novo">
  <svg class="lofi-canvas-svg" viewBox="0 0 240 135" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Cenario Ano Novo Lofi">
    <defs>
      <linearGradient id="nySkyReal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#030614"/>
        <stop offset="45%" stop-color="#070f2b"/>
        <stop offset="80%" stop-color="#111c47"/>
        <stop offset="100%" stop-color="#1a275c"/>
      </linearGradient>
      <radialGradient id="nyLanternGlowReal" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#fff599" stop-opacity="0.95"/>
        <stop offset="40%" stop-color="#ffd700" stop-opacity="0.6"/>
        <stop offset="75%" stop-color="#ff9900" stop-opacity="0.2"/>
        <stop offset="100%" stop-color="#ff6600" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <!-- Ceu Azul Meia-Noite Profundo -->
    <rect width="240" height="135" fill="url(#nySkyReal)"/>
    <!-- Estrelas Cintilantes no Ceu -->
    <g class="lofi-stars">
      <circle cx="16" cy="14" r="0.8" fill="#ffffff" opacity="0.85"/>
      <circle cx="58" cy="10" r="1.1" fill="#fff9c4" opacity="0.95"/>
      <circle cx="98" cy="22" r="0.7" fill="#ffffff" opacity="0.7"/>
      <circle cx="145" cy="12" r="0.9" fill="#80d8ff" opacity="0.85"/>
      <circle cx="205" cy="18" r="1" fill="#ffffff" opacity="0.9"/>
      <circle cx="178" cy="8" r="0.8" fill="#ffd54f" opacity="0.8"/>
    </g>
    <!-- FOGOS DE ARTIFICIO CINEMATOGRAFICOS (2 Explosões em Cascata) -->
    <!-- Fogo 1: Cascata Dourada (Esquerda) -->
    <g class="lofi-firework lofi-firework-1">
      <circle cx="0" cy="0" r="2.2" fill="#ffffff"/>
      <line x1="0" y1="0" x2="0" y2="-18" stroke="#ffd700" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="13" y2="-13" stroke="#fff599" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="18" y2="0" stroke="#ffd700" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="13" y2="13" stroke="#fff599" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="0" y2="18" stroke="#ffd700" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="-13" y2="13" stroke="#fff599" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="-18" y2="0" stroke="#ffd700" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="-13" y2="-13" stroke="#fff599" stroke-width="1.3" stroke-linecap="round"/>
      <!-- Fagulhas caindo com gravidade -->
      <circle cx="18" cy="-8" r="0.9" fill="#ffd700"/>
      <circle cx="-16" cy="6" r="0.9" fill="#ffd700"/>
      <circle cx="8" cy="20" r="0.9" fill="#fff599"/>
      <circle cx="-8" cy="20" r="0.9" fill="#fff599"/>
    </g>
    <!-- Fogo 2: Estrela Azul Turquesa / Violeta (Direita) -->
    <g class="lofi-firework lofi-firework-2">
      <circle cx="0" cy="0" r="2" fill="#ffffff"/>
      <line x1="0" y1="0" x2="0" y2="-16" stroke="#38bdf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="11" y2="-11" stroke="#818cf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="16" y2="0" stroke="#38bdf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="11" y2="11" stroke="#818cf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="0" y2="16" stroke="#38bdf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="-11" y2="11" stroke="#818cf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="-16" y2="0" stroke="#38bdf8" stroke-width="1.3" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="-11" y2="-11" stroke="#818cf8" stroke-width="1.3" stroke-linecap="round"/>
    </g>
    <!-- HORIZONTE DA CIDADE (Skyline Detalhado com Luzes em Andares) -->
    <g class="lofi-city-skyline">
      <!-- Edificios de Fundo (Silhuetas Escuras) -->
      <rect x="8" y="58" width="24" height="48" fill="#091026"/>
      <rect x="36" y="66" width="18" height="40" fill="#0c1636"/>
      <rect x="70" y="48" width="28" height="58" fill="#080e22"/>
      <polygon points="84,36 82,48 86,48" fill="#080e22"/> <!-- Agulha/Antena -->
      <circle cx="84" cy="36" r="1" fill="#f43f5e"/> <!-- Luz de alerta de voo -->
      <rect x="110" y="60" width="22" height="46" fill="#0a122e"/>
      <rect x="138" y="52" width="32" height="54" fill="#070d20"/>
      <polygon points="154,42 152,52 156,52" fill="#070d20"/>
      <circle cx="154" cy="42" r="1" fill="#f43f5e"/>
      <rect x="178" y="62" width="22" height="44" fill="#0b1433"/>
      <rect x="206" y="54" width="26" height="52" fill="#080f24"/>
      <!-- Grade Realista de Janelas Iluminadas em Tons Quentes e Frios -->
      <g fill="#ffd700" opacity="0.8">
        <rect x="12" y="64" width="2.8" height="3.5"/><rect x="20" y="72" width="2.8" height="3.5"/><rect x="12" y="82" width="2.8" height="3.5"/>
        <rect x="40" y="70" width="2.8" height="2.8"/><rect x="46" y="78" width="2.8" height="2.8"/>
        <rect x="75" y="54" width="2.8" height="4.5"/><rect x="82" y="64" width="2.8" height="4.5"/><rect x="89" y="54" width="2.8" height="4.5"/>
        <rect x="82" y="76" width="2.8" height="4.5"/><rect x="75" y="86" width="2.8" height="4.5"/>
        <rect x="114" y="66" width="2.8" height="3.5"/><rect x="122" y="74" width="2.8" height="3.5"/>
        <rect x="144" y="58" width="2.8" height="4.5"/><rect x="156" y="68" width="2.8" height="4.5"/><rect x="150" y="80" width="2.8" height="4.5"/>
        <rect x="182" y="68" width="2.8" height="3.5"/><rect x="190" y="76" width="2.8" height="3.5"/>
        <rect x="212" y="60" width="2.8" height="3.5"/><rect x="220" y="70" width="2.8" height="3.5"/>
      </g>
      <g fill="#38bdf8" opacity="0.65">
        <rect x="20" y="64" width="2.8" height="3.5"/><rect x="75" y="70" width="2.8" height="4.5"/><rect x="156" y="58" width="2.8" height="4.5"/>
        <rect x="220" y="60" width="2.8" height="3.5"/>
      </g>
    </g>
    <!-- SACADA PANORAMICA MODERNA (Primeiro Plano) -->
    <rect x="0" y="104" width="240" height="31" fill="#060914" stroke="#1b284a" stroke-width="1.2"/>
    <rect x="0" y="104" width="240" height="4.5" fill="#141f3d"/>
    <!-- Gradil de vidro e trilhos de aco da sacada -->
    <line x1="0" y1="110" x2="240" y2="110" stroke="#25355e" stroke-width="1.6"/>
    <g stroke="#1e2c4f" stroke-width="1.8">
      <line x1="24" y1="110" x2="24" y2="135"/><line x1="64" y1="110" x2="64" y2="135"/><line x1="104" y1="110" x2="104" y2="135"/>
      <line x1="144" y1="110" x2="144" y2="135"/><line x1="184" y1="110" x2="184" y2="135"/><line x1="224" y1="110" x2="224" y2="135"/>
    </g>
    <!-- Lanterna de Vidro e Latao Polido (Apoiada na grade a direita) -->
    <g class="lofi-lantern" transform="translate(184, 82)">
      <circle class="lofi-lantern-glow" cx="12" cy="14" r="18" fill="url(#nyLanternGlowReal)"/>
      <polygon points="5,7 19,7 15,2 9,2" fill="#c49b08" stroke="#ffd700" stroke-width="0.8"/>
      <rect x="5" y="7" width="14" height="15" fill="#0d142b" stroke="#ffd700" stroke-width="1.2"/>
      <rect x="7" y="9" width="10" height="11" fill="#fff9c4" opacity="0.95"/>
      <!-- Vela e chama dentro da lanterna -->
      <rect x="10" y="14" width="4" height="6" fill="#fdfcf0"/>
      <polygon points="12,10 10.5,14 13.5,14" fill="#ff9900"/>
      <rect x="4" y="22" width="16" height="3" rx="1" fill="#c49b08"/>
    </g>
  </svg>
  <div class="lofi-caption">Meia-Noite na Cidade | Ano Novo</div>
</div>
<div class="lofi-scene scene-pascoa">
  <svg class="lofi-canvas-svg" viewBox="0 0 240 135" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Cenario Pascoa Lofi">
    <defs>
      <linearGradient id="psSkyReal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#0f261d"/>
        <stop offset="45%" stop-color="#183d2e"/>
        <stop offset="85%" stop-color="#2a5742"/>
        <stop offset="100%" stop-color="#3d7559"/>
      </linearGradient>
      <radialGradient id="psSunReal" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#fffde7" stop-opacity="0.95"/>
        <stop offset="45%" stop-color="#fff59d" stop-opacity="0.6"/>
        <stop offset="80%" stop-color="#81c784" stop-opacity="0.2"/>
        <stop offset="100%" stop-color="#2a5742" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="psHill1" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#1a3d2c"/>
        <stop offset="100%" stop-color="#10261b"/>
      </linearGradient>
      <linearGradient id="psHill2" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#26543c"/>
        <stop offset="100%" stop-color="#183626"/>
      </linearGradient>
      <linearGradient id="psHill3" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#357050"/>
        <stop offset="100%" stop-color="#214733"/>
      </linearGradient>
    </defs>
    <!-- Ceu Matinal Primaveril Suave -->
    <rect width="240" height="135" fill="url(#psSkyReal)"/>
    <!-- Sol Nascente Suave com Halo Dourado -->
    <circle cx="204" cy="34" r="28" fill="url(#psSunReal)"/>
    <circle cx="204" cy="34" r="14" fill="#fff9c4"/>
    <!-- Nuvem de Manha Suavemente Flutuante -->
    <g class="lofi-cloud" opacity="0.4">
      <path d="M35 26 Q45 18 58 22 Q70 16 80 24 Q90 28 82 35 L35 35 Q26 30 35 26 Z" fill="#f0fff4"/>
    </g>
    <!-- Colinas Onduladas Verdes (3 Camadas de Profundidade) -->
    <path d="M0 84 Q70 66 140 78 Q200 88 240 72 L240 135 L0 135 Z" fill="url(#psHill1)"/>
    <path d="M0 96 Q80 84 160 94 Q210 100 240 90 L240 135 L0 135 Z" fill="url(#psHill2)"/>
    <path d="M0 110 Q90 100 170 108 Q210 114 240 106 L240 135 L0 135 Z" fill="url(#psHill3)"/>
    <!-- Flores do Campo Delicadas (Margaridas, Lavanda e Trevo) -->
    <g>
      <circle cx="32" cy="116" r="2.2" fill="#fff59d"/><circle cx="32" cy="116" r="4.2" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-dasharray="2,2"/>
      <circle cx="92" cy="120" r="1.8" fill="#fff59d"/><circle cx="92" cy="120" r="3.6" fill="none" stroke="#ffffff" stroke-width="1.6" stroke-dasharray="2,2"/>
      <circle cx="218" cy="118" r="2.2" fill="#fff59d"/><circle cx="218" cy="118" r="4.2" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-dasharray="2,2"/>
      <circle cx="56" cy="114" r="2.2" fill="#b794f4"/><circle cx="178" cy="115" r="2.2" fill="#b794f4"/>
      <circle cx="148" cy="122" r="1.8" fill="#f48fb1"/>
    </g>
    <!-- COELHINHO REALISTA MACIO ACONCHEGADO NA RELVA (Centro) -->
    <g class="lofi-bunny" transform="translate(122, 84)">
      <!-- Sombra do coelho na grama -->
      <ellipse cx="16" cy="26" rx="14" ry="4" fill="#0d2117" opacity="0.6"/>
      <!-- Corpo macio com degradê de pelagem -->
      <ellipse cx="14" cy="19" rx="10" ry="9" fill="#f5fdf7"/>
      <circle cx="23" cy="12" r="6.8" fill="#f5fdf7"/>
      <circle cx="4" cy="20" r="3.5" fill="#ffffff"/> <!-- Rabinho pompom -->
      <!-- Orelhas Macias com Interior Rosado e Movimento Realista -->
      <g class="lofi-bunny-ears">
        <ellipse cx="22" cy="3" rx="2.4" ry="6.8" fill="#f5fdf7" stroke="#e9d8fd" stroke-width="0.8"/>
        <ellipse cx="22" cy="3" rx="1.3" ry="4.8" fill="#fbb6ce"/>
        <ellipse cx="26" cy="3" rx="2.4" ry="6.8" fill="#f5fdf7" stroke="#e9d8fd" stroke-width="0.8"/>
        <ellipse cx="26" cy="3" rx="1.3" ry="4.8" fill="#fbb6ce"/>
      </g>
      <!-- Olhinho e Focinho Delicado -->
      <circle cx="26" cy="11" r="1.1" fill="#1b3d2e"/>
      <polygon points="28,13 29,14 27,14" fill="#fbb6ce"/>
      <!-- Ovo de Pascoa Decorado Delicadamente ao Lado do Coelho -->
      <ellipse cx="36" cy="22" rx="4.5" ry="6" fill="#b794f4"/>
      <line x1="32" y1="22" x2="40" y2="22" stroke="#faf089" stroke-width="1.3"/>
      <line x1="32.5" y1="20" x2="39.5" y2="20" stroke="#81e6d9" stroke-width="0.8"/>
    </g>
    <!-- Borboleta Colorida Esvoacante -->
    <g class="lofi-butterfly" transform="translate(68, 74)">
      <ellipse cx="3.5" cy="4" rx="3.5" ry="2.6" fill="#b794f4"/>
      <ellipse cx="3.5" cy="8.5" rx="2.6" ry="2.2" fill="#ffd54f"/>
      <line x1="0" y1="2" x2="0" y2="11" stroke="#1b3d2e" stroke-width="0.9"/>
    </g>
    <!-- Folhas de Grama Fresca Balancando com o Vento -->
    <g class="lofi-grass">
      <path d="M14 135 Q18 118 10 106 M24 135 Q20 120 28 110 M46 135 Q52 118 44 104" stroke="#48bb78" stroke-width="1.6" fill="none"/>
      <path d="M104 135 Q108 120 100 108 M116 135 Q112 116 120 104 M184 135 Q188 118 180 106" stroke="#38a169" stroke-width="1.6" fill="none"/>
    </g>
  </svg>
  <div class="lofi-caption">Brisa de Primavera | Manha Serena</div>
</div>
<div class="lofi-scene scene-default">
  <svg class="lofi-canvas-svg" viewBox="0 0 240 135" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Cenario Classico Lofi">
    <defs>
      <linearGradient id="defWoodDesk" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2a1a0e"/>
        <stop offset="50%" stop-color="#3d2716"/>
        <stop offset="100%" stop-color="#1c1108"/>
      </linearGradient>
      <radialGradient id="defLampBeam" cx="82%" cy="14%" r="85%">
        <stop offset="0%" stop-color="#fffde7" stop-opacity="0.85"/>
        <stop offset="35%" stop-color="#ffecb3" stop-opacity="0.5"/>
        <stop offset="70%" stop-color="#ffd54f" stop-opacity="0.2"/>
        <stop offset="100%" stop-color="#2a1a0e" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="defBrassMetal" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#ffffff"/>
        <stop offset="25%" stop-color="#fff275"/>
        <stop offset="65%" stop-color="#ffd700"/>
        <stop offset="100%" stop-color="#b38600"/>
      </linearGradient>
    </defs>
    <!-- Superficie da Escrivaninha de Mogno -->
    <rect width="240" height="135" fill="url(#defWoodDesk)"/>
    <!-- Cone Aconchegante de Luz da Luminaria de Mesa -->
    <rect class="lofi-lamp-warmth" width="240" height="135" fill="url(#defLampBeam)"/>
    <line x1="0" y1="104" x2="240" y2="104" stroke="#332216" stroke-width="1.6"/>
    <!-- Caderno de Estudos com Diagramas e Manuscrito (Esquerda) -->
    <g transform="translate(22, 74)">
      <polygon points="0,16 30,10 60,16 60,42 30,36 0,42" fill="#24180d" stroke="#7a5a26" stroke-width="1.2"/>
      <polygon points="2,17 29,11 29,35 2,39" fill="#f4ebd9"/>
      <polygon points="31,11 58,17 58,39 31,35" fill="#e8dac0"/>
      <line x1="6" y1="18" x2="25" y2="16" stroke="#8c7553" stroke-width="0.9"/>
      <line x1="6" y1="23" x2="25" y2="21" stroke="#8c7553" stroke-width="0.9"/>
      <line x1="6" y1="28" x2="20" y2="26" stroke="#8c7553" stroke-width="0.9"/>
      <!-- Esboco astronomico no caderno -->
      <circle cx="44" cy="24" r="5.5" fill="none" stroke="#8c7553" stroke-width="0.9"/>
      <line x1="44" y1="24" x2="48" y2="21" stroke="#8c7553" stroke-width="0.9"/>
      <ellipse cx="44" cy="24" rx="7" ry="2.5" fill="none" stroke="#8c7553" stroke-width="0.6"/>
    </g>
    <!-- ENGRENAGENS POLIDAS DE PRECISAO HEXTECH (Centro-Esquerda) -->
    <g class="lofi-cogs" transform="translate(100, 56)">
      <!-- Engrenagem Grande com Raios Abertos -->
      <g class="lofi-cog-large">
        <circle cx="0" cy="0" r="17" fill="none" stroke="url(#defBrassMetal)" stroke-width="4.5" stroke-dasharray="4.2,4.6"/>
        <circle cx="0" cy="0" r="13" fill="#171009" stroke="url(#defBrassMetal)" stroke-width="1.6"/>
        <line x1="-12" y1="0" x2="12" y2="0" stroke="url(#defBrassMetal)" stroke-width="1.4"/>
        <line x1="0" y1="-12" x2="0" y2="12" stroke="url(#defBrassMetal)" stroke-width="1.4"/>
        <circle cx="0" cy="0" r="3.5" fill="url(#defBrassMetal)"/>
      </g>
      <!-- Engrenagem Secundaria que Engrena e Contragira -->
      <g class="lofi-cog-small" transform="translate(24, 18)">
        <circle cx="0" cy="0" r="11" fill="none" stroke="url(#defBrassMetal)" stroke-width="3.5" stroke-dasharray="3.2,3.8"/>
        <circle cx="0" cy="0" r="8" fill="#171009" stroke="url(#defBrassMetal)" stroke-width="1.4"/>
        <circle cx="0" cy="0" r="2.5" fill="url(#defBrassMetal)"/>
      </g>
    </g>
    <!-- AMPULHETA DE CRISTAL E LATAO COM AREIA DOURADA REALISTA (Centro-Direita) -->
    <g class="lofi-hourglass" transform="translate(156, 42)">
      <!-- Placas superior e inferior usinadas -->
      <rect x="-16" y="0" width="32" height="4.5" rx="1.8" fill="url(#defBrassMetal)"/>
      <rect x="-16" y="60" width="32" height="4.5" rx="1.8" fill="url(#defBrassMetal)"/>
      <!-- Colunas de suporte de latao polido -->
      <line x1="-13" y1="4.5" x2="-13" y2="60" stroke="url(#defBrassMetal)" stroke-width="1.8"/>
      <line x1="13" y1="4.5" x2="13" y2="60" stroke="url(#defBrassMetal)" stroke-width="1.8"/>
      <!-- Bulbos de cristal transparente com brilho de vidro -->
      <path d="M-10 6 Q-10 23 0 32 Q10 23 10 6 Z" fill="#ffffff" fill-opacity="0.1" stroke="#d4af37" stroke-width="1"/>
      <path d="M-10 58 Q-10 41 0 32 Q10 41 10 58 Z" fill="#ffffff" fill-opacity="0.1" stroke="#d4af37" stroke-width="1"/>
      <!-- Areia dourada no bulbo superior -->
      <path d="M-8 14 Q0 26 8 14 Z" fill="#ffd54f"/>
      <!-- Fio contínuo de areia escorrendo pelo gargalo -->
      <line class="lofi-sand-stream" x1="0" y1="24" x2="0" y2="55" stroke="#ffd54f" stroke-width="1.6" stroke-dasharray="2.5,2"/>
      <!-- Monticulo de areia acumulada no bulbo inferior -->
      <path d="M-8 57 Q0 48 8 57 Z" fill="#ffd54f"/>
      <!-- Brilho especular no vidro -->
      <path d="M-7 10 Q-8 22 -3 28" stroke="#ffffff" stroke-width="0.8" fill="none" opacity="0.6"/>
      <path d="M7 38 Q8 50 3 56" stroke="#ffffff" stroke-width="0.8" fill="none" opacity="0.6"/>
    </g>
    <!-- Luminaria de Leitura Shaded Brass Lamp (Extremo Direito) -->
    <g transform="translate(212, 14)">
      <path d="M14 90 L14 24 Q14 12 -6 10" stroke="url(#defBrassMetal)" stroke-width="3.5" fill="none"/>
      <ellipse cx="-9" cy="14" rx="13" ry="6.5" fill="url(#defBrassMetal)"/>
      <circle cx="-9" cy="17" r="4.5" fill="#fff9c4"/>
    </g>
  </svg>
  <div class="lofi-caption">Oficina do Relojoeiro | Foco Suave</div>
</div>
<div class="lofi-player" id="lofi-player">
  <div class="yt-audio-host" aria-hidden="true">
    <div id="yt-player-music"></div>
    <div id="yt-player-fire"></div>
    <div id="yt-player-rain"></div>
    <div id="yt-player-vinyl"></div>
  </div>
  <div class="lofi-player-track">
    <div class="lofi-eq" id="lofi-eq" aria-hidden="true">
      <span class="lofi-eq-bar"></span>
      <span class="lofi-eq-bar"></span>
      <span class="lofi-eq-bar"></span>
    </div>
    <div class="lofi-track-info">
      <div class="lofi-track-title" id="lofi-track-title">Lofi Girl - Beats to Relax / Study</div>
      <div class="lofi-track-sub" id="lofi-track-sub">Audio Oficial Lofi Girl (YouTube)</div>
    </div>
  </div>
  <div class="lofi-controls">
    <button type="button" class="lofi-btn-play" id="lofi-btn-play" onclick="toggleLofiPlay()" title="Tocar / Pausar Musica Lofi">
      <svg class="lofi-ico-play" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg>
      <svg class="lofi-ico-pause" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
      <span id="lofi-play-label">Ouvir Lofi</span>
    </button>
    <div class="lofi-vol-wrap">
      <button type="button" class="lofi-btn-vol" id="lofi-btn-vol" onclick="toggleLofiMute()" title="Silenciar / Ativar Som">
        <svg class="lofi-ico-vol" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        <svg class="lofi-ico-mute" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/></svg>
      </button>
      <input type="range" class="lofi-slider" id="lofi-slider" min="0" max="100" value="50" oninput="setLofiVolume(this.value)" title="Volume Geral">
    </div>
  </div>
  <div class="lofi-ambient-row">
    <button type="button" class="lofi-pill active" id="lofi-pill-vinyl" onclick="toggleLofiAmbient('vinyl')" title="Chiado de vinil vintage (YouTube: NIP3fNueJMA)">Vinil</button>
    <button type="button" class="lofi-pill" id="lofi-pill-rain" onclick="toggleLofiAmbient('rain')" title="Chuva na janela (YouTube: V6V080RVeAE)">Chuva</button>
    <button type="button" class="lofi-pill" id="lofi-pill-fire" onclick="toggleLofiAmbient('fire')" title="Lareira estalando (YouTube: UgHKb_7884o)">Lareira</button>
  </div>
</div>'''
)

# ----------------------------------------------------------------------------------------------------------------------
# JS EARLY: aplica estado dos efeitos, menu e tema antes da primeira pintura (evita "piscar" ao recarregar).
# ----------------------------------------------------------------------------------------------------------------------
EARLY_JS = r"""
(function () {
  try {
    var root = document.documentElement;
    var fx = localStorage.getItem('jirabot_fx_paused');
    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (fx === '1' || (fx === null && reduced)) root.classList.add('fx-paused');
    if (localStorage.getItem('jirabot_sidebar_collapsed') === '1') root.classList.add('sidebar-collapsed');

    // Resolucao de tema antecipada para evitar flash ao abrir
    var pref = localStorage.getItem('jirabot_theme_pref') || localStorage.getItem('jirabot_theme') || 'auto';
    var eff = pref;
    if (pref === 'auto') {
      var now = new Date();
      var m = now.getMonth() + 1;
      var d = now.getDate();
      if ((m === 10 && d >= 1) || (m === 11 && d <= 3)) eff = 'halloween';
      else if (m === 12 && d >= 1 && d <= 26) eff = 'natal';
      else if ((m === 12 && d >= 27) || (m === 1 && d <= 6)) eff = 'ano_novo';
      else if ((m === 3 && d >= 20) || (m === 4 && d <= 25)) eff = 'pascoa';
      else eff = 'dark';
    }
    root.setAttribute('data-theme', eff);
    root.setAttribute('data-theme-preference', pref);
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

[data-theme="halloween"] {
  color-scheme: dark;
  --bg-body: #0a0512;
  --bg-solid: #150a24;
  --bg-card: #150a24;
  --bg-subtle: #1e0f33;
  --bg-input: #0e0618;
  --bg-input-readonly: #1a0c2b;
  --text-main: #f5edfc;
  --text-secondary: #d8b4fe;
  --text-muted: #9d7dbf;
  --border-color: #381959;
  --border-strong: #5a288e;
  --primary: #ff7518;
  --primary-hover: #ff9138;
  --primary-light: rgba(255, 117, 24, 0.16);
  --primary-text: #ffa048;
  --on-primary: #150a24;
  --gold: #ff7518;
  --gold-bright: #ffa34d;
  --gold-deep: #b34700;
  --success: #22c55e;
  --success-bg: rgba(34, 197, 94, 0.16);
  --warning: #eab308;
  --warning-bg: rgba(234, 179, 8, 0.16);
  --danger: #ef4444;
  --danger-bg: rgba(239, 68, 68, 0.16);
  --info: #a855f7;
  --info-bg: rgba(168, 85, 247, 0.16);
  --shadow: 0 6px 24px rgba(10, 5, 18, 0.6);
  --topbar-bg: #0d0617;
  --glow-1: rgba(255, 117, 24, 0.16);
  --glow-2: rgba(168, 85, 247, 0.14);
  --vignette: rgba(6, 2, 10, 0.55);
  --spot: rgba(255, 120, 25, 0.12);
  --glow-card: rgba(255, 117, 24, 0.18);
  --ember-rgb: 255, 125, 25;
  --fx-mode: embers;
  --btn-primary-from: #ffa34d;
  --btn-primary-to: #e65c00;
  --chart-1: #ff7518;
  --chart-2: #a855f7;
  --chart-3: #22c55e;
  --chart-4: #9d7dbf;
  --chart-5: #eab308;
  --bg-sidebar: #09040f;
  --bg-sidebar-hover: #180b29;
  --nav-text: #d8b4fe;
  --nav-text-hover: #ffffff;
  --side-gold: #ff7518;
  --side-border: rgba(255, 117, 24, 0.22);
}

[data-theme="natal"] {
  color-scheme: dark;
  --bg-body: #06120d;
  --bg-solid: #0c2018;
  --bg-card: #0c2018;
  --bg-subtle: #122c21;
  --bg-input: #081711;
  --bg-input-readonly: #10241b;
  --text-main: #f0fff4;
  --text-secondary: #c6f6d5;
  --text-muted: #82a893;
  --border-color: #1e4a37;
  --border-strong: #2c6e52;
  --primary: #e63946;
  --primary-hover: #ff4d5e;
  --primary-light: rgba(230, 57, 70, 0.16);
  --primary-text: #ff6b78;
  --on-primary: #ffffff;
  --gold: #ffd166;
  --gold-bright: #ffe399;
  --gold-deep: #b56a29;
  --success: #2ec4b6;
  --success-bg: rgba(46, 196, 182, 0.16);
  --warning: #ffd166;
  --warning-bg: rgba(255, 209, 102, 0.16);
  --danger: #e63946;
  --danger-bg: rgba(230, 57, 70, 0.18);
  --info: #48cae4;
  --info-bg: rgba(72, 202, 228, 0.16);
  --shadow: 0 6px 24px rgba(4, 14, 10, 0.6);
  --topbar-bg: #071610;
  --glow-1: rgba(230, 57, 70, 0.14);
  --glow-2: rgba(46, 196, 182, 0.12);
  --vignette: rgba(3, 9, 6, 0.55);
  --spot: rgba(255, 215, 120, 0.12);
  --glow-card: rgba(230, 57, 70, 0.16);
  --ember-rgb: 235, 245, 255;
  --fx-mode: snow;
  --btn-primary-from: #ff5263;
  --btn-primary-to: #c72030;
  --chart-1: #e63946;
  --chart-2: #2ec4b6;
  --chart-3: #ffd166;
  --chart-4: #82a893;
  --chart-5: #48cae4;
  --bg-sidebar: #050e0a;
  --bg-sidebar-hover: #0f241b;
  --nav-text: #c6f6d5;
  --nav-text-hover: #ffffff;
  --side-gold: #ffd166;
  --side-border: rgba(255, 209, 102, 0.22);
}

[data-theme="ano_novo"] {
  color-scheme: dark;
  --bg-body: #050814;
  --bg-solid: #0d142b;
  --bg-card: #0d142b;
  --bg-subtle: #131d3d;
  --bg-input: #090d1c;
  --bg-input-readonly: #111a36;
  --text-main: #f8fafc;
  --text-secondary: #cbd5e1;
  --text-muted: #7e8fa6;
  --border-color: #1f2e54;
  --border-strong: #2f457d;
  --primary: #ffd700;
  --primary-hover: #ffe24d;
  --primary-light: rgba(255, 215, 0, 0.15);
  --primary-text: #ffe066;
  --on-primary: #050814;
  --gold: #ffd700;
  --gold-bright: #fff275;
  --gold-deep: #b39200;
  --success: #38bdf8;
  --success-bg: rgba(56, 189, 248, 0.16);
  --warning: #fbbf24;
  --warning-bg: rgba(251, 191, 36, 0.16);
  --danger: #f43f5e;
  --danger-bg: rgba(244, 63, 94, 0.16);
  --info: #818cf8;
  --info-bg: rgba(129, 140, 248, 0.16);
  --shadow: 0 6px 24px rgba(3, 5, 14, 0.6);
  --topbar-bg: #070a1a;
  --glow-1: rgba(255, 215, 0, 0.15);
  --glow-2: rgba(96, 165, 250, 0.12);
  --vignette: rgba(2, 3, 10, 0.6);
  --spot: rgba(255, 225, 120, 0.14);
  --glow-card: rgba(255, 215, 0, 0.18);
  --ember-rgb: 255, 225, 110;
  --fx-mode: sparkle;
  --btn-primary-from: #fff07a;
  --btn-primary-to: #d4a900;
  --chart-1: #ffd700;
  --chart-2: #38bdf8;
  --chart-3: #818cf8;
  --chart-4: #7e8fa6;
  --chart-5: #fbbf24;
  --bg-sidebar: #040610;
  --bg-sidebar-hover: #0e1630;
  --nav-text: #cbd5e1;
  --nav-text-hover: #ffffff;
  --side-gold: #ffd700;
  --side-border: rgba(255, 215, 0, 0.24);
}

[data-theme="pascoa"] {
  color-scheme: dark;
  --bg-body: #0b140f;
  --bg-solid: #13221b;
  --bg-card: #13221b;
  --bg-subtle: #1c3026;
  --bg-input: #0e1a14;
  --bg-input-readonly: #162920;
  --text-main: #f0fff4;
  --text-secondary: #d6bcfa;
  --text-muted: #84a693;
  --border-color: #244737;
  --border-strong: #33664e;
  --primary: #48bb78;
  --primary-hover: #68d391;
  --primary-light: rgba(72, 187, 120, 0.16);
  --primary-text: #68d391;
  --on-primary: #0b140f;
  --gold: #ecc94b;
  --gold-bright: #faf089;
  --gold-deep: #b7791f;
  --success: #38a169;
  --success-bg: rgba(56, 161, 105, 0.16);
  --warning: #ecc94b;
  --warning-bg: rgba(236, 201, 75, 0.16);
  --danger: #f56565;
  --danger-bg: rgba(245, 101, 101, 0.16);
  --info: #b794f4;
  --info-bg: rgba(183, 148, 244, 0.16);
  --shadow: 0 6px 24px rgba(6, 14, 10, 0.55);
  --topbar-bg: #0d1712;
  --glow-1: rgba(72, 187, 120, 0.14);
  --glow-2: rgba(183, 148, 244, 0.12);
  --vignette: rgba(4, 9, 7, 0.5);
  --spot: rgba(120, 220, 160, 0.12);
  --glow-card: rgba(72, 187, 120, 0.18);
  --ember-rgb: 170, 230, 185;
  --fx-mode: petals;
  --btn-primary-from: #68d391;
  --btn-primary-to: #38a169;
  --chart-1: #48bb78;
  --chart-2: #b794f4;
  --chart-3: #ecc94b;
  --chart-4: #84a693;
  --chart-5: #38a169;
  --bg-sidebar: #070e0a;
  --bg-sidebar-hover: #122119;
  --nav-text: #c6f6d5;
  --nav-text-hover: #ffffff;
  --side-gold: #ecc94b;
  --side-border: rgba(236, 201, 75, 0.22);
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
  position: relative;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: block;
  filter: drop-shadow(0 0 8px rgba(200, 170, 110, 0.4));
  will-change: transform, opacity;
}

.brand-theme-badge {
  display: none !important;
  visibility: hidden !important;
  pointer-events: none !important;
  width: 0 !important;
  height: 0 !important;
  overflow: hidden !important;
}

.brand-logo .theme-logo {
  display: none;
  width: 100%;
  height: 100%;
}

html:not([data-theme]) .brand-logo .theme-logo.logo-default,
[data-theme="dark"] .brand-logo .theme-logo.logo-default,
[data-theme="light"] .brand-logo .theme-logo.logo-default {
  display: block;
}

[data-theme="halloween"] .brand-logo .theme-logo.logo-halloween {
  display: block;
}

[data-theme="natal"] .brand-logo .theme-logo.logo-natal {
  display: block;
}

[data-theme="ano_novo"] .brand-logo .theme-logo.logo-ano_novo {
  display: block;
}

[data-theme="pascoa"] .brand-logo .theme-logo.logo-pascoa {
  display: block;
}

[data-theme="halloween"] .brand-logo {
  filter: drop-shadow(0 0 10px rgba(255, 117, 24, 0.65));
}

[data-theme="natal"] .brand-logo {
  filter: drop-shadow(0 0 10px rgba(230, 57, 70, 0.55));
}

[data-theme="ano_novo"] .brand-logo {
  filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.65));
}

[data-theme="pascoa"] .brand-logo {
  filter: drop-shadow(0 0 10px rgba(72, 187, 120, 0.55));
}

.brand-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display) !important;
  font-size: 20px !important;
  font-weight: 700 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  line-height: 1.15 !important;
  margin: 0 !important;
  padding: 0 !important;
}

.brand-title .brand-name {
  font-family: var(--font-display) !important;
  font-size: 20px !important;
  font-weight: 700 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  display: inline-block !important;
  background: linear-gradient(180deg, #fbefc9 0%, #c8aa6e 55%, #8f6d30 100%) !important;
  -webkit-background-clip: text !important;
  background-clip: text !important;
  -webkit-text-fill-color: transparent !important;
  color: #c8aa6e !important;
}

.brand-title-icon {
  display: none;
  width: 28px !important;
  height: 28px !important;
  flex-shrink: 0;
  vertical-align: middle;
  filter: drop-shadow(0 2px 7px rgba(0, 0, 0, 0.55));
}

[data-theme="halloween"] .brand-title-icon.title-icon-halloween {
  display: inline-block;
  animation: titleIconFloat 3.2s ease-in-out infinite alternate;
}

[data-theme="natal"] .brand-title-icon.title-icon-natal {
  display: inline-block;
  animation: titleIconFloat 3.2s ease-in-out infinite alternate;
}

[data-theme="ano_novo"] .brand-title-icon.title-icon-ano_novo {
  display: inline-block;
  animation: titleIconFloat 3.2s ease-in-out infinite alternate;
}

[data-theme="pascoa"] .brand-title-icon.title-icon-pascoa {
  display: inline-block;
  animation: titleIconFloat 3.2s ease-in-out infinite alternate;
}

@keyframes titleIconFloat {
  0% { transform: translateY(0px) rotate(0deg); }
  50% { transform: translateY(-2px) rotate(3deg); }
  100% { transform: translateY(0px) rotate(0deg); }
}

html.sidebar-collapsed .brand-title-icon {
  display: none !important;
}

html:not(.fx-paused) .brand-logo {
  animation: fx-logo-glow 4.8s ease-in-out infinite;
}

/* ==================== CENARIOS ACONCHEGANTES ESTILO LOFI GIRL ==================== */
.sidebar-lofi-wrap {
  margin: 10px 12px 12px;
  background: #140f0a !important;
  border: 1px solid rgba(200, 170, 110, 0.28) !important;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.5);
  transition: opacity 0.3s ease;
}

html.sidebar-collapsed .sidebar-lofi-wrap {
  display: none !important;
}

.lofi-scene {
  display: none;
  width: 100%;
  position: relative;
}

[data-theme="halloween"] .lofi-scene.scene-halloween { display: block; }
[data-theme="natal"] .lofi-scene.scene-natal { display: block; }
[data-theme="ano_novo"] .lofi-scene.scene-ano_novo { display: block; }
[data-theme="pascoa"] .lofi-scene.scene-pascoa { display: block; }
html:not([data-theme]) .lofi-scene.scene-default,
[data-theme="dark"] .lofi-scene.scene-default,
[data-theme="light"] .lofi-scene.scene-default { display: block; }

.lofi-canvas-svg {
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: 16 / 9;
}

.lofi-caption {
  padding: 6px 10px 7px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-align: center;
  color: #f6e6b4 !important;
  background: rgba(12, 8, 5, 0.88) !important;
  border-top: 1px solid rgba(200, 170, 110, 0.25) !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ==================== REPRODUTOR DE AUDIO LOFI TEMATIZADO ==================== */
.lofi-player {
  background: rgba(14, 10, 6, 0.94);
  border-top: 1px solid rgba(200, 170, 110, 0.22);
  padding: 8px 10px 9px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  user-select: none;
}

.lofi-player-track {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lofi-eq {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.lofi-eq-bar {
  width: 3px;
  height: 4px;
  background: var(--gold-bright, #c9a050);
  border-radius: 1px;
  transition: height 0.15s ease;
}

.lofi-player.is-playing .lofi-eq-bar:nth-child(1) {
  animation: lofiEqPulse1 0.75s ease-in-out infinite alternate;
}
.lofi-player.is-playing .lofi-eq-bar:nth-child(2) {
  animation: lofiEqPulse2 0.6s ease-in-out infinite alternate 0.2s;
}
.lofi-player.is-playing .lofi-eq-bar:nth-child(3) {
  animation: lofiEqPulse3 0.85s ease-in-out infinite alternate 0.4s;
}

@keyframes lofiEqPulse1 { from { height: 3px; } to { height: 13px; } }
@keyframes lofiEqPulse2 { from { height: 5px; } to { height: 11px; } }
@keyframes lofiEqPulse3 { from { height: 4px; } to { height: 14px; } }

html.fx-paused .lofi-player.is-playing .lofi-eq-bar {
  animation: none !important;
  height: 9px !important;
}

.lofi-track-info {
  flex: 1;
  min-width: 0;
}

.lofi-track-title {
  font-size: 11.5px;
  font-weight: 700;
  color: #fff4d1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.25;
}

.lofi-track-sub {
  font-size: 10px;
  color: #c2b088;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}

.lofi-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.lofi-btn-play {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  background: linear-gradient(135deg, rgba(200, 160, 60, 0.25), rgba(120, 90, 30, 0.35));
  border: 1px solid rgba(212, 175, 55, 0.45);
  border-radius: 6px;
  color: #fff2c4;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.lofi-btn-play:hover {
  background: linear-gradient(135deg, rgba(200, 160, 60, 0.45), rgba(140, 105, 35, 0.55));
  border-color: rgba(230, 195, 75, 0.7);
  color: #ffffff;
}

.lofi-player .lofi-ico-pause { display: none; }
.lofi-player .lofi-ico-play { display: inline-block; }
.lofi-player.is-playing .lofi-ico-play { display: none; }
.lofi-player.is-playing .lofi-ico-pause { display: inline-block; }

.lofi-vol-wrap {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.lofi-btn-vol {
  background: none;
  border: none;
  color: #c2b088;
  cursor: pointer;
  padding: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s ease;
}

.lofi-btn-vol:hover {
  color: #fff2c4;
}

.lofi-player .lofi-ico-mute { display: none; }
.lofi-player .lofi-ico-vol { display: inline-block; }
.lofi-player.is-muted .lofi-ico-vol { display: none; }
.lofi-player.is-muted .lofi-ico-mute { display: inline-block; }

.lofi-slider {
  width: 54px;
  height: 4px;
  -webkit-appearance: none;
  background: rgba(200, 170, 110, 0.25);
  border-radius: 2px;
  outline: none;
}

.lofi-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #e6c34b;
  cursor: pointer;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
}

.lofi-ambient-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.lofi-pill {
  flex: 1;
  text-align: center;
  font-size: 9.5px;
  font-weight: 600;
  padding: 2px 4px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(200, 170, 110, 0.18);
  border-radius: 4px;
  color: #a89a80;
  cursor: pointer;
  transition: all 0.18s ease;
}

.lofi-pill:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #e6d3a8;
}

.lofi-pill.active {
  background: rgba(200, 160, 60, 0.22);
  border-color: rgba(212, 175, 55, 0.5);
  color: #fff2c4;
}

.lofi-link-yt {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.yt-audio-host {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0.001;
  pointer-events: none;
  overflow: hidden;
  left: -9999px;
  top: -9999px;
}

/* ==================== ANIMATION KEYFRAMES ==================== */
/* Halloween */
html:not(.fx-paused) .lofi-pumpkin-glow {
  animation: lofiPumpkinFlicker 3s ease-in-out infinite;
  transform-origin: center;
}
@keyframes lofiPumpkinFlicker {
  0%, 100% { opacity: 0.85; filter: drop-shadow(0 0 3px rgba(255, 140, 0, 0.6)); }
  45% { opacity: 1; filter: drop-shadow(0 0 8px rgba(255, 220, 50, 0.95)); }
  75% { opacity: 0.9; filter: drop-shadow(0 0 4px rgba(255, 120, 0, 0.7)); }
}

html:not(.fx-paused) .lofi-cat-tail {
  animation: lofiCatTail 4s ease-in-out infinite alternate;
  transform-origin: 14px 20px;
}
@keyframes lofiCatTail {
  0% { transform: rotate(-6deg); }
  100% { transform: rotate(12deg); }
}

html:not(.fx-paused) .lofi-cat-eyes {
  animation: lofiCatBlink 4.5s ease-in-out infinite;
  transform-origin: 9px 7px;
}
@keyframes lofiCatBlink {
  0%, 92%, 100% { transform: scaleY(1); }
  96% { transform: scaleY(0.1); }
}

html:not(.fx-paused) .lofi-wheat-1 {
  animation: lofiWheatSway1 4.2s ease-in-out infinite alternate;
  transform-origin: bottom center;
}
@keyframes lofiWheatSway1 {
  0% { transform: rotate(-2deg); }
  100% { transform: rotate(3deg); }
}

html:not(.fx-paused) .lofi-wheat-2 {
  animation: lofiWheatSway2 3.8s ease-in-out infinite alternate;
  transform-origin: bottom center;
}
@keyframes lofiWheatSway2 {
  0% { transform: rotate(2.5deg); }
  100% { transform: rotate(-2.5deg); }
}

html:not(.fx-paused) .lofi-ember-1 {
  animation: lofiEmberDrift1 3.5s ease-in infinite;
}
html:not(.fx-paused) .lofi-ember-2 {
  animation: lofiEmberDrift2 4.2s ease-in infinite 1.2s;
}
html:not(.fx-paused) .lofi-ember-3 {
  animation: lofiEmberDrift1 4.8s ease-in infinite 2.1s;
}
@keyframes lofiEmberDrift1 {
  0% { transform: translateY(0) translateX(0); opacity: 0; }
  30% { opacity: 0.85; }
  80% { opacity: 0.6; }
  100% { transform: translateY(-26px) translateX(6px); opacity: 0; }
}
@keyframes lofiEmberDrift2 {
  0% { transform: translateY(0) translateX(0); opacity: 0; }
  25% { opacity: 0.9; }
  75% { opacity: 0.5; }
  100% { transform: translateY(-24px) translateX(-5px); opacity: 0; }
}

/* Natal */
html:not(.fx-paused) .lofi-fire-flames {
  animation: lofiFireFlicker 2.6s ease-in-out infinite;
  transform-origin: 70px 114px;
}
@keyframes lofiFireFlicker {
  0%, 100% { transform: scaleY(0.95) skewX(-1.5deg); opacity: 0.92; }
  35% { transform: scaleY(1.06) skewX(2deg); opacity: 1; }
  70% { transform: scaleY(0.97) skewX(-1deg); opacity: 0.95; }
}

html:not(.fx-paused) .lofi-hearth-glow {
  animation: lofiHearthPulse 3.2s ease-in-out infinite;
}
@keyframes lofiHearthPulse {
  0%, 100% { opacity: 0.65; }
  50% { opacity: 0.95; }
}

html:not(.fx-paused) .lofi-window-snow {
  animation: lofiWindowSnowFall 3.8s linear infinite;
}
@keyframes lofiWindowSnowFall {
  0% { transform: translateY(-20px) translateX(0); }
  100% { transform: translateY(45px) translateX(-10px); }
}

html:not(.fx-paused) .lofi-steam {
  animation: lofiSteamRise 3s ease-out infinite;
}
@keyframes lofiSteamRise {
  0% { transform: translateY(0) scaleX(0.85); opacity: 0; }
  30% { opacity: 0.7; }
  100% { transform: translateY(-12px) scaleX(1.3); opacity: 0; }
}

/* Ano Novo */
html:not(.fx-paused) .lofi-stars circle {
  animation: lofiStarTwinkle 2.8s ease-in-out infinite alternate;
}
html:not(.fx-paused) .lofi-stars circle:nth-child(2n) {
  animation-delay: 1.4s;
}
@keyframes lofiStarTwinkle {
  0% { opacity: 0.35; transform: scale(0.85); }
  100% { opacity: 1; transform: scale(1.15); }
}

html:not(.fx-paused) .lofi-firework-1 {
  animation: lofiFireworkBurst1 4s cubic-bezier(0.1, 0.7, 0.3, 1) infinite;
  transform-origin: 65px 36px;
}
@keyframes lofiFireworkBurst1 {
  0% { transform: translate(65px, 36px) scale(0.1); opacity: 0; }
  15% { opacity: 1; }
  65% { transform: translate(65px, 36px) scale(1.05); opacity: 0.8; }
  100% { transform: translate(65px, 36px) scale(1.2); opacity: 0; }
}

html:not(.fx-paused) .lofi-firework-2 {
  animation: lofiFireworkBurst2 4s cubic-bezier(0.1, 0.7, 0.3, 1) infinite 2s;
  transform-origin: 170px 30px;
}
@keyframes lofiFireworkBurst2 {
  0% { transform: translate(170px, 30px) scale(0.1); opacity: 0; }
  15% { opacity: 1; }
  65% { transform: translate(170px, 30px) scale(1.05); opacity: 0.8; }
  100% { transform: translate(170px, 30px) scale(1.2); opacity: 0; }
}

html:not(.fx-paused) .lofi-lantern-glow {
  animation: lofiLanternPulse 3.4s ease-in-out infinite;
}
@keyframes lofiLanternPulse {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 0.95; }
}

/* Pascoa */
html:not(.fx-paused) .lofi-bunny-ears {
  animation: lofiBunnyEarTwitch 5s ease-in-out infinite;
  transform-origin: 23px 10px;
}
@keyframes lofiBunnyEarTwitch {
  0%, 82%, 100% { transform: rotate(0deg); }
  86% { transform: rotate(-7deg); }
  92% { transform: rotate(4deg); }
}

html:not(.fx-paused) .lofi-butterfly {
  animation: lofiButterflyFly 5s ease-in-out infinite alternate;
}
@keyframes lofiButterflyFly {
  0% { transform: translate(70px, 78px) scaleX(1); }
  25% { transform: translate(73px, 73px) scaleX(0.4); }
  50% { transform: translate(78px, 76px) scaleX(1); }
  75% { transform: translate(74px, 71px) scaleX(0.3); }
  100% { transform: translate(70px, 78px) scaleX(1); }
}

html:not(.fx-paused) .lofi-cloud {
  animation: lofiCloudMove 12s ease-in-out infinite alternate;
}
@keyframes lofiCloudMove {
  0% { transform: translateX(0); }
  100% { transform: translateX(20px); }
}

html:not(.fx-paused) .lofi-grass path {
  animation: lofiGrassWind 3.6s ease-in-out infinite alternate;
  transform-origin: bottom center;
}
@keyframes lofiGrassWind {
  0% { transform: rotate(-2deg); }
  100% { transform: rotate(3deg); }
}

/* Classico / Default */
html:not(.fx-paused) .lofi-cog-large {
  animation: lofiCogRotate 14s linear infinite;
  transform-origin: 0 0;
}
html:not(.fx-paused) .lofi-cog-small {
  animation: lofiCogRotateRev 9.3s linear infinite;
  transform-origin: 0 0;
}
@keyframes lofiCogRotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes lofiCogRotateRev {
  from { transform: translate(22px, 16px) rotate(0deg); }
  to { transform: translate(22px, 16px) rotate(-360deg); }
}

html:not(.fx-paused) .lofi-sand-stream {
  animation: lofiSandPulse 1.8s ease-in-out infinite;
}
@keyframes lofiSandPulse {
  0%, 100% { opacity: 0.9; }
  50% { opacity: 0.45; }
}

html:not(.fx-paused) .lofi-lamp-warmth {
  animation: lofiLampBreathe 4.5s ease-in-out infinite alternate;
}
@keyframes lofiLampBreathe {
  0% { opacity: 0.75; }
  100% { opacity: 1; }
}

/* Reducao de movimento e pausa global */
html.fx-paused .lofi-scene * {
  animation: none !important;
  animation-play-state: paused !important;
}

/* ==================== SELETOR DE TEMAS DROPDOWN ==================== */
.theme-dropdown-wrap {
  position: relative;
  display: inline-block;
}

.theme-selector-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-main);
  transition: all 0.2s var(--ease);
}

.theme-selector-btn:hover {
  border-color: var(--primary);
  background: var(--bg-subtle);
  color: var(--primary);
}

.theme-icon-slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--primary);
}

.theme-icon-slot svg {
  width: 16px;
  height: 16px;
}

.theme-caret {
  transition: transform 0.2s ease;
  opacity: 0.7;
}

.theme-dropdown-wrap.open .theme-caret {
  transform: rotate(180deg);
}

.theme-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 250px;
  background: var(--bg-solid);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  padding: 8px 6px;
  z-index: 1000;
  display: none;
  backdrop-filter: blur(12px);
  opacity: 1;
}

@keyframes themeMenuPop {
  from { opacity: 0; transform: translateY(-6px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

html:not(.fx-paused) .theme-dropdown-wrap.open .theme-menu {
  animation: themeMenuPop 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}

.theme-dropdown-wrap.open .theme-menu {
  display: block;
}

html.fx-paused .theme-menu,
html.fx-paused .theme-dropdown-wrap.open .theme-menu {
  animation: none !important;
  opacity: 1 !important;
  transform: none !important;
  visibility: visible !important;
}

.theme-menu-header {
  padding: 6px 10px 4px 10px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.theme-menu-group-label {
  padding: 8px 10px 4px 10px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.theme-menu-divider {
  height: 1px;
  background: var(--border-color);
  margin: 6px 4px;
}

.theme-menu-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius);
  color: var(--text-main);
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: var(--font-body);
}

.theme-menu-item:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--text-main);
}

.theme-menu-item.active {
  background: var(--primary-light);
  border-color: var(--primary);
  box-shadow: inset 0 0 0 1px var(--primary);
}

.theme-menu-item svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: var(--primary);
}

.theme-item-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.theme-item-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}

.theme-item-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.theme-menu-item.active .theme-item-title {
  color: var(--primary);
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

.brand-text span#sidebar-version-label,
.brand-text span.brand-version {
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

/* ==================== GRUPOS E DROPDOWNS DO MENU LATERAL ==================== */
.nav-section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--nav-text-muted, #8a7c64);
  padding: 10px 14px 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}

.nav-group {
  display: flex;
  flex-direction: column;
  margin-bottom: 2px;
}

.nav-group-toggle {
  width: 100%;
  background: transparent;
  border: none;
  color: var(--nav-text);
  padding: 10px 12px;
  border-radius: 4px;
  text-align: left;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  transition: background-color 0.2s ease, color 0.2s ease;
  user-select: none;
}

.nav-group-toggle:hover {
  background-color: var(--bg-sidebar-hover);
  color: var(--nav-text-hover);
}

.nav-group-title {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}

.nav-group-title svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
  flex-shrink: 0;
  transition: transform 0.25s var(--ease), filter 0.25s ease;
}

.nav-group-toggle:hover .nav-group-title svg {
  transform: scale(1.08);
  filter: drop-shadow(0 0 5px rgba(200, 170, 110, 0.5));
}

.nav-group-caret {
  width: 13px;
  height: 13px;
  stroke: currentColor;
  transition: transform 0.28s var(--ease);
  flex-shrink: 0;
  opacity: 0.65;
}

.nav-group.is-open .nav-group-caret {
  transform: rotate(180deg);
  opacity: 1;
}

.nav-group-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: 10px;
  margin-left: 16px;
  border-left: 1px solid rgba(200, 170, 110, 0.22);
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 0.32s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s ease, margin 0.25s ease;
}

.nav-group.is-open .nav-group-items {
  max-height: 300px;
  opacity: 1;
  margin-top: 2px;
  margin-bottom: 6px;
}

.nav-sub-btn {
  padding: 8px 12px !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  gap: 9px !important;
  border-radius: 3px !important;
}

.nav-sub-btn svg {
  width: 15px !important;
  height: 15px !important;
  opacity: 0.85;
}

.nav-sub-btn.active {
  background: rgba(200, 170, 110, 0.16) !important;
  color: #f6e8c6 !important;
  font-weight: 600 !important;
}

.nav-sub-btn.active svg {
  color: #f0d9a0 !important;
}

.sidebar-footer {
  padding: 12px 14px;
  font-size: 12px;
  color: #8f8368;
  position: relative;
  white-space: nowrap;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sidebar-footer-left {
  min-width: 0;
  flex: 1;
  overflow: hidden;
}

.lofi-footer-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  background: transparent;
  border: none;
  border-radius: 50%;
  text-decoration: none;
  flex-shrink: 0;
  transition: transform 0.2s ease, filter 0.2s ease;
  user-select: none;
  line-height: 1;
}

.lofi-footer-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  display: block;
  border: 1.5px solid rgba(212, 175, 55, 0.4);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.lofi-footer-btn:hover .lofi-footer-avatar {
  transform: scale(1.12);
  border-color: var(--primary);
  box-shadow: 0 0 10px rgba(212, 175, 55, 0.6);
}

html.sidebar-collapsed .lofi-footer-btn {
  display: none !important;
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
  html.sidebar-collapsed .footer-text,
  html.sidebar-collapsed .nav-group-caret,
  html.sidebar-collapsed .nav-section-label {
    max-width: 0;
    opacity: 0;
    display: none !important;
  }
  html.sidebar-collapsed .nav-btn,
  html.sidebar-collapsed .nav-group-toggle {
    gap: 0;
    padding-left: 29px;
    padding-right: 0;
  }
  html.sidebar-collapsed .nav-group-items {
    padding-left: 0;
    margin-left: 0;
    border-left: none;
  }
  html.sidebar-collapsed .nav-sub-btn {
    padding-left: 29px !important;
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

/* ==================== ABA: GESTAO DE TICKETS E DDS ==================== */
.tickets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.ticket-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  position: relative;
}

.ticket-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
  transform: translateY(-2px);
}

.ticket-card.is-active-bot {
  border-color: var(--gold);
  box-shadow: 0 0 16px rgba(245, 158, 11, 0.35);
  background: linear-gradient(180deg, rgba(200, 160, 60, 0.08) 0%, var(--bg-card) 100%);
}

.ticket-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.ticket-key-link {
  font-family: var(--font-heading);
  font-weight: 700;
  font-size: 13px;
  color: var(--primary);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.ticket-key-link:hover {
  text-decoration: underline;
  color: var(--primary-hover);
}

.ticket-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.4;
  margin: 4px 0 0 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ticket-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--text-muted);
}

.ticket-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--border-color);
  padding-top: 10px;
  margin-top: auto;
}

.badge-dds {
  background: rgba(14, 165, 233, 0.16);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.35);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.badge-parent {
  background: rgba(147, 51, 234, 0.15);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.35);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  text-decoration: none;
}

.parent-info-banner {
  background: rgba(147, 51, 234, 0.08);
  border: 1px solid rgba(168, 85, 247, 0.28);
  border-radius: var(--radius);
  padding: 9px 14px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--text-main);
}

.parent-link-pill {
  color: #c084fc;
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}

/* ==================== VISTA EM ARVORE HIERARQUICA (TICKETS PAI / FILHO) ==================== */
.tickets-tree-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  grid-column: 1 / -1;
}

.tree-parent-group {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.tree-parent-group:hover {
  border-color: rgba(147, 51, 234, 0.4);
}

.tree-parent-card {
  padding: 12px 16px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
}

.tree-parent-card:hover {
  background: var(--bg-hover);
}

.tree-parent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.tree-parent-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.4;
}

.tree-chevron-btn {
  background: transparent;
  border: none;
  padding: 4px;
  cursor: pointer;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: transform 0.2s ease, color 0.2s ease;
}

.tree-chevron-btn:hover {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.06);
}

.tree-chevron-btn.collapsed svg {
  transform: rotate(-90deg);
}

.tree-children-container {
  padding: 12px 16px 14px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--bg-card);
  border-left: 3px solid rgba(147, 51, 234, 0.4);
  margin-left: 18px;
  margin-top: 4px;
  margin-bottom: 8px;
}

.tree-children-container.collapsed {
  display: none;
}

.tree-child-card {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 10px 14px;
  transition: all 0.2s ease;
}

.tree-child-card:hover {
  border-color: rgba(147, 51, 234, 0.45);
  background: var(--bg-hover);
}

.tree-child-card.is-active-bot {
  border: 2px solid var(--gold-bright, #fbbf24);
  box-shadow: 0 0 14px rgba(251, 191, 36, 0.22);
}

.tree-child-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  margin: 6px 0 4px 0;
  line-height: 1.4;
}

.tree-child-meta {
  font-size: 11.5px;
  color: var(--text-muted);
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}

.tree-independent-section {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px dashed var(--border-color);
  grid-column: 1 / -1;
}

.tree-section-header {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.badge-active-pulse {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.5);
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.dds-link-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.3);
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--text-main);
  transition: all 0.2s ease;
}

.dds-link-card:hover {
  background: rgba(14, 165, 233, 0.18);
  border-color: #0284c7;
  transform: translateX(3px);
  color: #ffffff;
}

.ticket-filter-btn.active {
  background: var(--primary) !important;
  color: #ffffff !important;
  border-color: var(--primary) !important;
}

/* ==================== LEITOR INTEGRADO DE DDS E MODAL EXPANDIDO ==================== */
.modal-dialog.is-fullscreen {
  width: 96vw !important;
  max-width: 96vw !important;
  height: 94vh !important;
  max-height: 94vh !important;
  margin: 3vh auto !important;
  display: flex !important;
  flex-direction: column !important;
}

.modal-dialog.is-fullscreen .modal-body {
  flex: 1 !important;
  max-height: none !important;
  overflow-y: auto !important;
}

.modal-subtabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.modal-subtab-btn {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
}

.modal-subtab-btn:hover {
  background: var(--bg-hover);
  color: var(--text-main);
}

.modal-subtab-btn.active {
  background: var(--primary-light);
  color: var(--primary);
  border-color: rgba(200, 170, 110, 0.4);
}

.dds-viewer-container {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
  min-height: 480px;
}

.modal-dialog.is-fullscreen .dds-viewer-container {
  min-height: calc(94vh - 220px);
  flex: 1;
}

.dds-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.dds-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dds-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dds-doc-select {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  color: var(--text-main);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: inherit;
}

.dds-frame-host {
  flex: 1;
  width: 100%;
  min-height: 440px;
  position: relative;
  background: #ffffff;
}

.modal-dialog.is-fullscreen .dds-frame-host {
  height: 100%;
  min-height: calc(94vh - 270px);
}

.dds-iframe {
  width: 100%;
  height: 100%;
  min-height: 440px;
  border: none;
  display: block;
}

.modal-dialog.is-fullscreen .dds-iframe {
  min-height: calc(94vh - 270px);
}

.dds-fallback-banner {
  padding: 8px 14px;
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-subtle);
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

/* ==================== DDS NATIVO, TIMELINE E GALERIA DE IMAGENS ==================== */
.movidesk-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.25);
  border-radius: var(--radius);
  margin-bottom: 14px;
}

.movidesk-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 140px;
  flex: 1;
}

.movidesk-label {
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  color: var(--text-muted);
}

.movidesk-val {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  word-break: break-word;
}

.dds-native-viewer {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 18px 22px;
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--text-main);
  white-space: pre-wrap;
  font-family: var(--font-body);
  max-height: calc(85vh - 300px);
  overflow-y: auto;
}

.modal-dialog.is-fullscreen .dds-native-viewer {
  max-height: calc(94vh - 280px);
}

/* ==================== DDS ESTRUTURADA E SECOES INTELIGENTES ==================== */
.dds-structured-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dds-meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 12px 16px;
}

.dds-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dds-meta-label {
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  color: var(--text-muted);
}

.dds-meta-val {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  word-break: break-word;
}

.dds-section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
}

.dds-section-header {
  padding: 10px 16px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.dds-section-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 6px;
}

.dds-section-body {
  padding: 14px 16px;
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--text-main);
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-family: var(--font-body);
}

.dds-section-subblock {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
}

.dds-section-subblock-title {
  font-size: 11.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--primary);
  margin-bottom: 6px;
}

.dds-rich-p {
  margin: 0 0 8px 0;
}
.dds-rich-p:last-child {
  margin-bottom: 0;
}
.dds-rich-heading {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
  margin: 10px 0 6px 0;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-color);
}
.dds-rich-bullet,
.dds-rich-num {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 4px 0;
  padding-left: 4px;
}
.dds-bullet-dot,
.dds-num-idx {
  color: var(--primary);
  font-weight: 700;
  flex-shrink: 0;
  min-width: 14px;
}
.dds-rich-link {
  color: #38bdf8;
  text-decoration: underline;
  word-break: break-all;
}
.dds-inline-code {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 1px 5px;
  font-family: monospace;
  font-size: 12px;
}
.dds-code-block {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 12px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 8px 0;
  overflow-x: hidden;
}

.dds-inline-figure,
.docx-inline-figure {
  margin: 12px 0;
  padding: 8px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: zoom-in;
  max-width: 100%;
  box-sizing: border-box;
  transition: border-color 0.15s ease;
}
.dds-inline-figure:hover,
.docx-inline-figure:hover {
  border-color: var(--primary);
}
.dds-inline-img,
.docx-inline-img {
  max-width: 100%;
  max-height: 440px;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.12);
}
.dds-inline-caption,
.docx-inline-caption {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.dds-checklist-details {
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-card);
  overflow: hidden;
}

.dds-checklist-summary {
  padding: 10px 16px;
  background: var(--bg-subtle);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}

.dds-checklist-summary:hover {
  color: var(--text-main);
  background: var(--bg-hover);
}

.dds-checklist-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.dds-checklist-table th,
.dds-checklist-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  text-align: left;
}

.dds-checklist-table th {
  background: var(--bg-subtle);
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
}

/* Banner de Destaque do SharePoint */
.dds-sp-callout-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.25);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 14px;
}

/* Visualizador SharePoint Embed e Hub de Documentacao */
.sharepoint-embed-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 12px;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.sharepoint-embed-toolbar-left,
.sharepoint-embed-toolbar-right {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sharepoint-embed-note {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 14px;
  padding: 10px 14px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary);
  width: 100%;
  box-sizing: border-box;
}

.sharepoint-hub-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.sharepoint-hub-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  box-sizing: border-box;
}

.sharepoint-hub-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
}

.sharepoint-reader-box {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 14px 16px;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.sharepoint-reader-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 560px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  font-family: inherit;
}

.docx-visual-paper {
  max-height: 620px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius);
  border: 1px solid var(--border-color);
  width: 100%;
  box-sizing: border-box;
}

.modal-dialog.is-fullscreen .docx-visual-paper {
  max-height: calc(92vh - 250px);
}

.docx-document-root {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  box-sizing: border-box;
}

.docx-render-table {
  width: 100%;
  max-width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 12.5px;
  line-height: 1.5;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.docx-render-table th,
.docx-render-table td {
  border: 1px solid var(--border-color);
  padding: 7px 10px;
  vertical-align: top;
  word-break: break-word;
  overflow-wrap: anywhere;
  color: var(--text-main);
}

.docx-render-table th,
.docx-render-table tr.docx-tr-section td {
  background: rgba(14, 165, 233, 0.10);
  font-weight: 700;
  color: var(--text-main);
}

.docx-p {
  margin: 0 0 4px 0;
}
.docx-p:last-child {
  margin-bottom: 0;
}

.dds-offline-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  margin-bottom: 14px;
}

.modal-container.dds-drag-active {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.35) !important;
}

.sp-auth-panel {
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.30);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  box-sizing: border-box;
}

.sp-device-code-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px dashed var(--primary);
  border-radius: var(--radius-sm);
}

.sp-device-code-token {
  font-family: monospace;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--primary);
  padding: 4px 10px;
  background: var(--bg-subtle);
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.sharepoint-iframe-container {
  width: 100%;
  height: 520px;
  min-height: 480px;
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
  position: relative;
}

.modal-dialog.is-fullscreen .sharepoint-iframe-container {
  height: calc(92vh - 210px);
}

.dds-section-subblock {
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--bg-subtle);
  border-left: 3px solid #c084fc;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 13px;
}

.dds-section-subblock-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #c084fc;
  margin-bottom: 4px;
}

.mention-pill {
  display: inline-flex;
  align-items: center;
  background: rgba(200, 170, 110, 0.16);
  color: var(--gold-bright, #fbbf24);
  border: 1px solid rgba(200, 170, 110, 0.35);
  padding: 1px 7px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 12px;
  margin: 0 2px;
}

/* Timeline Quem Mandou o Que */
.timeline-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 0;
}

.timeline-card {
  display: flex;
  gap: 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 12px 14px;
  transition: border-color 0.2s ease;
}

.timeline-card.client-msg {
  background: rgba(14, 165, 233, 0.06);
  border-left: 3px solid #38bdf8;
}

.timeline-card.team-msg {
  background: var(--bg-card);
  border-left: 3px solid var(--primary);
}

.timeline-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  color: var(--text-muted);
}

.timeline-content {
  flex: 1;
  min-width: 0;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.timeline-author {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.timeline-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.timeline-date {
  font-size: 11px;
  color: var(--text-muted);
}

.timeline-body {
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Galeria de Imagens */
.image-gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.image-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.image-card:hover {
  transform: translateY(-2px);
  border-color: var(--primary);
  box-shadow: 0 4px 14px rgba(0,0,0,0.25);
}

.image-card-thumb-wrap {
  width: 100%;
  height: 130px;
  background: rgba(0,0,0,0.15);
  overflow: hidden;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-card-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.25s ease;
}

.image-card:hover .image-card-thumb {
  transform: scale(1.05);
}

.image-card-info {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.image-card-title {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.image-card-meta {
  font-size: 10.5px;
  color: var(--text-muted);
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
  overflow-x: hidden !important;
  max-width: 100%;
  box-sizing: border-box;
}

.modal-dialog {
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.modal-content {
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.ticket-modal {
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.dds-view-container {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
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

.an-date-picker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  padding: 4px 8px;
  flex-wrap: wrap;
}

.an-date-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.an-date-input {
  padding: 3px 7px;
  font-size: 12px;
  height: 28px;
  border-radius: 2px;
  width: auto;
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
    const fxMode = (getComputedStyle(document.documentElement).getPropertyValue('--fx-mode') || 'embers').trim();
    const isSnow = fxMode === 'snow';
    return {
      x: Math.random() * w,
      y: initial ? Math.random() * h : (isSnow ? -14 : h + 14),
      r: isSnow ? (0.8 + Math.random() * 2.2) : (0.7 + Math.random() * 1.8),
      vy: isSnow ? (16 + Math.random() * 28) : (12 + Math.random() * 30),
      vx: (Math.random() - 0.5) * (isSnow ? 14 : 8),
      ph: Math.random() * Math.PI * 2,
      sw: isSnow ? (0.6 + Math.random() * 1.3) : (0.4 + Math.random() * 1.1),
      a: isSnow ? (0.45 + Math.random() * 0.45) : (0.35 + Math.random() * 0.55),
      tw: Math.random() * Math.PI * 2,
      isSnow: isSnow
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
        p.tw += dt * (p.isSnow ? 1.4 : 2.6);
        if (p.isSnow) {
          p.y += p.vy * dt;
          p.x += (p.vx + Math.sin(p.ph) * 18) * dt;
          if (p.y > h + 16 || p.x < -20 || p.x > w + 20) particles[i] = spawn(false);
        } else {
          p.y -= p.vy * dt;
          p.x += (p.vx + Math.sin(p.ph) * 14) * dt;
          if (p.y < -16 || p.x < -20 || p.x > w + 20) particles[i] = spawn(false);
        }
      }
      const edge = Math.min(1, Math.max(0, p.y / (h * 0.25)), Math.max(0, (h - p.y) / (h * 0.12)) + 0.35);
      const alpha = p.a * (0.55 + 0.45 * Math.sin(p.tw)) * Math.min(1, edge) * mult;
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      const size = p.r * (p.isSnow ? 5.5 : 6.5);
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
      cachedRgb = '';
      particles = [];
      resize();
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

    // Recolore as brasas e atualiza trilha Lofi ao trocar de tema
    const obs = new MutationObserver(function () {
      Embers.redraw();
      if (window.LofiPlayer) {
        const cur = document.documentElement.getAttribute('data-theme') || 'dark';
        window.LofiPlayer.onThemeChanged(cur);
      }
    });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    if (window.LofiPlayer) {
      window.LofiPlayer.init();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

/* ==================== REPRODUTOR OFICIAL LOFI GIRL E AMBIENCIAS DO YOUTUBE ==================== */
const LofiAudioEngine = (function () {
  let isPlaying = false;
  let isMuted = false;
  let volume = 50;
  let currentTheme = 'dark';
  let apiLoaded = false;
  let musicReady = false;
  let fireReady = false;
  let rainReady = false;
  let vinylReady = false;
  let pendingPlay = false;

  let playerMusic = null;
  let playerFire = null;
  let playerRain = null;
  let playerVinyl = null;

  const ambientState = {
    vinyl: true,
    rain: false,
    fire: false
  };

  const TRACKS = {
    natal: {
      title: 'Lofi Girl - Christmas Cozy Radio',
      sub: 'Ao Vivo & Mix Natalino Oficial Lofi Girl',
      ytId: 'XSXEaikz0Bc',
      ytUrl: 'https://www.youtube.com/watch?v=XSXEaikz0Bc'
    },
    halloween: {
      title: 'Lofi Girl - Halloween Spooky Ambience',
      sub: 'Mix Oficial das Bruxas & Noite Assombrada',
      ytId: '0sfDth4lMLc',
      ytUrl: 'https://www.youtube.com/watch?v=0sfDth4lMLc'
    },
    ano_novo: {
      title: 'Lofi Girl - Night Protocol (Synthwave & Chill)',
      sub: 'Mix Cyberpunk & Foco Noturno da Virada',
      ytId: 'zXGb3k-A1Vo',
      ytUrl: 'https://www.youtube.com/watch?v=zXGb3k-A1Vo'
    },
    pascoa: {
      title: 'Lofi Girl - Quiet Forest & Peaceful Focus',
      sub: 'Mix Primavera, Natureza e Serenidade',
      ytId: 'xxYJONmXE8w',
      ytUrl: 'https://www.youtube.com/watch?v=xxYJONmXE8w'
    },
    dark: {
      title: 'Lofi Girl - Beats to Relax / Study',
      sub: 'Lofi Hip Hop Mix Oficial Lofi Girl',
      ytId: 'CFGLoQIhmow',
      ytUrl: 'https://www.youtube.com/watch?v=CFGLoQIhmow'
    }
  };
  TRACKS.light = TRACKS.dark;

  const VINYL_YT_ID = 'NIP3fNueJMA'; // ASMR Old Vinyl Record Player Noise, Pops and Crackles - Quantum Sound
  const FIRE_YT_ID = 'UgHKb_7884o'; // 12 Hours of Relaxing Fireplace Sounds - Cat Trumpet
  const RAIN_YT_ID = 'V6V080RVeAE'; // Som de Chuva leve e calma

  function initVinyl() {}
  function syncVinyl() {}

  function loadYouTubeAPI() {
    if (window.YT && window.YT.Player) {
      initPlayers();
      return;
    }
    if (document.getElementById('yt-iframe-api')) return;
    const tag = document.createElement('script');
    tag.id = 'yt-iframe-api';
    tag.src = 'https://www.youtube.com/iframe_api';
    const firstScript = document.getElementsByTagName('script')[0];
    if (firstScript && firstScript.parentNode) {
      firstScript.parentNode.insertBefore(tag, firstScript);
    } else {
      document.head.appendChild(tag);
    }
  }

  window.onYouTubeIframeAPIReady = function () {
    apiLoaded = true;
    initPlayers();
  };

  function initPlayers() {
    if (!window.YT || !window.YT.Player) return;

    const trk = TRACKS[currentTheme] || TRACKS.dark;

    if (!playerMusic && document.getElementById('yt-player-music')) {
      playerMusic = new YT.Player('yt-player-music', {
        height: '1',
        width: '1',
        videoId: trk.ytId,
        playerVars: {
          autoplay: 0,
          controls: 0,
          loop: 1,
          playlist: trk.ytId,
          playsinline: 1,
          enablejsapi: 1
        },
        events: {
          onReady: function (e) {
            musicReady = true;
            try {
              e.target.setVolume(volume);
              if (isMuted) e.target.mute();
            } catch (err) {}
            if (pendingPlay) {
              pendingPlay = false;
              play();
            }
          },
          onStateChange: function (e) {
            if (window.YT && e.data === YT.PlayerState.PLAYING) {
              isPlaying = true;
              updateUI();
            } else if (window.YT && (e.data === YT.PlayerState.PAUSED || e.data === YT.PlayerState.ENDED)) {
              if (e.data === YT.PlayerState.ENDED) {
                try { e.target.playVideo(); } catch (err) {}
              }
            }
          }
        }
      });
    }

    if (!playerVinyl && document.getElementById('yt-player-vinyl')) {
      playerVinyl = new YT.Player('yt-player-vinyl', {
        height: '1',
        width: '1',
        videoId: VINYL_YT_ID,
        playerVars: {
          autoplay: 0,
          controls: 0,
          loop: 1,
          playlist: VINYL_YT_ID,
          playsinline: 1,
          enablejsapi: 1
        },
        events: {
          onReady: function (e) {
            vinylReady = true;
            try {
              e.target.setVolume(Math.round(volume * 0.70));
              if (isMuted) e.target.mute();
            } catch (err) {}
            if (isPlaying && ambientState.vinyl) {
              try { e.target.playVideo(); } catch (err) {}
            }
          }
        }
      });
    }

    if (!playerFire && document.getElementById('yt-player-fire')) {
      playerFire = new YT.Player('yt-player-fire', {
        height: '1',
        width: '1',
        videoId: FIRE_YT_ID,
        playerVars: {
          autoplay: 0,
          controls: 0,
          loop: 1,
          playlist: FIRE_YT_ID,
          playsinline: 1,
          enablejsapi: 1
        },
        events: {
          onReady: function (e) {
            fireReady = true;
            try {
              e.target.setVolume(Math.round(volume * 0.75));
              if (isMuted) e.target.mute();
            } catch (err) {}
            if (isPlaying && ambientState.fire) {
              try { e.target.playVideo(); } catch (err) {}
            }
          }
        }
      });
    }

    if (!playerRain && document.getElementById('yt-player-rain')) {
      playerRain = new YT.Player('yt-player-rain', {
        height: '1',
        width: '1',
        videoId: RAIN_YT_ID,
        playerVars: {
          autoplay: 0,
          controls: 0,
          loop: 1,
          playlist: RAIN_YT_ID,
          playsinline: 1,
          enablejsapi: 1
        },
        events: {
          onReady: function (e) {
            rainReady = true;
            try {
              e.target.setVolume(Math.round(volume * 0.75));
              if (isMuted) e.target.mute();
            } catch (err) {}
            if (isPlaying && ambientState.rain) {
              try { e.target.playVideo(); } catch (err) {}
            }
          }
        }
      });
    }
  }

  function play() {
    isPlaying = true;
    updateUI();

    if (!musicReady) {
      pendingPlay = true;
      loadYouTubeAPI();
      return;
    }

    try {
      if (playerMusic && typeof playerMusic.playVideo === 'function') {
        playerMusic.playVideo();
      }
    } catch (e) {}

    if (ambientState.vinyl && playerVinyl && typeof playerVinyl.playVideo === 'function') {
      try { playerVinyl.playVideo(); } catch (e) {}
    }
    if (ambientState.fire && playerFire && typeof playerFire.playVideo === 'function') {
      try { playerFire.playVideo(); } catch (e) {}
    }
    if (ambientState.rain && playerRain && typeof playerRain.playVideo === 'function') {
      try { playerRain.playVideo(); } catch (e) {}
    }
  }

  function pause() {
    isPlaying = false;
    pendingPlay = false;
    updateUI();

    try {
      if (playerMusic && typeof playerMusic.pauseVideo === 'function') {
        playerMusic.pauseVideo();
      }
    } catch (e) {}
    try {
      if (playerVinyl && typeof playerVinyl.pauseVideo === 'function') {
        playerVinyl.pauseVideo();
      }
    } catch (e) {}
    try {
      if (playerFire && typeof playerFire.pauseVideo === 'function') {
        playerFire.pauseVideo();
      }
    } catch (e) {}
    try {
      if (playerRain && typeof playerRain.pauseVideo === 'function') {
        playerRain.pauseVideo();
      }
    } catch (e) {}
  }

  function updateUI() {
    const playerEl = document.getElementById('lofi-player');
    const playLabel = document.getElementById('lofi-play-label');
    const titleEl = document.getElementById('lofi-track-title');
    const subEl = document.getElementById('lofi-track-sub');
    const slider = document.getElementById('lofi-slider');
    const linkYt = document.getElementById('lofi-footer-link') || document.getElementById('lofi-link-yt');

    const trk = TRACKS[currentTheme] || TRACKS.dark;
    if (titleEl) titleEl.textContent = trk.title;
    if (subEl) subEl.textContent = trk.sub;
    if (linkYt) linkYt.href = trk.ytUrl || 'https://www.youtube.com/@LofiGirl';

    if (playerEl) {
      playerEl.classList.toggle('is-playing', isPlaying);
      playerEl.classList.toggle('is-muted', isMuted);
    }
    if (playLabel) {
      playLabel.textContent = isPlaying ? 'Pausar Lofi' : 'Ouvir Lofi';
    }
    if (slider) {
      slider.value = volume;
    }

    ['vinyl', 'rain', 'fire'].forEach(type => {
      const pill = document.getElementById('lofi-pill-' + type);
      if (pill) pill.classList.toggle('active', !!ambientState[type]);
    });
  }

  return {
    init: function () {
      try {
        const savedVol = localStorage.getItem('jirabot_lofi_vol');
        if (savedVol !== null) volume = Math.max(0, Math.min(100, parseInt(savedVol, 10)));
        const savedMuted = localStorage.getItem('jirabot_lofi_muted');
        if (savedMuted !== null) isMuted = savedMuted === '1';
        ['vinyl', 'rain', 'fire'].forEach(type => {
          const s = localStorage.getItem('jirabot_lofi_amb_' + type);
          if (s !== null) ambientState[type] = s === '1';
        });
      } catch (e) {}

      const eff = document.documentElement.getAttribute('data-theme') || 'dark';
      currentTheme = TRACKS[eff] ? eff : 'dark';
      updateUI();
      loadYouTubeAPI();
    },

    play: play,
    pause: pause,
    toggle: function () {
      if (isPlaying) pause(); else play();
    },

    setVolume: function (val) {
      volume = Math.max(0, Math.min(100, parseInt(val, 10)));
      isMuted = false;
      try { localStorage.setItem('jirabot_lofi_vol', String(volume)); } catch (e) {}

      try {
        if (playerMusic && typeof playerMusic.setVolume === 'function') {
          playerMusic.setVolume(volume);
          playerMusic.unMute();
        }
        if (playerVinyl && typeof playerVinyl.setVolume === 'function') {
          playerVinyl.setVolume(Math.round(volume * 0.70));
          playerVinyl.unMute();
        }
        if (playerFire && typeof playerFire.setVolume === 'function') {
          playerFire.setVolume(Math.round(volume * 0.75));
          playerFire.unMute();
        }
        if (playerRain && typeof playerRain.setVolume === 'function') {
          playerRain.setVolume(Math.round(volume * 0.75));
          playerRain.unMute();
        }
      } catch (e) {}
      updateUI();
    },

    toggleMute: function () {
      isMuted = !isMuted;
      try { localStorage.setItem('jirabot_lofi_muted', isMuted ? '1' : '0'); } catch (e) {}
      try {
        if (playerMusic && typeof playerMusic.mute === 'function') {
          if (isMuted) playerMusic.mute(); else playerMusic.unMute();
        }
        if (playerVinyl && typeof playerVinyl.mute === 'function') {
          if (isMuted) playerVinyl.mute(); else playerVinyl.unMute();
        }
        if (playerFire && typeof playerFire.mute === 'function') {
          if (isMuted) playerFire.mute(); else playerFire.unMute();
        }
        if (playerRain && typeof playerRain.mute === 'function') {
          if (isMuted) playerRain.mute(); else playerRain.unMute();
        }
      } catch (e) {}
      updateUI();
    },

    toggleAmbient: function (type) {
      if (!(type in ambientState)) return;
      ambientState[type] = !ambientState[type];
      try { localStorage.setItem('jirabot_lofi_amb_' + type, ambientState[type] ? '1' : '0'); } catch (e) {}

      let targetPlayer = null;
      if (type === 'vinyl') targetPlayer = playerVinyl;
      else if (type === 'fire') targetPlayer = playerFire;
      else if (type === 'rain') targetPlayer = playerRain;

      if (targetPlayer && typeof targetPlayer.playVideo === 'function') {
        try {
          if (ambientState[type]) {
            targetPlayer.playVideo();
          } else {
            targetPlayer.pauseVideo();
          }
        } catch (e) {}
      }
      updateUI();
    },

    toggleVinyl: function () { this.toggleAmbient('vinyl'); },
    toggleRain: function () { this.toggleAmbient('rain'); },
    toggleFire: function () { this.toggleAmbient('fire'); },
    initVinyl: initVinyl,
    syncVinyl: syncVinyl,

    onThemeChanged: function (newTheme) {
      const cleanTheme = TRACKS[newTheme] ? newTheme : 'dark';
      if (cleanTheme === currentTheme) return;
      currentTheme = cleanTheme;
      updateUI();

      const newTrk = TRACKS[currentTheme];
      if (playerMusic && typeof playerMusic.loadVideoById === 'function') {
        try {
          if (isPlaying) {
            playerMusic.loadVideoById({ videoId: newTrk.ytId });
          } else if (typeof playerMusic.cueVideoById === 'function') {
            playerMusic.cueVideoById({ videoId: newTrk.ytId });
          }
        } catch (e) {}
      }
    }
  };
})();

function toggleLofiPlay() { if (window.LofiPlayer) window.LofiPlayer.toggle(); }
function toggleLofiMute() { if (window.LofiPlayer) window.LofiPlayer.toggleMute(); }
function setLofiVolume(val) { if (window.LofiPlayer) window.LofiPlayer.setVolume(val); }
function toggleLofiAmbient(type) { if (window.LofiPlayer) window.LofiPlayer.toggleAmbient(type); }
window.LofiPlayer = LofiAudioEngine;
"""

# ----------------------------------------------------------------------------------------------------------------------
# JS DO DASHBOARD ANALITICO
# ----------------------------------------------------------------------------------------------------------------------
ANALYTICS_JS = r"""
/* ==================== DASHBOARD ANALITICO ==================== */
let analyticsStart = '';
let analyticsEnd = '';
let analyticsActivePreset = '30d';
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

function fmtIsoDate(d) {
  const p = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}

function calcPresetDates(preset) {
  const today = new Date();
  if (preset === 'today') {
    const s = fmtIsoDate(today);
    return { start: s, end: s };
  }
  if (preset === 'yesterday') {
    const y = new Date(today);
    y.setDate(today.getDate() - 1);
    const s = fmtIsoDate(y);
    return { start: s, end: s };
  }
  if (preset === 'this_month') {
    const first = new Date(today.getFullYear(), today.getMonth(), 1);
    return { start: fmtIsoDate(first), end: fmtIsoDate(today) };
  }
  if (preset === 'last_month') {
    const first = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const last = new Date(today.getFullYear(), today.getMonth(), 0);
    return { start: fmtIsoDate(first), end: fmtIsoDate(last) };
  }
  if (preset === '90d') {
    const past = new Date(today);
    past.setDate(today.getDate() - 89);
    return { start: fmtIsoDate(past), end: fmtIsoDate(today) };
  }
  // default: 30d
  const past = new Date(today);
  past.setDate(today.getDate() - 29);
  return { start: fmtIsoDate(past), end: fmtIsoDate(today) };
}

function setAnalyticsPreset(preset) {
  analyticsActivePreset = preset;
  const range = calcPresetDates(preset);
  analyticsStart = range.start;
  analyticsEnd = range.end;
  syncDateInputs();
  loadAnalytics(false);
}

function applyCustomAnalyticsDates() {
  const startEl = document.getElementById('an-start-date');
  const endEl = document.getElementById('an-end-date');
  if (!startEl || !endEl) return;
  let s = (startEl.value || '').trim();
  let e = (endEl.value || '').trim();
  if (!s && !e) return;
  if (!s) s = e;
  if (!e) e = s;
  if (s > e) {
    const tmp = s; s = e; e = tmp;
    startEl.value = s;
    endEl.value = e;
  }
  analyticsStart = s;
  analyticsEnd = e;
  analyticsActivePreset = '';
  syncDateInputs();
  loadAnalytics(false);
}

function syncDateInputs() {
  const startEl = document.getElementById('an-start-date');
  const endEl = document.getElementById('an-end-date');
  if (startEl && analyticsStart) startEl.value = analyticsStart;
  if (endEl && analyticsEnd) endEl.value = analyticsEnd;
  document.querySelectorAll('.seg-btn[data-preset]').forEach(b => {
    b.classList.toggle('active', b.dataset.preset === analyticsActivePreset);
  });
}

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
  const today = new Date();
  const past = new Date(today);
  past.setDate(today.getDate() - (days - 1));
  analyticsStart = fmtIsoDate(past);
  analyticsEnd = fmtIsoDate(today);
  analyticsActivePreset = (days === 30 ? '30d' : days === 90 ? '90d' : '');
  syncDateInputs();
  loadAnalytics(false);
}

async function loadAnalytics(force) {
  if (analyticsLoading) return;
  analyticsLoading = true;
  if (!analyticsStart || !analyticsEnd) {
    const def = calcPresetDates('30d');
    analyticsStart = def.start;
    analyticsEnd = def.end;
  }
  syncDateInputs();
  const stateEl = document.getElementById('an-state');
  const contentEl = document.getElementById('an-content');
  stateEl.style.display = '';
  stateEl.innerHTML = '<div class="an-loading"><span class="spinner"></span><span>Consultando o Jira e consolidando seus lançamentos...</span></div>';
  try {
    const data = await apiCall('/api/analytics?start=' + encodeURIComponent(analyticsStart)
      + '&end=' + encodeURIComponent(analyticsEnd)
      + (force ? '&refresh=1' : ''));
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

  if (d.start_date === d.end_date) {
    document.getElementById('an-subtitle').textContent =
      'Período: ' + anFmtDate(d.start_date) + ' (1 dia selecionado) - dados reais do Jira (atualizado em ' + (d.generated_at || '-') + ')';
  } else {
    document.getElementById('an-subtitle').textContent =
      'Período de ' + anFmtDate(d.start_date) + ' a ' + anFmtDate(d.end_date) + ' (' + d.period_days + ' dias) - dados reais do Jira (atualizado em ' + (d.generated_at || '-') + ')';
  }

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
