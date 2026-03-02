"""
Validador de bancos de preguntas (compatibilidad v1)

Uso:
    python utils/validate_question_banks.py
    python utils/validate_question_banks.py --path data/bancos
"""

import argparse
import json
import sys
from pathlib import Path

from validators import validate_banco_preguntas_v1_compatible


def _iter_json_files(base_path: Path) -> list[Path]:
    if base_path.is_file() and base_path.suffix.lower() == '.json':
        return [base_path]
    if base_path.is_dir():
        return sorted(base_path.rglob('*.json'))
    return []


def _validar_archivo(path: Path) -> tuple[bool, list[str], list[str]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as exc:
        return False, [f"No se pudo leer/parsear JSON: {exc}"], []

    return validate_banco_preguntas_v1_compatible(data)


def main() -> int:
    parser = argparse.ArgumentParser(description='Valida bancos de preguntas JSON (esquema compatible v1).')
    parser.add_argument(
        '--path',
        default='data/bancos',
        help='Ruta a archivo JSON o directorio con bancos (default: data/bancos)'
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    target = (root / args.path).resolve() if not Path(args.path).is_absolute() else Path(args.path)

    files = _iter_json_files(target)
    if not files:
        print(f"[ERROR] No se encontraron archivos JSON en: {target}")
        return 2

    total = len(files)
    ok_count = 0
    warn_count = 0
    error_count = 0

    print(f"Validando {total} archivo(s) en: {target}")

    for file_path in files:
        ok, errors, warnings = _validar_archivo(file_path)

        rel = file_path.relative_to(root) if file_path.is_relative_to(root) else file_path
        status = 'OK' if ok else 'ERROR'
        print(f"\n[{status}] {rel}")

        if warnings:
            warn_count += len(warnings)
            for warning in warnings:
                print(f"  - [WARN] {warning}")

        if errors:
            error_count += len(errors)
            for error in errors:
                print(f"  - [ERR]  {error}")
        else:
            ok_count += 1

    print("\n--- Resumen ---")
    print(f"Archivos válidos: {ok_count}/{total}")
    print(f"Advertencias: {warn_count}")
    print(f"Errores: {error_count}")

    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
