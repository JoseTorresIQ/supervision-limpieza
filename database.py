"""
Capa de Persistencia y Base de Datos SQLite: Sistema de Supervisión de Limpieza.
Manejo de transacciones seguras, histórico de auditorías, maestros editables, parámetros y edición de reportes.
"""
import sqlite3
import json
import os
import base64
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from config import (
    DATA_DIR, STATIC_DIR, UPLOADS_DIR, CHECKLIST_AREAS, TIPOS_INSPECCION,
    TURNOS_TRABAJO, COMPANY_NAME, FORMAT_CODE, FORMAT_VERSION, PUNTAJES
)

DB_PATH = DATA_DIR / "supervision_limpieza.db"


def get_connection():
    """Retorna una conexión a la base de datos con row_factory activo."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

SALT_PASSWORD = "CleanFacilityPro2026_SaltSecure"


def hash_password(password: str) -> str:
    """Genera un hash SHA-256 seguro con salt para almacenamiento de contraseñas."""
    import hashlib
    texto = f"{SALT_PASSWORD}_{password}"
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def init_db():
    """Crea las tablas maestras y transaccionales si no existen e inserta datos iniciales manteniendo datos previos."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Tabla de Parámetros Globales Editables (Razón social, Códigos, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parametros_sistema (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                descripcion TEXT
            )
        """)

        # 2. Tabla de Edificios / Clientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edificios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                direccion TEXT NOT NULL,
                distrito_ciudad TEXT DEFAULT 'Lima',
                administrador_contacto TEXT,
                telefono_email TEXT,
                num_pisos INTEGER DEFAULT 10,
                num_sotanos INTEGER DEFAULT 2,
                dotacion_personal_asignada INTEGER DEFAULT 4,
                observaciones TEXT,
                activo INTEGER DEFAULT 1
            )
        """)

        # 3. Tabla de Supervisores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supervisores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_completo TEXT NOT NULL,
                dni_ce TEXT NOT NULL UNIQUE,
                cargo TEXT DEFAULT 'Supervisor de Operaciones y Calidad',
                telefono TEXT,
                activo INTEGER DEFAULT 1
            )
        """)

        # 4. Tabla de Tipos de Inspección Editables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tipos_inspeccion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT,
                activo INTEGER DEFAULT 1
            )
        """)

        # 5. Tabla de Turnos de Trabajo Editables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS turnos_trabajo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                horario_referencial TEXT,
                activo INTEGER DEFAULT 1
            )
        """)

        # 6. Tabla de Catálogo de Áreas del Edificio
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_area TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                icono TEXT DEFAULT '🏢',
                orden INTEGER DEFAULT 0,
                activo INTEGER DEFAULT 1
            )
        """)

        # 7. Tabla de Catálogo de Criterios por Área
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_criterios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_criterio TEXT NOT NULL UNIQUE,
                id_area TEXT NOT NULL,
                item TEXT NOT NULL,
                descripcion TEXT,
                orden INTEGER DEFAULT 0,
                activo INTEGER DEFAULT 1,
                FOREIGN KEY (id_area) REFERENCES catalogo_areas (id_area) ON DELETE CASCADE
            )
        """)

        # 8. Tabla Principal de Supervisiones / Reportes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supervisiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_informe TEXT UNIQUE NOT NULL,
                fecha_inspeccion TEXT NOT NULL,
                hora_inicio TEXT,
                hora_fin TEXT,
                tipo_inspeccion TEXT NOT NULL,
                turno TEXT NOT NULL,
                edificio_id INTEGER,
                edificio_nombre TEXT NOT NULL,
                edificio_direccion TEXT,
                administrador_nombre TEXT,
                supervisor_id INTEGER,
                supervisor_nombre TEXT NOT NULL,
                supervisor_dni TEXT,
                lider_cuadrilla TEXT,
                personal_programado INTEGER DEFAULT 0,
                personal_presente INTEGER DEFAULT 0,
                personal_faltante INTEGER DEFAULT 0,
                score_global REAL NOT NULL,
                nivel_calidad TEXT NOT NULL,
                estado_aprobacion TEXT NOT NULL,
                total_items_evaluados INTEGER DEFAULT 0,
                total_conformes INTEGER DEFAULT 0,
                total_adecuados INTEGER DEFAULT 0,
                total_regulares INTEGER DEFAULT 0,
                total_no_conformes INTEGER DEFAULT 0,
                total_no_aplica INTEGER DEFAULT 0,
                epp_conforme INTEGER DEFAULT 1,
                maquinaria_conforme INTEGER DEFAULT 1,
                insumos_conforme INTEGER DEFAULT 1,
                incluir_firmas INTEGER DEFAULT 1,
                observaciones_generales TEXT,
                plan_accion_resumen TEXT,
                firma_supervisor_data TEXT,
                firma_cliente_data TEXT,
                firmante_cliente_nombre TEXT,
                firmante_cliente_cargo TEXT,
                creado_en TEXT NOT NULL,
                estado_informe TEXT DEFAULT 'FINALIZADO'
            )
        """)

        # Migración segura: agregar columnas si no existen
        try:
            cursor.execute("ALTER TABLE supervisiones ADD COLUMN incluir_firmas INTEGER DEFAULT 1")
        except Exception:
            pass

        try:
            cursor.execute("ALTER TABLE supervisiones ADD COLUMN total_adecuados INTEGER DEFAULT 0")
        except Exception:
            pass

        # 9. Tabla de Detalle de Criterios por Área
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supervision_detalles_areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supervision_id INTEGER NOT NULL,
                id_area TEXT NOT NULL,
                nombre_area TEXT NOT NULL,
                id_criterio TEXT NOT NULL,
                item_criterio TEXT NOT NULL,
                calificacion TEXT NOT NULL,
                puntos REAL,
                observacion TEXT,
                FOREIGN KEY (supervision_id) REFERENCES supervisiones (id) ON DELETE CASCADE
            )
        """)

        # 10. Tabla de Incidencias / No Conformidades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supervision_incidencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supervision_id INTEGER NOT NULL,
                area_nombre TEXT NOT NULL,
                descripcion_hallazgo TEXT NOT NULL,
                severidad TEXT NOT NULL,
                accion_correctiva TEXT NOT NULL,
                plazo_subsanacion TEXT NOT NULL,
                responsable TEXT NOT NULL,
                estado_subsanacion TEXT DEFAULT 'Pendiente',
                foto_hallazgo_ruta TEXT,
                FOREIGN KEY (supervision_id) REFERENCES supervisiones (id) ON DELETE CASCADE
            )
        """)

        # 11. Tabla de Fotos de Evidencia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supervision_fotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supervision_id INTEGER NOT NULL,
                area_nombre TEXT,
                tipo_evidencia TEXT DEFAULT 'Hallazgo',
                archivo_nombre TEXT NOT NULL,
                archivo_ruta TEXT NOT NULL,
                descripcion TEXT,
                origen TEXT DEFAULT 'REGISTRO_FOTOGRAFICO',
                foto_padre_id TEXT DEFAULT '',
                FOREIGN KEY (supervision_id) REFERENCES supervisiones (id) ON DELETE CASCADE
            )
        """)

        # Limpieza de posibles fotos duplicadas históricas en supervision_fotos
        try:
            cursor.execute("""
                DELETE FROM supervision_fotos
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM supervision_fotos
                    GROUP BY supervision_id, archivo_ruta
                )
            """)
        except Exception:
            pass

        # Migración segura: columna origen en supervision_fotos
        try:
            cursor.execute("ALTER TABLE supervision_fotos ADD COLUMN origen TEXT DEFAULT 'REGISTRO_FOTOGRAFICO'")
        except Exception:
            pass

        # Migración segura: columna foto_padre_id en supervision_fotos
        try:
            cursor.execute("ALTER TABLE supervision_fotos ADD COLUMN foto_padre_id TEXT DEFAULT ''")
        except Exception:
            pass

        # Migración segura: columnas de subsanación de incidencias (CAPA)
        columnas_incidencias = [
            ("fecha_subsanacion", "TEXT"),
            ("foto_subsanacion_ruta", "TEXT"),
            ("comentario_cierre", "TEXT"),
            ("cerrado_por", "TEXT"),
            ("foto_hallazgo_ruta", "TEXT")
        ]
        for col_nom, col_tipo in columnas_incidencias:
            try:
                cursor.execute(f"ALTER TABLE supervision_incidencias ADD COLUMN {col_nom} {col_tipo}")
            except Exception:
                pass

        # 12. Tabla de Cronograma de Supervisiones y Planificación
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cronograma_supervisiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edificio_id INTEGER,
                edificio_nombre TEXT NOT NULL,
                supervisor_id INTEGER,
                supervisor_nombre TEXT NOT NULL,
                fecha_programada TEXT NOT NULL,
                tipo_inspeccion TEXT NOT NULL,
                turno TEXT,
                estado TEXT DEFAULT 'Programada',
                observaciones TEXT,
                supervision_id INTEGER
            )
        """)

        # 13. Tabla de Control de Stock de Insumos y Químicos por Edificio
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS control_insumos_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edificio_id INTEGER,
                edificio_nombre TEXT NOT NULL,
                producto_nombre TEXT NOT NULL,
                categoria TEXT DEFAULT 'Químicos de Limpieza',
                unidad_medida TEXT NOT NULL,
                stock_actual REAL DEFAULT 0,
                stock_minimo REAL DEFAULT 0,
                ultimo_movimiento TEXT,
                activo INTEGER DEFAULT 1
            )
        """)

        # 14. Tabla de Movimientos (Kardex) de Insumos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos_insumos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                insumo_id INTEGER NOT NULL,
                tipo_movimiento TEXT NOT NULL,
                cantidad REAL NOT NULL,
                fecha_movimiento TEXT NOT NULL,
                responsable TEXT,
                motivo TEXT,
                FOREIGN KEY (insumo_id) REFERENCES control_insumos_stock (id) ON DELETE CASCADE
            )
        """)

        # 15. Tabla de Maquinarias y Equipos Asignados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maquinarias_equipos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_equipo TEXT UNIQUE NOT NULL,
                tipo_maquinaria TEXT NOT NULL,
                marca_modelo TEXT NOT NULL,
                serie TEXT,
                edificio_id INTEGER,
                edificio_nombre TEXT,
                estado_operativo TEXT DEFAULT 'Operativo',
                fecha_adquisicion TEXT,
                ultimo_mantenimiento TEXT,
                proximo_mantenimiento TEXT,
                observaciones TEXT,
                activo INTEGER DEFAULT 1
            )
        """)

        # 16. Tabla de Usuarios y Autenticación del Sistema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nombre_completo TEXT NOT NULL,
                rol TEXT NOT NULL,
                cargo TEXT,
                email TEXT,
                edificio_asignado TEXT DEFAULT 'Todos',
                activo INTEGER DEFAULT 1,
                creado_en TEXT,
                ultimo_acceso TEXT
            )
        """)

        # Insertar Parámetros Iniciales si no existen
        params_iniciales = [
            ("empresa_nombre", COMPANY_NAME, "Razón Social o Nombre Comercial de la Empresa de Limpieza"),
            ("empresa_subtitulo", "Control de Calidad, Estándares de Higiene y Cumplimiento de Servicio", "Subtítulo en encabezado de reportes"),
            ("formato_codigo", FORMAT_CODE, "Código oficial de formato de calidad"),
            ("formato_version", FORMAT_VERSION, "Versión de revisión del formato"),
            ("empresa_logo_path", "", "Ruta relativa o nombre del archivo de logotipo oficial de la empresa"),
            ("empresa_logo_base64", "", "Logotipo oficial de la empresa en base64"),
            ("email_smtp_servidor", "smtp.gmail.com", "Servidor SMTP para envío de informes"),
            ("email_smtp_puerto", "587", "Puerto SMTP"),
            ("email_smtp_remitente", "calidad@cleanfacilitypro.pe", "Correo remitente del sistema")
        ]
        for clave, valor, desc in params_iniciales:
            cursor.execute("""
                INSERT OR IGNORE INTO parametros_sistema (clave, valor, descripcion)
                VALUES (?, ?, ?)
            """, (clave, valor, desc))

        # Insertar edificio inicial (PSI) solo si la tabla está completamente vacía
        cursor.execute("SELECT COUNT(*) FROM edificios")
        if cursor.fetchone()[0] == 0:
            edificios_iniciales = [
                ("Programa Subsectorial de Irrigaciones (PSI)", "Av. Alameda del Corregidor N.° 155", "La Molina", "N.A.", "", 3, 0, 1, "Oficinas de manera modular, presencia de varias áreas verdes.")
            ]
            cursor.executemany("""
                INSERT INTO edificios (nombre, direccion, distrito_ciudad, administrador_contacto, telefono_email, num_pisos, num_sotanos, dotacion_personal_asignada, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, edificios_iniciales)

        # Insertar supervisor inicial solo si la tabla está completamente vacía
        cursor.execute("SELECT COUNT(*) FROM supervisores")
        if cursor.fetchone()[0] == 0:
            supervisores_iniciales = [
                ("José Torres Crisóstomo", "73066809", "Supervisor de Operaciones y Calidad del Servicio", "945207642")
            ]
            cursor.executemany("""
                INSERT INTO supervisores (nombre_completo, dni_ce, cargo, telefono)
                VALUES (?, ?, ?, ?)
            """, supervisores_iniciales)

        # Insertar Tipos de Inspección iniciales
        cursor.execute("SELECT COUNT(*) FROM tipos_inspeccion")
        if cursor.fetchone()[0] == 0:
            for t in TIPOS_INSPECCION:
                cursor.execute("INSERT OR IGNORE INTO tipos_inspeccion (nombre, descripcion) VALUES (?, ?)", (t, "Tipo de supervisión técnica estándar."))

        # Insertar Turnos de Trabajo iniciales
        cursor.execute("SELECT COUNT(*) FROM turnos_trabajo")
        if cursor.fetchone()[0] == 0:
            for turno in TURNOS_TRABAJO:
                cursor.execute("INSERT OR IGNORE INTO turnos_trabajo (nombre, horario_referencial) VALUES (?, ?)", (turno, "Horario regular de cuadrilla."))

        # Insertar Áreas y Criterios si están vacíos
        cursor.execute("SELECT COUNT(*) FROM catalogo_areas")
        if cursor.fetchone()[0] == 0:
            for idx_a, area in enumerate(CHECKLIST_AREAS):
                cursor.execute("""
                    INSERT OR IGNORE INTO catalogo_areas (id_area, nombre, icono, orden)
                    VALUES (?, ?, ?, ?)
                """, (area["id_area"], area["nombre"], area.get("icono", "🏢"), idx_a + 1))
                
                for idx_c, crit in enumerate(area["criterios"]):
                    cursor.execute("""
                        INSERT OR IGNORE INTO catalogo_criterios (id_criterio, id_area, item, descripcion, orden)
                        VALUES (?, ?, ?, ?, ?)
                    """, (crit["id"], area["id_area"], crit["item"], crit["descripcion"], idx_c + 1))

        # Insertar usuario administrador inicial únicamente si la tabla de usuarios está vacía
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            usuarios_iniciales = [
                (
                    "admin",
                    hash_password("admin123"),
                    "Ing. José Torres (Supervisor de Operaciones y Calidad)",
                    "👔 Administrador / Jefe de Operaciones",
                    "Supervisor de Operaciones y Calidad del Servicio",
                    "admin@cleanfacilitypro.pe",
                    "Todos",
                    1,
                    ahora_str
                )
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO usuarios (username, password_hash, nombre_completo, rol, cargo, email, edificio_asignado, activo, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, usuarios_iniciales)

        conn.commit()


# =====================================================================
# MÉTODOS CRUD: PARÁMETROS DEL SISTEMA (EMPRESA EDITABLE)
# =====================================================================
def obtener_parametro(clave: str, valor_defecto: str = "") -> str:
    """Obtiene el valor de un parámetro del sistema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM parametros_sistema WHERE clave = ?", (clave,))
        row = cursor.fetchone()
        return row[0] if row else valor_defecto


def guardar_parametro(clave: str, valor: str, descripcion: str = ""):
    """Guarda o actualiza un parámetro del sistema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO parametros_sistema (clave, valor, descripcion)
            VALUES (?, ?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, descripcion = COALESCE(excluded.descripcion, parametros_sistema.descripcion)
        """, (clave, valor, descripcion))
        conn.commit()
        return True


def obtener_todos_parametros() -> dict:
    """Retorna todos los parámetros como diccionario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clave, valor FROM parametros_sistema")
        return {r["clave"]: r["valor"] for r in cursor.fetchall()}


def guardar_logo_empresa(file_bytes: bytes, filename: str = "logo_empresa.png") -> str:
    """
    Procesa, optimiza y guarda el logotipo corporativo de la empresa.
    Guarda el archivo en el directorio de uploads y registra su ruta y base64 en la base de datos.
    Retorna la ruta absoluta del archivo guardado.
    """
    from PIL import Image as PILImage, ImageOps

    os.makedirs(UPLOADS_DIR, exist_ok=True)

    img = PILImage.open(io.BytesIO(file_bytes))
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Adecuar modos de color no soportados directamente al guardar en PNG
    if img.mode in ("CMYK", "YCbCr"):
        img = img.convert("RGB")
    elif img.mode in ("P", "1"):
        img = img.convert("RGBA")

    # Si la imagen es excesivamente grande, redimensionar manteniendo proporción (máx 1200x600)
    max_dims = (1200, 600)
    img.thumbnail(max_dims, PILImage.Resampling.LANCZOS)

    # Guardar en UPLOADS_DIR como PNG para conservar transparencia y nitidez
    destino_path = UPLOADS_DIR / "logo_empresa.png"
    img.save(destino_path, format="PNG", optimize=True)

    # Convertir a base64
    with open(destino_path, "rb") as f_out:
        saved_bytes = f_out.read()
    b64_str = f"data:image/png;base64,{base64.b64encode(saved_bytes).decode('utf-8')}"

    # Guardar en parámetros del sistema
    ruta_relativa = f"static/uploads/{destino_path.name}"
    guardar_parametro("empresa_logo_path", ruta_relativa, "Ruta relativa del logotipo oficial de la empresa")
    guardar_parametro("empresa_logo_base64", b64_str, "Logotipo oficial de la empresa en base64")

    return str(destino_path)


def obtener_logo_empresa() -> Optional[Dict[str, Any]]:
    """
    Obtiene la información y ruta del logotipo corporativo actual si existe.
    Retorna dict con 'path', 'bytes', 'base64', 'ancho', 'alto' o None si no hay logo.
    """
    from PIL import Image as PILImage

    logo_path = None
    # 1. Buscar en parámetro empresa_logo_path
    path_param = obtener_parametro("empresa_logo_path", "")
    if path_param:
        p_obj = Path(path_param) if isinstance(path_param, str) else path_param
        if os.path.isabs(str(p_obj)) and os.path.exists(str(p_obj)):
            logo_path = str(p_obj)
        elif (STATIC_DIR.parent / path_param).exists():
            logo_path = str(STATIC_DIR.parent / path_param)
        elif (UPLOADS_DIR / os.path.basename(path_param)).exists():
            logo_path = str(UPLOADS_DIR / os.path.basename(path_param))

    # 2. Si no se encontró por parámetro, verificar archivo físico predeterminado
    if not logo_path:
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            candidato = UPLOADS_DIR / f"logo_empresa{ext}"
            if candidato.exists() and candidato.stat().st_size > 0:
                logo_path = str(candidato)
                break

    # Si encontramos el archivo en disco
    if logo_path and os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as f:
                b = f.read()
            if b:
                with PILImage.open(io.BytesIO(b)) as p_img:
                    w, h = p_img.size
                b64 = f"data:image/png;base64,{base64.b64encode(b).decode('utf-8')}"
                return {
                    "path": logo_path,
                    "bytes": b,
                    "base64": b64,
                    "ancho": w,
                    "alto": h
                }
        except Exception:
            pass

    # 3. Si no está en disco pero está en base64 en la base de datos (ej: tras restaurar o migrar)
    b64_param = obtener_parametro("empresa_logo_base64", "")
    if b64_param:
        try:
            raw_b64 = b64_param.split(",")[-1]
            b = base64.b64decode(raw_b64)
            if b:
                destino = UPLOADS_DIR / "logo_empresa.png"
                os.makedirs(UPLOADS_DIR, exist_ok=True)
                with open(destino, "wb") as f_out:
                    f_out.write(b)
                with PILImage.open(io.BytesIO(b)) as p_img:
                    w, h = p_img.size
                return {
                    "path": str(destino),
                    "bytes": b,
                    "base64": b64_param,
                    "ancho": w,
                    "alto": h
                }
        except Exception:
            pass

    return None


def eliminar_logo_empresa() -> bool:
    """
    Elimina el logotipo corporativo configurado y restaura el estado predeterminado.
    """
    guardar_parametro("empresa_logo_path", "", "Ruta del logotipo oficial de la empresa")
    guardar_parametro("empresa_logo_base64", "", "Logotipo oficial de la empresa en base64")

    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        p = UPLOADS_DIR / f"logo_empresa{ext}"
        if p.exists():
            try:
                os.remove(p)
            except Exception:
                pass

    return True


# =====================================================================
# MÉTODOS CRUD: TIPOS DE INSPECCIÓN
# =====================================================================
def obtener_tipos_inspeccion(solo_activos=True):
    """Retorna la lista de tipos de inspección registrados."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM tipos_inspeccion"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY id ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows and solo_activos:
            return TIPOS_INSPECCION
        return [dict(r) for r in rows] if not solo_activos else [r["nombre"] for r in rows]


def agregar_tipo_inspeccion(nombre, descripcion=""):
    """Registra un nuevo tipo de inspección."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tipos_inspeccion (nombre, descripcion) VALUES (?, ?)", (nombre, descripcion))
        conn.commit()
        return cursor.lastrowid


def actualizar_tipo_inspeccion(tipo_id, nuevo_nombre, descripcion, activo=1):
    """Actualiza un tipo de inspección existente."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tipos_inspeccion SET nombre = ?, descripcion = ?, activo = ? WHERE id = ?", (nuevo_nombre, descripcion, activo, tipo_id))
        conn.commit()
        return True


def eliminar_tipo_inspeccion(tipo_id):
    """Elimina o desactiva un tipo de inspección."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tipos_inspeccion WHERE id = ?", (tipo_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: TURNOS DE TRABAJO
# =====================================================================
def obtener_turnos_trabajo(solo_activos=True):
    """Retorna la lista de turnos de trabajo registrados."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM turnos_trabajo"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY id ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows and solo_activos:
            return TURNOS_TRABAJO
        return [dict(r) for r in rows] if not solo_activos else [r["nombre"] for r in rows]


def agregar_turno_trabajo(nombre, horario=""):
    """Registra un nuevo turno de trabajo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO turnos_trabajo (nombre, horario_referencial) VALUES (?, ?)", (nombre, horario))
        conn.commit()
        return cursor.lastrowid


def actualizar_turno_trabajo(turno_id, nuevo_nombre, horario, activo=1):
    """Actualiza un turno de trabajo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE turnos_trabajo SET nombre = ?, horario_referencial = ?, activo = ? WHERE id = ?", (nuevo_nombre, horario, activo, turno_id))
        conn.commit()
        return True


def eliminar_turno_trabajo(turno_id):
    """Elimina un turno de trabajo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM turnos_trabajo WHERE id = ?", (turno_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: CATÁLOGO DE ÁREAS Y CRITERIOS DEL CHECKLIST
# =====================================================================
def obtener_checklist_completo(solo_activos=True):
    """
    Retorna el checklist completo estructurado por áreas con sus criterios.
    Compatible con la estructura de CHECKLIST_AREAS.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        query_areas = "SELECT * FROM catalogo_areas"
        if solo_activos:
            query_areas += " WHERE activo = 1"
        query_areas += " ORDER BY orden ASC, id ASC"
        
        cursor.execute(query_areas)
        areas_db = [dict(r) for r in cursor.fetchall()]

        if not areas_db:
            return CHECKLIST_AREAS

        resultado = []
        for a in areas_db:
            query_crit = "SELECT * FROM catalogo_criterios WHERE id_area = ?"
            if solo_activos:
                query_crit += " AND activo = 1"
            query_crit += " ORDER BY orden ASC, id ASC"

            cursor.execute(query_crit, (a["id_area"],))
            criterios_db = [dict(c) for c in cursor.fetchall()]

            criterios_lista = []
            for c in criterios_db:
                criterios_lista.append({
                    "id": c["id_criterio"],
                    "item": c["item"],
                    "descripcion": c.get("descripcion", "")
                })

            resultado.append({
                "id_area": a["id_area"],
                "nombre": a["nombre"],
                "icono": a.get("icono", "🏢"),
                "criterios": criterios_lista
            })

        return resultado


def obtener_areas_raw():
    """Retorna la lista directa de áreas en la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM catalogo_areas ORDER BY orden ASC, id ASC")
        return [dict(r) for r in cursor.fetchall()]


def obtener_criterios_raw(id_area=None):
    """Retorna la lista directa de criterios."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if id_area:
            cursor.execute("SELECT * FROM catalogo_criterios WHERE id_area = ? ORDER BY orden ASC, id ASC", (id_area,))
        else:
            cursor.execute("SELECT * FROM catalogo_criterios ORDER BY id_area ASC, orden ASC")
        return [dict(r) for r in cursor.fetchall()]


def agregar_area_catalogo(id_area, nombre, icono="🏢", orden=0):
    """Agrega una nueva zona/área al checklist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO catalogo_areas (id_area, nombre, icono, orden, activo)
            VALUES (?, ?, ?, ?, 1)
        """, (id_area, nombre, icono, orden))
        conn.commit()
        return cursor.lastrowid


def actualizar_area_catalogo(area_id, nombre, icono, orden, activo=1):
    """Actualiza los datos de un área."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE catalogo_areas
            SET nombre = ?, icono = ?, orden = ?, activo = ?
            WHERE id = ?
        """, (nombre, icono, orden, activo, area_id))
        conn.commit()
        return True


def eliminar_area_catalogo(area_id):
    """Elimina un área y sus criterios asociados."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_area FROM catalogo_areas WHERE id = ?", (area_id,))
        row = cursor.fetchone()
        if row:
            id_area = row[0]
            cursor.execute("DELETE FROM catalogo_criterios WHERE id_area = ?", (id_area,))
            cursor.execute("DELETE FROM catalogo_areas WHERE id = ?", (area_id,))
            conn.commit()
        return True


def agregar_criterio_catalogo(id_criterio, id_area, item, descripcion="", orden=0):
    """Agrega un nuevo criterio técnico a un área."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO catalogo_criterios (id_criterio, id_area, item, descripcion, orden, activo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (id_criterio, id_area, item, descripcion, orden))
        conn.commit()
        return cursor.lastrowid


def actualizar_criterio_catalogo(criterio_id, item, descripcion, orden, activo=1):
    """Actualiza un criterio técnico."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE catalogo_criterios
            SET item = ?, descripcion = ?, orden = ?, activo = ?
            WHERE id = ?
        """, (item, descripcion, orden, activo, criterio_id))
        conn.commit()
        return True


def eliminar_criterio_catalogo(criterio_id):
    """Elimina un criterio técnico del catálogo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM catalogo_criterios WHERE id = ?", (criterio_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: EDIFICIOS
# =====================================================================
def obtener_lista_edificios(solo_activos=True):
    """Retorna la lista de todos los edificios."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM edificios"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY nombre ASC"
        cursor.execute(query)
        return [dict(r) for r in cursor.fetchall()]


def agregar_edificio(nombre, direccion, distrito, administrador, telefono, pisos, sotanos, dotacion, observaciones):
    """Agrega un nuevo edificio a la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO edificios (nombre, direccion, distrito_ciudad, administrador_contacto, telefono_email, num_pisos, num_sotanos, dotacion_personal_asignada, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, direccion, distrito, administrador, telefono, pisos, sotanos, dotacion, observaciones))
        conn.commit()
        return cursor.lastrowid


def actualizar_edificio(edificio_id, nombre, direccion, distrito, administrador, telefono, pisos, sotanos, dotacion, observaciones, activo=1):
    """Actualiza un edificio existente."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE edificios
            SET nombre = ?, direccion = ?, distrito_ciudad = ?, administrador_contacto = ?, telefono_email = ?, num_pisos = ?, num_sotanos = ?, dotacion_personal_asignada = ?, observaciones = ?, activo = ?
            WHERE id = ?
        """, (nombre, direccion, distrito, administrador, telefono, pisos, sotanos, dotacion, observaciones, activo, edificio_id))
        conn.commit()
        return True


def eliminar_edificio_db(edificio_id):
    """Elimina un edificio de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM edificios WHERE id = ?", (edificio_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: SUPERVISORES
# =====================================================================
def obtener_lista_supervisores(solo_activos=True):
    """Retorna la lista de todos los supervisores."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM supervisores"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY nombre_completo ASC"
        cursor.execute(query)
        return [dict(r) for r in cursor.fetchall()]


def agregar_supervisor(nombre, dni, cargo, telefono):
    """Agrega un nuevo supervisor al maestro."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO supervisores (nombre_completo, dni_ce, cargo, telefono)
            VALUES (?, ?, ?, ?)
        """, (nombre, dni, cargo, telefono))
        conn.commit()
        return cursor.lastrowid


def actualizar_supervisor(supervisor_id, nombre, dni, cargo, telefono, activo=1):
    """Actualiza un supervisor existente."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE supervisores
            SET nombre_completo = ?, dni_ce = ?, cargo = ?, telefono = ?, activo = ?
            WHERE id = ?
        """, (nombre, dni, cargo, telefono, activo, supervisor_id))
        conn.commit()
        return True


def eliminar_supervisor_db(supervisor_id):
    """Elimina un supervisor del catálogo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM supervisores WHERE id = ?", (supervisor_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS DE SUPERVISIONES E INFORMES
# =====================================================================
def generar_nuevo_codigo():
    """Genera un código correlativo único para el informe: REP-LMP-YYYY-XXXX"""
    now = datetime.now()
    year = now.strftime("%Y")
    prefix = f"REP-LMP-{year}-"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo_informe FROM supervisiones WHERE codigo_informe LIKE ?", (f"{prefix}%",))
        rows = cursor.fetchall()
        max_num = 0
        for r in rows:
            cod = r[0]
            try:
                num = int(cod.replace(prefix, ""))
                if num > max_num:
                    max_num = num
            except (ValueError, TypeError):
                pass
        next_num = max_num + 1
        # Asegurar que no colisione
        while True:
            candidate = f"{prefix}{next_num:04d}"
            cursor.execute("SELECT 1 FROM supervisiones WHERE codigo_informe = ?", (candidate,))
            if not cursor.fetchone():
                return candidate
            next_num += 1


def guardar_supervision_completa(datos_gral, detalles_evaluacion, incidencias, fotos_guardadas):
    """
    Guarda la supervisión completa en una transacción atómica segura.
    Retorna el ID de la supervisión y su código.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Insertar Cabecera
        cursor.execute("""
            INSERT INTO supervisiones (
                codigo_informe, fecha_inspeccion, hora_inicio, hora_fin, tipo_inspeccion, turno,
                edificio_id, edificio_nombre, edificio_direccion, administrador_nombre,
                supervisor_id, supervisor_nombre, supervisor_dni, lider_cuadrilla,
                personal_programado, personal_presente, personal_faltante,
                score_global, nivel_calidad, estado_aprobacion,
                total_items_evaluados, total_conformes, total_adecuados, total_regulares, total_no_conformes, total_no_aplica,
                epp_conforme, maquinaria_conforme, insumos_conforme, incluir_firmas,
                observaciones_generales, plan_accion_resumen,
                firma_supervisor_data, firma_cliente_data,
                firmante_cliente_nombre, firmante_cliente_cargo, creado_en, estado_informe
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos_gral["codigo_informe"],
            datos_gral["fecha_inspeccion"],
            datos_gral.get("hora_inicio", ""),
            datos_gral.get("hora_fin", ""),
            datos_gral["tipo_inspeccion"],
            datos_gral["turno"],
            datos_gral.get("edificio_id"),
            datos_gral["edificio_nombre"],
            datos_gral.get("edificio_direccion", ""),
            datos_gral.get("administrador_nombre", ""),
            datos_gral.get("supervisor_id"),
            datos_gral["supervisor_nombre"],
            datos_gral.get("supervisor_dni", ""),
            datos_gral.get("lider_cuadrilla", ""),
            datos_gral.get("personal_programado", 0),
            datos_gral.get("personal_presente", 0),
            datos_gral.get("personal_faltante", 0),
            datos_gral["score_global"],
            datos_gral["nivel_calidad"],
            datos_gral["estado_aprobacion"],
            datos_gral.get("total_items_evaluados", 0),
            datos_gral.get("total_conformes", 0),
            datos_gral.get("total_adecuados", 0),
            datos_gral.get("total_regulares", 0),
            datos_gral.get("total_no_conformes", 0),
            datos_gral.get("total_no_aplica", 0),
            datos_gral.get("epp_conforme", 1),
            datos_gral.get("maquinaria_conforme", 1),
            datos_gral.get("insumos_conforme", 1),
            datos_gral.get("incluir_firmas", 1),
            datos_gral.get("observaciones_generales", ""),
            datos_gral.get("plan_accion_resumen", ""),
            datos_gral.get("firma_supervisor_data", ""),
            datos_gral.get("firma_cliente_data", ""),
            datos_gral.get("firmante_cliente_nombre", ""),
            datos_gral.get("firmante_cliente_cargo", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datos_gral.get("estado_informe", "FINALIZADO")
        ))
        supervision_id = cursor.lastrowid

        # 2. Insertar Detalle de Evaluación de Áreas
        for d in detalles_evaluacion:
            cursor.execute("""
                INSERT INTO supervision_detalles_areas (
                    supervision_id, id_area, nombre_area, id_criterio, item_criterio, calificacion, puntos, observacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supervision_id,
                d["id_area"],
                d["nombre_area"],
                d["id_criterio"],
                d["item_criterio"],
                d["calificacion"],
                d.get("puntos", PUNTAJES.get(d.get("calificacion", "C"), {}).get("puntos", 100)),
                d.get("observacion", "")
            ))

        # 3. Insertar Incidencias
        for inc in incidencias:
            f_hallazgo = inc.get("foto_ruta") or (inc.get("fotos")[0] if inc.get("fotos") else inc.get("foto_hallazgo_ruta", ""))
            cursor.execute("""
                INSERT INTO supervision_incidencias (
                    supervision_id, area_nombre, descripcion_hallazgo, severidad,
                    accion_correctiva, plazo_subsanacion, responsable, estado_subsanacion,
                    foto_hallazgo_ruta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supervision_id,
                inc.get("area_nombre", "General"),
                inc.get("descripcion_hallazgo", ""),
                inc.get("severidad", "Media"),
                inc.get("accion_correctiva", ""),
                inc.get("plazo_subsanacion", "24 horas"),
                inc.get("responsable", "Supervisor de Turno"),
                inc.get("estado_subsanacion", inc.get("estado_subsanacion", "Pendiente")),
                f_hallazgo
            ))

        # 4. Insertar Fotos evitando duplicados
        rutas_insertadas = set()
        for f in (fotos_guardadas or []):
            ruta = f.get("archivo_ruta", "")
            if not ruta:
                continue
            ruta_norm = os.path.normpath(ruta)
            if ruta_norm in rutas_insertadas:
                continue
            rutas_insertadas.add(ruta_norm)
            nom_arch = f.get("archivo_nombre") or os.path.basename(ruta_norm)
            f_padre = str(f.get("foto_padre_id", ""))
            try:
                cursor.execute("""
                    INSERT INTO supervision_fotos (
                        supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen, foto_padre_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    supervision_id,
                    f.get("area_nombre", "General"),
                    f.get("tipo_evidencia", "Hallazgo / No Conforme"),
                    nom_arch,
                    ruta_norm,
                    f.get("descripcion", ""),
                    f.get("origen", "REGISTRO_FOTOGRAFICO"),
                    f_padre
                ))
            except Exception:
                cursor.execute("""
                    INSERT INTO supervision_fotos (
                        supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    supervision_id,
                    f.get("area_nombre", "General"),
                    f.get("tipo_evidencia", "Hallazgo / No Conforme"),
                    nom_arch,
                    ruta_norm,
                    f.get("descripcion", ""),
                    f.get("origen", "REGISTRO_FOTOGRAFICO")
                ))
            foto_id_padre = cursor.lastrowid

            # Insertar fotos adicionales / complementarias asociadas a esta evidencia
            for sub_f in f.get("fotos_adicionales", []):
                sub_r = sub_f.get("archivo_ruta", "")
                if not sub_r:
                    continue
                sub_r_norm = os.path.normpath(sub_r)
                if sub_r_norm in rutas_insertadas:
                    continue
                rutas_insertadas.add(sub_r_norm)
                sub_nom = sub_f.get("archivo_nombre") or os.path.basename(sub_r_norm)
                try:
                    cursor.execute("""
                        INSERT INTO supervision_fotos (
                            supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen, foto_padre_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        supervision_id,
                        sub_f.get("area_nombre") or f.get("area_nombre", "General"),
                        sub_f.get("tipo_evidencia", "Después de Limpieza"),
                        sub_nom,
                        sub_r_norm,
                        sub_f.get("descripcion", ""),
                        sub_f.get("origen", "FOTO_ADICIONAL"),
                        str(foto_id_padre)
                    ))
                except Exception:
                    cursor.execute("""
                        INSERT INTO supervision_fotos (
                            supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        supervision_id,
                        sub_f.get("area_nombre") or f.get("area_nombre", "General"),
                        sub_f.get("tipo_evidencia", "Después de Limpieza"),
                        sub_nom,
                        sub_r_norm,
                        sub_f.get("descripcion", ""),
                        sub_f.get("origen", "FOTO_ADICIONAL")
                    ))

        conn.commit()
        return supervision_id, datos_gral["codigo_informe"]


def actualizar_supervision_completa(supervision_id: int, datos_gral: dict, detalles_evaluacion: list, incidencias: list, fotos_guardadas: list = None):
    """
    Actualiza una supervisión existente en el Historial o un Borrador.
    Permite modificar datos generales, checklist, incidencias, notas, estado y fotos.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Actualizar Cabecera
        cursor.execute("""
            UPDATE supervisiones SET
                codigo_informe = COALESCE(?, codigo_informe),
                fecha_inspeccion = ?, hora_inicio = ?, hora_fin = ?, tipo_inspeccion = ?, turno = ?,
                edificio_id = ?, edificio_nombre = ?, edificio_direccion = ?, administrador_nombre = ?,
                supervisor_id = ?, supervisor_nombre = ?, supervisor_dni = ?, lider_cuadrilla = ?,
                personal_programado = ?, personal_presente = ?, personal_faltante = ?,
                score_global = ?, nivel_calidad = ?, estado_aprobacion = ?,
                total_items_evaluados = ?, total_conformes = ?, total_adecuados = ?, total_regulares = ?, total_no_conformes = ?, total_no_aplica = ?,
                epp_conforme = ?, maquinaria_conforme = ?, insumos_conforme = ?, incluir_firmas = ?,
                observaciones_generales = ?, plan_accion_resumen = ?,
                firmante_cliente_nombre = ?, firmante_cliente_cargo = ?,
                estado_informe = ?
            WHERE id = ?
        """, (
            datos_gral.get("codigo_informe"),
            datos_gral["fecha_inspeccion"],
            datos_gral.get("hora_inicio", ""),
            datos_gral.get("hora_fin", ""),
            datos_gral["tipo_inspeccion"],
            datos_gral["turno"],
            datos_gral.get("edificio_id"),
            datos_gral["edificio_nombre"],
            datos_gral.get("edificio_direccion", ""),
            datos_gral.get("administrador_nombre", ""),
            datos_gral.get("supervisor_id"),
            datos_gral["supervisor_nombre"],
            datos_gral.get("supervisor_dni", ""),
            datos_gral.get("lider_cuadrilla", ""),
            datos_gral.get("personal_programado", 0),
            datos_gral.get("personal_presente", 0),
            datos_gral.get("personal_faltante", 0),
            datos_gral["score_global"],
            datos_gral["nivel_calidad"],
            datos_gral["estado_aprobacion"],
            datos_gral.get("total_items_evaluados", 0),
            datos_gral.get("total_conformes", 0),
            datos_gral.get("total_adecuados", 0),
            datos_gral.get("total_regulares", 0),
            datos_gral.get("total_no_conformes", 0),
            datos_gral.get("total_no_aplica", 0),
            datos_gral.get("epp_conforme", 1),
            datos_gral.get("maquinaria_conforme", 1),
            datos_gral.get("insumos_conforme", 1),
            datos_gral.get("incluir_firmas", 1),
            datos_gral.get("observaciones_generales", ""),
            datos_gral.get("plan_accion_resumen", ""),
            datos_gral.get("firmante_cliente_nombre", ""),
            datos_gral.get("firmante_cliente_cargo", ""),
            datos_gral.get("estado_informe", "FINALIZADO"),
            supervision_id
        ))

        # 2. Reemplazar Detalle de Evaluación
        cursor.execute("DELETE FROM supervision_detalles_areas WHERE supervision_id = ?", (supervision_id,))
        for d in detalles_evaluacion:
            cursor.execute("""
                INSERT INTO supervision_detalles_areas (
                    supervision_id, id_area, nombre_area, id_criterio, item_criterio, calificacion, puntos, observacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supervision_id,
                d["id_area"],
                d["nombre_area"],
                d["id_criterio"],
                d["item_criterio"],
                d["calificacion"],
                d.get("puntos", PUNTAJES.get(d.get("calificacion", "C"), {}).get("puntos", 100)),
                d.get("observacion", "")
            ))

        # 3. Reemplazar Incidencias
        cursor.execute("DELETE FROM supervision_incidencias WHERE supervision_id = ?", (supervision_id,))
        for inc in incidencias:
            f_hallazgo = inc.get("foto_ruta") or (inc.get("fotos")[0] if inc.get("fotos") else inc.get("foto_hallazgo_ruta", ""))
            cursor.execute("""
                INSERT INTO supervision_incidencias (
                    supervision_id, area_nombre, descripcion_hallazgo, severidad,
                    accion_correctiva, plazo_subsanacion, responsable, estado_subsanacion,
                    foto_hallazgo_ruta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supervision_id,
                inc.get("area_nombre", "General"),
                inc.get("descripcion_hallazgo", ""),
                inc.get("severidad", "Media"),
                inc.get("accion_correctiva", ""),
                inc.get("plazo_subsanacion", "24 horas"),
                inc.get("responsable", "Supervisor de Turno"),
                inc.get("estado_subsanacion", inc.get("estado_subsanacion", "Pendiente")),
                f_hallazgo
            ))

        # 4. Actualizar fotos de la supervisión
        if fotos_guardadas is not None:
            cursor.execute("DELETE FROM supervision_fotos WHERE supervision_id = ?", (supervision_id,))
            rutas_insertadas = set()
            for f in fotos_guardadas:
                ruta = f.get("archivo_ruta", "")
                if not ruta:
                    continue
                ruta_norm = os.path.normpath(ruta)
                if ruta_norm in rutas_insertadas:
                    continue
                rutas_insertadas.add(ruta_norm)
                nom_arch = f.get("archivo_nombre") or os.path.basename(ruta_norm)
                f_padre = str(f.get("foto_padre_id", ""))
                try:
                    cursor.execute("""
                        INSERT INTO supervision_fotos (
                            supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen, foto_padre_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        supervision_id,
                        f.get("area_nombre", "General"),
                        f.get("tipo_evidencia", "Hallazgo / No Conforme"),
                        nom_arch,
                        ruta_norm,
                        f.get("descripcion", ""),
                        f.get("origen", "REGISTRO_FOTOGRAFICO"),
                        f_padre
                    ))
                except Exception:
                    cursor.execute("""
                        INSERT INTO supervision_fotos (
                            supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        supervision_id,
                        f.get("area_nombre", "General"),
                        f.get("tipo_evidencia", "Hallazgo / No Conforme"),
                        nom_arch,
                        ruta_norm,
                        f.get("descripcion", ""),
                        f.get("origen", "REGISTRO_FOTOGRAFICO")
                    ))
                foto_id_padre = cursor.lastrowid

                # Insertar fotos adicionales / complementarias asociadas a esta evidencia
                for sub_f in f.get("fotos_adicionales", []):
                    sub_r = sub_f.get("archivo_ruta", "")
                    if not sub_r:
                        continue
                    sub_r_norm = os.path.normpath(sub_r)
                    if sub_r_norm in rutas_insertadas:
                        continue
                    rutas_insertadas.add(sub_r_norm)
                    sub_nom = sub_f.get("archivo_nombre") or os.path.basename(sub_r_norm)
                    try:
                        cursor.execute("""
                            INSERT INTO supervision_fotos (
                                supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen, foto_padre_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            supervision_id,
                            sub_f.get("area_nombre") or f.get("area_nombre", "General"),
                            sub_f.get("tipo_evidencia", "Después de Limpieza"),
                            sub_nom,
                            sub_r_norm,
                            sub_f.get("descripcion", ""),
                            sub_f.get("origen", "FOTO_ADICIONAL"),
                            str(foto_id_padre)
                        ))
                    except Exception:
                        cursor.execute("""
                            INSERT INTO supervision_fotos (
                                supervision_id, area_nombre, tipo_evidencia, archivo_nombre, archivo_ruta, descripcion, origen
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            supervision_id,
                            sub_f.get("area_nombre") or f.get("area_nombre", "General"),
                            sub_f.get("tipo_evidencia", "Después de Limpieza"),
                            sub_nom,
                            sub_r_norm,
                            sub_f.get("descripcion", ""),
                            sub_f.get("origen", "FOTO_ADICIONAL")
                        ))

        conn.commit()
        return True


def obtener_supervisiones(filtro_edificio=None, filtro_fecha_desde=None, filtro_fecha_hasta=None, filtro_supervisor=None):
    """Consulta la lista de supervisiones con filtros opcionales."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM supervisiones WHERE 1=1"
        params = []

        if filtro_edificio and filtro_edificio != "Todos":
            query += " AND edificio_nombre = ?"
            params.append(filtro_edificio)

        if filtro_supervisor and filtro_supervisor != "Todos":
            query += " AND supervisor_nombre = ?"
            params.append(filtro_supervisor)

        if filtro_fecha_desde:
            query += " AND fecha_inspeccion >= ?"
            params.append(str(filtro_fecha_desde))

        if filtro_fecha_hasta:
            query += " AND fecha_inspeccion <= ?"
            params.append(str(filtro_fecha_hasta))

        query += " ORDER BY fecha_inspeccion DESC, id DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def obtener_supervision_por_id(supervision_id: int):
    """Obtiene toda la información de una supervisión específica (cabecera, detalles, incidencias, fotos)."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM supervisiones WHERE id = ?", (supervision_id,))
        cabecera_row = cursor.fetchone()
        if not cabecera_row:
            return None
        cabecera = dict(cabecera_row)

        cursor.execute("SELECT * FROM supervision_detalles_areas WHERE supervision_id = ?", (supervision_id,))
        detalles = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM supervision_incidencias WHERE supervision_id = ?", (supervision_id,))
        incidencias = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM supervision_fotos WHERE supervision_id = ?", (supervision_id,))
        todas_fotos_db = [dict(r) for r in cursor.fetchall()]

        # Reconstruir estructura: fotos principales y sus fotos adicionales vinculadas
        fotos_principales = []
        fotos_por_id = {}
        sub_fotos_pendientes = []
        for r_f in todas_fotos_db:
            padre_id = str(r_f.get("foto_padre_id") or "").strip()
            if not padre_id:
                r_f["fotos_adicionales"] = []
                fotos_principales.append(r_f)
                fotos_por_id[str(r_f.get("id"))] = r_f
            else:
                sub_fotos_pendientes.append(r_f)

        for sub_r in sub_fotos_pendientes:
            padre_ref = str(sub_r.get("foto_padre_id", "")).strip()
            if padre_ref in fotos_por_id:
                fotos_por_id[padre_ref]["fotos_adicionales"].append(sub_r)
            else:
                sub_r["fotos_adicionales"] = []
                fotos_principales.append(sub_r)

        return {
            "cabecera": cabecera,
            "detalles": detalles,
            "incidencias": incidencias,
            "fotos": fotos_principales,
            "todas_las_fotos": todas_fotos_db
        }


def obtener_supervision_por_codigo(codigo_informe: str) -> Optional[Dict[str, Any]]:
    """Obtiene toda la información de una supervisión buscando por su código de informe."""
    if not codigo_informe or not str(codigo_informe).strip():
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM supervisiones WHERE codigo_informe = ?", (str(codigo_informe).strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        return obtener_supervision_por_id(row["id"])


def existe_codigo_informe(codigo_informe: str, excluir_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Verifica si un código de informe ya existe en la base de datos.
    Retorna los datos de cabecera si existe o None si está disponible.
    """
    if not codigo_informe or not str(codigo_informe).strip():
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        if excluir_id:
            cursor.execute("""
                SELECT id, codigo_informe, edificio_nombre, fecha_inspeccion, estado_informe, score_global, nivel_calidad
                FROM supervisiones
                WHERE codigo_informe = ? AND id != ?
            """, (str(codigo_informe).strip(), excluir_id))
        else:
            cursor.execute("""
                SELECT id, codigo_informe, edificio_nombre, fecha_inspeccion, estado_informe, score_global, nivel_calidad
                FROM supervisiones
                WHERE codigo_informe = ?
            """, (str(codigo_informe).strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def eliminar_supervision(supervision_id: int):
    """Elimina una supervisión y sus registros asociados en cascada."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM supervision_fotos WHERE supervision_id = ?", (supervision_id,))
        cursor.execute("DELETE FROM supervision_incidencias WHERE supervision_id = ?", (supervision_id,))
        cursor.execute("DELETE FROM supervision_detalles_areas WHERE supervision_id = ?", (supervision_id,))
        cursor.execute("DELETE FROM supervisiones WHERE id = ?", (supervision_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: GESTIÓN DE INCIDENCIAS (CAPA TRACKER)
# =====================================================================
def obtener_todas_incidencias(filtro_edificio=None, filtro_estado=None, filtro_severidad=None):
    """Retorna todas las incidencias registradas con datos de la supervisión asociada."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                i.*,
                s.codigo_informe,
                s.fecha_inspeccion,
                s.edificio_nombre,
                s.supervisor_nombre
            FROM supervision_incidencias i
            JOIN supervisiones s ON i.supervision_id = s.id
            WHERE 1=1
        """
        params = []
        if filtro_edificio and filtro_edificio != "Todos":
            query += " AND s.edificio_nombre = ?"
            params.append(filtro_edificio)
        if filtro_estado and filtro_estado != "Todos":
            query += " AND i.estado_subsanacion = ?"
            params.append(filtro_estado)
        if filtro_severidad and filtro_severidad != "Todos":
            query += " AND i.severidad = ?"
            params.append(filtro_severidad)

        query += " ORDER BY s.fecha_inspeccion DESC, i.id DESC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def actualizar_estado_incidencia(incidencia_id: int, nuevo_estado: str, fecha_subsanacion: str = "", foto_subsanacion_ruta: str = "", comentario_cierre: str = "", cerrado_por: str = ""):
    """Actualiza el estado de resolución y evidencia fotográfica de una no conformidad (CAPA)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE supervision_incidencias SET
                estado_subsanacion = ?,
                fecha_subsanacion = COALESCE(NULLIF(?, ''), fecha_subsanacion),
                foto_subsanacion_ruta = COALESCE(NULLIF(?, ''), foto_subsanacion_ruta),
                comentario_cierre = COALESCE(NULLIF(?, ''), comentario_cierre),
                cerrado_por = COALESCE(NULLIF(?, ''), cerrado_por)
            WHERE id = ?
        """, (nuevo_estado, fecha_subsanacion, foto_subsanacion_ruta, comentario_cierre, cerrado_por, incidencia_id))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: CRONOGRAMA Y PLANIFICACIÓN DE SUPERVISIONES
# =====================================================================
def obtener_cronograma(filtro_edificio=None, filtro_estado=None, filtro_supervisor=None):
    """Consulta las tareas programadas en el calendario de supervisión."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM cronograma_supervisiones WHERE 1=1"
        params = []
        if filtro_edificio and filtro_edificio != "Todos":
            query += " AND edificio_nombre = ?"
            params.append(filtro_edificio)
        if filtro_estado and filtro_estado != "Todos":
            query += " AND estado = ?"
            params.append(filtro_estado)
        if filtro_supervisor and filtro_supervisor != "Todos":
            query += " AND supervisor_nombre = ?"
            params.append(filtro_supervisor)
        query += " ORDER BY fecha_programada ASC, id ASC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def agregar_item_cronograma(edificio_id, edificio_nombre, supervisor_id, supervisor_nombre, fecha_programada, tipo_inspeccion, turno, observaciones=""):
    """Programa una nueva inspección en el cronograma."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cronograma_supervisiones (
                edificio_id, edificio_nombre, supervisor_id, supervisor_nombre,
                fecha_programada, tipo_inspeccion, turno, estado, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Programada', ?)
        """, (edificio_id, edificio_nombre, supervisor_id, supervisor_nombre, fecha_programada, tipo_inspeccion, turno, observaciones))
        conn.commit()
        return cursor.lastrowid


def actualizar_estado_cronograma(cronograma_id: int, nuevo_estado: str, supervision_id=None):
    """Actualiza el estado de una tarea programada (ej. Realizada, Cancelada)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cronograma_supervisiones SET
                estado = ?,
                supervision_id = COALESCE(?, supervision_id)
            WHERE id = ?
        """, (nuevo_estado, supervision_id, cronograma_id))
        conn.commit()
        return True


def eliminar_item_cronograma(cronograma_id: int):
    """Elimina una tarea del cronograma."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cronograma_supervisiones WHERE id = ?", (cronograma_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: CONTROL DE INSUMOS Y KARDEX DE QUÍMICOS
# =====================================================================
def obtener_insumos(filtro_edificio=None):
    """Retorna la lista de insumos de limpieza y químicos en stock."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM control_insumos_stock WHERE activo = 1"
        params = []
        if filtro_edificio and filtro_edificio != "Todos":
            query += " AND edificio_nombre = ?"
            params.append(filtro_edificio)
        query += " ORDER BY edificio_nombre ASC, producto_nombre ASC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def agregar_insumo(edificio_id, edificio_nombre, producto_nombre, categoria, unidad_medida, stock_actual, stock_minimo):
    """Registra un nuevo insumo asignado a una sede."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO control_insumos_stock (
                edificio_id, edificio_nombre, producto_nombre, categoria,
                unidad_medida, stock_actual, stock_minimo, ultimo_movimiento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (edificio_id, edificio_nombre, producto_nombre, categoria, unidad_medida, stock_actual, stock_minimo))
        conn.commit()
        return cursor.lastrowid


def registrar_movimiento_insumo(insumo_id: int, tipo_movimiento: str, cantidad: float, responsable: str, motivo: str):
    """Registra un movimiento en el Kardex y actualiza el stock actual."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Insertar movimiento
        cursor.execute("""
            INSERT INTO movimientos_insumos (insumo_id, tipo_movimiento, cantidad, fecha_movimiento, responsable, motivo)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, (insumo_id, tipo_movimiento, cantidad, responsable, motivo))

        # Actualizar stock
        delta = cantidad if tipo_movimiento == "Ingreso" else (-cantidad if tipo_movimiento == "Egreso" else 0)
        if tipo_movimiento == "Ajuste":
            cursor.execute("UPDATE control_insumos_stock SET stock_actual = ?, ultimo_movimiento = datetime('now') WHERE id = ?", (cantidad, insumo_id))
        else:
            cursor.execute("UPDATE control_insumos_stock SET stock_actual = MAX(0, stock_actual + ?), ultimo_movimiento = datetime('now') WHERE id = ?", (delta, insumo_id))

        conn.commit()
        return True


def eliminar_insumo(insumo_id: int):
    """Desactiva un insumo del catálogo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE control_insumos_stock SET activo = 0 WHERE id = ?", (insumo_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS CRUD: MAQUINARIAS Y EQUIPOS
# =====================================================================
def obtener_maquinarias(filtro_edificio=None, filtro_estado=None):
    """Retorna el inventario y estado operativo de maquinarias."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM maquinarias_equipos WHERE activo = 1"
        params = []
        if filtro_edificio and filtro_edificio != "Todos":
            query += " AND edificio_nombre = ?"
            params.append(filtro_edificio)
        if filtro_estado and filtro_estado != "Todos":
            query += " AND estado_operativo = ?"
            params.append(filtro_estado)
        query += " ORDER BY edificio_nombre ASC, codigo_equipo ASC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def agregar_maquinaria(codigo_equipo, tipo_maquinaria, marca_modelo, serie, edificio_id, edificio_nombre, estado_operativo, fecha_adq, ultimo_mant, prox_mant, observaciones):
    """Registra una maquinaria en el inventario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO maquinarias_equipos (
                codigo_equipo, tipo_maquinaria, marca_modelo, serie,
                edificio_id, edificio_nombre, estado_operativo,
                fecha_adquisicion, ultimo_mantenimiento, proximo_mantenimiento, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (codigo_equipo, tipo_maquinaria, marca_modelo, serie, edificio_id, edificio_nombre, estado_operativo, fecha_adq, ultimo_mant, prox_mant, observaciones))
        conn.commit()
        return cursor.lastrowid


def actualizar_maquinaria(equipo_id: int, estado_operativo: str, ultimo_mant: str, prox_mant: str, observaciones: str):
    """Actualiza la ficha técnica y mantenimiento de un equipo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE maquinarias_equipos SET
                estado_operativo = ?,
                ultimo_mantenimiento = ?,
                proximo_mantenimiento = ?,
                observaciones = ?
            WHERE id = ?
        """, (estado_operativo, ultimo_mant, prox_mant, observaciones, equipo_id))
        conn.commit()
        return True


def eliminar_maquinaria(equipo_id: int):
    """Desactiva un equipo del inventario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE maquinarias_equipos SET activo = 0 WHERE id = ?", (equipo_id,))
        conn.commit()
        return True


# =====================================================================
# MÉTODOS DE ANALÍTICA AVANZADA, PARETO, BORRADORES Y CONSOLIDADOS
# =====================================================================
def obtener_ultima_supervision_edificio(edificio_nombre: str):
    """Retorna la última supervisión realizada para un edificio específico."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, codigo_informe, fecha_inspeccion, score_global, nivel_calidad, estado_aprobacion, total_no_conformes
            FROM supervisiones
            WHERE edificio_nombre = ? AND estado_informe = 'FINALIZADO'
            ORDER BY fecha_inspeccion DESC, id DESC
            LIMIT 1
        """, (edificio_nombre,))
        row = cursor.fetchone()
        return dict(row) if row else None


def obtener_estadisticas_causa_raiz():
    """
    Retorna el conteo y porcentaje acumulado de criterios observados (NC y R)
    para generar el Diagrama de Pareto de Causa Raíz.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                item_criterio,
                nombre_area,
                COUNT(*) as total_fallas,
                SUM(CASE WHEN calificacion = 'NC' THEN 1 ELSE 0 END) as total_nc,
                SUM(CASE WHEN calificacion = 'R' THEN 1 ELSE 0 END) as total_r
            FROM supervision_detalles_areas
            WHERE calificacion IN ('NC', 'R')
            GROUP BY item_criterio, nombre_area
            ORDER BY total_fallas DESC
            LIMIT 15
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        
        # Calcular porcentaje acumulado
        gran_total = sum(r["total_fallas"] for r in rows) if rows else 0
        acumulado = 0
        for r in rows:
            acumulado += r["total_fallas"]
            r["pct_individual"] = (r["total_fallas"] / gran_total * 100.0) if gran_total > 0 else 0
            r["pct_acumulado"] = (acumulado / gran_total * 100.0) if gran_total > 0 else 0

        return rows


def obtener_supervisiones_mes(edificio_nombre: str, anio: int, mes: int):
    """Obtiene todas las supervisiones de un edificio dentro de un mes y año para informe consolidado."""
    with get_connection() as conn:
        cursor = conn.cursor()
        mes_str = f"{mes:02d}"
        cursor.execute("""
            SELECT * FROM supervisiones
            WHERE edificio_nombre = ?
              AND strftime('%Y', fecha_inspeccion) = ?
              AND strftime('%m', fecha_inspeccion) = ?
            ORDER BY fecha_inspeccion ASC
        """, (edificio_nombre, str(anio), mes_str))
        return [dict(r) for r in cursor.fetchall()]


def obtener_borradores_supervisiones():
    """Retorna las supervisiones guardadas en estado Borrador."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, codigo_informe, fecha_inspeccion, edificio_nombre, supervisor_nombre, score_global, creado_en
            FROM supervisiones
            WHERE estado_informe = 'BORRADOR'
            ORDER BY id DESC
        """)
        return [dict(r) for r in cursor.fetchall()]


# =====================================================================
# MÉTODOS CRUD: USUARIOS Y AUTENTICACIÓN
# =====================================================================
def autenticar_usuario(username: str, password: str) -> dict | None:
    """Verifica las credenciales del usuario y retorna sus datos si es válido y activo."""
    if not username or not password:
        return None
    
    pwd_h = hash_password(password.strip())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM usuarios
            WHERE (LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?))
              AND password_hash = ?
        """, (username.strip(), username.strip(), pwd_h))
        row = cursor.fetchone()
        if not row:
            return None
        
        user_data = dict(row)
        if not user_data.get("activo", 1):
            return {"error": "inactivo", "usuario": user_data}
        
        # Actualizar fecha y hora de último acceso
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE usuarios SET ultimo_acceso = ? WHERE id = ?", (ahora, user_data["id"]))
        conn.commit()
        user_data["ultimo_acceso"] = ahora
        return user_data


def obtener_lista_usuarios(solo_activos: bool = False) -> list[dict]:
    """Obtiene el listado de usuarios del sistema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT id, username, nombre_completo, rol, cargo, email, edificio_asignado, activo, creado_en, ultimo_acceso FROM usuarios"
        if solo_activos:
            query += " WHERE activo = 1"
        query += " ORDER BY rol ASC, nombre_completo ASC"
        cursor.execute(query)
        return [dict(r) for r in cursor.fetchall()]


def obtener_usuario_por_id(usuario_id: int) -> dict | None:
    """Obtiene los datos de un usuario por su ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def agregar_usuario(username: str, password: str, nombre_completo: str, rol: str, cargo: str = "", email: str = "", edificio_asignado: str = "Todos") -> tuple[bool, str]:
    """Registra un nuevo usuario en la base de datos."""
    if not username or not password or not nombre_completo:
        return False, "Usuario, contraseña y nombre completo son obligatorios."
    
    u_clean = username.strip().lower()
    pwd_h = hash_password(password.strip())
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, nombre_completo, rol, cargo, email, edificio_asignado, activo, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (u_clean, pwd_h, nombre_completo.strip(), rol, cargo.strip(), email.strip(), edificio_asignado, ahora))
            conn.commit()
            return True, f"Usuario '{u_clean}' creado con éxito."
    except sqlite3.IntegrityError:
        return False, f"El nombre de usuario '{u_clean}' ya está registrado. Elija otro."
    except Exception as e:
        return False, f"Error al crear usuario: {str(e)}"


def actualizar_usuario(usuario_id: int, nombre_completo: str, rol: str, cargo: str = "", email: str = "", activo: int = 1, edificio_asignado: str = "Todos") -> tuple[bool, str]:
    """Actualiza los datos del perfil de un usuario existente."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE usuarios
                SET nombre_completo = ?, rol = ?, cargo = ?, email = ?, activo = ?, edificio_asignado = ?
                WHERE id = ?
            """, (nombre_completo.strip(), rol, cargo.strip(), email.strip(), int(activo), edificio_asignado, usuario_id))
            conn.commit()
            return True, "Datos de usuario actualizados correctamente."
    except Exception as e:
        return False, f"Error al actualizar usuario: {str(e)}"


def cambiar_password_usuario(usuario_id: int, nuevo_password: str) -> tuple[bool, str]:
    """Actualiza la contraseña de un usuario."""
    if not nuevo_password or len(nuevo_password.strip()) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."
    
    pwd_h = hash_password(nuevo_password.strip())
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (pwd_h, usuario_id))
            conn.commit()
            return True, "Contraseña actualizada exitosamente."
    except Exception as e:
        return False, f"Error al cambiar contraseña: {str(e)}"


def eliminar_usuario_db(usuario_id: int) -> tuple[bool, str]:
    """Elimina un usuario del sistema (protegiendo el admin principal)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM usuarios WHERE id = ?", (usuario_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Usuario no encontrado."
        
        if row["username"] == "admin":
            return False, "No se puede eliminar el usuario administrador principal ('admin')."
        
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        conn.commit()
        return True, "Usuario eliminado del sistema."

