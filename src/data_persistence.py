"""
Persistencia de Datos
Maneja el guardado de resultados en Google Sheets
"""
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List
import time
import random
import logging
import threading
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from zoneinfo import ZoneInfo


class DataPersistence:
    """Clase para manejar la persistencia en Google Sheets"""

    COLUMNA_ESTADO = 14
    COLUMNA_AUTORIZADO_CONTINUAR = 16
    COLUMNA_ESTADO_JSON = 17
    RANGO_DATOS = 'A:R'
    MAX_REINTENTOS_API = 5
    RETRY_BASE_SECONDS = 0.4
    MIN_INTERVALO_REQUEST_SECONDS = 0.20
    _api_rate_lock = threading.Lock()
    _api_next_request_ts = 0.0

    _logger = logging.getLogger("examenes.data_persistence")
    if not _logger.handlers:
        _logger.setLevel(logging.INFO)
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        _logger.addHandler(_handler)

    @classmethod
    def _respetar_rate_limit(cls):
        """Aplica limitación global de requests para proteger cuota de Google Sheets."""
        with cls._api_rate_lock:
            ahora = time.time()
            if ahora < cls._api_next_request_ts:
                time.sleep(cls._api_next_request_ts - ahora)
            cls._api_next_request_ts = time.time() + cls.MIN_INTERVALO_REQUEST_SECONDS

    def _ejecutar_con_reintentos(self, request, descripcion: str = "operación"):
        """
        Ejecuta un request de Google API con reintentos para errores transitorios.
        """
        ultimo_error = None
        for intento in range(self.MAX_REINTENTOS_API):
            try:
                self._respetar_rate_limit()
                return request.execute()
            except HttpError as e:
                ultimo_error = e
                status = getattr(e.resp, 'status', None)
                transitorio = status in (408, 409, 429, 500, 502, 503, 504)
                self._logger.warning(
                    "Sheets error transitorio=%s status=%s intento=%s desc=%s",
                    transitorio,
                    status,
                    intento + 1,
                    descripcion
                )
                if (not transitorio) or intento == self.MAX_REINTENTOS_API - 1:
                    raise

                pausa = self.RETRY_BASE_SECONDS * (2 ** intento) + random.uniform(0, 0.25)
                time.sleep(pausa)
            except Exception as e:
                ultimo_error = e
                self._logger.warning(
                    "Sheets excepción intento=%s desc=%s error=%s",
                    intento + 1,
                    descripcion,
                    str(e)
                )
                if intento == self.MAX_REINTENTOS_API - 1:
                    raise
                pausa = self.RETRY_BASE_SECONDS * (2 ** intento) + random.uniform(0, 0.25)
                time.sleep(pausa)

        if ultimo_error:
            raise ultimo_error

    def obtener_progreso_en_curso(self, codigo_estudiante: str) -> dict:
        """
        Obtiene el registro EN_CURSO del estudiante para restaurar el estado.
        Returns: dict con los campos del progreso o None si no existe.
        """
        try:
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
            ), "obtener_progreso_en_curso")
            values = result.get('values', [])
            encabezados = values[0] if values else []
            for row in reversed(values[1:]):
                if len(row) > self.COLUMNA_ESTADO and len(row) > 1:
                    if row[1] == codigo_estudiante and row[self.COLUMNA_ESTADO] == 'EN_CURSO':
                        while len(row) < len(encabezados):
                            row.append('')
                        return dict(zip(encabezados, row))
            return None
        except Exception:
            return None
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el sistema de persistencia
        
        Args:
            config: Configuración del examen
        """
        self.config = config
        self.spreadsheet_id = config['persistencia']['spreadsheet_id']
        
        # Nombre de pestaña exacto derivado del ID del examen.
        # Formato esperado: Asignatura_NombreDeEvaluacion_FechaDeInicio
        # Si no hay _examen_id, usa "Resultados" por compatibilidad.
        examen_id = config.get('_examen_id', '')
        self.nombre_hoja = str(examen_id) if examen_id else 'Resultados'
        
        self.service = None
        self._inicializar_servicio()
    
    def _inicializar_servicio(self):
        """Inicializa el servicio de Google Sheets"""
        try:
            # Obtener credenciales desde secrets
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            
            # Crear servicio
            self.service = build('sheets', 'v4', credentials=credentials)
            
        except Exception as e:
            st.error(f"⚠️ Error al inicializar Google Sheets: {str(e)}")
            raise
    
    def guardar_inicio_examen(self, codigo_estudiante: str) -> bool:
        """
        Guarda el registro de inicio de examen
        
        Args:
            codigo_estudiante: Código del estudiante
            
        Returns:
            True si se guardó exitosamente
        """
        try:
            fecha_hora = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
            
            datos = [
                fecha_hora,
                codigo_estudiante,
                0,  # preguntas_respondidas
                0,  # correctas
                0,  # incorrectas
                0,  # porcentaje
                self.config['parametros']['nivel_inicial'],  # nivel_final
                0.0,  # nota_final
                '',  # preguntas_ids
                '',  # theta
                '',  # consistencia
                '',  # nivel_habilidad
                '',  # rating
                '',  # cambio_rating
                'EN_CURSO',  # razon_terminacion
                self.config['sistema_calificacion']['tipo'],  # sistema
                'NO',  # autorizado_continuar
                ''  # estado_json
            ]
            
            self._verificar_o_crear_hoja()
            self._agregar_fila(datos)
            
            return True
            
        except Exception as e:
            st.warning(f"⚠️ No se pudo guardar el inicio del examen: {str(e)}")
            return False
    
    def actualizar_progreso_examen(
        self, 
        codigo_estudiante: str,
        preguntas_respondidas: int,
        correctas: int,
        incorrectas: int,
        nivel_actual: int = None,
        nota_actual: float = None,
        preguntas_ids: List[str] = None,
        theta_actual: float = None,
        estado_json: str = None
    ) -> bool:
        """
        Actualiza el progreso del examen en curso
        
        Args:
            codigo_estudiante: Código del estudiante
            preguntas_respondidas: Número de preguntas respondidas
            correctas: Número de correctas
            incorrectas: Número de incorrectas
            
        Returns:
            True si se actualizó exitosamente
        """
        try:
            # Buscar la última fila del estudiante con estado EN_CURSO
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
            ), "leer progreso examen")
            
            values = result.get('values', [])
            
            # Encontrar la última fila EN_CURSO de este estudiante
            fila_a_actualizar = None
            for i in range(len(values) - 1, 0, -1):  # Buscar desde el final
                if len(values[i]) > 1 and values[i][1] == codigo_estudiante:
                    if len(values[i]) > self.COLUMNA_ESTADO and values[i][self.COLUMNA_ESTADO] == 'EN_CURSO':
                        fila_a_actualizar = i + 1  # +1 porque sheets es 1-indexed
                        break
            
            if fila_a_actualizar:
                # Actualizar solo las columnas de progreso
                porcentaje = (correctas / preguntas_respondidas * 100) if preguntas_respondidas > 0 else 0
                
                updates = [
                    {
                        'range': f'{self.nombre_hoja}!C{fila_a_actualizar}',
                        'values': [[preguntas_respondidas]]
                    },
                    {
                        'range': f'{self.nombre_hoja}!D{fila_a_actualizar}',
                        'values': [[correctas]]
                    },
                    {
                        'range': f'{self.nombre_hoja}!E{fila_a_actualizar}',
                        'values': [[incorrectas]]
                    },
                    {
                        'range': f'{self.nombre_hoja}!F{fila_a_actualizar}',
                        'values': [[round(porcentaje, 1)]]
                    }
                ]

                if nivel_actual is not None:
                    updates.append({
                        'range': f'{self.nombre_hoja}!G{fila_a_actualizar}',
                        'values': [[int(max(1, min(5, nivel_actual)))]]
                    })

                if nota_actual is not None:
                    updates.append({
                        'range': f'{self.nombre_hoja}!H{fila_a_actualizar}',
                        'values': [[round(float(nota_actual), 2)]]
                    })

                if preguntas_ids is not None:
                    updates.append({
                        'range': f'{self.nombre_hoja}!I{fila_a_actualizar}',
                        'values': [[','.join(preguntas_ids)]]
                    })

                if theta_actual is not None:
                    updates.append({
                        'range': f'{self.nombre_hoja}!J{fila_a_actualizar}',
                        'values': [[round(float(theta_actual), 3)]]
                    })

                if estado_json is not None:
                    updates.append({
                        'range': f'{self.nombre_hoja}!R{fila_a_actualizar}',
                        'values': [[estado_json]]
                    })
                
                body = {'data': updates, 'valueInputOption': 'RAW'}
                self._ejecutar_con_reintentos(self.service.spreadsheets().values().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ), "actualizar progreso examen")
                
                return True
            
            return False
            
        except Exception as e:
            # No mostrar error al usuario, solo registrar
            return False
    
    def verificar_examen_en_curso(self, codigo_estudiante: str) -> bool:
        """
        Verifica si el estudiante tiene un examen en curso
        
        Args:
            codigo_estudiante: Código del estudiante
            
        Returns:
            True si tiene un examen EN_CURSO
        """
        try:
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
            ), "verificar examen en curso")
            
            values = result.get('values', [])
            
            # Buscar si hay alguna fila EN_CURSO para este estudiante
            for row in reversed(values[1:]):  # Skip header, buscar desde el final
                if len(row) > self.COLUMNA_ESTADO and len(row) > 1:
                    if row[1] == codigo_estudiante and row[self.COLUMNA_ESTADO] == 'EN_CURSO':
                        return True
            
            return False
            
        except Exception:
            return False
    
    def verificar_examen_completado(self, codigo_estudiante: str) -> bool:
        """
        Verifica si el estudiante ya completó el examen
        
        Args:
            codigo_estudiante: Código del estudiante
            
        Returns:
            True si ya completó el examen (tiene registro con razón_terminacion diferente a EN_CURSO)
        """
        try:
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
            ), "verificar examen completado")
            
            values = result.get('values', [])
            
            # Buscar si hay alguna fila COMPLETADA para este estudiante
            for row in values[1:]:  # Skip header
                if len(row) > self.COLUMNA_ESTADO and len(row) > 1:
                    if row[1] == codigo_estudiante:
                        # Si el estado NO es EN_CURSO, significa que completó
                        if row[self.COLUMNA_ESTADO] != 'EN_CURSO' and row[self.COLUMNA_ESTADO] != '':
                            return True
            
            return False
            
        except Exception:
            return False
    
    def guardar_resultados(self, codigo_estudiante: str, stats: Dict[str, Any]) -> bool:
        """
        Guarda los resultados del examen en Google Sheets
        Actualiza la fila EN_CURSO si existe, o crea una nueva
        
        Args:
            codigo_estudiante: Código del estudiante
            stats: Estadísticas del examen
            
        Returns:
            True si se guardó exitosamente, False en caso contrario
        """
        try:
            # Preparar datos
            datos = self._preparar_datos(codigo_estudiante, stats)
            
            # Verificar si existe la hoja
            self._verificar_o_crear_hoja()
            
            # Buscar si hay una fila EN_CURSO para este estudiante
            try:
                result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
                ), "leer resultados previos")
                
                values = result.get('values', [])
                fila_a_actualizar = None
                
                # Buscar la última fila EN_CURSO de este estudiante
                for i in range(len(values) - 1, 0, -1):
                    if len(values[i]) > 1 and values[i][1] == codigo_estudiante:
                        if len(values[i]) > self.COLUMNA_ESTADO and values[i][self.COLUMNA_ESTADO] == 'EN_CURSO':
                            fila_a_actualizar = i + 1  # +1 porque sheets es 1-indexed
                            break
                
                if fila_a_actualizar:
                    # Actualizar la fila existente
                    range_to_update = f'{self.nombre_hoja}!A{fila_a_actualizar}:R{fila_a_actualizar}'
                    body = {'values': [datos]}
                    self._ejecutar_con_reintentos(self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_to_update,
                        valueInputOption='RAW',
                        body=body
                    ), "actualizar resultados finales")
                else:
                    # Agregar nueva fila
                    self._agregar_fila(datos)
                
                return True
                
            except HttpError:
                # Fallback seguro: intentar append para no perder resultados.
                try:
                    self._agregar_fila(datos)
                    return True
                except Exception:
                    return False
            
        except Exception as e:
            st.error(f"⚠️ Error al guardar resultados: {str(e)}")
            return False
    
    def _preparar_datos(self, codigo_estudiante: str, stats: Dict[str, Any]) -> List[Any]:
        """
        Prepara los datos para guardar en Google Sheets
        
        Args:
            codigo_estudiante: Código del estudiante
            stats: Estadísticas del examen
            
        Returns:
            Lista con los datos a guardar
        """
        # Fecha y hora actual
        fecha_hora = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
        
        # IDs de preguntas separados por coma
        preguntas_ids = ",".join(stats['preguntas_ids'])
        
        # Datos básicos
        datos = [
            fecha_hora,
            codigo_estudiante,
            stats['preguntas_respondidas'],
            stats['correctas'],
            stats['incorrectas'],
            stats['porcentaje_correctas'],
            stats['nivel_final'],
            stats['nota_final'],
            preguntas_ids
        ]
        
        # Agregar estadísticas del sistema de calificación
        stats_sistema = stats.get('stats_sistema', {})
        
        # Theta (IRT)
        datos.append(stats_sistema.get('theta', ''))
        
        # Consistencia (IRT)
        datos.append(stats_sistema.get('consistencia', ''))
        
        # Nivel de habilidad (IRT)
        datos.append(stats_sistema.get('nivel_habilidad', ''))
        
        # Rating (Elo)
        datos.append(stats_sistema.get('rating', ''))
        
        # Cambio de rating (Elo)
        datos.append(stats_sistema.get('cambio_rating', ''))
        
        # Razón de terminación
        datos.append(stats['razon_terminacion'])
        
        # Sistema de calificación usado
        datos.append(self.config['sistema_calificacion']['tipo'])

        # Autorización para continuar (solo aplica EN_CURSO)
        datos.append('NO')

        # Estado serializado (solo aplica EN_CURSO)
        datos.append('')
        
        return datos
    
    def _verificar_o_crear_hoja(self):
        """Verifica si existe la hoja de resultados, si no, la crea con encabezados"""
        try:
            # Intentar obtener información de la hoja
            sheet_metadata = self._ejecutar_con_reintentos(self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ), "obtener metadata de hoja")
            
            # Verificar si existe la pestaña del examen
            sheets = sheet_metadata.get('sheets', [])
            existe_hoja = any(
                sheet['properties']['title'] == self.nombre_hoja 
                for sheet in sheets
            )
            
            if not existe_hoja:
                # Crear la hoja
                self._crear_hoja_resultados()
            else:
                # Verificar si tiene encabezados
                self._verificar_encabezados()
                
        except HttpError as e:
            raise Exception(f"Error al verificar hoja: {str(e)}")
    
    def _crear_hoja_resultados(self):
        """Crea la hoja de Resultados con encabezados"""
        try:
            # Crear nueva pestaña para este examen
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': self.nombre_hoja,
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 20
                            }
                        }
                    }
                }]
            }
            
            self._ejecutar_con_reintentos(self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ), "crear pestaña de resultados")
            
            # Agregar encabezados
            self._escribir_encabezados()
            
        except HttpError as e:
            raise Exception(f"Error al crear hoja: {str(e)}")
    
    def _verificar_encabezados(self):
        """Verifica si la primera fila tiene encabezados, si no, los agrega"""
        try:
            # Leer primera fila
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!A1:R1'
            ), "verificar encabezados")
            
            values = result.get('values', [])
            
            # Si está vacía, escribir encabezados
            if not values or not values[0]:
                self._escribir_encabezados()
            elif len(values[0]) < 18:
                # Hoja antigua: actualizar encabezados al esquema actual
                self._escribir_encabezados()
                
        except HttpError:
            # Si hay error, intentar escribir encabezados
            self._escribir_encabezados()
    
    def _escribir_encabezados(self):
        """Escribe los encabezados en la primera fila"""
        encabezados = [
            'Fecha_Hora',
            'Codigo_Estudiante',
            'Preguntas_Respondidas',
            'Correctas',
            'Incorrectas',
            'Porcentaje_Correctas',
            'Nivel_Final',
            'Nota_Final',
            'Preguntas_IDs',
            'Theta_IRT',
            'Consistencia_IRT',
            'Nivel_Habilidad_IRT',
            'Rating_Elo',
            'Cambio_Rating_Elo',
            'Razon_Terminacion',
            'Sistema_Calificacion',
            'Autorizado_Continuar',
            'Estado_JSON'
        ]
        
        body = {
            'values': [encabezados]
        }
        
        self._ejecutar_con_reintentos(self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f'{self.nombre_hoja}!A1',
            valueInputOption='RAW',
            body=body
        ), "escribir encabezados")
    
    def _agregar_fila(self, datos: List[Any]):
        """
        Agrega una fila con datos al final de la hoja
        
        Args:
            datos: Lista con los datos a agregar
        """
        body = {
            'values': [datos]
        }
        
        self._ejecutar_con_reintentos(self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f'{self.nombre_hoja}!A:R',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ), "agregar fila")
    
    def obtener_resultados(
        self,
        codigo_estudiante: str = None,
        limite: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtiene resultados de la hoja
        
        Args:
            codigo_estudiante: Si se proporciona, filtra por este código
            limite: Número máximo de resultados a retornar
            
        Returns:
            Lista de diccionarios con resultados
        """
        try:
            # Leer datos
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!A:R'
            ), "obtener resultados")
            
            values = result.get('values', [])
            
            if not values or len(values) < 2:
                return []
            
            # Encabezados
            encabezados = values[0]
            
            # Datos
            resultados = []
            for row in values[1:]:
                # Asegurar que la fila tenga todos los campos
                while len(row) < len(encabezados):
                    row.append('')
                
                # Crear diccionario
                resultado = dict(zip(encabezados, row))
                
                # Filtrar por código si se proporciona
                if codigo_estudiante:
                    if resultado.get('Codigo_Estudiante') == codigo_estudiante:
                        resultados.append(resultado)
                else:
                    resultados.append(resultado)
                
                # Limitar resultados
                if len(resultados) >= limite:
                    break
            
            return resultados
            
        except HttpError as e:
            st.error(f"⚠️ Error al obtener resultados: {str(e)}")
            return []
    
    def obtener_estadisticas_globales(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas globales de todos los exámenes
        
        Returns:
            Diccionario con estadísticas
        """
        try:
            resultados = self.obtener_resultados()
            
            if not resultados:
                return {
                    'total_examenes': 0,
                    'promedio_nota': 0,
                    'promedio_preguntas': 0
                }
            
            # Calcular estadísticas
            total = len(resultados)
            notas = [float(r.get('Nota_Final', 0)) for r in resultados]
            preguntas = [int(r.get('Preguntas_Respondidas', 0)) for r in resultados]
            
            return {
                'total_examenes': total,
                'promedio_nota': sum(notas) / len(notas) if notas else 0,
                'nota_maxima': max(notas) if notas else 0,
                'nota_minima': min(notas) if notas else 0,
                'promedio_preguntas': sum(preguntas) / len(preguntas) if preguntas else 0
            }
            
        except Exception as e:
            st.error(f"⚠️ Error al calcular estadísticas globales: {str(e)}")
            return {}
    
    def verificar_conexion(self) -> bool:
        """
        Verifica que la conexión con Google Sheets funcione
        
        Returns:
            True si la conexión es exitosa
        """
        try:
            # Intentar obtener metadata del spreadsheet
            self._ejecutar_con_reintentos(self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ), "verificar conexión")
            return True
        except Exception as e:
            st.error(f"⚠️ Error de conexión con Google Sheets: {str(e)}")
            return False

    def asegurar_hoja_resultados(self) -> bool:
        """Asegura que exista la hoja de resultados y tenga encabezados válidos."""
        try:
            self._verificar_o_crear_hoja()
            return True
        except Exception:
            return False

    def listar_examenes_en_curso(self) -> List[Dict[str, Any]]:
        """Lista registros con estado EN_CURSO para la hoja actual."""
        try:
            self._verificar_o_crear_hoja()
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
            ), "listar examenes en curso")

            values = result.get('values', [])
            if not values or len(values) < 2:
                return []

            encabezados = values[0]
            salida = []
            for i, row in enumerate(values[1:], start=2):
                while len(row) < len(encabezados):
                    row.append('')
                registro = dict(zip(encabezados, row))
                if registro.get('Razon_Terminacion', '') == 'EN_CURSO':
                    registro['_row_number'] = i
                    salida.append(registro)
            return salida
        except Exception:
            return []

    def autorizar_continuacion(self, codigo_estudiante: str, autorizar: bool = True) -> bool:
        """
        Actualiza la última fila EN_CURSO del estudiante en la hoja actual,
        estableciendo `Autorizado_Continuar` en SI/NO.
        """
        try:
            result = self._ejecutar_con_reintentos(self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!{self.RANGO_DATOS}'
            ), "leer autorizacion continuacion")
            values = result.get('values', [])

            fila_objetivo = None
            for i in range(len(values) - 1, 0, -1):
                row = values[i]
                if len(row) > 1 and row[1] == codigo_estudiante:
                    estado = row[self.COLUMNA_ESTADO] if len(row) > self.COLUMNA_ESTADO else ''
                    if estado == 'EN_CURSO':
                        fila_objetivo = i + 1
                        break

            if not fila_objetivo:
                return False

            valor = 'SI' if autorizar else 'NO'
            body = {'values': [[valor]]}
            self._ejecutar_con_reintentos(self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.nombre_hoja}!Q{fila_objetivo}',
                valueInputOption='RAW',
                body=body
            ), "actualizar autorizacion continuacion")
            return True
        except Exception:
            return False
