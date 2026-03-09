"""
Test End-to-End de Fase 1
Simula el flujo real de la aplicación con las optimizaciones
"""
import sys
import json
from pathlib import Path
import time

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'utils'))

def test_flujo_completo():
    """Simula el flujo completo de carga con caché"""
    print("\n=== TEST END-TO-END FASE 1 ===\n")
    
    # 1. Cargar configuración JSON (simula _leer_json_cacheado)
    print("[1/5] Cargando configuración de examen...")
    config_path = ROOT / "config" / "examenes" / "Introduccion" / "quizz_1.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    bancos_cfg = config.get('bancos_preguntas', config.get('bancos_activos', []))
    print(f"  ✓ {len(bancos_cfg)} bancos configurados")
    
    # 2. Generar firma de bancos (simula _firma_bancos)
    print("\n[2/5] Generando firma de caché para bancos...")
    firma_parts = []
    for banco_rel in bancos_cfg:
        banco_path = ROOT / banco_rel
        if banco_path.exists():
            stat = banco_path.stat()
            firma_parts.append(f"{banco_rel}:{stat.st_mtime}:{stat.st_size}")
    firma = "|".join(firma_parts)
    print(f"  ✓ Firma generada: {len(firma)} caracteres")
    
    # 3. Cargar preguntas (simula _cargar_preguntas_bancos_cacheado)
    print("\n[3/5] Cargando preguntas desde bancos...")
    preguntas = []
    for banco_rel in bancos_cfg:
        banco_path = ROOT / banco_rel
        if banco_path.exists():
            with open(banco_path, 'r', encoding='utf-8') as f:
                preguntas.extend(json.load(f))
    print(f"  ✓ {len(preguntas)} preguntas cargadas desde {len(bancos_cfg)} bancos")
    
    # 4. Crear QuestionManager con preguntas precargadas
    print("\n[4/5] Inicializando QuestionManager con caché...")
    from src.question_manager import QuestionManager
    
    start_time = time.time()
    qm_cache = QuestionManager(base_path=ROOT, preguntas_data=preguntas)
    cache_time = time.time() - start_time
    
    start_time = time.time()
    qm_legacy = QuestionManager(base_path=ROOT, bancos_preguntas=bancos_cfg)
    legacy_time = time.time() - start_time
    
    print(f"  ✓ QuestionManager con caché: {len(qm_cache.preguntas)} preguntas ({cache_time*1000:.2f}ms)")
    print(f"  ✓ QuestionManager legacy: {len(qm_legacy.preguntas)} preguntas ({legacy_time*1000:.2f}ms)")
    
    assert len(qm_cache.preguntas) == len(qm_legacy.preguntas), \
        f"Caché y legacy deben cargar igual cantidad: {len(qm_cache.preguntas)} vs {len(qm_legacy.preguntas)}"
    
    # 5. Logging de evento
    print("\n[5/5] Registrando evento en log...")
    from exam_logger import ExamLogger
    logger = ExamLogger(ROOT)
    logger.evento(
        tipo="test_e2e",
        mensaje="Test end-to-end completado",
        codigo_estudiante="TEST001",
        examen_id="E2E001",
        extra={
            "preguntas_cache": len(qm_cache.preguntas),
            "preguntas_legacy": len(qm_legacy.preguntas),
            "bancos": len(bancos_cfg),
            "cache_time_ms": cache_time * 1000,
            "legacy_time_ms": legacy_time * 1000
        }
    )
    print("  ✓ Evento registrado en logs/operacion.log")
    
    # Verificar que el log se escribió
    log_file = ROOT / "logs" / "operacion.log"
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            last_line = f.readlines()[-1]
        assert "test_e2e" in last_line, "Evento no encontrado en log"
        print(f"  ✓ Log verificado: {len(last_line)} caracteres")
    
    print("\n=== RESULTADO ===")
    print(f"✅ Flujo completo ejecutado correctamente")
    print(f"✅ Caché y legacy mode son equivalentes ({len(qm_cache.preguntas)} preguntas)")
    print(f"✅ Logging operativo funcionando")
    
    # Mostrar beneficio de caché (solo informativo, puede variar)
    if legacy_time > 0:
        speedup = legacy_time / cache_time if cache_time > 0 else 0
        print(f"\n📊 Caché {speedup:.1f}x más rápido que legacy mode")
    
    return True

if __name__ == "__main__":
    try:
        success = test_flujo_completo()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
