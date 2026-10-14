# 🏢 CLEANFACILITY PRO — Sistema de Supervisión de Limpieza de Edificios

Sistema integral modular para la auditoría técnica, control de cuadrillas, evaluación por áreas, registro de incidencias (CAPA), evidencias fotográficas y emisión automática de **Informes Técnicos en PDF** con firma digital y código QR de verificación.

Desarrollado bajo estándares internacionales **ISSA CIMS (Cleaning Industry Management Standard)**, **OSHA**, **ISO 9001:2015** y **Ley N° 29783 de Seguridad y Salud en el Trabajo (Perú)**.

---

## 🚀 Inicio Rápido (Ejecución)

### Opción 1: Lanzador Directo (Recomendado)
Haga doble clic en el archivo bat ubicado en la raíz del espacio de trabajo:
- `ejecutar_supervision_limpieza.bat`

O dentro de la carpeta del proyecto:
- `20261008 - SUPERVISION LIMPIEZA EDIFICIOS/ejecutar_supervision.bat`

### Opción 2: Terminal / Línea de Comandos
```bash
cd "c:\Users\ADMIN\OneDrive\PYTHON\20261008 - SUPERVISION LIMPIEZA EDIFICIOS"
python -m streamlit run app.py --server.port=8502
```

### Opción 3: Aplicación Web Móvil Offline (PWA)
Abra directamente en cualquier navegador (Google Chrome, Edge, Safari en celular o tablet):
- `20261008 - SUPERVISION LIMPIEZA EDIFICIOS/web_pwa/index.html`

---

## 🔐 Interfaz de Acceso y Credenciales de Usuarios

El sistema cuenta con una interfaz de autenticación con contraseña según usuarios y perfiles:

| Perfil / Rol | Usuario | Contraseña | Alcance y Permisos |
|---|---|---|---|
| 👔 **Administrador / Jefe de Operaciones** | `admin` | `admin123` | Acceso total: todas las auditorías, CAPA, cronogramas, consolidados, reportes, gestión de usuarios y configuración. |
| 👷 **Supervisor de Campo** | `supervisor` | `super123` | Auditorías en terreno, checklist de 10 zonas, registro de evidencias fotográficas, kardex de insumos y CAPA. |
| 👷 **Supervisor Técnico (2)** | `supervisor2` | `super123` | Inspección técnica sanitaria y control de cuadrillas. |
| 🏢 **Cliente / Administrador de Edificio** | `cliente` | `cliente123` | Consulta histórica de informes de su sede, seguimiento CAPA, indicadores de calidad y consolidado mensual PDF. |

*Nota: Desde el módulo `⚙️ Configuración & Maestros > 👥 Usuarios & Accesos`, los administradores pueden crear nuevos usuarios, editar roles y restablecer contraseñas.*

---

## 📋 Módulos Principales del Sistema

### 1. 📋 Nueva Supervisión (Formulario Guiado)
- **Paso 1: Datos Generales y Control de Dotación:** Selección de edificio, supervisor, turno (Mañana/Tarde/Noche), tipo de inspección y registro de personal programado vs. presente vs. faltante.
- **Paso 2: Checklist Técnico por 10 Zonas:**
  1. *Hall de Ingreso / Lobby / Recepción* (Pisos, cristales, mobiliario, alfombras atrapapolvo, aromatización).
  2. *Ascensores y Cabinas* (Botoneras, acero inoxidable, espejos, rieles de puertas, techos y rejillas).
  3. *Pasadizos y Áreas Comunes* (Pisos mopados, paredes/zócalos, extintores, gabinetes, ventanas).
  4. *Servicios Higiénicos (SS.HH.)* (Inodoros, urinarios, griferías cromadas, espejos, dispensadores abastecidos, tachos).
  5. *Oficinas y Zonas de Trabajo* (Escritorios despolvados, equipos informáticos, papeleras, alfombras).
  6. *Escaleras de Emergencia* (Peldaños, barandas metálicas, puertas cortafuego, vías despejadas SST).
  7. *Cuarto de Basura y Residuos* (Lavado de contenedores, código de colores NTP, desengrase, control de olores).
  8. *Estacionamientos y Sótanos* (Barrido mecánico, desmanchado de aceite, tuberías aéreas y telarañas).
  9. *Fachada y Exteriores* (Veredas perimetrales, rampas peatonales/vehiculares, cristales bajos).
  10. *Cuarto de Limpieza (Office)* (Químicos rotulados con MSDS/FDS, herramientas limpias, maquinarias en buen estado).
- **Paso 3: Seguridad y Salud (SST) & Recursos:** Verificación de EPPs (calzado antideslizante, guantes, lentes, mascarilla, señalética "Piso Mojado") y operatividad de maquinarias.
- **Paso 4: Matriz de No Conformidades (CAPA):** Registro dinámico de incidencias con severidad (Baja/Media/Alta/Crítica), acción correctiva inmediata, plazo de subsanación y responsable.
- **Paso 5: Registro Fotográfico:** Carga de fotos con clasificación (Antes, Después, Hallazgo, General) y descripción técnica.
- **Paso 6: Scoring en Vivo y Firmas:** Semáforo de calidad instantáneo y pad de firma digital para el Supervisor y el Cliente / Administrador.

---

## 🎯 Escala de Calificación y Semáforo de Calidad

Cada ítem se evalúa con:
- **C (Conforme / 100 pts):** Limpieza impecable conforme al estándar.
- **R (Regular / 60 pts):** Aceptable con observación menor.
- **NC (No Conforme / 0 pts):** Deficiente o sucio.
- **NA (No Aplica):** No existe en la sede (se excluye de la ponderación).

### Categorías de Calidad Global:
- 🟢 **90.0% – 100% | EXCELENTE (NIVEL A):** Aprobado con distinción.
- 🔵 **80.0% – 89.9% | BUENO (NIVEL B):** Aprobado satisfactorio (cumple SLA).
- 🟡 **70.0% – 79.9% | REGULAR (NIVEL C):** Aprobado condicionado (plan de mejora).
- 🔴 **< 70.0% | CRÍTICO (NIVEL D):** No conforme / Rechazado.

---

## 📄 Informe Técnico en PDF de Alta Calidad
Generado automáticamente con **ReportLab**, incluye:
- Membrete institucional con logotipo y código de formato (`FOR-SGI-LMP-04`).
- **Código QR de validación digital** único por auditoría.
- Resumen ejecutivo con semáforo de calidad y métricas de dotación de personal.
- Tabla exhaustiva de hallazgos por área.
- Matriz de Incidencias y Plan de Acción Correctivo Inmediato.
- Galería fotográfica en 2 columnas con pie de foto técnico.
- Recuadro de firmas digitales del supervisor y receptor.

---

## 📊 Dashboard y Analítica
- KPIs globales (Total auditorías, promedio histórico de calidad, cumplimiento de cuadrilla, no conformidades).
- **Análisis de Causa Raíz (Diagrama de Pareto 80/20):** Identificación de los criterios y áreas críticas que concentran la mayor recurrencia de fallas.
- Ranking de calidad por edificio y evolución temporal de notas.
- Distribución de estados C / R / NC / NA y asistencia de personal por turno.
- Exportación completa del histórico a **Excel (.xlsx)**.

---

## 🚀 Nuevos Módulos y Mejoras Implementadas

1. **🚨 Seguimiento de Incidencias & Plan de Acción (CAPA Tracker):**
   - Gestión integral de estados (*Pendiente*, *En Proceso*, *Subsanada*).
   - Levantamiento de observaciones con subida de **foto de evidencia "Después"**.
   - Registro de responsable, fecha de resolución y cálculo del SLA de cumplimiento.
   - Exportación de la Matriz CAPA a Excel.

2. **📅 Cronograma & Planificador de Supervisiones:**
   - Programación anticipada de visitas técnicas y asignación de inspectores.
   - **Alerta temprana de sedes desatendidas:** Notificación visual para edificios con más de 7 días sin auditoría técnica.
   - Control de estados (*Programada*, *Realizada*, *Atrasada*) y exportación del cronograma.

3. **📦 Recursos Operativos (Químicos, Insumos & Maquinarias):**
   - **Kardex de Químicos:** Registro de entradas, salidas para cuadrilla y ajustes de stock con alerta de stock crítico.
   - **Ficha Técnica de Maquinarias:** Control preventivo de lustradoras, aspiradoras e hidrolavadoras con semáforo de días restantes para próximo mantenimiento.

4. **📑 Informe Consolidado Mensual en PDF:**
   - Generación de informe ejecutivo consolidado por edificio y mes para presentar a Juntas de Propietarios y Gerencias de Inmuebles.
   - Resumen del periodo, índice ponderado, asistencia de personal y tabla cronológica de inspecciones.

5. **📲 Comunicación Instantánea & Correo:**
   - **Botón Compartir por WhatsApp:** Generación de mensaje ejecutivo preformateado con emojis y KPIs para el administrador del edificio.
   - **Envío por Correo Electrónico:** Envío del PDF adjunto a través de servidor SMTP.

6. **💾 Copia de Seguridad (Backup ZIP) en 1 Clic y Restauración:**
   - Descarga directa de archivo `.zip` con la base de datos `supervision_limpieza.db` y las evidencias fotográficas de `static/uploads/`.
   - Restaurador de respaldos integrado en la pestaña de Configuración.

7. **📸 Cámara Directa, Compresión Automática y Borradores:**
   - Captura directa con la cámara del dispositivo móvil (`st.camera_input`) y compresión automática con Pillow.
   - Soporte para guardar auditorías como **Borrador** y reanudarlas en cualquier momento.

8. **📲 Sincronización PWA Offline ➔ Sistema Central:**
   - La PWA (`web_pwa`) incluye el botón *"📲 Exportar para Sistema Central (JSON)"*.
   - Streamlit permite importar el archivo JSON para integrar automáticamente auditorías tomadas en sótanos sin señal.

9. **👔 Selector de Perfiles y Roles de Acceso:**
   - *Administrador / Jefe de Operaciones:* Acceso total a todos los módulos y herramientas.
   - *Supervisor de Campo:* Enfoque en registro, CAPA, cronograma e insumos.
   - *Cliente / Administrador de Edificio:* Vista de solo lectura para consulta de informes, consolidado mensual y dashboard.

---

## 🧱 Estructura de Archivos
```
20261008 - SUPERVISION LIMPIEZA EDIFICIOS/
├── app.py                          # Entrada principal Streamlit con selector de roles
├── config.py                       # Configuración, normas ISSA y checklist
├── database.py                     # SQLite (tablas, consultas, transacciones, CAPA, kardex)
├── test_supervision.py             # Pruebas automatizadas unitarias (9 tests)
├── requirements.txt                # Dependencias Python
├── ejecutar_supervision.bat        # Lanzador bat local
│
├── modules/
│   ├── auth.py                     # Autenticación, login con contraseña y control de sesiones
│   ├── nueva_supervision.py        # Formulario guiado, borradores, cámara directa y PWA import
│   ├── capa_tracker.py             # Módulo CAPA de resolución de no conformidades con foto 'Después'
│   ├── cronograma.py               # Planificador de visitas y alertas de edificios >7 días
│   ├── recursos_operativos.py      # Control de químicos (kardex) y mantenimiento de maquinarias
│   ├── reportes_consolidados.py    # Generador ReportLab de Informe Mensual Consolidado PDF
│   ├── historial.py                # Historial, WhatsApp share, envío por correo, edición y Excel
│   ├── dashboard.py                # Dashboard y analítica Altair con Diagrama de Pareto
│   ├── configuracion_maestros.py   # Maestros, backup/restauración ZIP y servidor SMTP
│   └── reportes_pdf.py             # Motor ReportLab de generación de PDF formal
│
├── static/
│   ├── css/style.css               # Estilos modernos y corporativos
│   └── uploads/                    # Almacén de fotos de evidencias
│
└── web_pwa/                        # App Web Móvil Offline independiente
    ├── index.html                  # Interfaz web responsiva con botón de exportación JSON
    ├── styles.css                  # Estilos modernos con modo impresión
    └── app.js                      # Lógica offline con LocalStorage y exportación a JSON
```
