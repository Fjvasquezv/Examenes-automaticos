"""
Sistema de Examen Adaptativo Modular
Orquestador Principal
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import unicodedata
import re
import subprocess

# Agregar AMBOS directorios al path
base = Path(__file__).parent
sys.path.insert(0, str(base / "src"))
sys.path.insert(0, str(base / "utils"))

# Importar SIN prefijos
from config_loader import ConfigLoader
from question_manager import QuestionManager
from exam_logic import ExamLogic
from ui_components import UIComponents
from src.data_persistence import DataPersistence
from validators import validate_codigo_estudiante


def _serializar_estado_exam_logic(exam_logic) -> str:
    """Serializa el estado mínimo necesario para restaurar un examen en curso."""
    respuestas_minimas = []
    for r in exam_logic.preguntas_respondidas:
        respuestas_minimas.append({
            'pregunta_id': r.get('pregunta_id', ''),
            'dificultad': r.get('dificultad', 3),
            'categoria': r.get('categoria', 'Sin categoría'),
            'correcta': bool(r.get('correcta', False)),
            'nivel_en_pregunta': r.get('nivel_en_pregunta', 3)
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
    return json.dumps(payload, ensure_ascii=False)


def _restaurar_estado_exam_logic(exam_logic, progreso: dict) -> bool:
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


def _leer_json(ruta: Path) -> dict:
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)


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


def _git_status_config(base_path: Path) -> tuple[bool, bool, str]:
    try:
        res = _run_git(base_path, ["status", "--porcelain", "--", "config/examenes", "config/disponibilidad.json"])
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

        r_add = _run_git(base_path, ["add", "config/examenes", "config/disponibilidad.json"])
        if r_add.returncode != 0:
            return False, (r_add.stderr or r_add.stdout or "No se pudo hacer git add").strip()

        r_diff = _run_git(base_path, ["diff", "--cached", "--quiet", "--", "config/examenes", "config/disponibilidad.json"])
        if r_diff.returncode == 0:
            return False, "No hay cambios de configuración para publicar."

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

    tab_exam, tab_prog, tab_ops = st.tabs(["Exámenes", "Programación", "Operación"])

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
        st.subheader("Activar / Desactivar / Programar pruebas")
        ruta_disp = _ruta_disponibilidad(base_path)
        disp = _leer_json(ruta_disp)

        habilitado = st.checkbox("Sistema habilitado", value=bool(disp.get("habilitado", True)), key="admin_disp_hab")
        zona_horaria = st.text_input("Zona horaria", value=disp.get("zona_horaria", "America/Bogota"), key="admin_disp_tz")

        periodos = disp.get("periodos", [])
        etiquetas = [f"{i+1}. {p.get('nombre', 'Sin nombre')}" for i, p in enumerate(periodos)]
        opciones_periodo = ["<Nuevo periodo>"] + etiquetas
        sel_periodo = st.selectbox("Periodo", options=opciones_periodo, key="admin_disp_sel_periodo")

        configs_rel = _listar_configs_examenes(base_path)
        periodo_data = {"nombre": "", "examen_config": "", "inicio": "", "fin": "", "grupo": "", "temas": []}
        idx_periodo = None
        if sel_periodo != "<Nuevo periodo>":
            idx_periodo = int(sel_periodo.split('.')[0]) - 1
            periodo_data.update(periodos[idx_periodo])

        nombre_p = st.text_input("Nombre de prueba", value=periodo_data.get("nombre", ""), key="admin_p_nombre")
        examen_cfg = st.selectbox(
            "Examen config",
            options=configs_rel,
            index=(configs_rel.index(periodo_data.get("examen_config")) if periodo_data.get("examen_config") in configs_rel else 0) if configs_rel else 0,
            key="admin_p_excfg"
        ) if configs_rel else st.text_input("Examen config", value=periodo_data.get("examen_config", ""), key="admin_p_excfg_text")
        inicio_p = st.text_input("Inicio (YYYY-MM-DD HH:MM)", value=periodo_data.get("inicio", ""), key="admin_p_inicio")
        fin_p = st.text_input("Fin (YYYY-MM-DD HH:MM)", value=periodo_data.get("fin", ""), key="admin_p_fin")
        grupo_p = st.text_input("Grupo (opcional, genera hoja separada)", value=periodo_data.get("grupo", ""), key="admin_p_grupo")

        temas_disponibles = []
        try:
            cfg_temas = _cargar_config_examen_por_relpath(base_path, examen_cfg)
            temas_disponibles = list(cfg_temas.get("bancos_por_tema", {}).keys())
        except Exception:
            temas_disponibles = []

        temas_sel = st.multiselect(
            "Temas para esta prueba",
            options=temas_disponibles,
            default=periodo_data.get("temas", []),
            key="admin_p_temas"
        )

        colp_save, colp_del, colp_disp = st.columns(3)
        with colp_save:
            if st.button("💾 Guardar periodo", key="admin_p_save", use_container_width=True):
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
                    disp["habilitado"] = bool(habilitado)
                    disp["zona_horaria"] = zona_horaria
                    backup_rel = _crear_backup_config(base_path, ruta_disp, "disponibilidad")
                    _escribir_json(ruta_disp, disp)
                    st.success("Periodo guardado")
                    if backup_rel:
                        st.info(f"Backup creado: {backup_rel}")

        with colp_del:
            if idx_periodo is not None and st.button("🗑️ Eliminar periodo", key="admin_p_del", use_container_width=True):
                nuevos_periodos = list(periodos)
                nuevos_periodos.pop(idx_periodo)
                ok_cal, msg_cal = _validar_calendario(nuevos_periodos)
                if not ok_cal:
                    st.error(msg_cal)
                else:
                    disp["periodos"] = nuevos_periodos
                    disp["habilitado"] = bool(habilitado)
                    disp["zona_horaria"] = zona_horaria
                    backup_rel = _crear_backup_config(base_path, ruta_disp, "disponibilidad")
                    _escribir_json(ruta_disp, disp)
                    st.success("Periodo eliminado")
                    if backup_rel:
                        st.info(f"Backup creado: {backup_rel}")

        with colp_disp:
            if st.button("✅ Guardar disponibilidad", key="admin_disp_save", use_container_width=True):
                ok_cal, msg_cal = _validar_calendario(periodos)
                if not ok_cal:
                    st.error(msg_cal)
                else:
                    disp["habilitado"] = bool(habilitado)
                    disp["zona_horaria"] = zona_horaria
                    disp["periodos"] = periodos
                    backup_rel = _crear_backup_config(base_path, ruta_disp, "disponibilidad")
                    _escribir_json(ruta_disp, disp)
                    st.success("Disponibilidad guardada")
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
        st.caption("Opción A: guardar local y publicar cambios de configuración al repositorio.")

        ok_git, hay_pendientes, detalle_git = _git_status_config(base_path)
        if not ok_git:
            st.error(f"No se pudo consultar estado git: {detalle_git}")
        else:
            if hay_pendientes:
                st.warning("Hay cambios de configuración pendientes por publicar.")
                st.code(detalle_git)
            else:
                st.success("No hay cambios pendientes en config/examenes y config/disponibilidad.json")

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
    # ============================================
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
    
    # ============================================
    # EXAMEN DISPONIBLE - CONTINUAR NORMALMENTE
    # ============================================
    try:
        # Cargar bancos de preguntas (arquitectura modular)
        if 'bancos_preguntas' not in config:
            raise ValueError("La configuración del examen debe definir 'bancos_preguntas' (arquitectura modular)")

        question_manager = QuestionManager(
            bancos_preguntas=config['bancos_preguntas'],
            base_path=base_path
        )
        
        # Inicializar componentes
        ui = UIComponents(config)
        
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
            mostrar_pantalla_inicio(config, ui)
        elif st.session_state.exam_finished:
            mostrar_resultados(config, ui)
        else:
            ejecutar_examen(config, question_manager, ui)
            
    except FileNotFoundError as e:
        st.error(f"❌ Error: No se encontró archivo.\n{str(e)}")
    except Exception as e:
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
        with open(ruta_disponibilidad, 'r', encoding='utf-8') as f:
            disponibilidad = json.load(f)
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

                with open(ruta_examen, 'r', encoding='utf-8') as f:
                    config_examen = json.load(f)

                # Aplicar overrides modulares desde disponibilidad (si existen)
                _aplicar_bancos_modulares(config_examen, periodo)
                
                # Validar configuración del examen
                loader = ConfigLoader(base_path=base_path)
                loader.validar_config_dict(config_examen)
                
                config_examen['_examen_id'] = examen_id_estable  # Guardar ID para referencia
                
                # Cargar instrucciones desde archivo separado
                ruta_instrucciones = base_path / "config" / "instrucciones.json"
                try:
                    with open(ruta_instrucciones, 'r', encoding='utf-8') as f2:
                        instrucciones = json.load(f2)
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


def mostrar_pantalla_inicio(config, ui):
    """Muestra la pantalla de inicio del examen"""
    
    # Mostrar instrucciones
    ui.mostrar_instrucciones()
    
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
                
                try:
                    persistence = DataPersistence(config)
                    if persistence.verificar_examen_completado(codigo_limpio):
                        st.error("⚠️ Ya completaste este examen anteriormente.")
                        st.info("💡 Solo se permite un intento por estudiante.")
                        return
                    progreso = persistence.obtener_progreso_en_curso(codigo_limpio)
                    if progreso:
                        autorizado = str(progreso.get('Autorizado_Continuar', 'NO')).strip().upper() in ('SI', 'SÍ', 'YES', 'TRUE', '1')
                        if not autorizado:
                            st.error("🔒 Tienes un examen en curso bloqueado para reanudación.")
                            st.info("🧑‍🏫 Solicita autorización docente. En Google Sheets, cambia la columna 'Autorizado_Continuar' a 'SI' en tu fila EN_CURSO.")
                            return

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
                    st.warning(f"⚠️ Error al verificar progreso: {e}")
                st.session_state.codigo_estudiante = codigo_limpio
                st.session_state.exam_started = True
                st.rerun()
    
    with col3:
        with st.expander("ℹ️ Más información"):
            st.write(f"""
            **{config['metadata']['asignatura']}**
            - ✅ Preguntas adaptadas a tu nivel
            - ✅ Entre {config['parametros']['preguntas_minimas']} y {config['parametros']['preguntas_maximas']} preguntas
            - ✅ Calificación basada en IRT
            """)

def ejecutar_examen(config, question_manager, ui):
    """Ejecuta la lógica del examen"""
    
    # Inicializar lógica del examen si es necesario
    if 'exam_logic' not in st.session_state:
        st.session_state.exam_logic = ExamLogic(config, question_manager)
        progreso = st.session_state.pop('progreso_a_restaurar', None)

        if progreso:
            restaurado = _restaurar_estado_exam_logic(st.session_state.exam_logic, progreso)
            if not restaurado:
                st.warning("⚠️ No se pudo restaurar completamente el estado. Se continuará con estado parcial.")
        else:
            try:
                persistence = DataPersistence(config)
                persistence.guardar_inicio_examen(st.session_state.codigo_estudiante)
            except Exception as e:
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
            st.session_state.exam_finished = True
            guardar_resultados(config, exam_logic)
            st.rerun()
            return
        
        st.session_state[pregunta_key] = pregunta_obj
        st.session_state[opciones_key] = exam_logic.mezclar_opciones(pregunta_obj['opciones'])
    
    pregunta_obj = st.session_state[pregunta_key]
    opciones_mezcladas = st.session_state[opciones_key]
    
    # Layout dos columnas
    col_pregunta, col_opciones = st.columns([3, 2])
    
    with col_pregunta:
        dificultad = pregunta_obj['dificultad']
        color = ui._get_dificultad_color(dificultad)
        categoria = pregunta_obj.get('categoria', '')
        categoria_html = f"<span style='color: #6c757d;'>📂 {categoria}</span>" if categoria else ""
        
        # Header de la tarjeta
        html_header = f"<div style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px 8px 0 0; overflow: hidden;'><div style='background-color: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #dee2e6; display: flex; justify-content: space-between; align-items: center;'><span style='font-weight: bold;'>Pregunta {exam_logic.pregunta_actual + 1}</span><div>{categoria_html}<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-left: 10px;'>Nivel {dificultad}</span></div></div></div>"
        st.markdown(html_header, unsafe_allow_html=True)
        
        # Contenido de la pregunta (separado para que el código se renderice bien)
        st.markdown(pregunta_obj['pregunta'])
    
    with col_opciones:
        html_header = "<div style='background-color: #f8f9fa; padding: 8px 15px; border: 1px solid #dee2e6; border-radius: 8px 8px 0 0; border-bottom: none;'><span style='font-weight: bold; color: #495057;'>Seleccione su respuesta:</span></div>"
        st.markdown(html_header, unsafe_allow_html=True)
        
        respuesta_seleccionada = st.radio(
            "Respuesta:",
            options=list(opciones_mezcladas.keys()),
            format_func=lambda x: f"{x}) {opciones_mezcladas[x]}",
            key=f"respuesta_{exam_logic.pregunta_actual}",
            label_visibility="collapsed"
        )
        
        if st.button("🚀 Confirmar Respuesta", type="primary", use_container_width=True):
            exam_logic.procesar_respuesta(
                pregunta_obj,
                respuesta_seleccionada,
                opciones_mezcladas
            )
            
            if pregunta_key in st.session_state:
                del st.session_state[pregunta_key]
            if opciones_key in st.session_state:
                del st.session_state[opciones_key]
            
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
            except:
                pass
            
            st.rerun()
            
def guardar_resultados(config, exam_logic):
    """Guarda los resultados del examen en Google Sheets"""
    try:
        # 1. PRIMERO: Calcular estadísticas
        stats = exam_logic.calcular_estadisticas_finales()
        
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
            st.success("✅ Resultados guardados exitosamente")
        else:
            st.warning("⚠️ Los resultados se muestran pero hubo un problema al guardar en Sheets")
        
    except Exception as e:
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
