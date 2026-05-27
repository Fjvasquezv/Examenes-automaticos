"""
Seguridad de cliente para sesiones de examen en Streamlit.

Esta capa NO solicita permisos del sistema operativo y se limita a controles
de navegador para disuasion y reduccion de riesgo.

Arquitectura en tres capas:
  1. Perfiles predefinidos (quiz, parcial, supletorio, sin_restricciones)
  2. Politica efectiva = perfil base + overrides especificos del examen
  3. Sentinel bidireccional JS→Python: input numerico oculto que JS actualiza
     al detectar perdidas de foco; en el proximo rerun Streamlit lee el valor.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import streamlit as st
import streamlit.components.v1 as st_components


# ─── Perfiles predefinidos ────────────────────────────────────────────────────

SECURITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "sin_restricciones": {
        "habilitado": False,
        "fullscreen_obligatorio": False,
        "bloquear_copiar_pegar": False,
        "bloquear_menu_contexto": False,
        "bloquear_seleccion_texto": False,
        "bloquear_atajos_comunes": False,
        "bloquear_captura_pantalla": False,
        "mostrar_marca_agua": False,
        "detectar_perdida_foco": False,
        "advertir_salida_pestana": False,
        "max_perdidas_foco_permitidas": 0,
        "detectar_multiples_pestanas": False,
        "detectar_devtools": False,
        "inactividad_max_minutos": 0,
        "min_segundos_por_pregunta": 0,
    },
    "quiz": {
        "habilitado": True,
        "fullscreen_obligatorio": False,
        "bloquear_copiar_pegar": True,
        "bloquear_menu_contexto": True,
        "bloquear_seleccion_texto": True,
        "bloquear_atajos_comunes": True,
        "bloquear_captura_pantalla": False,
        "mostrar_marca_agua": True,
        "detectar_perdida_foco": True,
        "advertir_salida_pestana": True,
        "max_perdidas_foco_permitidas": 0,   # registro sin bloqueo automatico
        "detectar_multiples_pestanas": True,
        "detectar_devtools": False,
        "inactividad_max_minutos": 20,
        "min_segundos_por_pregunta": 3,
    },
    "parcial": {
        "habilitado": True,
        "fullscreen_obligatorio": True,
        "bloquear_copiar_pegar": True,
        "bloquear_menu_contexto": True,
        "bloquear_seleccion_texto": True,
        "bloquear_atajos_comunes": True,
        "bloquear_captura_pantalla": True,
        "mostrar_marca_agua": True,
        "detectar_perdida_foco": True,
        "advertir_salida_pestana": True,
        "max_perdidas_foco_permitidas": 5,   # bloquea al 5to cambio de foco
        "detectar_multiples_pestanas": True,
        "detectar_devtools": True,
        "inactividad_max_minutos": 15,
        "min_segundos_por_pregunta": 5,
    },
    "supletorio": {
        "habilitado": True,
        "fullscreen_obligatorio": True,
        "bloquear_copiar_pegar": True,
        "bloquear_menu_contexto": True,
        "bloquear_seleccion_texto": True,
        "bloquear_atajos_comunes": True,
        "bloquear_captura_pantalla": True,
        "mostrar_marca_agua": True,
        "detectar_perdida_foco": True,
        "advertir_salida_pestana": True,
        "max_perdidas_foco_permitidas": 3,   # umbral mas estricto
        "detectar_multiples_pestanas": True,
        "detectar_devtools": True,
        "inactividad_max_minutos": 10,
        "min_segundos_por_pregunta": 5,
    },
}

# ─── Politica por defecto (cuando no se usa perfil ni overrides) ──────────────

DEFAULT_SECURITY_POLICY: Dict[str, Any] = {
    "habilitado": True,
    "fullscreen_obligatorio": True,
    "bloquear_copiar_pegar": True,
    "bloquear_menu_contexto": True,
    "bloquear_seleccion_texto": True,
    "bloquear_atajos_comunes": True,
    "bloquear_captura_pantalla": True,
    "mostrar_marca_agua": True,
    "detectar_perdida_foco": True,
    "advertir_salida_pestana": True,
    "mensaje_disuasion": "Modo examen activo. Evite cambiar de pestana o usar atajos no permitidos.",
    "max_alertas_en_pantalla": 3,
    "max_perdidas_foco_permitidas": 0,  # 0 = sin bloqueo automatico
    "detectar_multiples_pestanas": True,
    "detectar_devtools": True,
    "inactividad_max_minutos": 15,      # 0 = sin limite
    "min_segundos_por_pregunta": 5,     # 0 = sin umbral
}

# ─── Constantes del sentinel bidireccional ───────────────────────────────────

# Etiqueta unica que JS busca en el DOM para encontrar el input centinela.
SENTINEL_LABEL = "___sec_fl___"
# Clave de session_state para el valor del centinela.
SENTINEL_KEY = "_sec_fl_v1"

# Sentinel de texto para fingerprint (userAgent + resolucion).
FINGERPRINT_LABEL = "___sec_fp___"
FINGERPRINT_KEY = "_sec_fp_v1"


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    txt = str(value).strip().lower()
    if txt in ("1", "true", "yes", "si", "s"):
        return True
    if txt in ("0", "false", "no", "n"):
        return False
    return fallback


# ─── API publica ──────────────────────────────────────────────────────────────

def get_security_policy(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construye la politica efectiva: defaults → perfil base → overrides examen.

    En seguridad_cliente del JSON del examen se puede especificar:
      "perfil": "quiz" | "parcial" | "supletorio" | "sin_restricciones"
    y opcionalmente sobrescribir campos puntuales.
    """
    policy = dict(DEFAULT_SECURITY_POLICY)
    cfg = config.get("seguridad_cliente", {}) if isinstance(config, dict) else {}
    if not isinstance(cfg, dict):
        cfg = {}

    # 1. Aplicar perfil base
    perfil = str(cfg.get("perfil", "")).strip()
    if perfil and perfil in SECURITY_PROFILES:
        policy.update(SECURITY_PROFILES[perfil])

    # 2. Aplicar overrides especificos del examen sobre el perfil
    for key, default in DEFAULT_SECURITY_POLICY.items():
        if key not in cfg or key == "perfil":
            continue
        if isinstance(default, bool):
            policy[key] = _to_bool(cfg.get(key), default)
        elif isinstance(default, int):
            try:
                policy[key] = max(0, int(cfg.get(key)))
            except Exception:
                policy[key] = default
        else:
            policy[key] = str(cfg.get(key)).strip() or default

    return policy


def render_security_banner(policy: Dict[str, Any]) -> None:
    """Muestra aviso informativo de modo supervisado en la pantalla de inicio."""
    if not policy.get("habilitado", True):
        return

    partes = []
    if policy.get("fullscreen_obligatorio"):
        partes.append("pantalla completa")
    if policy.get("bloquear_copiar_pegar"):
        partes.append("sin copiar/pegar")
    if policy.get("bloquear_atajos_comunes"):
        partes.append("atajos bloqueados")
    if policy.get("bloquear_captura_pantalla"):
        partes.append("captura de pantalla bloqueada")
    if policy.get("mostrar_marca_agua"):
        partes.append("marca de agua activa")
    if policy.get("detectar_perdida_foco"):
        max_fl = int(policy.get("max_perdidas_foco_permitidas", 0))
        if max_fl > 0:
            partes.append(f"máx. {max_fl} cambios de pestaña permitidos")
        else:
            partes.append("cambios de pestaña registrados")

    desc = " · ".join(partes) if partes else "controles activos"
    st.info(f"🔒 Modo supervisado: {desc} (solo nivel navegador).")


def render_focus_counter_sentinel(policy: Dict[str, Any]) -> int:
    """
    Renderiza un input numerico OCULTO que el JS puede actualizar via
    React native setter cuando detecta una perdida de foco.

    El JS escritura el nuevo contador → Streamlit detecta el cambio de widget
    → rerun → Python lee el valor actualizado en session_state.

    Returns:
        Numero de perdidas de foco actualmente registradas en el servidor.
    """
    if not policy.get("habilitado", True) or not policy.get("detectar_perdida_foco", True):
        return 0

    if SENTINEL_KEY not in st.session_state:
      st.session_state[SENTINEL_KEY] = "0"
    elif not isinstance(st.session_state[SENTINEL_KEY], str):
      st.session_state[SENTINEL_KEY] = str(st.session_state[SENTINEL_KEY])

    # Usamos text_input oculto en vez de number_input porque Streamlit no siempre
    # renderiza number_input como input[type="number"], lo que vuelve frágil la
    # detección del sentinel desde JS.
    focus_count = st.text_input(
        SENTINEL_LABEL,
        key=SENTINEL_KEY,
        label_visibility="collapsed",
      max_chars=4,
    )

    try:
      return max(0, int(str(focus_count or "0").strip()))
    except Exception:
      return 0


def render_fingerprint_sentinel(policy: Dict[str, Any]) -> str:
    """
    Renderiza un text_input OCULTO que JS rellena con el fingerprint del
    cliente (userAgent + resolucion de pantalla) en el primer render.

    Returns:
        Cadena de fingerprint leida desde session_state, o "" si no aplica.
    """
    if not policy.get("habilitado", True):
        return ""

    if FINGERPRINT_KEY not in st.session_state:
        st.session_state[FINGERPRINT_KEY] = ""

    fp = st.text_input(
        FINGERPRINT_LABEL,
        key=FINGERPRINT_KEY,
        label_visibility="collapsed",
        max_chars=400,
    )
    return str(fp or "")


def apply_client_hardening(policy: Dict[str, Any], codigo_estudiante: str = "") -> None:
    """
    Inyecta controles de seguridad del lado cliente via HTML/JS.

    Nota: son controles de navegador; no sustituyen un entorno kiosk.
    El sentinel numerico (SENTINEL_LABEL) permite reportar perdidas de foco
    al servidor sin requerir un componente personalizado externo.

    Args:
        policy: Politica de seguridad efectiva del examen.
        codigo_estudiante: Codigo del estudiante para la marca de agua.
    """
    if not policy.get("habilitado", True):
        return

    policy_json = json.dumps(policy, ensure_ascii=True)
    sentinel_label = SENTINEL_LABEL
    fingerprint_label = FINGERPRINT_LABEL
    # Sanitizar el codigo para uso seguro en JS (solo alfanumericos y guiones)
    codigo_seguro = "".join(c for c in str(codigo_estudiante) if c.isalnum() or c in "-_").upper()

    style = """
    <style>
      body.exam-locked,
      body.exam-locked * {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
      }
      #exam-security-toast {
        position: fixed;
        right: 14px;
        bottom: 14px;
        z-index: 999999;
        max-width: 360px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #fff3cd;
        border-left: 4px solid #b8860b;
        color: #2d2d2d;
        box-shadow: 0 8px 24px rgba(0,0,0,.18);
        border-radius: 8px;
        padding: 10px 12px;
        opacity: 0;
        transform: translateY(12px);
        transition: all .18s ease;
        pointer-events: none;
      }
      #exam-security-toast.show {
        opacity: 1;
        transform: translateY(0);
      }
      #exam-watermark {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        pointer-events: none;
        z-index: 999990;
        overflow: hidden;
        user-select: none;
        -webkit-user-select: none;
      }
      #exam-watermark span {
        position: absolute;
        white-space: nowrap;
        font-size: 13px;
        font-family: monospace;
        font-weight: bold;
        letter-spacing: 2px;
        color: rgba(180, 0, 0, 0.07);
        transform: rotate(-30deg);
        transform-origin: center center;
        pointer-events: none;
      }
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)

    script = f"""
    <script>
      (function() {{
        const policy = {policy_json};
        const sentinelLabel = "{sentinel_label}";
        const fingerprintLabel = "{fingerprint_label}";
        const codigoEstudiante = "{codigo_seguro}";
        const rootWindow = window.parent || window;
        const rootDoc   = rootWindow.document || document;

        // ── Singleton de estado (persiste entre reruns de Streamlit) ──────────
        if (!rootWindow.__examSecurityState) {{
          rootWindow.__examSecurityState = {{
            installed: false,
            toastAlerts: 0,
            focusLosses: parseInt(sessionStorage.getItem('_sec_fl') || '0'),
            fingerprintSent: false,
          }};
        }}
        const state = rootWindow.__examSecurityState;

        // ── Toast de aviso ────────────────────────────────────────────────────
        const ensureToast = () => {{
          let t = rootDoc.getElementById("exam-security-toast");
          if (!t) {{
            t = rootDoc.createElement("div");
            t.id = "exam-security-toast";
            rootDoc.body.appendChild(t);
          }}
          return t;
        }};
        const showAlert = (msg) => {{
          if (state.toastAlerts >= Number(policy.max_alertas_en_pantalla || 3)) return;
          state.toastAlerts += 1;
          const t = ensureToast();
          t.textContent = msg;
          t.classList.add("show");
          rootWindow.setTimeout(() => t.classList.remove("show"), 2400);
        }};

        // ── Sentinel numerico: encuentra el input de cambios de foco ──────────
        const findSentinel = () => {{
          const inputs = rootDoc.querySelectorAll('input');
          for (const inp of inputs) {{
            const wrap = inp.closest('[data-testid="stTextInput"]') ||
                         inp.closest('[data-testid="stNumberInput"]');
            if (!wrap) continue;
            const lbl = wrap.querySelector('[data-testid="stWidgetLabel"]');
            if (lbl && lbl.textContent && lbl.textContent.includes(sentinelLabel)) {{
              return inp;
            }}
          }}
          return null;
        }};

        // ── Sentinel de texto: encuentra el input de fingerprint ──────────────
        const findFingerprintSentinel = () => {{
          const inputs = rootDoc.querySelectorAll('input[type="text"]');
          for (const inp of inputs) {{
            const wrap = inp.closest('[data-testid="stTextInput"]');
            if (!wrap) continue;
            const lbl = wrap.querySelector('[data-testid="stWidgetLabel"]');
            if (lbl && lbl.textContent && lbl.textContent.includes(fingerprintLabel)) {{
              return inp;
            }}
          }}
          return null;
        }};

        const hideSentinel = (inp) => {{
          const c = inp.closest('[data-testid="stElementContainer"]') ||
                    inp.closest('[data-testid="stNumberInput"]') ||
                    inp.closest('[data-testid="stTextInput"]');
          if (c) c.setAttribute('style',
            'position:absolute;width:0;height:0;overflow:hidden;visibility:hidden;opacity:0;pointer-events:none;'
          );
        }};
        const pushToNumberSentinel = (count) => {{
          const s = findSentinel();
          if (!s) return;
          hideSentinel(s);
          try {{
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(s, String(count));
            s.dispatchEvent(new Event('input', {{ bubbles: true }}));
          }} catch(e) {{}}
        }};
        const pushToFingerprintSentinel = (fp) => {{
          const s = findFingerprintSentinel();
          if (!s) return;
          hideSentinel(s);
          try {{
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(s, fp);
            s.dispatchEvent(new Event('input', {{ bubbles: true }}));
          }} catch(e) {{}}
        }};

        // Debounce: reporta al servidor 2 s despues del ultimo evento de foco
        let sentinelTimer = null;
        const schedulePush = () => {{
          if (sentinelTimer) clearTimeout(sentinelTimer);
          sentinelTimer = rootWindow.setTimeout(() => pushToNumberSentinel(state.focusLosses), 2000);
        }};

        // ── Accion al perder foco ─────────────────────────────────────────────
        const onFocusLoss = (reason) => {{
          state.focusLosses += 1;
          sessionStorage.setItem('_sec_fl', String(state.focusLosses));
          showAlert(reason || "Se detecto cambio de foco.");
          if (policy.detectar_perdida_foco) schedulePush();
        }};

        // ── Pantalla completa ─────────────────────────────────────────────────
        const activateFullScreen = () => {{
          if (!policy.fullscreen_obligatorio) return;
          const de = rootDoc.documentElement;
          if (!rootDoc.fullscreenElement && de && de.requestFullscreen) {{
            de.requestFullscreen().catch(() => {{}});
          }}
        }};

        // ── Bloqueo de seleccion de texto ─────────────────────────────────────
        if (policy.bloquear_seleccion_texto) {{
          rootDoc.body.classList.add("exam-locked");
        }} else {{
          rootDoc.body.classList.remove("exam-locked");
        }}

        // ── Marca de agua con codigo del estudiante ───────────────────────────
        if (policy.mostrar_marca_agua && codigoEstudiante && !rootDoc.getElementById("exam-watermark")) {{
          const wm = rootDoc.createElement("div");
          wm.id = "exam-watermark";
          const texto = codigoEstudiante + " \u2022 EXAMEN EN CURSO \u2022 " + codigoEstudiante;
          let html = "";
          for (let y = -10; y < 120; y += 12) {{
            for (let x = -10; x < 130; x += 35) {{
              html += '<span style="left:' + x + '%;top:' + y + '%">' + texto + '</span>';
            }}
          }}
          wm.innerHTML = html;
          rootDoc.body.appendChild(wm);
        }}

        // ── Ocultar sentinels en el primer render ─────────────────────────────
        rootWindow.setTimeout(() => {{
          const s = findSentinel(); if (s) hideSentinel(s);
          const fp = findFingerprintSentinel(); if (fp) hideSentinel(fp);
        }}, 500);

        // ── Captura de fingerprint (una sola vez por sesion) ──────────────────
        if (!state.fingerprintSent) {{
          rootWindow.setTimeout(() => {{
            const ua   = (navigator.userAgent || '').replace(/[^a-zA-Z0-9 _.;()/]/g, '').substring(0, 200);
            const res  = rootWindow.screen.width + 'x' + rootWindow.screen.height;
            const lang = navigator.language || '';
            const tz   = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
            const fp   = (ua + '|' + res + '|' + lang + '|' + tz).substring(0, 380);
            pushToFingerprintSentinel(fp);
            state.fingerprintSent = true;
          }}, 1200);
        }}

        // ── Instalacion de listeners (solo una vez por sesion) ────────────────
        if (!state.installed) {{
          state.installed = true;

          // ── Pantalla completa ─────────────────────────────────────────────
          if (policy.fullscreen_obligatorio) {{
            const oneShotFs = () => {{
              activateFullScreen();
              rootDoc.removeEventListener("click",   oneShotFs, true);
              rootDoc.removeEventListener("keydown", oneShotFs, true);
            }};
            rootDoc.addEventListener("click",   oneShotFs, true);
            rootDoc.addEventListener("keydown", oneShotFs, true);
            rootDoc.addEventListener("fullscreenchange", () => {{
              if (!rootDoc.fullscreenElement)
                showAlert("Pantalla completa desactivada. Vuelva a activarla.");
            }});
          }}

          // ── Perdida de foco normal ────────────────────────────────────────
          if (policy.detectar_perdida_foco) {{
            rootWindow.addEventListener("blur", () =>
              onFocusLoss("Se detecto cambio de foco.")
            );
            rootDoc.addEventListener("visibilitychange", () => {{
              if (rootDoc.visibilityState !== "visible")
                onFocusLoss("Se detecto salida de la pestana del examen.");
            }});
          }}

          // ── Deteccion de multiples pestanas (BroadcastChannel) ────────────
          if (policy.detectar_multiples_pestanas && rootWindow.BroadcastChannel) {{
            const channelId = "exam_sec_" + (codigoEstudiante || "default");
            const bc = new BroadcastChannel(channelId);
            bc.postMessage({{ type: "exam_check" }});
            bc.addEventListener("message", (evt) => {{
              if (evt.data && evt.data.type === "exam_alive") {{
                onFocusLoss("Multiples pestanas del examen detectadas.");
              }} else if (evt.data && evt.data.type === "exam_check") {{
                bc.postMessage({{ type: "exam_alive" }});
              }}
            }});
          }}

          // ── Deteccion de DevTools abiertos ────────────────────────────────
          if (policy.detectar_devtools) {{
            let devtoolsOpen = false;
            const checkDevTools = () => {{
              const widthDiff  = rootWindow.outerWidth  - rootWindow.innerWidth;
              const heightDiff = rootWindow.outerHeight - rootWindow.innerHeight;
              if (widthDiff > 160 || heightDiff > 200) {{
                if (!devtoolsOpen) {{
                  devtoolsOpen = true;
                  showAlert("Se detectaron herramientas de desarrollador abiertas.");
                  onFocusLoss("DevTools detectado.");
                }}
              }} else {{
                devtoolsOpen = false;
              }}
            }};
            rootWindow.setInterval(checkDevTools, 3000);
          }}

          // ── Deteccion de inactividad ──────────────────────────────────────
          const inactividad = Number(policy.inactividad_max_minutos || 0);
          if (inactividad > 0) {{
            let lastActivity = Date.now();
            const activityEvents = ["mousemove", "keydown", "mousedown", "touchstart", "scroll"];
            activityEvents.forEach(evt =>
              rootDoc.addEventListener(evt, () => {{ lastActivity = Date.now(); }}, {{ passive: true }})
            );
            rootWindow.setInterval(() => {{
              const idleSecs = (Date.now() - lastActivity) / 1000;
              if (idleSecs >= inactividad * 60) {{
                onFocusLoss("Inactividad prolongada detectada (" + Math.floor(idleSecs / 60) + " min).");
                lastActivity = Date.now(); // reset para no disparar en cada tick
              }}
            }}, 30000);
          }}

          // ── Menu contextual ───────────────────────────────────────────────
          if (policy.bloquear_menu_contexto) {{
            rootDoc.addEventListener("contextmenu", (e) => e.preventDefault(), true);
          }}

          // ── Copiar / pegar ────────────────────────────────────────────────
          if (policy.bloquear_copiar_pegar) {{
            ["copy", "cut", "paste", "dragstart", "drop"].forEach((evt) => {{
              rootDoc.addEventListener(evt, (e) => {{
                e.preventDefault();
                showAlert("Accion bloqueada en modo examen.");
              }}, true);
            }});
            rootWindow.addEventListener("focus", () => {{
              try {{
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                  navigator.clipboard.writeText("").catch(() => {{}});
                }}
              }} catch(e) {{}}
            }});
          }}

          // ── Atajos de teclado ─────────────────────────────────────────────
          if (policy.bloquear_atajos_comunes) {{
            rootDoc.addEventListener("keydown", (e) => {{
              const k     = (e.key || "").toLowerCase();
              const kRaw  = e.key || "";
              const ctrl  = !!e.ctrlKey;
              const shift = !!e.shiftKey;
              const meta  = !!e.metaKey;
              const blocked =
                (ctrl && ["c","v","x","u","s","p","f","g","h","j","a"].includes(k)) ||
                (ctrl && shift && ["i","j","c","s"].includes(k)) ||
                ((meta) && ["c","v","x","a","s","p"].includes(k)) ||
                k === "f12" ||
                kRaw === "PrintScreen" ||
                (shift && kRaw === "F10");
              if (blocked) {{
                e.preventDefault();
                e.stopPropagation();
                showAlert("Atajo bloqueado en modo examen.");
              }}
            }}, true);
          }}

          // ── Captura de pantalla ───────────────────────────────────────────
          if (policy.bloquear_captura_pantalla) {{
            try {{
              if (navigator.mediaDevices) {{
                navigator.mediaDevices.getDisplayMedia = async function(...args) {{
                  showAlert("Captura de pantalla bloqueada en modo examen.");
                  throw new DOMException("Bloqueado por modo examen.", "NotAllowedError");
                }};
              }}
            }} catch(e) {{}}
          }}

          // ── Advertencia al salir ──────────────────────────────────────────
          if (policy.advertir_salida_pestana) {{
            rootWindow.addEventListener("beforeunload", (e) => {{
              const msg = "Existe un examen en curso. Salir puede bloquear su intento.";
              e.preventDefault();
              e.returnValue = msg;
              return msg;
            }});
          }}
        }}

        if (policy.mensaje_disuasion) {{
          showAlert(String(policy.mensaje_disuasion));
        }}
      }})();
    </script>
    """
    st_components.html(script, height=0, scrolling=False)
