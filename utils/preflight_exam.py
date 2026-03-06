"""
Preflight operativo de exámenes

Valida, en un solo comando:
- disponibilidad y periodo activo (o periodo específico)
- carga de configuración de examen
- resolución de bancos por temas (si aplica)
- existencia y validez de bancos JSON
- conteo de preguntas vs mínimo requerido

Uso:
    python utils/preflight_exam.py
    python utils/preflight_exam.py --periodo "QUIZZ 1 - Introducción a la Tecnología"
    python utils/preflight_exam.py --fecha "2026-03-06 11:50"
"""

import argparse
import json
import sys
import unicodedata
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# Permitir imports desde root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

from config_loader import ConfigLoader
from validators import validate_banco_preguntas_v1_compatible


def _slugify(texto: str) -> str:
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()


def _slug_archivo(texto: str) -> str:
    base = _slugify(texto)
    base = re.sub(r'[^a-z0-9]+', '_', base).strip('_')
    return base or 'examen'


def _resolver_ruta_examen_config(periodo: dict, base_path: Path) -> tuple[Path, str]:
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

    bancos_unicos = list(dict.fromkeys(bancos_seleccionados))
    if not bancos_unicos:
        raise ValueError("La selección de temas no produjo bancos de preguntas")

    config_examen['bancos_preguntas'] = bancos_unicos
    config_examen.pop('archivo_preguntas', None)


def _cargar_disponibilidad(base_path: Path) -> Dict[str, Any]:
    path = base_path / "config" / "disponibilidad.json"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _seleccionar_periodo(disponibilidad: dict, ahora: datetime, periodo_nombre: str = "") -> dict:
    periodos = disponibilidad.get('periodos', [])
    if not periodos:
        raise ValueError("No hay periodos configurados")

    if periodo_nombre:
        for p in periodos:
            if str(p.get('nombre', '')).strip() == periodo_nombre.strip():
                return p
        raise ValueError(f"No se encontró periodo con nombre exacto: {periodo_nombre}")

    for p in periodos:
        inicio = datetime.strptime(p['inicio'], "%Y-%m-%d %H:%M")
        fin = datetime.strptime(p['fin'], "%Y-%m-%d %H:%M")
        if inicio <= ahora <= fin:
            return p

    raise ValueError("No hay periodo activo para la fecha/hora indicada")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight operativo del examen")
    parser.add_argument('--periodo', default='', help='Nombre exacto del periodo en disponibilidad.json')
    parser.add_argument('--fecha', default='', help='Fecha/hora de referencia YYYY-MM-DD HH:MM (zona disponibilidad)')
    args = parser.parse_args()

    base_path = ROOT
    disponibilidad = _cargar_disponibilidad(base_path)

    if not disponibilidad.get('habilitado', False):
        print("[ERROR] Sistema deshabilitado en disponibilidad.json")
        return 1

    zona = ZoneInfo(disponibilidad.get('zona_horaria', 'America/Bogota'))
    if args.fecha:
        ahora = datetime.strptime(args.fecha, "%Y-%m-%d %H:%M")
    else:
        ahora = datetime.now(zona).replace(tzinfo=None)

    try:
        periodo = _seleccionar_periodo(disponibilidad, ahora, args.periodo)
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    print(f"[OK] Periodo seleccionado: {periodo.get('nombre', 'Sin nombre')}")
    print(f"     Ventana: {periodo.get('inicio')} -> {periodo.get('fin')}")

    try:
        ruta_examen, examen_id = _resolver_ruta_examen_config(periodo, base_path)
    except Exception as e:
        print(f"[ERROR] No se pudo resolver examen_config: {e}")
        return 1

    if not ruta_examen.exists():
        print(f"[ERROR] No existe config de examen: {ruta_examen}")
        return 1

    with open(ruta_examen, 'r', encoding='utf-8') as f:
        config_examen = json.load(f)

    try:
        _aplicar_bancos_modulares(config_examen, periodo)
    except Exception as e:
        print(f"[ERROR] Error aplicando bancos modulares: {e}")
        return 1

    config_examen['_examen_id'] = examen_id

    loader = ConfigLoader(base_path=base_path)
    try:
        loader.validar_config_dict(config_examen)
        print("[OK] Configuración de examen válida")
    except Exception as e:
        print(f"[ERROR] Configuración inválida: {e}")
        return 1

    bancos = config_examen.get('bancos_preguntas', [])
    if not bancos:
        print("[ERROR] No hay bancos_preguntas tras aplicar configuración")
        return 1

    total_preguntas = 0
    bancos_invalidos = 0
    ids_globales = set()
    ids_duplicados_globales = set()

    print(f"[OK] Bancos activos: {len(bancos)}")
    for banco_rel in bancos:
        banco_path = base_path / banco_rel
        if not banco_path.exists():
            print(f"  [ERROR] Banco no encontrado: {banco_rel}")
            bancos_invalidos += 1
            continue

        try:
            with open(banco_path, 'r', encoding='utf-8') as f:
                preguntas = json.load(f)
        except Exception as e:
            print(f"  [ERROR] JSON inválido en {banco_rel}: {e}")
            bancos_invalidos += 1
            continue

        ok_banco, errores, warnings = validate_banco_preguntas_v1_compatible(preguntas)
        if not ok_banco:
            print(f"  [ERROR] Banco inválido: {banco_rel}")
            for err in errores[:5]:
                print(f"         - {err}")
            if len(errores) > 5:
                print(f"         - ... {len(errores) - 5} errores adicionales")
            bancos_invalidos += 1
            continue

        for warning in warnings[:3]:
            print(f"  [WARN] {banco_rel}: {warning}")

        count = len(preguntas)
        total_preguntas += count

        for p in preguntas:
            pid = p.get('id', None)
            if isinstance(pid, str) and pid:
                if pid in ids_globales:
                    ids_duplicados_globales.add(pid)
                ids_globales.add(pid)

        print(f"  [OK] {banco_rel} -> {count} preguntas")

    if bancos_invalidos > 0:
        print(f"[ERROR] Hay {bancos_invalidos} banco(s) inválidos")
        return 1

    if ids_duplicados_globales:
        print(f"[ERROR] IDs duplicados entre bancos: {len(ids_duplicados_globales)}")
        ejemplo = sorted(list(ids_duplicados_globales))[:10]
        print(f"        Ejemplos: {', '.join(ejemplo)}")
        return 1

    preguntas_minimas = int(config_examen['parametros']['preguntas_minimas'])
    if total_preguntas < preguntas_minimas:
        print(f"[ERROR] Banco total insuficiente: {total_preguntas} < mínimo {preguntas_minimas}")
        return 1

    print(f"[OK] Preguntas totales: {total_preguntas} (mínimo requerido: {preguntas_minimas})")
    print("[OK] PREFLIGHT APROBADO")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
