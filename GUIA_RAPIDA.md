# 🚀 Guía Rápida de Despliegue - Examen Adaptativo

## ⏱️ Tiempo estimado: 15 minutos

### 1️⃣ Preparar GitHub (5 minutos)

**Si NO tienes cuenta GitHub:**
1. Ve a https://github.com → Sign up
2. Verifica tu email

**Crear repositorio:**
1. En GitHub: Click en "+" → "New repository"
2. Nombre: `examen-adaptativo-python`
3. Selecciona: **Private**
4. Click "Create repository"

**Subir archivos:**
1. Click "uploading an existing file"
2. Arrastra estos 4 archivos:
   - ✅ `examen_adaptativo.py`
   - ✅ `preguntas.json`
   - ✅ `requirements.txt`
   - ✅ `.gitignore`
3. Escribe: "Inicial commit"
4. Click "Commit changes"

✅ **Checkpoint:** Tu repositorio debe tener 4 archivos

---

### 2️⃣ Desplegar en Streamlit Cloud (10 minutos)

1. **Ir a:** https://streamlit.io/cloud
2. **Click:** "Sign up" (usa tu cuenta de GitHub)
3. **Autorizar** Streamlit en GitHub
4. **Click:** "New app" (botón grande rosado)
5. **Configurar:**
   ```
   Repository: [tu-usuario]/examen-adaptativo-python
   Branch: main
   Main file: examen_adaptativo.py
   ```
6. **Click:** "Deploy!" (botón azul)
7. **Esperar** 2-3 minutos mientras despliega

✅ **Checkpoint:** Verás la aplicación funcionando

---

### 3️⃣ Obtener y compartir URL

**Tu URL será algo como:**
```
https://tu-usuario-examen-adaptativo-python-abc123.streamlit.app
```

📧 **Comparte esta URL con tus estudiantes**

---

### 4️⃣ Descargar resultados después del examen

1. Ve a tu repositorio en GitHub
2. Busca el archivo `resultados_examen.csv`
3. Click en el archivo → "Download"
4. Ábrelo en Excel para ver las notas

**Columnas importantes:**
- `Código`: Identificación del estudiante
- `Nota_Final`: Nota sobre 5.0
- `Nivel_Final`: Nivel alcanzado (1-5)
- `Correctas` / `Incorrectas`: Estadísticas

---

## 🆘 Solución rápida de problemas

| Problema | Solución |
|----------|----------|
| "App is not loading" | Espera 1 minuto más, refresca la página |
| No aparece resultados_examen.csv | Se crea cuando el primer estudiante termina |
| Estudiante no puede acceder | Verifica que compartiste la URL completa |
| Quiero modificar preguntas | Edita `preguntas.json` en GitHub, espera 2 min |

---

## 📱 Compartir con estudiantes

**Mensaje sugerido:**

```
Hola,

Realizarán el examen final de Programación en Python de forma adaptativa.

🔗 Link del examen: [TU_URL_AQUI]

📋 Instrucciones:
- Ingresa tu código de estudiante
- El examen se adapta a tu nivel
- Duración aproximada: 30 minutos
- NO cierres el navegador hasta terminar

Éxitos!
Prof. Francisco
```

---

## ✅ Lista de verificación final

Antes de compartir con estudiantes:

- [ ] La URL funciona (ábrela en incógnito)
- [ ] Puedes ingresar un código de prueba
- [ ] Las preguntas se muestran correctamente
- [ ] Puedes completar el examen de prueba
- [ ] El archivo CSV se creó con tus resultados de prueba

**¡Todo listo para el examen! 🎓**

---

## 📞 Contacto

Si necesitas ayuda adicional, revisa el README.md completo que incluye configuración avanzada y personalización del examen.
