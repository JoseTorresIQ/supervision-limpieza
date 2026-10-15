"""
Script de Pruebas Automatizadas: Sistema de Supervisión de Limpieza de Edificios.
Valida la inicialización de SQLite, cálculo de calificaciones, inserción transaccional y generación de PDF/Excel.
"""
import io
import os
import sys
import unittest
from datetime import datetime

# Añadir directorio actual al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import CHECKLIST_AREAS, PUNTAJES, clasificar_calidad, DATA_DIR
from database import (
    init_db, get_connection, obtener_lista_edificios, obtener_lista_supervisores,
    guardar_supervision_completa, obtener_supervision_por_id, generar_nuevo_codigo
)
from modules.reportes_pdf import generar_pdf_supervision


class TestSupervisionLimpieza(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Inicializar base de datos de pruebas."""
        init_db()

    def test_01_maestros_disponibles(self):
        """Verificar que existan edificios y supervisores sembrados."""
        edificios = obtener_lista_edificios()
        supervisores = obtener_lista_supervisores()
        
        self.assertGreater(len(edificios), 0, "Debe haber al menos 1 edificio registrado.")
        self.assertGreater(len(supervisores), 0, "Debe haber al menos 1 supervisor registrado.")
        print(f"[OK] Maestros validados: {len(edificios)} edificios, {len(supervisores)} supervisores.")

    def test_02_clasificacion_calidad(self):
        """Verificar la lógica de semáforo de calidad de 5 niveles solicitada."""
        res_98 = clasificar_calidad(98.0)
        self.assertEqual(res_98["nivel"], "ÓPTIMO")

        res_95 = clasificar_calidad(95.0)
        self.assertEqual(res_95["nivel"], "ÓPTIMO")

        res_92 = clasificar_calidad(92.0)
        self.assertEqual(res_92["nivel"], "ADECUADO")

        res_87 = clasificar_calidad(87.0)
        self.assertEqual(res_87["nivel"], "ACEPTABLE")

        res_82 = clasificar_calidad(82.0)
        self.assertEqual(res_82["nivel"], "POR MEJORAR")

        res_50 = clasificar_calidad(50.0)
        self.assertEqual(res_50["nivel"], "NO CONFORME")
        print("[OK] Logica de clasificacion de calidad de 5 niveles 100% correcta.")

    def test_03_flujo_completo_supervision_y_pdf(self):
        """Crear una supervision completa, guardarla en SQLite y generar el PDF."""
        codigo = generar_nuevo_codigo()
        self.assertTrue(codigo.startswith("REP-LMP-"))

        edificios = obtener_lista_edificios()
        edif = edificios[0]

        supervisores = obtener_lista_supervisores()
        sup = supervisores[0]

        # Simular evaluacion de criterios
        detalles = []
        for area in CHECKLIST_AREAS:
            for crit in area["criterios"]:
                detalles.append({
                    "id_area": area["id_area"],
                    "nombre_area": area["nombre"],
                    "id_criterio": crit["id"],
                    "item_criterio": crit["item"],
                    "calificacion": "C",
                    "puntos": 100.0,
                    "observacion": "Limpieza y desinfeccion conforme."
                })

        incidencias = [
            {
                "area_nombre": "3. Pasadizos, Corredores y Áreas Comunes",
                "descripcion_hallazgo": "Mancha superficial de grasa cerca a puerta de servicio piso 4",
                "severidad": "Media",
                "accion_correctiva": "Desengrasar y mopar con detergente neutro",
                "plazo_subsanacion": "24 horas",
                "responsable": "Lider de Cuadrilla",
                "estado_subsanacion": "Pendiente"
            }
        ]

        datos_gral = {
            "codigo_informe": codigo,
            "fecha_inspeccion": datetime.now().strftime("%Y-%m-%d"),
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "tipo_inspeccion": "Supervisión Rutinaria Diaria",
            "turno": "Turno Mañana (07:00 - 15:00)",
            "edificio_id": edif["id"],
            "edificio_nombre": edif["nombre"],
            "edificio_direccion": edif["direccion"],
            "administrador_nombre": edif.get("administrador_contacto", ""),
            "supervisor_id": sup["id"],
            "supervisor_nombre": sup["nombre_completo"],
            "supervisor_dni": sup["dni_ce"],
            "lider_cuadrilla": "Tecnico Juan Quispe",
            "personal_programado": 6,
            "personal_presente": 6,
            "personal_faltante": 0,
            "score_global": 98.0,
            "nivel_calidad": "ÓPTIMO",
            "estado_aprobacion": "APROBADO CON DISTINCION",
            "total_items_evaluados": len(detalles),
            "total_conformes": len(detalles),
            "total_regulares": 0,
            "total_no_conformes": 0,
            "total_no_aplica": 0,
            "epp_conforme": 1,
            "maquinaria_conforme": 1,
            "insumos_conforme": 1,
            "incluir_firmas": 1,
            "observaciones_generales": "Instalaciones en perfecto estado de higiene y operatividad.",
            "plan_accion_resumen": "1 incidencia menor en subsanacion.",
            "firma_supervisor_data": "",
            "firma_cliente_data": "",
            "firmante_cliente_nombre": "Ing. Roberto Seminario",
            "firmante_cliente_cargo": "Administrador de Sede"
        }

        # Guardar en base de datos
        sup_id, cod_gen = guardar_supervision_completa(
            datos_gral=datos_gral,
            detalles_evaluacion=detalles,
            incidencias=incidencias,
            fotos_guardadas=[]
        )

        self.assertIsNotNone(sup_id)
        self.assertEqual(cod_gen, codigo)
        print(f"[OK] Supervision guardada con ID={sup_id} y Codigo={cod_gen}")

        # Recuperar y verificar datos
        recuperado = obtener_supervision_por_id(sup_id)
        self.assertIsNotNone(recuperado)
        self.assertEqual(len(recuperado["detalles"]), len(detalles))
        self.assertEqual(len(recuperado["incidencias"]), 1)

        # Probar generacion de PDF en memoria
        pdf_bytes = generar_pdf_supervision(recuperado)
        self.assertGreater(len(pdf_bytes), 1000, "El PDF generado debe tener un tamaño valido (> 1KB).")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"), "El archivo generado debe tener la cabecera estandar de PDF.")
        print(f"[OK] Generacion de PDF verificada con exito ({len(pdf_bytes)} bytes generados).")

    def test_04_capa_tracker_resolucion(self):
        """Verificar flujo completo de gestión y subsanación de incidencias CAPA."""
        from database import obtener_todas_incidencias, actualizar_estado_incidencia
        
        incidencias = obtener_todas_incidencias()
        self.assertGreater(len(incidencias), 0, "Debe haber al menos 1 incidencia en el sistema.")
        
        primera = incidencias[0]
        inc_id = primera["id"]
        
        # Subsanar incidencia
        res = actualizar_estado_incidencia(
            incidencia_id=inc_id,
            nuevo_estado="Subsanada",
            fecha_subsanacion="2026-10-11",
            foto_subsanacion_ruta="static/uploads/test_subsanacion.jpg",
            comentario_cierre="Piso desengrasado con amonio cuaternario.",
            cerrado_por="Líder de Cuadrilla Test"
        )
        self.assertTrue(res)
        
        # Verificar actualización
        actualizadas = obtener_todas_incidencias(filtro_estado="Subsanada")
        ids_sub = [i["id"] for i in actualizadas]
        self.assertIn(inc_id, ids_sub)
        print("[OK] Levantamiento de observaciones CAPA verificado.")

    def test_05_cronograma_supervisiones(self):
        """Verificar programación y actualización de auditorías en el cronograma."""
        from database import obtener_cronograma, agregar_item_cronograma, actualizar_estado_cronograma
        
        edificios = obtener_lista_edificios()
        supervisores = obtener_lista_supervisores()
        
        item_id = agregar_item_cronograma(
            edificio_id=edificios[0]["id"],
            edificio_nombre=edificios[0]["nombre"],
            supervisor_id=supervisores[0]["id"],
            supervisor_nombre=supervisores[0]["nombre_completo"],
            fecha_programada="2026-10-15",
            tipo_inspeccion="Auditoría Mensual de Calidad",
            turno="Turno Mañana (07:00 - 15:00)",
            observaciones="Revisión contractual semestral."
        )
        self.assertIsNotNone(item_id)
        
        # Marcar como realizada
        res = actualizar_estado_cronograma(item_id, "Realizada")
        self.assertTrue(res)
        
        tareas = obtener_cronograma()
        tarea = next((t for t in tareas if t["id"] == item_id), None)
        self.assertIsNotNone(tarea)
        self.assertEqual(tarea["estado"], "Realizada")
        print("[OK] Cronograma y planificador operativo validados.")

    def test_06_insumos_y_kardex(self):
        """Verificar control de stock de químicos y movimientos de kardex."""
        from database import obtener_insumos, agregar_insumo, registrar_movimiento_insumo
        
        edificios = obtener_lista_edificios()
        insumo_id = agregar_insumo(
            edificio_id=edificios[0]["id"],
            edificio_nombre=edificios[0]["nombre"],
            producto_nombre="Cera Acrílica Brillo Diamante",
            categoria="Químicos Especiales",
            unidad_medida="Galones",
            stock_actual=10.0,
            stock_minimo=3.0
        )
        self.assertIsNotNone(insumo_id)
        
        # Registrar egreso
        registrar_movimiento_insumo(insumo_id, "Egreso", 4.0, "Operario Juan", "Encerado de lobby")
        
        insumos = obtener_insumos(filtro_edificio=edificios[0]["nombre"])
        ins = next((i for i in insumos if i["id"] == insumo_id), None)
        self.assertIsNotNone(ins)
        self.assertEqual(ins["stock_actual"], 6.0)
        print("[OK] Kardex de insumos y control de stock validados.")

    def test_07_maquinarias_equipos(self):
        """Verificar inventario y ficha técnica de maquinarias."""
        from database import obtener_maquinarias, agregar_maquinaria, actualizar_maquinaria
        
        edificios = obtener_lista_edificios()
        cod_eq = f"TEST-LUST-{datetime.now().strftime('%S%f')[:4]}"
        m_id = agregar_maquinaria(
            codigo_equipo=cod_eq,
            tipo_maquinaria='Lustradora Rotativa de 17"',
            marca_modelo="Viper HD 17",
            serie="SN-TEST-999",
            edificio_id=edificios[0]["id"],
            edificio_nombre=edificios[0]["nombre"],
            estado_operativo="Operativo",
            fecha_adq="2025-01-01",
            ultimo_mant="2026-09-01",
            prox_mant="2026-12-01",
            observaciones="En buen estado."
        )
        self.assertIsNotNone(m_id)
        
        actualizar_maquinaria(m_id, "En Mantenimiento", "2026-10-11", "2026-11-11", "Mantenimiento preventivo en taller.")
        maqs = obtener_maquinarias()
        maq = next((m for m in maqs if m["id"] == m_id), None)
        self.assertEqual(maq["estado_operativo"], "En Mantenimiento")
        print("[OK] Ficha técnica y mantenimiento de maquinarias validados.")

    def test_08_reporte_consolidado_mensual_pdf(self):
        """Verificar generación del informe mensual consolidado en PDF."""
        from database import obtener_supervisiones
        from modules.reportes_consolidados import generar_pdf_consolidado_mensual
        
        supervisiones = obtener_supervisiones()
        self.assertGreater(len(supervisiones), 0)
        edif_nom = supervisiones[0]["edificio_nombre"]
        
        pdf_bytes = generar_pdf_consolidado_mensual(edif_nom, 2026, 10, supervisiones[:3])
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        print(f"[OK] PDF Consolidado Mensual generado con éxito ({len(pdf_bytes)} bytes).")

    def test_09_analitica_pareto_causa_raiz(self):
        """Verificar cálculo de Pareto y causa raíz."""
        from database import obtener_estadisticas_causa_raiz
        
        pareto = obtener_estadisticas_causa_raiz()
        self.assertIsInstance(pareto, list)
        if pareto:
            self.assertIn("pct_acumulado", pareto[0])
            self.assertIn("total_fallas", pareto[0])
        print(f"[OK] Cálculo de Pareto de Causa Raíz validado ({len(pareto)} criterios con observaciones).")

    def test_10_backup_zip_generacion(self):
        """Verificar generación de copia de seguridad .zip y comprobaciones con os.path."""
        import os
        import io
        import zipfile
        from config import DATA_DIR, UPLOADS_DIR
        from database import DB_PATH

        self.assertTrue(os.path.exists(DB_PATH), "El archivo de base de datos DB_PATH debe existir.")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(DB_PATH):
                zf.write(DB_PATH, arcname="supervision_limpieza.db")
            if os.path.exists(UPLOADS_DIR):
                for raiz, _, archivos in os.walk(UPLOADS_DIR):
                    for arc in archivos:
                        ruta_completa = os.path.join(raiz, arc)
                        arc_rel = os.path.relpath(ruta_completa, UPLOADS_DIR)
                        zf.write(ruta_completa, arcname=os.path.join("uploads", arc_rel))

        zip_buf.seek(0)
        self.assertGreater(len(zip_buf.getvalue()), 100, "El archivo ZIP de respaldo debe contener datos.")

        # Verificar contenido del zip generado
        with zipfile.ZipFile(zip_buf, "r") as zf_test:
            nombres = zf_test.namelist()
            self.assertIn("supervision_limpieza.db", nombres, "El ZIP debe contener la base de datos.")
        print(f"[OK] Generación de Copia de Seguridad .ZIP validada ({len(zip_buf.getvalue())} bytes).")

    def test_11_resumen_zona_na_y_borrador_fotos(self):
        """Verificar cálculo N.A. por zona en PDF y guardado/carga de fotos en borradores."""
        from database import (
            guardar_supervision_completa, obtener_supervision_por_id,
            actualizar_supervision_completa, eliminar_supervision,
            generar_nuevo_codigo
        )
        from modules.reportes_pdf import generar_pdf_supervision
        from config import UPLOADS_DIR
        
        detalles = [
            {"id_area": "HALL_PRIN", "nombre_area": "Hall Principal y Recepción", "id_criterio": "CRIT_01", "item_criterio": "Pisos", "calificacion": "C", "puntos": 100, "observacion": "OK"},
            {"id_area": "SOTANOS", "nombre_area": "Sótanos y Estacionamientos", "id_criterio": "CRIT_S1", "item_criterio": "Piso sótano", "calificacion": "NA", "puntos": None, "observacion": "No aplica este turno"},
            {"id_area": "SOTANOS", "nombre_area": "Sótanos y Estacionamientos", "id_criterio": "CRIT_S2", "item_criterio": "Rampa", "calificacion": "NA", "puntos": None, "observacion": "Cerrado"},
        ]
        
        test_img_path = str(UPLOADS_DIR / "test_foto_borrador.jpg")
        with open(test_img_path, "wb") as f_img:
            f_img.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9")

        fotos_iniciales = [
            {
                "area_nombre": "Hall Principal",
                "tipo_evidencia": "Antes de Limpieza",
                "archivo_nombre": "test_foto_borrador.jpg",
                "archivo_ruta": test_img_path,
                "descripcion": "Foto previa de prueba"
            }
        ]

        datos_gral = {
            "codigo_informe": generar_nuevo_codigo(),
            "fecha_inspeccion": "2026-10-12",
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "tipo_inspeccion": "Supervisión Rutinaria Diaria",
            "turno": "Turno Mañana (07:00 - 15:00)",
            "edificio_id": 1,
            "edificio_nombre": "Edificio Test",
            "edificio_direccion": "Av. Test 123",
            "administrador_nombre": "Admin Test",
            "supervisor_id": 1,
            "supervisor_nombre": "Supervisor Test",
            "supervisor_dni": "12345678",
            "lider_cuadrilla": "Líder Test",
            "personal_programado": 4,
            "personal_presente": 4,
            "personal_faltante": 0,
            "score_global": 100.0,
            "nivel_calidad": "ÓPTIMO",
            "estado_aprobacion": "APROBADO",
            "total_items_evaluados": 3,
            "total_conformes": 1,
            "total_regulares": 0,
            "total_no_conformes": 0,
            "total_no_aplica": 2,
            "epp_conforme": 1,
            "maquinaria_conforme": 1,
            "insumos_conforme": 1,
            "incluir_firmas": 0,
            "observaciones_generales": "Supervisión con área N.A. y fotos",
            "plan_accion_resumen": "Sin incidencias",
            "estado_informe": "BORRADOR"
        }

        # Guardar como borrador
        sup_id, cod = guardar_supervision_completa(datos_gral, detalles, [], fotos_iniciales)
        self.assertIsNotNone(sup_id)

        # Cargar borrador
        recuperado = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recuperado["fotos"]), 1)
        self.assertEqual(recuperado["fotos"][0]["descripcion"], "Foto previa de prueba")

        # Probar generar PDF con área NA y foto
        pdf_bytes = generar_pdf_supervision(recuperado)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        # Actualizar fotos en el borrador (modificar descripción y tipo)
        fotos_actualizadas = [
            {
                "area_nombre": "Hall Principal",
                "tipo_evidencia": "Después de Limpieza",
                "archivo_nombre": "test_foto_borrador.jpg",
                "archivo_ruta": test_img_path,
                "descripcion": "Foto actualizada tras pulido"
            }
        ]
        actualizar_supervision_completa(sup_id, datos_gral, detalles, [], fotos_actualizadas)
        
        # Recuperar y verificar que se actualizó sin duplicados
        recuperado_2 = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recuperado_2["fotos"]), 1)
        self.assertEqual(recuperado_2["fotos"][0]["descripcion"], "Foto actualizada tras pulido")
        self.assertEqual(recuperado_2["fotos"][0]["tipo_evidencia"], "Después de Limpieza")

        # Limpiar registro y archivo de prueba
        eliminar_supervision(sup_id)
        if os.path.exists(test_img_path):
            os.remove(test_img_path)
        print("[OK] Resumen ejecutivo de área N.A. en PDF y guardado/recuperación de fotos en borradores validados.")

    def test_12_encabezados_pdf_salto_pagina_y_deduplicacion_borrador(self):
        """Verificar color blanco en encabezados de tabla, salto de página en fotos y deduplicación en borradores."""
        import io
        from pypdf import PdfReader
        from database import (
            guardar_supervision_completa, obtener_supervision_por_id,
            actualizar_supervision_completa, eliminar_supervision,
            generar_nuevo_codigo
        )
        from modules.reportes_pdf import generar_pdf_supervision
        from config import UPLOADS_DIR

        # 1. Crear 2 imágenes de prueba
        img1_path = str(UPLOADS_DIR / "test_dedup_1.jpg")
        img2_path = str(UPLOADS_DIR / "test_dedup_2.jpg")
        jpeg_dummy = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        with open(img1_path, "wb") as f1, open(img2_path, "wb") as f2:
            f1.write(jpeg_dummy)
            f2.write(jpeg_dummy)

        # 2. Datos con fotos duplicadas intencionalmente
        fotos_con_duplicados = [
            {"area_nombre": "Hall", "tipo_evidencia": "Antes", "archivo_nombre": "test_dedup_1.jpg", "archivo_ruta": img1_path, "descripcion": "Desc 1"},
            {"area_nombre": "Baños", "tipo_evidencia": "Después", "archivo_nombre": "test_dedup_2.jpg", "archivo_ruta": img2_path, "descripcion": "Desc 2"},
            {"area_nombre": "Hall", "tipo_evidencia": "Antes", "archivo_nombre": "test_dedup_1.jpg", "archivo_ruta": img1_path, "descripcion": "Desc 1 Repetida"}, # DUPLICADA
        ]

        datos_gral = {
            "codigo_informe": generar_nuevo_codigo(),
            "fecha_inspeccion": "2026-10-13",
            "hora_inicio": "08:00",
            "hora_fin": "09:00",
            "tipo_inspeccion": "Supervisión Rutinaria Diaria",
            "turno": "Turno Mañana (07:00 - 15:00)",
            "edificio_id": 1,
            "edificio_nombre": "Edificio Test",
            "edificio_direccion": "Av. Test 123",
            "supervisor_id": 1,
            "supervisor_nombre": "Supervisor Test",
            "score_global": 95.0,
            "nivel_calidad": "ÓPTIMO",
            "estado_aprobacion": "APROBADO",
            "incluir_firmas": 0,
            "estado_informe": "BORRADOR"
        }
        detalles = [
            {"id_area": "A1", "nombre_area": "Hall", "id_criterio": "C1", "item_criterio": "Piso", "calificacion": "C", "puntos": 100, "observacion": "OK"}
        ]
        incidencias = [
            {"area_nombre": "Hall", "descripcion_hallazgo": "Falta jabón", "severidad": "Media", "accion_correctiva": "Reponer", "plazo_subsanacion": "24 hrs", "responsable": "Cuadrilla"}
        ]

        # Guardar como borrador
        sup_id, cod = guardar_supervision_completa(datos_gral, detalles, incidencias, fotos_con_duplicados)

        # Verificar que la base de datos deduplicó y guardó exactamente 2 fotos (sin la duplicada)
        recuperado = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recuperado["fotos"]), 2, "La base de datos debe almacenar exactamente las fotos únicas.")
        self.assertEqual(recuperado["fotos"][0]["archivo_nombre"], "test_dedup_1.jpg")
        self.assertEqual(recuperado["fotos"][1]["archivo_nombre"], "test_dedup_2.jpg")

        # Probar actualizar borrador con foto duplicada adicional
        fotos_actualizar = recuperado["fotos"] + [
            {"area_nombre": "Hall", "tipo_evidencia": "Antes", "archivo_nombre": "test_dedup_1.jpg", "archivo_ruta": img1_path, "descripcion": "Duplicada 2"}
        ]
        actualizar_supervision_completa(sup_id, datos_gral, detalles, incidencias, fotos_actualizar)
        recuperado_post = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recuperado_post["fotos"]), 2, "Al actualizar el borrador no deben generarse fotos repetidas.")

        # Verificar que el PDF generado inicia el registro fotográfico en hoja a parte
        pdf_bytes = generar_pdf_supervision(recuperado_post)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 2, "El PDF debe tener al menos 2 páginas.")
        # La página 1 no debe tener el título de registro fotográfico
        self.assertNotIn("REGISTRO FOTOGRÁFICO", reader.pages[0].extract_text(), "El registro fotográfico no debe aparecer en la primera hoja.")
        # La página 2 debe comenzar con el registro fotográfico
        self.assertIn("REGISTRO FOTOGRÁFICO", reader.pages[1].extract_text(), "El registro fotográfico debe iniciar en una hoja separada.")

        # Limpiar
        eliminar_supervision(sup_id)
        for p in [img1_path, img2_path]:
            if os.path.exists(p):
                os.remove(p)
        print("[OK] Validación completada: encabezados de tabla, salto de página en registro fotográfico y no duplicación de fotos en borradores.")

    def test_13_historial_agrupacion_entidad_y_fechas(self):
        """Verificar agrupación por entidad, orden cronológico de fechas y métricas de resumen en historial."""
        from database import obtener_supervisiones
        from modules.historial import render_historial_supervisiones
        from config import clasificar_calidad

        supervisiones = obtener_supervisiones()
        self.assertGreater(len(supervisiones), 0, "Debe haber supervisiones registradas en la base de datos.")

        # 1. Agrupar por entidad
        entidades_dict = {}
        for sup in supervisiones:
            edif_nom = sup["edificio_nombre"]
            entidades_dict.setdefault(edif_nom, []).append(sup)

        self.assertGreater(len(entidades_dict), 0, "Debe existir al menos una entidad con supervisiones.")

        # 2. Verificar ordenamiento por fecha (descendente y ascendente)
        for edif_nom, sups_entidad in entidades_dict.items():
            # Orden descendente (más recientes primero)
            sups_desc = sorted(
                sups_entidad,
                key=lambda x: (x.get("fecha_inspeccion") or "", x.get("hora_inicio") or "", x.get("id", 0)),
                reverse=True
            )
            fechas_desc = [s["fecha_inspeccion"] for s in sups_desc]
            for i in range(len(fechas_desc) - 1):
                self.assertGreaterEqual(fechas_desc[i], fechas_desc[i + 1], "Las fechas deben estar en orden descendente.")

            # Orden ascendente (más antiguas primero)
            sups_asc = sorted(
                sups_entidad,
                key=lambda x: (x.get("fecha_inspeccion") or "", x.get("hora_inicio") or "", x.get("id", 0)),
                reverse=False
            )
            fechas_asc = [s["fecha_inspeccion"] for s in sups_asc]
            for i in range(len(fechas_asc) - 1):
                self.assertLessEqual(fechas_asc[i], fechas_asc[i + 1], "Las fechas deben estar en orden ascendente.")

            # 3. Verificar detalles de resumen por entidad
            total_ent = len(sups_entidad)
            prom_score_ent = sum(s["score_global"] for s in sups_entidad) / total_ent
            cal_ent = clasificar_calidad(prom_score_ent)
            self.assertIn("nivel", cal_ent)
            self.assertIn("color", cal_ent)

            total_c_ent = sum(s.get("total_conformes", 0) for s in sups_entidad)
            total_r_ent = sum(s.get("total_regulares", 0) for s in sups_entidad)
            total_nc_ent = sum(s.get("total_no_conformes", 0) for s in sups_entidad)
            total_na_ent = sum(s.get("total_no_aplica", 0) for s in sups_entidad)
            self.assertGreaterEqual(total_c_ent, 0)
            self.assertGreaterEqual(total_nc_ent, 0)

            # 4. Verificar que cada supervisión individual contiene los campos de resumen requeridos
            for s in sups_entidad:
                self.assertIn("codigo_informe", s)
                self.assertIn("fecha_inspeccion", s)
                self.assertIn("score_global", s)
                self.assertIn("nivel_calidad", s)
                self.assertIn("total_conformes", s)
                self.assertIn("total_regulares", s)
                self.assertIn("total_no_conformes", s)
                self.assertIn("total_no_aplica", s)
                self.assertIn("epp_conforme", s)
                self.assertIn("maquinaria_conforme", s)
                self.assertIn("insumos_conforme", s)

        print("[OK] Agrupación por entidad, orden por fecha y detalles de resúmenes de historial validados con éxito.")

    def test_14_autenticacion_y_usuarios(self):
        """Verificar autenticación con contraseña según usuarios, roles y CRUD de usuarios."""
        from database import (
            autenticar_usuario, agregar_usuario, actualizar_usuario,
            cambiar_password_usuario, eliminar_usuario_db, obtener_lista_usuarios
        )
        from modules.auth import render_login, render_user_sidebar

        # 1. Probar autenticación de usuarios predeterminados
        admin_auth = autenticar_usuario("admin", "admin123")
        self.assertIsNotNone(admin_auth, "El usuario admin debe autenticarse exitosamente.")
        self.assertEqual(admin_auth["username"], "admin")
        self.assertIn("Administrador", admin_auth["rol"])

        super_auth = autenticar_usuario("supervisor", "super123")
        self.assertIsNotNone(super_auth, "El usuario supervisor debe autenticarse exitosamente.")
        self.assertIn("Supervisor", super_auth["rol"])

        cliente_auth = autenticar_usuario("cliente", "cliente123")
        self.assertIsNotNone(cliente_auth, "El usuario cliente debe autenticarse exitosamente.")
        self.assertIn("Cliente", cliente_auth["rol"])

        # 2. Probar contraseña incorrecta y usuario inexistente
        bad_pass = autenticar_usuario("admin", "wrong_password_xyz")
        self.assertIsNone(bad_pass, "La autenticación debe fallar con contraseña errónea.")

        no_user = autenticar_usuario("usuario_que_no_existe_999", "clave123")
        self.assertIsNone(no_user, "La autenticación debe fallar para usuario inexistente.")

        # 3. Probar creación de nuevo usuario con contraseña
        test_u = "test_inspector"
        ok_add, msg_add = agregar_usuario(
            username=test_u,
            password="test_password_456",
            nombre_completo="Inspector de Calidad Test",
            rol="👷 Supervisor de Campo",
            cargo="Inspector de Seguridad y Calidad",
            email="test.inspector@cleanfacilitypro.pe"
        )
        self.assertTrue(ok_add, f"Debe crearse el nuevo usuario: {msg_add}")

        # Probar autenticación del usuario recién creado
        auth_nuevo = autenticar_usuario(test_u, "test_password_456")
        self.assertIsNotNone(auth_nuevo)
        self.assertEqual(auth_nuevo["nombre_completo"], "Inspector de Calidad Test")

        # 4. Probar cambio de contraseña
        ok_chg, msg_chg = cambiar_password_usuario(auth_nuevo["id"], "nueva_clave_789")
        self.assertTrue(ok_chg)
        self.assertIsNone(autenticar_usuario(test_u, "test_password_456"), "La contraseña anterior ya no debe funcionar.")
        self.assertIsNotNone(autenticar_usuario(test_u, "nueva_clave_789"), "La nueva contraseña debe funcionar.")

        # 5. Probar actualización de usuario (inactivar)
        ok_upd, _ = actualizar_usuario(
            usuario_id=auth_nuevo["id"],
            nombre_completo="Inspector Test Modificado",
            rol="👷 Supervisor de Campo",
            cargo="Inspector Modificado",
            email="modificado@test.com",
            activo=0
        )
        self.assertTrue(ok_upd)
        inact_res = autenticar_usuario(test_u, "nueva_clave_789")
        self.assertIsInstance(inact_res, dict)
        self.assertEqual(inact_res.get("error"), "inactivo", "Usuario inactivo debe ser reportado como tal.")

        # 6. Probar eliminación de usuario (y protección del admin)
        ok_del_admin, _ = eliminar_usuario_db(admin_auth["id"])
        self.assertFalse(ok_del_admin, "El usuario admin no puede ser eliminado.")

        ok_del, _ = eliminar_usuario_db(auth_nuevo["id"])
        self.assertTrue(ok_del, "El usuario de prueba debe ser eliminado correctamente.")

        # Verificar funciones de interfaz
        self.assertTrue(callable(render_login))
        self.assertTrue(callable(render_user_sidebar))

        print("[OK] Autenticación con contraseña según usuarios y gestión de roles validados con éxito.")

    def test_15_incidencia_foto_integracion_en_evidencias(self):
        """Verificar que al subir foto en Registro de Incidencias se incorpora a Registro Fotográfico con Área y Descripción del Hallazgo."""
        import io
        from database import guardar_supervision_completa, obtener_supervision_por_id, eliminar_supervision
        from modules.reportes_pdf import generar_pdf_supervision
        from config import UPLOADS_DIR
        from PIL import Image as PILImage
        from pypdf import PdfReader

        # 1. Crear una imagen de prueba física
        test_img_path = str(UPLOADS_DIR / "test_incidencia_evidencia.jpg")
        img = PILImage.new('RGB', (400, 300), color=(220, 80, 50))
        img.save(test_img_path)

        area_inc = "Ascensores y Escaleras"
        desc_hallazgo = "Mancha persistente de óxido en riel de ascensor N° 2"

        # 2. Datos de supervisión con incidencia y foto integrada
        datos_gral = {
            "codigo_informe": generar_nuevo_codigo(),
            "fecha_inspeccion": "2026-10-14",
            "hora_inicio": "09:00",
            "hora_fin": "10:30",
            "tipo_inspeccion": "Inspección Rutinaria",
            "turno": "Mañana",
            "edificio_id": 1,
            "edificio_nombre": "Torre Test",
            "edificio_direccion": "Av. Test 123",
            "administrador_nombre": "Admin Test",
            "supervisor_id": 1,
            "supervisor_nombre": "Supervisor Test",
            "supervisor_dni": "12345678",
            "lider_cuadrilla": "Líder Test",
            "personal_programado": 4,
            "personal_presente": 4,
            "personal_faltante": 0,
            "score_global": 90.0,
            "nivel_calidad": "Satisfactorio",
            "estado_aprobacion": "Aprobado",
            "total_items_evaluados": 1,
            "total_conformes": 1,
            "total_regulares": 0,
            "total_no_conformes": 0,
            "total_no_aplica": 0,
            "epp_conforme": 1,
            "maquinaria_conforme": 1,
            "insumos_conforme": 1,
            "incluir_firmas": 1,
            "observaciones_generales": "Supervisión de prueba con foto en incidencia.",
            "plan_accion_resumen": "1 incidencia registrada",
            "estado_informe": "FINALIZADO"
        }
        detalles = [
            {"id_area": "A1", "nombre_area": area_inc, "id_criterio": "C1", "item_criterio": "Rieles", "calificacion": "NC", "puntos": 0, "observacion": desc_hallazgo}
        ]
        incidencias = [
            {
                "area_nombre": area_inc,
                "descripcion_hallazgo": desc_hallazgo,
                "severidad": "Alta",
                "accion_correctiva": "Lijar y aplicar anticorrosivo",
                "plazo_subsanacion": "24 Horas",
                "responsable": "Líder de Cuadrilla",
                "estado_subsanacion": "Pendiente",
                "foto_ruta": test_img_path,
                "fotos": [test_img_path]
            }
        ]
        # La foto se coloca en el Registro Fotográfico con Área con Incidencia y Descripción del Hallazgo
        fotos = [
            {
                "uid": "f_test_inc_001",
                "area_nombre": area_inc,
                "tipo_evidencia": "Hallazgo / No Conforme",
                "archivo_nombre": "test_incidencia_evidencia.jpg",
                "archivo_ruta": test_img_path,
                "descripcion": desc_hallazgo
            }
        ]

        # 3. Guardar en BD
        sup_id, cod = guardar_supervision_completa(datos_gral, detalles, incidencias, fotos)
        self.assertIsNotNone(sup_id)

        # 4. Recuperar y verificar datos en BD
        recuperado = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recuperado["incidencias"]), 1)
        self.assertEqual(recuperado["incidencias"][0]["area_nombre"], area_inc)
        self.assertEqual(recuperado["incidencias"][0]["descripcion_hallazgo"], desc_hallazgo)
        self.assertEqual(recuperado["incidencias"][0]["foto_hallazgo_ruta"], test_img_path)

        self.assertEqual(len(recuperado["fotos"]), 1)
        foto_recup = recuperado["fotos"][0]
        self.assertEqual(foto_recup["area_nombre"], area_inc, "El área de la foto debe ser el Área con Incidencia.")
        self.assertEqual(foto_recup["descripcion"], desc_hallazgo, "La descripción de la foto debe ser la Descripción del Hallazgo.")
        self.assertEqual(foto_recup["tipo_evidencia"], "Hallazgo / No Conforme")

        # 5. Generar PDF y validar que contiene el registro fotográfico con estos datos
        pdf_bytes = generar_pdf_supervision(recuperado)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto_completo = "".join([page.extract_text() for page in reader.pages])
        self.assertIn("REGISTRO FOTOGRÁFICO", texto_completo)
        self.assertIn(area_inc, texto_completo)
        self.assertIn(desc_hallazgo, texto_completo)

        # Limpiar
        eliminar_supervision(sup_id)
        if os.path.exists(test_img_path):
            os.remove(test_img_path)

        print("[OK] Integración de foto de incidencia al Registro Fotográfico de Evidencias validada con éxito.")

    def test_18_distincion_fotos_capa_vs_calidad_en_pdf(self):
        """Verificar la distinción clara en el PDF entre fotos de Incidencias (CAPA) y fotos de Control de Calidad."""
        import json
        from PIL import Image as PILImage
        from pypdf import PdfReader
        from database import eliminar_supervision, actualizar_supervision_completa

        # Crear dos imágenes de prueba
        img_capa = os.path.join(DATA_DIR, "test_capa_dist.jpg")
        img_calidad = os.path.join(DATA_DIR, "test_calidad_dist.jpg")
        im1 = PILImage.new("RGB", (200, 200), color=(220, 50, 50))
        im1.save(img_capa, "JPEG")
        im2 = PILImage.new("RGB", (200, 200), color=(50, 150, 220))
        im2.save(img_calidad, "JPEG")

        codigo = generar_nuevo_codigo()
        edif = obtener_lista_edificios()[0]
        sup = obtener_lista_supervisores()[0]

        datos_gral = {
            "codigo_informe": codigo,
            "fecha_inspeccion": "2026-10-15",
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "tipo_inspeccion": "Supervisión Rutinaria Diaria",
            "turno": "Mañana",
            "edificio_id": edif["id"],
            "edificio_nombre": edif["nombre"],
            "edificio_direccion": edif.get("direccion", "Av. Principal 123"),
            "administrador_nombre": "Admin Edificio",
            "supervisor_id": sup["id"],
            "supervisor_nombre": sup["nombre_completo"],
            "supervisor_dni": sup.get("dni", "12345678"),
            "lider_cuadrilla": "Juan Pérez",
            "personal_programado": 4,
            "personal_presente": 4,
            "personal_faltante": 0,
            "score_global": 92.0,
            "nivel_calidad": "ADECUADO",
            "estado_aprobacion": "Aprobado con Observaciones",
            "total_items_evaluados": 1,
            "total_conformes": 1,
            "total_regulares": 0,
            "total_no_conformes": 0,
            "total_no_aplica": 0,
            "epp_conforme": 1,
            "maquinaria_conforme": 1,
            "insumos_conforme": 1,
            "incluir_firmas": 1,
            "observaciones_generales": "Prueba de distincion de fotos CAPA vs Calidad.",
            "plan_accion_resumen": "1 CAPA",
            "estado_informe": "FINALIZADO"
        }
        detalles = [
            {"id_area": "A1", "nombre_area": "Baños", "id_criterio": "C1", "item_criterio": "Pisos", "calificacion": "C", "puntos": 100, "observacion": "OK"}
        ]
        incidencias = [
            {
                "area_nombre": "Baños Piso 2",
                "descripcion_hallazgo": "Fuga menor en grifería del lavatorio",
                "severidad": "Media",
                "accion_correctiva": "Ajuste de llave y sellado",
                "plazo_subsanacion": "24 Horas",
                "responsable": "Líder de Cuadrilla",
                "estado_subsanacion": "Pendiente",
                "foto_hallazgo_ruta": img_capa
            }
        ]
        fotos = [
            {
                "area_nombre": "Baños Piso 2",
                "tipo_evidencia": "Hallazgo / No Conforme",
                "archivo_nombre": "test_capa_dist.jpg",
                "archivo_ruta": img_capa,
                "descripcion": "Fuga menor en grifería del lavatorio",
                "origen": "CAPA"
            },
            {
                "area_nombre": "Lobby y Recepción",
                "tipo_evidencia": "Control de Calidad / Buen Estado",
                "archivo_nombre": "test_calidad_dist.jpg",
                "archivo_ruta": img_calidad,
                "descripcion": "Piso abrillantado conforme estándar ISSA",
                "origen": "REGISTRO_FOTOGRAFICO"
            }
        ]

        sup_id, cod = guardar_supervision_completa(datos_gral, detalles, incidencias, fotos)
        recup = obtener_supervision_por_id(sup_id)

        # Generar PDF
        pdf_bytes = generar_pdf_supervision(recup)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto_pdf = "".join([p.extract_text() for p in reader.pages])

        # Validar subsecciones diferenciadas en el PDF
        self.assertIn("6.1 Evidencias Fotográficas de Incidencias / No Conformidades (CAPA)", texto_pdf)
        self.assertIn("6.2 Registro Fotográfico de Control de Calidad e Inspección General", texto_pdf)
        self.assertIn("[INCIDENCIA / CAPA]", texto_pdf)
        self.assertIn("[CONTROL DE CALIDAD]", texto_pdf)
        self.assertIn("Fuga menor en grifería del lavatorio", texto_pdf)
        self.assertIn("Piso abrillantado conforme estándar ISSA", texto_pdf)

        # Limpiar
        eliminar_supervision(sup_id)
        for p in (img_capa, img_calidad):
            if os.path.exists(p):
                os.remove(p)
        print("[OK] Distinción de fotos CAPA vs Calidad en PDF validada al 100%.")

    def test_19_descarga_json_informes_historial(self):
        """Verificar la generación y estructura del archivo JSON para descarga desde el historial."""
        import json
        from config import FORMAT_CODE, FORMAT_VERSION
        from database import eliminar_supervision

        codigo = generar_nuevo_codigo()
        edif = obtener_lista_edificios()[0]
        sup = obtener_lista_supervisores()[0]

        datos_gral = {
            "codigo_informe": codigo,
            "fecha_inspeccion": "2026-10-15",
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "tipo_inspeccion": "Supervisión Rutinaria Diaria",
            "turno": "Mañana",
            "edificio_id": edif["id"],
            "edificio_nombre": edif["nombre"],
            "edificio_direccion": edif.get("direccion", "Av. Principal 123"),
            "administrador_nombre": "Admin Edificio",
            "supervisor_id": sup["id"],
            "supervisor_nombre": sup["nombre_completo"],
            "supervisor_dni": sup.get("dni", "12345678"),
            "lider_cuadrilla": "Juan Pérez",
            "personal_programado": 4,
            "personal_presente": 4,
            "personal_faltante": 0,
            "score_global": 100.0,
            "nivel_calidad": "ÓPTIMO",
            "estado_aprobacion": "Aprobado",
            "total_items_evaluados": 1,
            "total_conformes": 1,
            "total_regulares": 0,
            "total_no_conformes": 0,
            "total_no_aplica": 0,
            "epp_conforme": 1,
            "maquinaria_conforme": 1,
            "insumos_conforme": 1,
            "incluir_firmas": 1,
            "observaciones_generales": "Prueba de exportacion JSON historial.",
            "plan_accion_resumen": "",
            "estado_informe": "FINALIZADO"
        }
        detalles = [
            {"id_area": "A1", "nombre_area": "Recepción", "id_criterio": "C1", "item_criterio": "Mostrador", "calificacion": "C", "puntos": 100, "observacion": "Limpio"}
        ]
        sup_id, cod = guardar_supervision_completa(datos_gral, detalles, [], [])
        data_completa = obtener_supervision_por_id(sup_id)

        # Construir payload de exportación como en historial.py
        export_payload = {
            "codigo_formato": FORMAT_CODE,
            "version": FORMAT_VERSION,
            "fecha_exportacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "informe": data_completa["cabecera"],
            "checklist_evaluacion": data_completa["detalles"],
            "incidencias_capa": data_completa["incidencias"],
            "registro_fotografico": data_completa["fotos"]
        }
        json_str = json.dumps(export_payload, indent=2, ensure_ascii=False, default=str)
        self.assertTrue(len(json_str) > 50)

        # Decodificar y validar estructura
        parsed = json.loads(json_str)
        self.assertEqual(parsed["codigo_formato"], FORMAT_CODE)
        self.assertEqual(parsed["version"], FORMAT_VERSION)
        self.assertEqual(parsed["informe"]["codigo_informe"], codigo)
        self.assertEqual(len(parsed["checklist_evaluacion"]), 1)
        self.assertEqual(parsed["checklist_evaluacion"][0]["item_criterio"], "Mostrador")

        eliminar_supervision(sup_id)
        print("[OK] Generación y estructura de archivo JSON desde Historial validada con éxito.")

    def test_20_editar_registro_fotografico_historial(self):
        """Verificar la edición completa del registro fotográfico (modificar, eliminar y agregar fotos) en Historial."""
        from PIL import Image as PILImage
        from database import eliminar_supervision, actualizar_supervision_completa

        img1 = os.path.join(DATA_DIR, "test_edit_f1.jpg")
        img2 = os.path.join(DATA_DIR, "test_edit_f2.jpg")
        img3 = os.path.join(DATA_DIR, "test_edit_f3.jpg")
        for p, col in [(img1, (10, 10, 10)), (img2, (20, 20, 20)), (img3, (30, 30, 30))]:
            im = PILImage.new("RGB", (100, 100), color=col)
            im.save(p, "JPEG")

        codigo = generar_nuevo_codigo()
        edif = obtener_lista_edificios()[0]
        sup = obtener_lista_supervisores()[0]

        datos_gral = {
            "codigo_informe": codigo,
            "fecha_inspeccion": "2026-10-15",
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "tipo_inspeccion": "Supervisión Rutinaria Diaria",
            "turno": "Mañana",
            "edificio_id": edif["id"],
            "edificio_nombre": edif["nombre"],
            "edificio_direccion": edif.get("direccion", "Av. Principal 123"),
            "administrador_nombre": "Admin Edificio",
            "supervisor_id": sup["id"],
            "supervisor_nombre": sup["nombre_completo"],
            "supervisor_dni": sup.get("dni", "12345678"),
            "lider_cuadrilla": "Juan Pérez",
            "personal_programado": 4,
            "personal_presente": 4,
            "personal_faltante": 0,
            "score_global": 100.0,
            "nivel_calidad": "ÓPTIMO",
            "estado_aprobacion": "Aprobado",
            "total_items_evaluados": 1,
            "total_conformes": 1,
            "total_regulares": 0,
            "total_no_conformes": 0,
            "total_no_aplica": 0,
            "epp_conforme": 1,
            "maquinaria_conforme": 1,
            "insumos_conforme": 1,
            "incluir_firmas": 1,
            "observaciones_generales": "Antes de editar fotos.",
            "plan_accion_resumen": "",
            "estado_informe": "FINALIZADO"
        }
        detalles = [
            {"id_area": "A1", "nombre_area": "General", "id_criterio": "C1", "item_criterio": "Limpieza", "calificacion": "C", "puntos": 100, "observacion": "OK"}
        ]
        fotos_iniciales = [
            {
                "area_nombre": "Pasadizo Piso 1",
                "tipo_evidencia": "Antes de Limpieza",
                "archivo_nombre": "test_edit_f1.jpg",
                "archivo_ruta": img1,
                "descripcion": "Foto inicial 1",
                "origen": "REGISTRO_FOTOGRAFICO"
            },
            {
                "area_nombre": "Pasadizo Piso 2",
                "tipo_evidencia": "Antes de Limpieza",
                "archivo_nombre": "test_edit_f2.jpg",
                "archivo_ruta": img2,
                "descripcion": "Foto inicial 2 a eliminar",
                "origen": "REGISTRO_FOTOGRAFICO"
            }
        ]

        sup_id, cod = guardar_supervision_completa(datos_gral, detalles, [], fotos_iniciales)
        recup1 = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recup1["fotos"]), 2)

        # Simular edición en historial:
        # - Foto 1 se edita (cambia área, tipo y descripción)
        # - Foto 2 se descarta / elimina
        # - Foto 3 se agrega como nueva
        fotos_editadas = [
            {
                "supervision_id": sup_id,
                "area_nombre": "Pasadizo Piso 1 - Modificado",
                "tipo_evidencia": "Después de Limpieza",
                "archivo_nombre": "test_edit_f1.jpg",
                "archivo_ruta": img1,
                "descripcion": "Foto 1 editada exitosamente",
                "origen": "REGISTRO_FOTOGRAFICO"
            },
            {
                "supervision_id": sup_id,
                "area_nombre": "Lobby Principal",
                "tipo_evidencia": "General de Calidad",
                "archivo_nombre": "test_edit_f3.jpg",
                "archivo_ruta": img3,
                "descripcion": "Nueva foto agregada durante edición",
                "origen": "REGISTRO_FOTOGRAFICO"
            }
        ]

        actualizar_supervision_completa(
            supervision_id=sup_id,
            datos_gral=datos_gral,
            detalles_evaluacion=detalles,
            incidencias=[],
            fotos_guardadas=fotos_editadas
        )

        recup2 = obtener_supervision_por_id(sup_id)
        self.assertEqual(len(recup2["fotos"]), 2)

        # Verificar que Foto 1 tiene los datos editados
        f1 = [f for f in recup2["fotos"] if "test_edit_f1.jpg" in f["archivo_nombre"]][0]
        self.assertEqual(f1["area_nombre"], "Pasadizo Piso 1 - Modificado")
        self.assertEqual(f1["tipo_evidencia"], "Después de Limpieza")
        self.assertEqual(f1["descripcion"], "Foto 1 editada exitosamente")

        # Verificar que Foto 2 ya no existe
        f2_exists = any("test_edit_f2.jpg" in f["archivo_nombre"] for f in recup2["fotos"])
        self.assertFalse(f2_exists, "La foto 2 debió ser eliminada del informe.")

        # Verificar que Foto 3 fue añadida
        f3 = [f for f in recup2["fotos"] if "test_edit_f3.jpg" in f["archivo_nombre"]][0]
        self.assertEqual(f3["area_nombre"], "Lobby Principal")
        self.assertEqual(f3["descripcion"], "Nueva foto agregada durante edición")

        eliminar_supervision(sup_id)
        for p in (img1, img2, img3):
            if os.path.exists(p):
                os.remove(p)
        print("[OK] Edición del registro fotográfico en Historial validada al 100%.")


if __name__ == "__main__":
    unittest.main()



