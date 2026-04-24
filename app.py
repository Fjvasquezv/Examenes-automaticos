"""
Sistema de Examen Adaptativo Modular
Orquestador Principal
"""
import streamlit as st
import streamlit.components.v1 as st_components
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import unicodedata
import re
import subprocess
import time

# Imports robustos para ejecución local y en Streamlit Cloud.
try:
    from src.config_loader import ConfigLoader
    from src.question_manager import QuestionManager
    from src.exam_logic import ExamLogic
    from src.ui_components import UIComponents
    from src.exam_security import (
        get_security_policy,
        render_security_banner,
        apply_client_hardening,
        render_focus_counter_sentinel,
        render_fingerprint_sentinel,
    )
    from src.data_persistence import DataPersistence
    from utils.validators import validate_codigo_estudiante
    from utils.exam_logger import ExamLogger
except ModuleNotFoundError:
    # Compatibilidad con ejecución donde src/ y utils/ están en PYTHONPATH.
    from config_loader import ConfigLoader
    from question_manager import QuestionManager
    from exam_logic import ExamLogic
    from ui_components import UIComponents
    from exam_security import (
        get_security_policy,
        render_security_banner,
        apply_client_hardening,
        render_focus_counter_sentinel,
        render_fingerprint_sentinel,
    )
    from data_persistence import DataPersistence
    from validators import validate_codigo_estudiante
    from exam_logger import ExamLogger


def _serializar_estado_exam_logic(exam_logic, pregunta_pendiente=None, opciones_pendientes=None) -> str:
    """Serializa el estado mínimo necesario para restaurar un examen en curso."""
    respuestas_minimas = []
    for r in exam_logic.preguntas_respondidas:
        respuestas_minimas.append({
            'pregunta_id': r.get('pregunta_id', ''),
            'dificultad': r.get('dificultad', 3),
            'categoria': r.get('categoria', 'Sin categoría'),
            'correcta': bool(r.get('correcta', False)),
            'nivel_en_pregunta': r.get('nivel_en_pregunta', 3),
            'letra_seleccionada': r.get('letra_seleccionada', ''),
        })

    payload = {
        'pregunta_actual': exam_logic.pregunta_actual,
        'nivel_actual': exam_logic.nivel_actual,
        'theta_actual': exam_logic.theta_actual,
        'correctas': exam_logic.correctas,
        'incorrectas': exam_logic.incorrectas,
        'preguntas_usadas': list(exam_logic.preguntas_usadas),
        'historial_notas': list(exam_logic.historial_notas),
        'categorias_evaluadas': list(exam_logic.categorias_evaluadas),
        'preguntas_respondidas': respuestas_minimas,
    }

    if pregunta_pendiente and opciones_pendientes:
        payload['pregunta_pendiente'] = {
            'pregunta_id': pregunta_pendiente.get('id', ''),
            'opciones_mezcladas': dict(opciones_pendientes),
        }

    return json.dumps(payload, ensure_ascii=False)


def _restaurar_estado_exam_logic(exam_logic, question_manager, progreso: dict) -> bool:
    """Restaura el estado de exam_logic desde una fila EN_CURSO de Sheets."""
    try:
        estado_json = progreso.get('Estado_JSON', '')

        if estado_json:
            estado = json.loads(estado_json)
            exam_logic.pregunta_actual = int(estado.get('pregunta_actual', 0))
            exam_logic.nivel_actual = max(1, min(5, int(estado.get('nivel_actual', exam_logic.nivel_actual))))
            exam_logic.theta_actual = float(estado.get('theta_actual', exam_logic.theta_actual))
            exam_logic.correctas = int(estado.get('correctas', 0))
            exam_logic.incorrectas = int(estado.get('incorrectas', 0))
            exam_logic.preguntas_usadas = list(estado.get('preguntas_usadas', []))
            exam_logic.preguntas_usadas_set = set(exam_logic.preguntas_usadas)
            exam_logic.historial_notas = list(estado.get('historial_notas', []))
            exam_logic.categorias_evaluadas = set(estado.get('categorias_evaluadas', []))
            exam_logic.preguntas_respondidas = list(estado.get('preguntas_respondidas', []))

            pregunta_pendiente = estado.get('pregunta_pendiente') or {}
            pregunta_id = str(pregunta_pendiente.get('pregunta_id', '')).strip()
            opciones_mezcladas = pregunta_pendiente.get('opciones_mezcladas') or {}
            if pregunta_id and isinstance(opciones_mezcladas, dict):
                pregunta_obj = question_manager.obtener_pregunta_por_id(pregunta_id)
                if pregunta_obj is None:
                    return False

                pregunta_key = f"pregunta_actual_{exam_logic.pregunta_actual}"
                opciones_key = f"opciones_pregunta_{exam_logic.pregunta_actual}"
                st.session_state[pregunta_key] = pregunta_obj
                st.session_state[opciones_key] = dict(opciones_mezcladas)
                st.session_state[f'_ts_q_{exam_logic.pregunta_actual}'] = time.time()

            return True

        exam_logic.pregunta_actual = int(progreso.get('Preguntas_Respondidas', 0) or 0)
        exam_logic.correctas = int(progreso.get('Correctas', 0) or 0)
        exam_logic.incorrectas = int(progreso.get('Incorrectas', 0) or 0)
        exam_logic.nivel_actual = max(1, min(5, int(progreso.get('Nivel_Final', exam_logic.nivel_actual) or exam_logic.nivel_actual)))
        theta_val = progreso.get('Theta_IRT', '')
        if theta_val not in ('', None):
            exam_logic.theta_actual = float(theta_val)

        preguntas_ids = progreso.get('Preguntas_IDs', '')
        exam_logic.preguntas_usadas = [p.strip() for p in preguntas_ids.split(',') if p.strip()]
        exam_logic.preguntas_usadas_set = set(exam_logic.preguntas_usadas)

        nota = progreso.get('Nota_Final', '')
        if nota not in ('', None):
            exam_logic.historial_notas = [float(nota)]

        return True
    except Exception:
        return False


def _slugify(texto: str) -> str:
    """Normaliza texto para usarlo como identificador estable."""
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()


def _obtener_clave_admin() -> str:
    """Obtiene la clave de admin desde secrets, soportando claves simples y anidadas."""
    try:
        if 'ADMIN_PASSWORD' in st.secrets:
            return str(st.secrets['ADMIN_PASSWORD'])
        if 'admin_password' in st.secrets:
            return str(st.secrets['admin_password'])
        if 'app' in st.secrets:
            app_cfg = st.secrets['app']
            if isinstance(app_cfg, dict):
                if 'ADMIN_PASSWORD' in app_cfg:
                    return str(app_cfg['ADMIN_PASSWORD'])
                if 'admin_password' in app_cfg:
                    return str(app_cfg['admin_password'])
    except Exception:
        return ''
    return ''


def _ruta_disponibilidad(base_path: Path) -> Path:
    return base_path / "config" / "disponibilidad.json"


@st.cache_data(ttl=60, show_spinner=False)
def _leer_json_cacheado(ruta_str: str, firma: str) -> dict:
    ruta = Path(ruta_str)
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)


def _leer_json(ruta: Path) -> dict:
    firma = "missing"
    if ruta.exists():
        stat = ruta.stat()
        firma = f"{stat.st_mtime_ns}-{stat.st_size}"
    return _leer_json_cacheado(str(ruta), firma)


@st.cache_data(ttl=3600, show_spinner=False)
def _cargar_preguntas_bancos_cacheado(base_path_str: str, bancos: tuple[str, ...], firma: str) -> list[dict]:
    base_path = Path(base_path_str)
    preguntas = []
    for archivo in bancos:
        ruta = base_path / archivo
        with open(ruta, 'r', encoding='utf-8') as f:
            bloque = json.load(f)
        if not isinstance(bloque, list):
            raise ValueError(f"El banco debe contener una lista: {archivo}")
        preguntas.extend(bloque)
    return preguntas


def _firma_bancos(base_path: Path, bancos: list[str]) -> str:
    piezas = []
    for archivo in bancos:
        ruta = base_path / archivo
        if ruta.exists():
            stat = ruta.stat()
            piezas.append(f"{archivo}:{stat.st_mtime_ns}:{stat.st_size}")
        else:
            piezas.append(f"{archivo}:missing")
    return "|".join(piezas)


@st.cache_resource(show_spinner=False)
def _obtener_exam_logger(base_path_str: str) -> ExamLogger:
    return ExamLogger(Path(base_path_str))


def _log_evento_operacion(base_path: Path, tipo: str, mensaje: str, codigo: str = "", examen_id: str = "", extra: dict | None = None) -> None:
    try:
        logger = _obtener_exam_logger(str(base_path))
        logger.evento(tipo=tipo, mensaje=mensaje, codigo_estudiante=codigo, examen_id=examen_id, extra=extra)
    except Exception:
        pass


def _escribir_json(ruta: Path, data: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _crear_backup_config(base_path: Path, ruta: Path, etiqueta: str) -> str:
    if not ruta.exists():
        return ''
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    raiz_config = base_path / "config"
    try:
        rel = ruta.relative_to(raiz_config)
    except Exception:
        rel = Path(ruta.name)
    destino = raiz_config / "_backup" / f"{marca_tiempo}_{etiqueta}" / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(ruta.read_bytes())
    return str(destino.relative_to(base_path)).replace('\\', '/')


def _validar_periodo(periodo: dict) -> tuple[bool, str, datetime, datetime]:
    nombre = str(periodo.get('nombre', '')).strip()
    examen_config = str(periodo.get('examen_config', '')).strip()
    inicio_txt = str(periodo.get('inicio', '')).strip()
    fin_txt = str(periodo.get('fin', '')).strip()

    if not nombre:
        return False, "El periodo requiere 'nombre'.", None, None
    if not examen_config:
        return False, "El periodo requiere 'examen_config'.", None, None
    if not inicio_txt or not fin_txt:
        return False, "El periodo requiere 'inicio' y 'fin'.", None, None

    try:
        inicio_dt = datetime.strptime(inicio_txt, "%Y-%m-%d %H:%M")
        fin_dt = datetime.strptime(fin_txt, "%Y-%m-%d %H:%M")
    except ValueError:
        return False, "Formato de fecha inválido. Usa YYYY-MM-DD HH:MM.", None, None

    if inicio_dt >= fin_dt:
        return False, "'inicio' debe ser menor que 'fin'.", None, None

    return True, "", inicio_dt, fin_dt


def _validar_calendario(periodos: list[dict]) -> tuple[bool, str]:
    parseados = []
    for i, p in enumerate(periodos):
        ok, msg, inicio_dt, fin_dt = _validar_periodo(p)
        if not ok:
            return False, f"Periodo {i + 1}: {msg}"
        parseados.append((i, p, inicio_dt, fin_dt))

    for i in range(len(parseados)):
        _, p1, ini1, fin1 = parseados[i]
        for j in range(i + 1, len(parseados)):
            _, p2, ini2, fin2 = parseados[j]
            if ini1 < fin2 and ini2 < fin1:
                n1 = p1.get('nombre', f'Periodo {i + 1}')
                n2 = p2.get('nombre', f'Periodo {j + 1}')
                return False, f"Solape detectado entre '{n1}' y '{n2}'."

    return True, ""


def _slug_archivo(texto: str) -> str:
    base = _slugify(texto)
    base = re.sub(r'[^a-z0-9]+', '_', base).strip('_')
    return base or 'examen'


def _catalogo_examenes(base_path: Path) -> list[dict]:
    catalogo = []
    for rel in _listar_configs_examenes(base_path):
        parts = Path(rel).parts
        asignatura = parts[0] if len(parts) > 1 else "General"
        evaluacion_slug = Path(rel).stem
        nombre_examen = evaluacion_slug.replace('_', ' ').title()
        try:
            cfg = _cargar_config_examen_por_relpath(base_path, rel)
            nombre_examen = cfg.get("metadata", {}).get("nombre_examen", nombre_examen) or nombre_examen
        except Exception:
            pass
        catalogo.append({
            "rel": rel,
            "asignatura": asignatura,
            "evaluacion_slug": evaluacion_slug,
            "nombre_examen": nombre_examen,
            "label": f"{nombre_examen} ({evaluacion_slug})"
        })
    return sorted(catalogo, key=lambda x: (x["asignatura"].lower(), x["nombre_examen"].lower()))


def _run_git(base_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(base_path),
        capture_output=True,
        text=True,
        check=False
    )


GIT_PUBLICABLE_PATHS = [
    "config/examenes",
    "config/disponibilidad.json",
    "data/bancos",
    "data/preguntas"
]


def _git_status_config(base_path: Path) -> tuple[bool, bool, str]:
    try:
        res = _run_git(base_path, ["status", "--porcelain", "--"] + GIT_PUBLICABLE_PATHS)
        if res.returncode != 0:
            msg = (res.stderr or res.stdout or "").strip()
            return False, False, msg or "No se pudo consultar estado git"
        salida = (res.stdout or "").strip()
        return True, bool(salida), salida
    except Exception as e:
        return False, False, str(e)


def _git_publicar_config(base_path: Path, mensaje_commit: str) -> tuple[bool, str]:
    try:
        r_branch = _run_git(base_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if r_branch.returncode != 0:
            return False, (r_branch.stderr or r_branch.stdout or "No se pudo obtener rama actual").strip()
        rama = (r_branch.stdout or "main").strip() or "main"

        r_add = _run_git(base_path, ["add"] + GIT_PUBLICABLE_PATHS)
        if r_add.returncode != 0:
            return False, (r_add.stderr or r_add.stdout or "No se pudo hacer git add").strip()

        r_diff = _run_git(base_path, ["diff", "--cached", "--quiet", "--"] + GIT_PUBLICABLE_PATHS)
        if r_diff.returncode == 0:
            return False, "No hay cambios publicables (configuración/bancos) para publicar."

        r_commit = _run_git(base_path, ["commit", "-m", mensaje_commit])
        if r_commit.returncode != 0:
            return False, (r_commit.stderr or r_commit.stdout or "No se pudo hacer commit").strip()

        r_push = _run_git(base_path, ["push", "origin", rama])
        if r_push.returncode != 0:
            return False, (r_push.stderr or r_push.stdout or "No se pudo hacer push").strip()

        resumen = (r_commit.stdout or "").strip()
        return True, resumen or f"Publicado en origin/{rama}"
    except Exception as e:
        return False, str(e)


def _git_status_todo(base_path: Path) -> tuple[bool, bool, str]:
    try:
        res = _run_git(base_path, ["status", "--porcelain"])
        if res.returncode != 0:
            msg = (res.stderr or res.stdout or "").strip()
            return False, False, msg or "No se pudo consultar estado git"
        salida = (res.stdout or "").strip()
        return True, bool(salida), salida
    except Exception as e:
        return False, False, str(e)


def _git_publicar_todo(base_path: Path, mensaje_commit: str) -> tuple[bool, str]:
    try:
        r_branch = _run_git(base_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if r_branch.returncode != 0:
            return False, (r_branch.stderr or r_branch.stdout or "No se pudo obtener rama actual").strip()
        rama = (r_branch.stdout or "main").strip() or "main"

        r_add = _run_git(base_path, ["add", "-A"])
        if r_add.returncode != 0:
            return False, (r_add.stderr or r_add.stdout or "No se pudo hacer git add").strip()

        r_diff = _run_git(base_path, ["diff", "--cached", "--quiet"])
        if r_diff.returncode == 0:
            return False, "No hay cambios en el repositorio para publicar."

        r_commit = _run_git(base_path, ["commit", "-m", mensaje_commit])
        if r_commit.returncode != 0:
            return False, (r_commit.stderr or r_commit.stdout or "No se pudo hacer commit").strip()

        r_push = _run_git(base_path, ["push", "origin", rama])
        if r_push.returncode != 0:
            return False, (r_push.stderr or r_push.stdout or "No se pudo hacer push").strip()

        resumen = (r_commit.stdout or "").strip()
        return True, resumen or f"Publicado todo en origin/{rama}"
    except Exception as e:
        return False, str(e)


def _reset_admin_exam_form_state(config_base: dict) -> None:
    md = config_base.get("metadata", {})
    params = config_base.get("parametros", {})
    desc = config_base.get("descripcion", {})
    pers = config_base.get("persistencia", {})

    st.session_state["admin_exam_nombre"] = md.get("nombre_examen", "")
    st.session_state["admin_exam_desc"] = desc.get("texto", "")
    st.session_state["admin_exam_dur"] = _normalizar_duracion(desc.get("duracion_estimada", ""))
    st.session_state["admin_exam_sheet"] = pers.get("spreadsheet_id", "")
    st.session_state["admin_exam_bancos"] = list(config_base.get("bancos_preguntas", []))
    st.session_state["admin_exam_temas"] = ", ".join(list(config_base.get("bancos_por_tema", {}).keys()))
    st.session_state["admin_exam_pmin"] = int(params.get("preguntas_minimas", 15))
    st.session_state["admin_exam_pmax"] = int(params.get("preguntas_maximas", 25))
    st.session_state["admin_exam_nivel_ini"] = int(params.get("nivel_inicial", 3))

    tema_keys = [k for k in list(st.session_state.keys()) if str(k).startswith("admin_exam_tema_bancos_")]
    for key in tema_keys:
        del st.session_state[key]
    tema_chk_keys = [k for k in list(st.session_state.keys()) if str(k).startswith("admin_exam_tema_chk_")]
    for key in tema_chk_keys:
        del st.session_state[key]


def _opciones_duracion(duracion_actual: str = "") -> list[str]:
    return [f"{m} min" for m in range(15, 121, 15)]


def _normalizar_duracion(duracion_actual: str = "") -> str:
    texto = str(duracion_actual or "").strip().lower()
    if not texto:
        return "60 min"

    match = re.search(r"(\d+)", texto)
    valor = int(match.group(1)) if match else 60

    if "hora" in texto and "min" not in texto:
        valor = valor * 60

    valor = max(15, min(120, valor))
    valor = int(round(valor / 15) * 15)
    valor = max(15, min(120, valor))
    return f"{valor} min"


def _asignatura_de_banco(ruta_rel: str) -> str:
    partes = Path(ruta_rel).parts
    for i, parte in enumerate(partes):
        if parte.lower() == "bancos" and i + 1 < len(partes):
            return partes[i + 1]
    return ""


def _filtrar_bancos_por_asignatura(bancos_rel: list[str], asignatura: str) -> list[str]:
    objetivo = _slug_archivo(asignatura)
    if not objetivo:
        return []
    salida = []
    for banco in bancos_rel:
        asig_banco = _asignatura_de_banco(banco)
        if _slug_archivo(asig_banco) == objetivo:
            salida.append(banco)
    return salida


def _render_contenido_pregunta(pregunta_obj: dict, base_path: Path) -> None:
    tipo = str(pregunta_obj.get('tipo', 'texto')).strip().lower()

    if tipo == 'imagen':
        imagen_ref = str(pregunta_obj.get('imagen', '')).strip()
        if imagen_ref:
            ruta_img = Path(imagen_ref)
            if not ruta_img.is_absolute():
                ruta_img = base_path / ruta_img

            if ruta_img.exists():
                caption = pregunta_obj.get('imagen_caption', '')
                ancho = pregunta_obj.get('imagen_ancho', None)
                try:
                    ancho = int(ancho) if ancho not in (None, '') else None
                except Exception:
                    ancho = None
                st.image(str(ruta_img), caption=caption if caption else None, width=ancho)
            else:
                st.warning(f"No se encontró la imagen de la pregunta: {imagen_ref}")

        st.markdown(pregunta_obj.get('pregunta', ''))
        return

    if tipo == 'mermaid':
        st.markdown(pregunta_obj.get('pregunta', ''))
        return

    st.markdown(pregunta_obj.get('pregunta', ''))


def _opciones_hora_jornada(jornada_noche: bool) -> list[str]:
    inicio = datetime.strptime("18:00", "%H:%M") if jornada_noche else datetime.strptime("08:00", "%H:%M")
    fin = datetime.strptime("21:45", "%H:%M") if jornada_noche else datetime.strptime("12:00", "%H:%M")
    opciones = []
    actual = inicio
    while actual <= fin:
        opciones.append(actual.strftime("%H:%M"))
        actual = actual.replace(minute=actual.minute + 15) if actual.minute <= 44 else actual.replace(hour=actual.hour + 1, minute=(actual.minute + 15) % 60)
    return opciones


def _parse_fecha_hora(valor: str) -> tuple:
    try:
        dt = datetime.strptime(str(valor or "").strip(), "%Y-%m-%d %H:%M")
        return dt.date(), dt.strftime("%H:%M")
    except ValueError:
        hoy = datetime.now().date()
        return hoy, "08:00"


def _listar_configs_examenes(base_path: Path) -> list[str]:
    raiz = base_path / "config" / "examenes"
    if not raiz.exists():
        return []
    rutas = [
        str(p.relative_to(raiz)).replace('\\', '/')
        for p in raiz.rglob('*.json')
    ]
    return sorted(rutas)


def _listar_bancos_disponibles(base_path: Path) -> list[str]:
    candidatos = []
    for sub in [base_path / "data" / "bancos", base_path / "data" / "preguntas"]:
        if sub.exists():
            candidatos.extend([
                str(p.relative_to(base_path)).replace('\\', '/')
                for p in sub.rglob('*.json')
            ])
    return sorted(dict.fromkeys(candidatos))


def _cargar_config_examen_por_relpath(base_path: Path, examen_config_rel: str) -> dict:
    ruta = base_path / "config" / "examenes" / examen_config_rel
    return _leer_json(ruta)


def _render_panel_admin(base_path: Path):
    st.markdown("### 🛠️ Panel de Administración")

    col_admin_left, col_admin_mid, col_admin_right = st.columns([8, 1, 1])
    with col_admin_mid:
        if st.button("Cerrar sesión", key="admin_logout", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.session_state.admin_mode = False
            st.session_state.admin_prompt = False
            st.session_state.admin_last_activity_ts = 0.0
            if 'admin_password_input' in st.session_state:
                del st.session_state['admin_password_input']
            st.rerun()
    with col_admin_right:
        if st.button("Cerrar", key="admin_close", use_container_width=True):
            st.session_state.admin_mode = False
            st.rerun()

    tab_exam, tab_prog, tab_ops, tab_mon = st.tabs(["Exámenes", "Programación", "Operación", "Monitoreo"])

    with tab_exam:
        catalogo = _catalogo_examenes(base_path)
        bancos_disponibles = _listar_bancos_disponibles(base_path)
        asignaturas = sorted(list(dict.fromkeys([c["asignatura"] for c in catalogo])))

        col_stats_t, col_stats_1, col_stats_2, col_stats_3, col_accion = st.columns([3, 1, 1, 1, 2])
        with col_stats_t:
            st.markdown("#### Gestión de exámenes")
        with col_stats_1:
            st.metric("Exámenes", len(catalogo))
        with col_stats_2:
            st.metric("Asignaturas", len(asignaturas))
        with col_stats_3:
            st.metric("Bancos", len(bancos_disponibles))
        with col_accion:
            st.markdown("**Acción**")
            accion = st.radio(
                "Acción",
                options=["Crear", "Editar", "Eliminar"],
                horizontal=False,
                key="admin_exam_action",
                label_visibility="collapsed"
            )

        plantilla = {
            "metadata": {
                "nombre_examen": "Nuevo Examen",
                "asignatura": "Asignatura",
                "institucion": "Universidad ECCI",
                "codigo_asignatura": "COD101"
            },
            "descripcion": {
                "texto": "Descripción",
                "temas": [],
                "duracion_estimada": "1 hora"
            },
            "parametros": {
                "preguntas_minimas": 15,
                "preguntas_maximas": 25,
                "nivel_inicial": 3,
                "umbral_estabilizacion": 0.2,
                "ventana_estabilizacion": 3
            },
            "sistema_calificacion": {
                "tipo": "irt_simplificado",
                "parametros": {"max_iteraciones": 10}
            },
            "persistencia": {
                "metodo": "google_sheets",
                "spreadsheet_id": ""
            },
            "bancos_preguntas": [],
            "bancos_por_tema": {}
        }

        config_base = dict(plantilla)
        ruta_destino_rel = ""
        modo_creacion = "Desde cero"
        mostrar_formulario = True
        contexto_form = "crear:base"
        fuente_rel = ""
        asignatura_destino = ""

        if accion == "Crear":
            modo_creacion = st.radio(
                "Cómo crear",
                options=["Desde cero", "Duplicar existente"],
                horizontal=True,
                key="admin_exam_create_mode"
            )

            if modo_creacion == "Duplicar existente":
                if not catalogo:
                    st.warning("No hay exámenes existentes para duplicar.")
                    modo_creacion = "Desde cero"
                else:
                    fuente_labels = [c["label"] for c in catalogo]
                    fuente_sel = st.selectbox("Examen a duplicar", fuente_labels, key="admin_exam_dup_source")
                    fuente = next(c for c in catalogo if c["label"] == fuente_sel)
                    fuente_rel = fuente["rel"]
                    config_base = _cargar_config_examen_por_relpath(base_path, fuente["rel"])

            col_crear_1, col_crear_2 = st.columns(2)
            with col_crear_1:
                opciones_asig = asignaturas + ["+ Nueva asignatura"]
                asig_sel = st.selectbox("Asignatura", opciones_asig, key="admin_exam_asig_pick") if opciones_asig else st.selectbox("Asignatura", ["+ Nueva asignatura"], key="admin_exam_asig_pick_empty")
                if asig_sel == "+ Nueva asignatura":
                    asig_destino = st.text_input("Nueva asignatura", value="", key="admin_exam_new_asig")
                else:
                    asig_destino = asig_sel
            with col_crear_2:
                nombre_evaluacion = st.text_input("Nombre de la evaluación", value="Quiz 1", key="admin_exam_eval_name")

            eval_slug = _slug_archivo(nombre_evaluacion)
            ruta_destino_rel = f"{asig_destino.strip()}/{eval_slug}.json" if asig_destino.strip() else ""
            asignatura_destino = asig_destino.strip()
            contexto_form = f"crear:{modo_creacion}:{fuente_rel}"

        elif accion == "Editar":
            if not catalogo:
                st.warning("No hay exámenes para editar.")
                mostrar_formulario = False
            else:
                asig_edit = st.selectbox("Asignatura", asignaturas, key="admin_exam_edit_asig")
                opciones_edit = [c for c in catalogo if c["asignatura"] == asig_edit]
                sel_label = st.selectbox("Evaluación", [c["label"] for c in opciones_edit], key="admin_exam_edit_sel")
                seleccionado = next(c for c in opciones_edit if c["label"] == sel_label)
                ruta_destino_rel = seleccionado["rel"]
                config_base = _cargar_config_examen_por_relpath(base_path, ruta_destino_rel)
                asignatura_destino = seleccionado["asignatura"]
                st.info(f"Editando: {seleccionado['nombre_examen']}")
                contexto_form = f"editar:{ruta_destino_rel}"

        else:  # Eliminar
            mostrar_formulario = False
            if not catalogo:
                st.caption("No hay exámenes para eliminar.")
            else:
                st.markdown("##### Eliminación segura")
                asig_del = st.selectbox("Asignatura", asignaturas, key="admin_exam_del_asig")
                opciones_del = [c for c in catalogo if c["asignatura"] == asig_del]
                del_label = st.selectbox("Evaluación", [c["label"] for c in opciones_del], key="admin_exam_delete_target")
                del_target = next(c for c in opciones_del if c["label"] == del_label)
                confirmar_eliminar = st.checkbox("Confirmo que quiero eliminar esta configuración", key="admin_exam_delete_confirm")
                texto_confirmacion = st.text_input("Escribe ELIMINAR para confirmar", key="admin_exam_delete_text")

                if st.button("🗑️ Eliminar examen", key="admin_exam_delete", use_container_width=True):
                    if not confirmar_eliminar or texto_confirmacion.strip().upper() != "ELIMINAR":
                        st.error("Confirmación incompleta para eliminar.")
                    else:
                        ruta_del = base_path / "config" / "examenes" / del_target["rel"]
                        if ruta_del.exists():
                            backup_rel = _crear_backup_config(base_path, ruta_del, "examenes")
                            ruta_del.unlink()
                            st.success(f"Examen eliminado: {del_target['nombre_examen']}")
                            if backup_rel:
                                st.info(f"Backup creado: {backup_rel}")

        if not mostrar_formulario:
            st.info("Selecciona Crear o Editar para ver el formulario de configuración.")
            st.markdown("---")
        if mostrar_formulario:
            if st.session_state.get("admin_exam_form_context") != contexto_form:
                _reset_admin_exam_form_state(config_base)
                st.session_state["admin_exam_form_context"] = contexto_form

            params = config_base.get("parametros", {})
            bancos_por_tema_default = config_base.get("bancos_por_tema", {})
            pers = config_base.get("persistencia", {})

            if accion == "Crear":
                if modo_creacion == "Desde cero" and not pers.get("spreadsheet_id") and asignatura_destino:
                    for c in catalogo:
                        if c["asignatura"] == asignatura_destino:
                            try:
                                cfg_asig = _cargar_config_examen_por_relpath(base_path, c["rel"])
                                pers = cfg_asig.get("persistencia", pers)
                                break
                            except Exception:
                                pass

            bancos_asig = _filtrar_bancos_por_asignatura(bancos_disponibles, asignatura_destino)
            mapa_temas = {}
            for banco in bancos_asig:
                tema_nombre = Path(banco).stem.replace('_', ' ').replace('-', ' ').title()
                if tema_nombre not in mapa_temas:
                    mapa_temas[tema_nombre] = banco

            with st.form("admin_exam_form"):
                st.markdown("##### Configuración del examen")

                with st.expander("Identidad y descripción", expanded=True):
                    col_i1, col_i2 = st.columns(2)
                    with col_i1:
                        nombre_examen = st.text_input("Nombre examen", key="admin_exam_nombre")
                    with col_i2:
                        duracion_opts = _opciones_duracion(st.session_state.get("admin_exam_dur", ""))
                        duracion_normal = _normalizar_duracion(st.session_state.get("admin_exam_dur", ""))
                        if duracion_normal not in duracion_opts:
                            duracion_normal = "60 min"
                        st.session_state["admin_exam_dur"] = duracion_normal
                        duracion = st.selectbox("Duración", options=duracion_opts, key="admin_exam_dur")
                    texto_desc = st.text_area("Descripción", key="admin_exam_desc")

                with st.expander("Parámetros de examen", expanded=True):
                    colp1, colp2, colp3 = st.columns(3)
                    with colp1:
                        pmin = st.number_input("Preguntas mínimas", min_value=1, key="admin_exam_pmin")
                    with colp2:
                        pmax = st.number_input("Preguntas máximas", min_value=1, key="admin_exam_pmax")
                    with colp3:
                        nivel_ini = st.number_input("Nivel inicial", min_value=1, max_value=5, key="admin_exam_nivel_ini")

                with st.expander("Bancos y temas", expanded=True):
                    if not bancos_asig:
                        st.warning("No hay bancos disponibles para la asignatura seleccionada.")
                    bancos_por_tema = {}
                    bancos_sel = []
                    temas_seleccionados = []
                    temas_default = set(bancos_por_tema_default.keys())
                    for i, (tema, banco) in enumerate(mapa_temas.items()):
                        key_chk = f"admin_exam_tema_chk_{i}"
                        if key_chk not in st.session_state:
                            st.session_state[key_chk] = (tema in temas_default) or (banco in config_base.get("bancos_preguntas", []))
                        marcado = st.checkbox(tema, key=key_chk, help=banco)
                        if marcado:
                            temas_seleccionados.append(tema)
                            bancos_sel.append(banco)
                            bancos_por_tema[tema] = [banco]

                submit_guardar = st.form_submit_button("💾 Guardar examen", use_container_width=True)

            if submit_guardar:
                if not ruta_destino_rel.strip() or ruta_destino_rel.startswith("/") or "/" not in ruta_destino_rel:
                    st.error("Ruta destino inválida.")
                elif int(pmin) > int(pmax):
                    st.error("'Preguntas mínimas' no puede ser mayor que 'Preguntas máximas'.")
                elif not nombre_examen.strip() or not asignatura_destino.strip():
                    st.error("Completa Nombre y Asignatura.")
                elif not bancos_sel:
                    st.error("Selecciona al menos un tema disponible para la asignatura.")
                elif not pers.get("spreadsheet_id", "").strip():
                    st.error("No hay spreadsheet_id configurado para esta asignatura/examen.")
                else:
                    codigo_asig = config_base.get("metadata", {}).get("codigo_asignatura", "") or _slug_archivo(asignatura_destino).upper()[:8]
                    spreadsheet_id = pers.get("spreadsheet_id", "")
                    nuevo = {
                        "metadata": {
                            "nombre_examen": nombre_examen,
                            "asignatura": asignatura_destino,
                            "institucion": "Universidad ECCI",
                            "codigo_asignatura": codigo_asig
                        },
                        "descripcion": {
                            "texto": texto_desc,
                            "temas": temas_seleccionados,
                            "duracion_estimada": duracion
                        },
                        "parametros": {
                            "preguntas_minimas": int(pmin),
                            "preguntas_maximas": int(pmax),
                            "nivel_inicial": int(nivel_ini),
                            "umbral_estabilizacion": float(params.get("umbral_estabilizacion", 0.2)),
                            "ventana_estabilizacion": int(params.get("ventana_estabilizacion", 3))
                        },
                        "sistema_calificacion": config_base.get("sistema_calificacion", {"tipo": "irt_simplificado", "parametros": {"max_iteraciones": 10}}),
                        "persistencia": {
                            "metodo": "google_sheets",
                            "spreadsheet_id": spreadsheet_id
                        },
                        "bancos_preguntas": list(bancos_sel),
                        "bancos_por_tema": bancos_por_tema
                    }

                    ruta_destino = base_path / "config" / "examenes" / ruta_destino_rel
                    if accion == "Crear" and ruta_destino.exists() and modo_creacion == "Desde cero":
                        st.error("Ya existe un examen con ese nombre de evaluación en la asignatura seleccionada.")
                    else:
                        backup_rel = _crear_backup_config(base_path, ruta_destino, "examenes")
                        _escribir_json(ruta_destino, nuevo)
                        accion_msg = "actualizado" if accion == "Editar" else "guardado"
                        st.success(f"Examen {accion_msg}: {nombre_examen}")
                        if backup_rel:
                            st.info(f"Backup creado: {backup_rel}")

    with tab_prog:
        ruta_disp = _ruta_disponibilidad(base_path)
        disp = _leer_json(ruta_disp)
        habilitado_actual = bool(disp.get("habilitado", True))
        zona_horaria_actual = disp.get("zona_horaria", "America/Bogota")

        periodos = disp.get("periodos", [])
        configs_rel = _listar_configs_examenes(base_path)
        st.markdown("#### Programación")

        if not configs_rel:
            st.warning("No hay exámenes disponibles para programar. Primero crea un examen en la pestaña Exámenes.")
        else:
            etiquetas = [f"{i+1}. {p.get('nombre', 'Sin nombre')}" for i, p in enumerate(periodos)]
            opciones_prog = ["Nueva programación"] + etiquetas
            sel_prog = st.selectbox("Programación", options=opciones_prog, key="admin_prog_sel")

            periodo_data = {"nombre": "", "examen_config": "", "inicio": "", "fin": "", "grupo": "", "temas": []}
            idx_periodo = None
            if sel_prog != "Nueva programación":
                idx_periodo = int(sel_prog.split('.')[0]) - 1
                periodo_data.update(periodos[idx_periodo])

            cfg_actual = str(periodo_data.get("examen_config", ""))
            asignaturas_cfg = sorted(list(dict.fromkeys([
                Path(c).parts[0] if len(Path(c).parts) > 1 else "General"
                for c in configs_rel
            ])))

            asig_default = ""
            if cfg_actual in configs_rel:
                partes_cfg = Path(cfg_actual).parts
                asig_default = partes_cfg[0] if len(partes_cfg) > 1 else "General"
            elif asignaturas_cfg:
                asig_default = asignaturas_cfg[0]

            col_top1, col_top2, col_top3 = st.columns(3)
            with col_top1:
                nombre_p = st.text_input("Nombre de prueba", value=periodo_data.get("nombre", ""), key="admin_p_nombre")
            with col_top2:
                asignatura_prog = st.selectbox(
                    "Asignatura",
                    options=asignaturas_cfg,
                    index=(asignaturas_cfg.index(asig_default) if asig_default in asignaturas_cfg else 0) if asignaturas_cfg else 0,
                    key="admin_p_asig"
                )
            with col_top3:
                examenes_asig = [
                    c for c in configs_rel
                    if (Path(c).parts[0] if len(Path(c).parts) > 1 else "General") == asignatura_prog
                ]
                idx_ex = examenes_asig.index(cfg_actual) if cfg_actual in examenes_asig else 0
                examen_cfg = st.selectbox("Examen", options=examenes_asig, index=idx_ex, key="admin_p_excfg")

            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                inicio_fecha_default, inicio_hora_default = _parse_fecha_hora(periodo_data.get("inicio", ""))
                inicio_fecha = st.date_input("Inicio (fecha)", value=inicio_fecha_default, key="admin_p_inicio_fecha")
            with col_f2:
                fin_fecha_default, fin_hora_default = _parse_fecha_hora(periodo_data.get("fin", ""))
                fin_fecha = st.date_input("Fin (fecha)", value=fin_fecha_default, key="admin_p_fin_fecha")
            with col_f3:
                grupo_p = st.text_input("Grupo", value=periodo_data.get("grupo", ""), key="admin_p_grupo")

            jornada_noche = st.checkbox(
                "Jornada noche (6:00 PM a 9:45 PM)",
                value=(inicio_hora_default >= "18:00"),
                key="admin_p_jornada_noche"
            )
            hora_opts = _opciones_hora_jornada(jornada_noche)

            if st.session_state.get("admin_p_inicio_hora") not in hora_opts:
                st.session_state["admin_p_inicio_hora"] = inicio_hora_default if inicio_hora_default in hora_opts else hora_opts[0]
            if st.session_state.get("admin_p_fin_hora") not in hora_opts:
                st.session_state["admin_p_fin_hora"] = fin_hora_default if fin_hora_default in hora_opts else hora_opts[-1]

            col_h1, col_h2 = st.columns(2)
            with col_h1:
                inicio_hora = st.selectbox("Inicio (hora)", options=hora_opts, key="admin_p_inicio_hora")
            with col_h2:
                fin_hora = st.selectbox("Fin (hora)", options=hora_opts, key="admin_p_fin_hora")

            inicio_p = f"{inicio_fecha.strftime('%Y-%m-%d')} {inicio_hora}"
            fin_p = f"{fin_fecha.strftime('%Y-%m-%d')} {fin_hora}"

            temas_disponibles = []
            try:
                if examen_cfg:
                    cfg_temas = _cargar_config_examen_por_relpath(base_path, examen_cfg)
                    temas_disponibles = list(cfg_temas.get("bancos_por_tema", {}).keys())
            except Exception:
                temas_disponibles = []

            contexto_temas_prog = f"{sel_prog}|{examen_cfg}|{','.join(temas_disponibles)}"
            if st.session_state.get("admin_prog_temas_context") != contexto_temas_prog:
                for key in [k for k in list(st.session_state.keys()) if str(k).startswith("admin_p_tema_chk_")]:
                    del st.session_state[key]
                st.session_state["admin_prog_temas_context"] = contexto_temas_prog

            st.markdown("**Temas**")
            temas_sel = []
            if temas_disponibles:
                temas_default = set(periodo_data.get("temas", []))
                for i, tema in enumerate(temas_disponibles):
                    key_chk = f"admin_p_tema_chk_{i}"
                    if key_chk not in st.session_state:
                        st.session_state[key_chk] = tema in temas_default
                    if st.checkbox(tema, key=key_chk):
                        temas_sel.append(tema)
            else:
                st.caption("Sin temas configurados para este examen.")

            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Guardar programación", key="admin_p_save", use_container_width=True):
                    nuevo_periodo = {
                        "nombre": nombre_p,
                        "examen_config": examen_cfg,
                        "inicio": inicio_p,
                        "fin": fin_p
                    }
                    if grupo_p.strip():
                        nuevo_periodo["grupo"] = grupo_p.strip()
                    if temas_sel:
                        nuevo_periodo["temas"] = temas_sel

                    nuevos_periodos = list(periodos)
                    if idx_periodo is None:
                        nuevos_periodos.append(nuevo_periodo)
                    else:
                        nuevos_periodos[idx_periodo] = nuevo_periodo

                    ok_cal, msg_cal = _validar_calendario(nuevos_periodos)
                    if not ok_cal:
                        st.error(msg_cal)
                    else:
                        disp["periodos"] = nuevos_periodos
                        disp["habilitado"] = habilitado_actual
                        disp["zona_horaria"] = zona_horaria_actual
                        backup_rel = _crear_backup_config(base_path, ruta_disp, "disponibilidad")
                        _escribir_json(ruta_disp, disp)
                        st.success("Programación guardada")
                        if backup_rel:
                            st.info(f"Backup creado: {backup_rel}")

            with col_del:
                if idx_periodo is not None:
                    confirmar_eliminar_p = st.checkbox("Confirmo eliminar esta programación", key="admin_p_del_confirm")
                    texto_eliminar_p = st.text_input("Escribe ELIMINAR", key="admin_p_del_text")
                    if st.button("🗑️ Eliminar programación", key="admin_p_del", use_container_width=True):
                        if not confirmar_eliminar_p or texto_eliminar_p.strip().upper() != "ELIMINAR":
                            st.error("Confirmación incompleta para eliminar.")
                        else:
                            nuevos_periodos = list(periodos)
                            nuevos_periodos.pop(idx_periodo)
                            ok_cal, msg_cal = _validar_calendario(nuevos_periodos)
                            if not ok_cal:
                                st.error(msg_cal)
                            else:
                                disp["periodos"] = nuevos_periodos
                                disp["habilitado"] = habilitado_actual
                                disp["zona_horaria"] = zona_horaria_actual
                                backup_rel = _crear_backup_config(base_path, ruta_disp, "disponibilidad")
                                _escribir_json(ruta_disp, disp)
                                st.success("Programación eliminada")
                                if backup_rel:
                                    st.info(f"Backup creado: {backup_rel}")

    with tab_ops:
        st.subheader("Operación: hojas por prueba/grupo y desbloqueo")
        disp = _leer_json(_ruta_disponibilidad(base_path))
        periodos = disp.get("periodos", [])
        if not periodos:
            st.info("No hay periodos configurados")
            return

        etiquetas = [f"{i+1}. {p.get('nombre', 'Sin nombre')}" for i, p in enumerate(periodos)]
        sel_op = st.selectbox("Prueba objetivo", etiquetas, key="admin_ops_periodo")
        idx = int(sel_op.split('.')[0]) - 1
        periodo = periodos[idx]

        try:
            ruta_examen, examen_id_estable = _resolver_ruta_examen_config(periodo, base_path)
            cfg = _leer_json(ruta_examen)
            _aplicar_bancos_modulares(cfg, periodo)
            cfg['_examen_id'] = examen_id_estable

            st.write(f"**Config:** {periodo.get('examen_config', '')}")
            st.write(f"**Pestaña destino:** {examen_id_estable}")

            persistence = DataPersistence(cfg)

            col_ops1, col_ops2 = st.columns(2)
            with col_ops1:
                if st.button("📄 Crear/Verificar hoja de resultados", key="admin_ops_sheet", use_container_width=True):
                    ok = persistence.asegurar_hoja_resultados()
                    if ok:
                        st.success("Hoja lista")
                    else:
                        st.error("No se pudo crear/verificar hoja")

            with col_ops2:
                if st.button("🔄 Refrescar bloqueos", key="admin_ops_refresh", use_container_width=True):
                    st.rerun()

            en_curso = persistence.listar_examenes_en_curso()
            if not en_curso:
                st.info("No hay exámenes EN_CURSO para esta prueba")
            else:
                st.dataframe(en_curso, use_container_width=True)
                codigos = [r.get('Codigo_Estudiante', '') for r in en_curso if r.get('Codigo_Estudiante')]
                codigo_sel = st.selectbox("Estudiante", codigos, key="admin_ops_codigo") if codigos else None
                if codigo_sel:
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        if st.button("🔓 Autorizar continuación", key="admin_ops_unlock", use_container_width=True):
                            if persistence.autorizar_continuacion(codigo_sel, True):
                                st.success(f"Autorizado: {codigo_sel}")
                            else:
                                st.error("No se pudo autorizar")
                    with col_u2:
                        if st.button("🔒 Bloquear continuación", key="admin_ops_lock", use_container_width=True):
                            if persistence.autorizar_continuacion(codigo_sel, False):
                                st.success(f"Bloqueado: {codigo_sel}")
                            else:
                                st.error("No se pudo bloquear")
        except Exception as e:
            st.error(f"Error en operación admin: {e}")

        st.markdown("---")
        st.subheader("Publicación a GitHub")
        st.caption("Opción A: guardar local y publicar cambios de configuración y bancos al repositorio.")

        ok_git, hay_pendientes, detalle_git = _git_status_config(base_path)
        if not ok_git:
            st.error(f"No se pudo consultar estado git: {detalle_git}")
        else:
            if hay_pendientes:
                st.warning("Hay cambios pendientes por publicar (configuración/bancos).")
                st.code(detalle_git)
            else:
                st.success("No hay cambios pendientes en rutas publicables (configuración/bancos)")

            mensaje_default = f"chore: publicar cambios admin {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            mensaje_commit = st.text_input("Mensaje de commit", value=mensaje_default, key="admin_git_commit_msg")

            if st.button("🚀 Publicar cambios a GitHub", key="admin_git_publish", use_container_width=True):
                ok_pub, msg_pub = _git_publicar_config(base_path, mensaje_commit)
                if ok_pub:
                    st.success("Cambios publicados en GitHub")
                    if msg_pub:
                        st.code(msg_pub)
                else:
                    st.error(msg_pub or "No se pudo publicar cambios")

        st.markdown("---")
        st.subheader("Publicación completa del repositorio")
        st.caption("Opción B: publicar TODOS los cambios del repositorio (incluye código y otros archivos).")

        ok_git_all, hay_pendientes_all, detalle_git_all = _git_status_todo(base_path)
        if not ok_git_all:
            st.error(f"No se pudo consultar estado git completo: {detalle_git_all}")
        else:
            if hay_pendientes_all:
                st.warning("Hay cambios pendientes en el repositorio completo.")
                st.code(detalle_git_all)
            else:
                st.success("No hay cambios pendientes en el repositorio.")

            mensaje_all_default = f"chore: publicar todo admin {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            mensaje_commit_all = st.text_input("Mensaje commit (todo)", value=mensaje_all_default, key="admin_git_commit_msg_all")
            confirmar_publicar_todo = st.checkbox(
                "Confirmo que deseo publicar TODOS los cambios del repositorio",
                key="admin_git_publish_all_confirm"
            )

            if st.button("🚀 Publicar TODO a GitHub", key="admin_git_publish_all", use_container_width=True):
                if not confirmar_publicar_todo:
                    st.error("Debes confirmar la publicación completa del repositorio.")
                else:
                    ok_pub_all, msg_pub_all = _git_publicar_todo(base_path, mensaje_commit_all)
                    if ok_pub_all:
                        st.success("Repositorio completo publicado en GitHub")
                        if msg_pub_all:
                            st.code(msg_pub_all)
                    else:
                        st.error(msg_pub_all or "No se pudo publicar el repositorio completo")

    with tab_mon:
        st.subheader("Monitoreo en tiempo real")
        disp = _leer_json(_ruta_disponibilidad(base_path))
        periodos = disp.get("periodos", [])
        if not periodos:
            st.info("No hay periodos configurados")
            return

        etiquetas = [f"{i+1}. {p.get('nombre', 'Sin nombre')}" for i, p in enumerate(periodos)]
        sel_mon = st.selectbox("Prueba a monitorear", etiquetas, key="admin_mon_periodo")
        idx_mon = int(sel_mon.split('.')[0]) - 1
        periodo_mon = periodos[idx_mon]

        auto_refresh = st.checkbox("Auto refrescar", value=False, key="admin_mon_auto")
        intervalo = st.selectbox("Intervalo (segundos)", [5, 10, 15, 30], index=1, key="admin_mon_intervalo")
        if st.button("🔄 Refrescar ahora", key="admin_mon_refresh", use_container_width=True):
            st.rerun()

        try:
            ruta_examen, examen_id_estable = _resolver_ruta_examen_config(periodo_mon, base_path)
            cfg_mon = _leer_json(ruta_examen)
            _aplicar_bancos_modulares(cfg_mon, periodo_mon)
            cfg_mon['_examen_id'] = examen_id_estable

            persistence_mon = DataPersistence(cfg_mon)
            en_curso = persistence_mon.listar_examenes_en_curso()
            resultados = persistence_mon.obtener_resultados(limite=2000)

            completados = [r for r in resultados if str(r.get('Razon_Terminacion', '')).strip() not in ('', 'EN_CURSO')]
            bloqueados = [
                r for r in en_curso
                if str(r.get('Autorizado_Continuar', 'NO')).strip().upper() not in ('SI', 'SÍ', 'YES', 'TRUE', '1')
            ]

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Activos (EN_CURSO)", len(en_curso))
            with col_m2:
                st.metric("Completados", len(completados))
            with col_m3:
                st.metric("Bloqueados", len(bloqueados))
            with col_m4:
                total_vistos = len(en_curso) + len(completados)
                pct = (len(completados) / total_vistos * 100.0) if total_vistos > 0 else 0.0
                st.metric("Tasa completación", f"{pct:.1f}%")

            st.markdown("**Estudiantes activos**")
            if en_curso:
                filas = []
                for r in en_curso:
                    filas.append({
                        "Código": r.get("Codigo_Estudiante", ""),
                        "Respondidas": r.get("Preguntas_Respondidas", ""),
                        "Correctas": r.get("Correctas", ""),
                        "Incorrectas": r.get("Incorrectas", ""),
                        "Nivel": r.get("Nivel_Final", ""),
                        "Autorizado": r.get("Autorizado_Continuar", "NO"),
                        "Último estado": "EN_CURSO"
                    })
                st.dataframe(filas, use_container_width=True)
            else:
                st.info("No hay estudiantes activos en este momento.")

        except Exception as e:
            st.error(f"Error en monitoreo: {e}")

        if auto_refresh:
            time.sleep(int(intervalo))
            st.rerun()


def _resolver_ruta_examen_config(periodo: dict, base_path: Path) -> tuple[Path, str]:
    """
    Resuelve ruta de config de examen en arquitectura anidada.

    Formato requerido:
    periodo['examen_config'] = 'Programacion/quizz_1' o 'Programacion/quizz_1.json'
    """
    raiz_examenes = base_path / "config" / "examenes"

    examen_config = periodo.get('examen_config')
    if not examen_config:
        raise ValueError("Cada periodo debe definir 'examen_config' en formato '<Asignatura>/<evaluacion>.json'")

    ruta_rel = str(examen_config).replace('\\', '/').lstrip('./')
    if not ruta_rel.lower().endswith('.json'):
        ruta_rel += '.json'
    ruta_examen = raiz_examenes / ruta_rel

    partes = Path(ruta_rel).parts
    asignatura = partes[0] if partes else "asignatura"
    evaluacion = str(periodo.get('nombre', '')).strip() or Path(ruta_rel).stem

    inicio_raw = str(periodo.get('inicio', '')).strip()
    try:
        inicio_dt = datetime.strptime(inicio_raw, "%Y-%m-%d %H:%M")
        fecha_inicio = inicio_dt.strftime("%Y%m%d_%H%M")
    except ValueError:
        fecha_inicio = _slug_archivo(inicio_raw) or datetime.now().strftime("%Y%m%d_%H%M")

    examen_id_estable = f"{_slug_archivo(asignatura)}_{_slug_archivo(evaluacion)}_{fecha_inicio}"
    if len(examen_id_estable) > 95:
        examen_id_estable = examen_id_estable[:95]
    return ruta_examen, examen_id_estable


def _aplicar_bancos_modulares(config_examen: dict, periodo: dict) -> None:
    """
    Permite selección modular de bancos por evaluación sin romper compatibilidad.

    Opciones soportadas:
    - periodo['bancos_preguntas']: override directo de bancos.
    - periodo['temas']: lista de temas a activar, usando config_examen['bancos_por_tema'].
    """
    bancos_override = periodo.get('bancos_preguntas')
    if bancos_override:
        if not isinstance(bancos_override, list) or not bancos_override:
            raise ValueError("'bancos_preguntas' en disponibilidad debe ser lista no vacía")
        config_examen['bancos_preguntas'] = bancos_override
        config_examen.pop('archivo_preguntas', None)
        return

    temas = periodo.get('temas')
    if not temas:
        return

    if not isinstance(temas, list) or not temas:
        raise ValueError("'temas' en disponibilidad debe ser lista no vacía")

    bancos_por_tema = config_examen.get('bancos_por_tema', {})
    if not isinstance(bancos_por_tema, dict) or not bancos_por_tema:
        raise ValueError("Para usar 'temas', el examen debe definir 'bancos_por_tema' en su configuración")

    bancos_seleccionados = []
    temas_no_encontrados = []
    for tema in temas:
        bancos_tema = bancos_por_tema.get(tema)
        if bancos_tema is None:
            temas_no_encontrados.append(tema)
            continue

        if isinstance(bancos_tema, str):
            bancos_seleccionados.append(bancos_tema)
        elif isinstance(bancos_tema, list):
            bancos_seleccionados.extend(bancos_tema)
        else:
            raise ValueError(f"El tema '{tema}' debe mapear a string o lista de bancos")

    if temas_no_encontrados:
        raise ValueError(f"Temas no definidos en bancos_por_tema: {', '.join(temas_no_encontrados)}")

    # Mantener orden y quitar duplicados
    bancos_unicos = list(dict.fromkeys(bancos_seleccionados))
    if not bancos_unicos:
        raise ValueError("La selección de temas no produjo bancos de preguntas")

    config_examen['bancos_preguntas'] = bancos_unicos
    config_examen.pop('archivo_preguntas', None)
    config_examen['_temas_activos'] = temas


def inicializar_session_state():
    """Inicializa las variables de session state necesarias"""
    if 'exam_started' not in st.session_state:
        st.session_state.exam_started = False
    if 'exam_finished' not in st.session_state:
        st.session_state.exam_finished = False
    if 'codigo_estudiante' not in st.session_state:
        st.session_state.codigo_estudiante = None
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    if 'respuestas' not in st.session_state:
        st.session_state.respuestas = []
    if 'notas_historicas' not in st.session_state:
        st.session_state.notas_historicas = []
    if 'preguntas_usadas' not in st.session_state:
        st.session_state.preguntas_usadas = []


def main():
    """Función principal de la aplicación"""
    base_path = Path(__file__).parent
    
    # Configuración de la página
    st.set_page_config(
        page_title="Sistema de Exámenes - ECCI",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Reducir espacio superior de Streamlit
    st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Inicializar session state
    inicializar_session_state()
    if 'admin_mode' not in st.session_state:
        st.session_state.admin_mode = False
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    if 'admin_prompt' not in st.session_state:
        st.session_state.admin_prompt = False
    if 'admin_last_activity_ts' not in st.session_state:
        st.session_state.admin_last_activity_ts = 0.0
    if 'admin_timeout_seconds' not in st.session_state:
        st.session_state.admin_timeout_seconds = 900
    if 'admin_timeout_notice' not in st.session_state:
        st.session_state.admin_timeout_notice = False

    ahora_ts = datetime.now().timestamp()
    if st.session_state.admin_authenticated:
        last_ts = float(st.session_state.get('admin_last_activity_ts', 0.0) or 0.0)
        timeout_s = int(st.session_state.get('admin_timeout_seconds', 900))
        if last_ts and (ahora_ts - last_ts) > timeout_s:
            st.session_state.admin_authenticated = False
            st.session_state.admin_mode = False
            st.session_state.admin_prompt = False
            st.session_state.admin_last_activity_ts = 0.0
            st.session_state.admin_timeout_notice = True
            if 'admin_password_input' in st.session_state:
                del st.session_state['admin_password_input']
        else:
            st.session_state.admin_last_activity_ts = ahora_ts

    if st.session_state.admin_timeout_notice:
        st.warning("La sesión de administrador se cerró por inactividad.")
        st.session_state.admin_timeout_notice = False

    top_left, top_right = st.columns([9, 1])
    with top_right:
        if st.button("admin", key="toggle_admin", use_container_width=True):
            if st.session_state.admin_mode:
                st.session_state.admin_mode = False
                st.session_state.admin_prompt = False
            else:
                if st.session_state.admin_authenticated:
                    st.session_state.admin_mode = True
                else:
                    st.session_state.admin_prompt = True
            st.rerun()

    if st.session_state.admin_prompt and not st.session_state.admin_authenticated:
        with st.container(border=True):
            st.markdown("### 🔐 Acceso administrador")
            clave_ingresada = st.text_input("Contraseña admin", type="password", key="admin_password_input")
            col_auth1, col_auth2 = st.columns(2)
            with col_auth1:
                if st.button("Ingresar", key="admin_login_btn", use_container_width=True):
                    clave_configurada = _obtener_clave_admin()
                    if not clave_configurada:
                        st.error("No hay clave admin configurada en secrets (ADMIN_PASSWORD).")
                    elif clave_ingresada == clave_configurada:
                        st.session_state.admin_authenticated = True
                        st.session_state.admin_mode = True
                        st.session_state.admin_prompt = False
                        st.session_state.admin_last_activity_ts = datetime.now().timestamp()
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta")
            with col_auth2:
                if st.button("Cancelar", key="admin_login_cancel", use_container_width=True):
                    st.session_state.admin_prompt = False
                    st.rerun()

    if st.session_state.admin_mode:
        _render_panel_admin(base_path)
        return
    
    # ============================================
    # VERIFICAR DISPONIBILIDAD Y OBTENER EXAMEN
    # Nota: una vez iniciado, se conserva el examen en sesión
    # para evitar reinicios por cierre de ventana horaria.
    # ============================================
    config = None
    mensaje = ""
    periodos = None

    examen_en_sesion = (
        (st.session_state.exam_started or st.session_state.exam_finished)
        and ('config_examen_activo' in st.session_state)
    )

    if examen_en_sesion:
        disponible = True
        config = st.session_state.config_examen_activo
        mensaje = st.session_state.get('periodo_activo_nombre', 'Examen en curso')
    else:
        disponible, config, mensaje, periodos = verificar_disponibilidad()
    
    if not disponible:
        # Mostrar pantalla de "no disponible"
        st.title("🎓 Sistema de Exámenes")
        st.error("⏰ No hay exámenes disponibles en este momento")
        st.warning(f"📅 {mensaje}")
        
        # Mostrar hora actual
        zona = ZoneInfo("America/Bogota")
        ahora = datetime.now(zona)
        st.info(f"🕐 Hora actual: {ahora.strftime('%d/%m/%Y %H:%M')} (Colombia)")
        
        # Mostrar calendario
        if periodos:
            st.markdown("### 📆 Próximos exámenes programados")
            for p in periodos:
                inicio = datetime.strptime(p['inicio'], "%Y-%m-%d %H:%M")
                if inicio > ahora.replace(tzinfo=None):
                    st.write(f"📝 **{p.get('nombre', 'Examen')}:** {p['inicio']} → {p['fin']}")
        return
    
    # Antes de iniciar: sincronizar examen activo. Durante el intento: conservarlo fijo.
    if not st.session_state.exam_started and not st.session_state.exam_finished:
        st.session_state.config_examen_activo = config
        st.session_state.periodo_activo_nombre = mensaje

    # ============================================
    # EXAMEN DISPONIBLE - CONTINUAR NORMALMENTE
    # ============================================
    try:
        # Cargar bancos de preguntas (arquitectura modular)
        if 'bancos_preguntas' not in config:
            raise ValueError("La configuración del examen debe definir 'bancos_preguntas' (arquitectura modular)")

        bancos_cfg = list(config.get('bancos_preguntas', []))
        firma_bancos = _firma_bancos(base_path, bancos_cfg)
        preguntas_cacheadas = _cargar_preguntas_bancos_cacheado(str(base_path), tuple(bancos_cfg), firma_bancos)

        question_manager = QuestionManager(
            base_path=base_path,
            preguntas_data=preguntas_cacheadas
        )
        
        # Inicializar componentes
        ui = UIComponents(config)
        security_policy = get_security_policy(config)
        
        # Verificar que hay suficientes preguntas
        total_preguntas = len(question_manager.preguntas)
        if total_preguntas < config['parametros']['preguntas_minimas']:
            st.error(f"⚠️ Error: El banco tiene {total_preguntas} preguntas, "
                    f"se necesitan al menos {config['parametros']['preguntas_minimas']}")
            return
        
        # Mostrar header con nombre del examen
        ui.mostrar_header(periodo_activo=mensaje)
        
        # Flujo principal
        if not st.session_state.exam_started:
            mostrar_pantalla_inicio(config, ui, security_policy)
        elif st.session_state.exam_finished:
            mostrar_resultados(config, ui)
        else:
            ejecutar_examen(config, question_manager, ui, security_policy)
            
    except FileNotFoundError as e:
        _log_evento_operacion(base_path, "error_archivo", f"Archivo no encontrado: {str(e)}", examen_id=str(config.get('_examen_id', '')) if isinstance(config, dict) else "")
        st.error(f"❌ Error: No se encontró archivo.\n{str(e)}")
    except Exception as e:
        _log_evento_operacion(base_path, "error_general", str(e), examen_id=str(config.get('_examen_id', '')) if isinstance(config, dict) else "")
        st.error(f"❌ Error inesperado: {str(e)}")
        st.exception(e)

def verificar_disponibilidad():
    """
    Verifica qué examen está disponible según el calendario.
    Retorna: (disponible, examen_config, mensaje, periodos)
    """
    # Cargar archivo de disponibilidad
    try:
        ruta_disponibilidad = Path(__file__).parent / "config" / "disponibilidad.json"
        disponibilidad = _leer_json(ruta_disponibilidad)
    except FileNotFoundError:
        return False, None, "No se encontró archivo de disponibilidad", None
    
    # Si no está habilitado, no hay exámenes disponibles
    if not disponibilidad.get('habilitado', False):
        return False, None, "Sistema de exámenes deshabilitado", None
    
    # Configurar zona horaria
    zona = ZoneInfo(disponibilidad.get('zona_horaria', 'America/Bogota'))
    ahora = datetime.now(zona)
    
    periodos = disponibilidad.get('periodos', [])
    if not periodos:
        return False, None, "No hay periodos configurados", None
    
    # Buscar si estamos DENTRO de algún periodo
    for periodo in periodos:
        inicio = datetime.strptime(periodo['inicio'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        fin = datetime.strptime(periodo['fin'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        
        if inicio <= ahora <= fin:
            # ✅ Estamos dentro de un periodo válido - cargar config del examen
            try:
                base_path = Path(__file__).parent
                ruta_examen, examen_id_estable = _resolver_ruta_examen_config(periodo, base_path)
                config_examen = _leer_json(ruta_examen)

                # Aplicar overrides modulares desde disponibilidad (si existen)
                _aplicar_bancos_modulares(config_examen, periodo)
                
                # Validar configuración del examen
                loader = ConfigLoader(base_path=base_path)
                loader.validar_config_dict(config_examen)
                
                config_examen['_examen_id'] = examen_id_estable  # Guardar ID para referencia
                
                # Cargar instrucciones desde archivo separado
                ruta_instrucciones = base_path / "config" / "instrucciones.json"
                try:
                    instrucciones = _leer_json(ruta_instrucciones)
                except FileNotFoundError:
                    instrucciones = {"titulo": "Instrucciones", "items": [], "advertencias": []}
                
                # Combinar con descripción del examen
                config_examen['instrucciones'] = instrucciones
                config_examen['instrucciones']['descripcion'] = config_examen.get('descripcion', {})
                return True, config_examen, periodo.get('nombre', 'Examen activo'), periodos
            except FileNotFoundError as e:
                examen_ref = periodo.get('examen_config', '')
                return False, None, f"Error en examen '{examen_ref}': {str(e)}", periodos
            except ValueError as e:
                examen_ref = periodo.get('examen_config', '')
                return False, None, f"Configuración inválida para '{examen_ref}': {str(e)}", periodos
    
    # ❌ NO estamos en ningún periodo - buscar el próximo
    proximos = []
    for periodo in periodos:
        inicio = datetime.strptime(periodo['inicio'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        if inicio > ahora:
            proximos.append((inicio, periodo))
    
    if proximos:
        proximos.sort(key=lambda x: x[0])
        proximo = proximos[0][1]
        mensaje = f"Próximo examen: {proximo.get('nombre', '')} - {proximo['inicio']}"
    else:
        mensaje = "No hay exámenes programados"
    
    return False, None, mensaje, periodos


def mostrar_pantalla_inicio(config, ui, security_policy):
    """Muestra la pantalla de inicio del examen"""
    
    # Mostrar instrucciones
    ui.mostrar_instrucciones()
    render_security_banner(security_policy)
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.markdown("##### 📝 Comencemos por tú código (ARCA)")

    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        codigo = st.text_input(
            "Código de estudiante:",
            placeholder="Ejemplo: 12345678",
            max_chars=20,
            key="input_codigo",
            label_visibility="collapsed"
        )
    
    with col2:
        if st.button("🚀 Comenzar Examen", type="primary", use_container_width=True):
            if not codigo:
                st.error("⚠️ Por favor ingrese su código de estudiante")
            elif not validate_codigo_estudiante(codigo):
                st.error("⚠️ Código inválido. Debe contener solo números y letras")
            else:
                codigo_limpio = codigo.strip().upper()
                base_path = Path(__file__).parent
                examen_id = str(config.get('_examen_id', ''))
                
                try:
                    persistence = DataPersistence(config)
                    if persistence.verificar_examen_completado(codigo_limpio):
                        _log_evento_operacion(base_path, "acceso_bloqueado", "Intento repetido de examen completado", codigo=codigo_limpio, examen_id=examen_id)
                        st.error("⚠️ Ya completaste este examen anteriormente.")
                        st.info("💡 Solo se permite un intento por estudiante.")
                        return
                    progreso = persistence.obtener_progreso_en_curso(codigo_limpio)
                    if progreso:
                        autorizado = str(progreso.get('Autorizado_Continuar', 'NO')).strip().upper() in ('SI', 'SÍ', 'YES', 'TRUE', '1')
                        if not autorizado:
                            _log_evento_operacion(base_path, "acceso_bloqueado", "Reanudación no autorizada", codigo=codigo_limpio, examen_id=examen_id)
                            st.error("🔒 Tienes un examen en curso bloqueado para reanudación.")
                            st.info("🧑‍🏫 Solicita autorización docente. En Google Sheets, cambia la columna 'Autorizado_Continuar' a 'SI' en tu fila EN_CURSO.")
                            return

                        # Consumir autorización al momento de reanudar para evitar
                        # que el estudiante entre/salga repetidamente del parcial.
                        if not persistence.autorizar_continuacion(codigo_limpio, False):
                            _log_evento_operacion(base_path, "acceso_bloqueado", "No se pudo consumir autorización de reanudación", codigo=codigo_limpio, examen_id=examen_id)
                            st.error("🔒 No se pudo validar el consumo de autorización para reanudar.")
                            st.info("🧑‍🏫 Intenta nuevamente o solicita autorización docente.")
                            return

                        _log_evento_operacion(base_path, "autorizacion_consumida", "Autorización de reanudación consumida", codigo=codigo_limpio, examen_id=examen_id)

                        _log_evento_operacion(base_path, "restauracion", "Examen reanudado desde estado EN_CURSO", codigo=codigo_limpio, examen_id=examen_id)
                        st.info("🔄 Se detectó un examen en curso autorizado. Restaurando progreso...")
                        st.session_state.codigo_estudiante = codigo_limpio
                        st.session_state.exam_started = True
                        st.session_state.exam_finished = False
                        st.session_state.current_question_index = int(progreso.get('Preguntas_Respondidas', 0) or 0)
                        st.session_state.respuestas = []
                        st.session_state.notas_historicas = []
                        st.session_state.preguntas_usadas = progreso.get('Preguntas_IDs', '').split(',') if progreso.get('Preguntas_IDs') else []
                        st.session_state.progreso_a_restaurar = progreso
                        st.rerun()
                        return
                except Exception as e:
                    _log_evento_operacion(base_path, "warning_persistencia", f"Error verificando progreso: {e}", codigo=codigo_limpio, examen_id=examen_id)
                    st.warning(f"⚠️ Error al verificar progreso: {e}")
                st.session_state.codigo_estudiante = codigo_limpio
                st.session_state.exam_started = True
                _log_evento_operacion(base_path, "inicio", "Inicio de examen", codigo=codigo_limpio, examen_id=examen_id)
                st.rerun()
    
    with col3:
        with st.expander("ℹ️ Más información"):
            st.write(f"""
            **{config['metadata']['asignatura']}**
            - ✅ Preguntas adaptadas a tu nivel
            - ✅ Entre {config['parametros']['preguntas_minimas']} y {config['parametros']['preguntas_maximas']} preguntas
            - ✅ Calificación basada en IRT
            """)

def _manejar_umbral_foco(config: dict, security_policy: dict, focus_count: int) -> None:
    """
    Registra nuevas perdidas de foco en el log y, si se supera el umbral
    configurado, registra la alerta en Sheets y detiene el examen.
    """
    if not security_policy.get("habilitado", True):
        return
    if not security_policy.get("detectar_perdida_foco", True):
        return

    prev = int(st.session_state.get('_sec_fl_prev_logged', 0))
    if focus_count > prev:
        delta = focus_count - prev
        st.session_state['_sec_fl_prev_logged'] = focus_count
        _log_evento_operacion(
            Path(__file__).parent,
            "perdida_foco",
            f"Cambios de foco detectados: +{delta} (total={focus_count})",
            codigo=st.session_state.get('codigo_estudiante', ''),
            examen_id=str(config.get('_examen_id', '')),
            extra={"focus_losses": focus_count, "delta": delta},
        )
        try:
            persistence = DataPersistence(config)
            persistence.actualizar_contador_cambios_foco(
                st.session_state.get('codigo_estudiante', ''),
                focus_count,
            )
        except Exception:
            pass

    max_perm = int(security_policy.get("max_perdidas_foco_permitidas", 0))
    if max_perm > 0 and focus_count >= max_perm:
        _log_evento_operacion(
            Path(__file__).parent,
            "alerta_seguridad",
            f"Umbral de perdidas de foco superado: {focus_count}/{max_perm}",
            codigo=st.session_state.get('codigo_estudiante', ''),
            examen_id=str(config.get('_examen_id', '')),
            extra={"focus_losses": focus_count, "max": max_perm},
        )
        try:
            persistence = DataPersistence(config)
            persistence.registrar_alerta_seguridad(
                st.session_state.get('codigo_estudiante', ''),
                "max_perdidas_foco",
                f"focus_losses={focus_count},max_permitidas={max_perm}",
            )
        except Exception:
            pass

        st.error(
            f"🚨 Se detectaron {focus_count} cambios de pestaña/foco "
            f"(máximo permitido: {max_perm}). "
            "El intento ha sido marcado para revisión docente. "
            "No puedes continuar este examen."
        )
        st.warning("Si crees que es un error, comunícate con tu docente.")
        st.stop()


def ejecutar_examen(config, question_manager, ui, security_policy):
    """Ejecuta la lógica del examen"""

    codigo = str(st.session_state.get("codigo_estudiante") or "")
    apply_client_hardening(security_policy, codigo_estudiante=codigo)
    focus_count = render_focus_counter_sentinel(security_policy)
    _manejar_umbral_foco(config, security_policy, focus_count)

    # ── Fingerprint de sesion ─────────────────────────────────────────────────
    fingerprint = render_fingerprint_sentinel(security_policy)
    if fingerprint and not st.session_state.get('_fp_guardado'):
        st.session_state['_fp_guardado'] = True
        st.session_state['_fingerprint_sesion'] = fingerprint
        _log_evento_operacion(
            Path(__file__).parent,
            "fingerprint_sesion",
            "Fingerprint de cliente registrado",
            codigo=codigo,
            examen_id=str(config.get('_examen_id', '')),
            extra={"fingerprint": fingerprint},
        )
        try:
            persistence = DataPersistence(config)
            persistence.actualizar_fingerprint_sesion(codigo, fingerprint)
        except Exception:
            pass
    elif fingerprint and st.session_state.get('_fp_guardado'):
        prev_fp = st.session_state.get('_fingerprint_sesion', '')
        if prev_fp and fingerprint != prev_fp:
            _log_evento_operacion(
                Path(__file__).parent,
                "alerta_seguridad",
                "Cambio de fingerprint detectado durante el examen",
                codigo=codigo,
                examen_id=str(config.get('_examen_id', '')),
                extra={"fp_previo": prev_fp, "fp_nuevo": fingerprint},
            )
            try:
                persistence = DataPersistence(config)
                persistence.registrar_alerta_seguridad(
                    codigo, "cambio_fingerprint",
                    f"fp_previo={prev_fp[:80]},fp_nuevo={fingerprint[:80]}"
                )
            except Exception:
                pass

    if 'security_policy_logged' not in st.session_state:
        st.session_state.security_policy_logged = False
    if not st.session_state.security_policy_logged:
        _log_evento_operacion(
            Path(__file__).parent,
            "seguridad_cliente",
            "Politica de hardening cliente aplicada",
            codigo=st.session_state.get('codigo_estudiante', ''),
            examen_id=str(config.get('_examen_id', '')),
            extra={"policy": security_policy}
        )
        st.session_state.security_policy_logged = True
    
    # Inicializar lógica del examen si es necesario
    if 'exam_logic' not in st.session_state:
        st.session_state.exam_logic = ExamLogic(config, question_manager)
        progreso = st.session_state.pop('progreso_a_restaurar', None)

        if progreso:
            restaurado = _restaurar_estado_exam_logic(st.session_state.exam_logic, question_manager, progreso)
            if not restaurado:
                st.warning("⚠️ No se pudo restaurar completamente el estado. Se continuará con estado parcial.")
        else:
            try:
                persistence = DataPersistence(config)
                persistence.guardar_inicio_examen(st.session_state.codigo_estudiante)
                _log_evento_operacion(Path(__file__).parent, "inicio_persistido", "Registro EN_CURSO creado", codigo=st.session_state.codigo_estudiante, examen_id=str(config.get('_examen_id', '')))
            except Exception as e:
                _log_evento_operacion(Path(__file__).parent, "warning_persistencia", f"No se pudo guardar inicio: {e}", codigo=st.session_state.codigo_estudiante, examen_id=str(config.get('_examen_id', '')))
                st.warning(f"⚠️ No se pudo guardar el inicio del examen: {e}")
    
    exam_logic = st.session_state.exam_logic
    
    # Verificar si el examen debe terminar
    if exam_logic.debe_terminar_examen():
        st.session_state.exam_finished = True
        guardar_resultados(config, exam_logic)
        st.rerun()
        return
    
    # Mostrar métricas de progreso
    ui.mostrar_metricas_progreso(
        codigo=st.session_state.codigo_estudiante,
        pregunta_actual=exam_logic.pregunta_actual + 1,
        total_preguntas=config['parametros']['preguntas_maximas'],
        correctas=exam_logic.correctas,
        incorrectas=exam_logic.incorrectas
    )
    
    # Obtener pregunta actual
    pregunta_key = f"pregunta_actual_{exam_logic.pregunta_actual}"
    opciones_key = f"opciones_pregunta_{exam_logic.pregunta_actual}"
    
    if pregunta_key not in st.session_state:
        pregunta_obj = exam_logic.obtener_siguiente_pregunta()
        
        if pregunta_obj is None:
            if exam_logic.pregunta_actual < exam_logic.preguntas_minimas:
                faltantes = exam_logic.preguntas_minimas - exam_logic.pregunta_actual
                _log_evento_operacion(
                    Path(__file__).parent,
                    "error_sin_preguntas_minimo_no_cumplido",
                    f"Sin preguntas disponibles antes de mínimo: respondidas={exam_logic.pregunta_actual}, minimo={exam_logic.preguntas_minimas}, faltantes={faltantes}",
                    codigo=st.session_state.get('codigo_estudiante', ''),
                    examen_id=str(config.get('_examen_id', ''))
                )
                st.error(
                    f"⚠️ No hay suficientes preguntas disponibles para completar el mínimo del examen. "
                    f"Respondidas: {exam_logic.pregunta_actual} / Mínimo: {exam_logic.preguntas_minimas}."
                )
                st.stop()

            st.session_state.exam_finished = True
            guardar_resultados(config, exam_logic)
            st.rerun()
            return
        
        st.session_state[pregunta_key] = pregunta_obj
        st.session_state[opciones_key] = exam_logic.mezclar_opciones(pregunta_obj['opciones'])
        # Registrar momento en que se muestra la pregunta para medir tiempo de respuesta
        st.session_state[f'_ts_q_{exam_logic.pregunta_actual}'] = time.time()

        try:
            persistence = DataPersistence(config)
            persistence.actualizar_progreso_examen(
                st.session_state.codigo_estudiante,
                exam_logic.pregunta_actual,
                exam_logic.correctas,
                exam_logic.incorrectas,
                nivel_actual=exam_logic.nivel_actual,
                nota_actual=exam_logic.historial_notas[-1] if exam_logic.historial_notas else 0.0,
                preguntas_ids=exam_logic.preguntas_usadas,
                theta_actual=exam_logic.theta_actual,
                estado_json=_serializar_estado_exam_logic(
                    exam_logic,
                    pregunta_pendiente=pregunta_obj,
                    opciones_pendientes=st.session_state[opciones_key],
                )
            )
        except Exception as e:
            _log_evento_operacion(Path(__file__).parent, "warning_persistencia", f"No se pudo persistir pregunta pendiente: {e}", codigo=st.session_state.codigo_estudiante, examen_id=str(config.get('_examen_id', '')))
    
    pregunta_obj = st.session_state[pregunta_key]
    opciones_mezcladas = st.session_state[opciones_key]
    
    # Layout dos columnas
    col_pregunta, col_opciones = st.columns([3, 2])
    
    with col_pregunta:
        base_path = Path(__file__).parent
        dificultad = pregunta_obj['dificultad']
        color = ui._get_dificultad_color(dificultad)
        categoria = pregunta_obj.get('categoria', '')
        categoria_html = f"<span style='color: #6c757d;'>📂 {categoria}</span>" if categoria else ""
        
        # Header de la tarjeta
        html_header = f"<div style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px 8px 0 0; overflow: hidden;'><div style='background-color: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #dee2e6; display: flex; justify-content: space-between; align-items: center;'><span style='font-weight: bold;'>Pregunta {exam_logic.pregunta_actual + 1}</span><div>{categoria_html}<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-left: 10px;'>Nivel {dificultad}</span></div></div></div>"
        st.markdown(html_header, unsafe_allow_html=True)
        
        # Contenido de la pregunta (texto, imagen o mermaid)
        _render_contenido_pregunta(pregunta_obj, base_path)

    with col_opciones:

        html_header = "<div style='background-color: #f8f9fa; padding: 8px 15px; border: 1px solid #dee2e6; border-radius: 8px 8px 0 0; border-bottom: none;'><span style='font-weight: bold; color: #495057;'>Seleccione su respuesta:</span></div>"
        st.markdown(html_header, unsafe_allow_html=True)
        
        respuesta_seleccionada = st.radio(
            "Respuesta:",
            options=list(opciones_mezcladas.keys()),
            format_func=lambda x: f"{x}) {opciones_mezcladas[x]}",
            key=f"respuesta_{exam_logic.pregunta_actual}",
            index=None,
            label_visibility="collapsed"
        )
        
        if st.button("🚀 Confirmar Respuesta", type="primary", use_container_width=True):
            if not respuesta_seleccionada:
                st.warning("⚠️ Debes seleccionar una opción antes de confirmar.")
                st.stop()

            _ts_inicio = st.session_state.get(f'_ts_q_{exam_logic.pregunta_actual}')
            _tiempo_resp = round(time.time() - _ts_inicio, 1) if _ts_inicio else None

            exam_logic.procesar_respuesta(
                pregunta_obj,
                respuesta_seleccionada,
                opciones_mezcladas,
                tiempo_respuesta_s=_tiempo_resp,
            )
            
            if pregunta_key in st.session_state:
                del st.session_state[pregunta_key]
            if opciones_key in st.session_state:
                del st.session_state[opciones_key]
            respuesta_key = f"respuesta_{exam_logic.pregunta_actual - 1}"
            if respuesta_key in st.session_state:
                del st.session_state[respuesta_key]
            
            try:
                persistence = DataPersistence(config)
                persistence.actualizar_progreso_examen(
                    st.session_state.codigo_estudiante,
                    exam_logic.pregunta_actual,
                    exam_logic.correctas,
                    exam_logic.incorrectas,
                    nivel_actual=exam_logic.nivel_actual,
                    nota_actual=exam_logic.historial_notas[-1] if exam_logic.historial_notas else 0.0,
                    preguntas_ids=exam_logic.preguntas_usadas,
                    theta_actual=exam_logic.theta_actual,
                    estado_json=_serializar_estado_exam_logic(exam_logic)
                )
            except Exception as e:
                _log_evento_operacion(Path(__file__).parent, "warning_persistencia", f"No se pudo actualizar progreso: {e}", codigo=st.session_state.codigo_estudiante, examen_id=str(config.get('_examen_id', '')))
                pass
            
            st.rerun()

    # Diagrama mermaid renderizado a ancho completo, debajo de las columnas
    if str(pregunta_obj.get('tipo', 'texto')).strip().lower() == 'mermaid':
        mermaid_src = str(pregunta_obj.get('mermaid', '')).strip()
        if mermaid_src:
            html = f"""
            <div id="mermaid-wrap" style="background:#fff; padding:12px; border-radius:8px; border:1px solid #dee2e6;">
              <pre class="mermaid">{mermaid_src}</pre>
            </div>
            <script type="module">
              import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
              mermaid.initialize({{ startOnLoad: false, theme: 'default' }});
              await mermaid.run();
              const wrap = document.getElementById('mermaid-wrap');
              const resize = () => {{
                const h = wrap.scrollHeight;
                if (window.frameElement) window.frameElement.height = h + 24;
              }};
              resize();
              setTimeout(resize, 150);
              setTimeout(resize, 400);
            </script>
            """
            st_components.html(html, height=800, scrolling=False)

def guardar_resultados(config, exam_logic):
    """Guarda los resultados del examen en Google Sheets"""
    try:
        # 1. PRIMERO: Calcular estadísticas
        stats = exam_logic.calcular_estadisticas_finales()

        # Inyectar métricas de seguridad en config para _preparar_datos
        config['_fingerprint_sesion'] = st.session_state.get('_fingerprint_sesion', '')
        config['_respuestas_rapidas'] = stats.get('respuestas_rapidas', 0)

        # 2. SEGUNDO: Guardar en session_state INMEDIATAMENTE (antes de cualquier st.write)
        st.session_state.final_stats = stats
        
        # 3. TERCERO: Ahora sí guardar en Sheets (con mensajes)
        st.info("🔄 Guardando resultados en Google Sheets...")
        
        persistence = DataPersistence(config)
        resultado = persistence.guardar_resultados(
            codigo_estudiante=st.session_state.codigo_estudiante,
            stats=stats
        )
        
        if resultado:
            _log_evento_operacion(Path(__file__).parent, "fin", "Resultados guardados exitosamente", codigo=st.session_state.codigo_estudiante, examen_id=str(config.get('_examen_id', '')), extra={"nota_final": stats.get('nota_final', 0), "preguntas": stats.get('preguntas_respondidas', 0)})
            st.success("✅ Resultados guardados exitosamente")
        else:
            _log_evento_operacion(Path(__file__).parent, "warning_persistencia", "Guardado de resultados devolvió False", codigo=st.session_state.codigo_estudiante, examen_id=str(config.get('_examen_id', '')))
            st.warning("⚠️ Los resultados se muestran pero hubo un problema al guardar en Sheets")
        
    except Exception as e:
        _log_evento_operacion(Path(__file__).parent, "error_persistencia", f"Error al guardar resultados: {str(e)}", codigo=st.session_state.get('codigo_estudiante', ''), examen_id=str(config.get('_examen_id', '')))
        st.error(f"⚠️ Error al guardar en Sheets: {str(e)}")
        # Los resultados se mostrarán igual porque ya están en session_state



def mostrar_resultados(config, ui):
    """Muestra los resultados finales del examen"""
    
    if 'final_stats' not in st.session_state:
        st.error("❌ Error: No se encontraron resultados del examen")
        return
    
    stats = st.session_state.final_stats
    
    # Mostrar resultados
    ui.mostrar_resultados_finales(
        stats=stats,
        codigo=st.session_state.codigo_estudiante
    )
    
    # Botón para reiniciar
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 Realizar otro examen", type="primary", use_container_width=True):
            # Limpiar session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()
