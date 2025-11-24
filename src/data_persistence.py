"""
Persistencia de Datos
Maneja el guardado de resultados en Google Sheets
"""
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class DataPersistence:
    """Clase para manejar la persistencia en Google Sheets"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el sistema de persistencia
        
        Args:
            config: Configuración del examen
        """
        self.config = config
        self.spreadsheet_id = config['persistencia']['spreadsheet_id']
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
    
    def guardar_resultados(self, codigo_estudiante: str, stats: Dict[str, Any]) -> bool:
        """
        Guarda los resultados del examen en Google Sheets
        
        Args:
            codigo_estudiante: Código del estudiante
            stats: Estadísticas del examen
            
        Returns:
            True si se guardó exitosamente
        """
        try:
            # Preparar datos
            datos = self._preparar_datos(codigo_estudiante, stats)
            
            # Verificar si existe la hoja, si no, crearla
            self._verificar_o_crear_hoja()
            
            # Agregar fila
            self._agregar_fila(datos)
            
            return True
            
        except HttpError as e:
            st.error(f"⚠️ Error HTTP al guardar en Google Sheets: {str(e)}")
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
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
        
        return datos
    
    def _verificar_o_crear_hoja(self):
        """Verifica si existe la hoja de resultados, si no, la crea con encabezados"""
        try:
            # Intentar obtener información de la hoja
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            # Verificar si existe la hoja "Resultados"
            sheets = sheet_metadata.get('sheets', [])
            existe_hoja = any(
                sheet['properties']['title'] == 'Resultados' 
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
            # Crear nueva hoja
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': 'Resultados',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 20
                            }
                        }
                    }
                }]
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            # Agregar encabezados
            self._escribir_encabezados()
            
        except HttpError as e:
            raise Exception(f"Error al crear hoja: {str(e)}")
    
    def _verificar_encabezados(self):
        """Verifica si la primera fila tiene encabezados, si no, los agrega"""
        try:
            # Leer primera fila
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Resultados!A1:Q1'
            ).execute()
            
            values = result.get('values', [])
            
            # Si está vacía, escribir encabezados
            if not values or not values[0]:
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
            'Sistema_Calificacion'
        ]
        
        body = {
            'values': [encabezados]
        }
        
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range='Resultados!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
    
    def _agregar_fila(self, datos: List[Any]):
        """
        Agrega una fila con datos al final de la hoja
        
        Args:
            datos: Lista con los datos a agregar
        """
        body = {
            'values': [datos]
        }
        
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range='Resultados!A:Q',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    
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
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Resultados!A:Q'
            ).execute()
            
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
            self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            return True
        except Exception as e:
            st.error(f"⚠️ Error de conexión con Google Sheets: {str(e)}")
            return False
