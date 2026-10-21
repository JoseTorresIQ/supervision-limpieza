"""
Módulo de Formulario de Nueva Supervisión: Proceso guiado paso a paso con cálculo en tiempo real,
evaluación por áreas, control de dotación/EPP, incidencias, fotos y firma digital.
"""
import os
import io
import json
import base64
import uuid
import hashlib
from datetime import datetime, date, time
from PIL import Image, ImageOps
import streamlit as st
import pandas as pd

from config import (
    PUNTAJES, ITEMS_EPP, clasificar_calidad, UPLOADS_DIR
)
from database import (
    obtener_lista_edificios, obtener_lista_supervisores,
    obtener_tipos_inspeccion, obtener_turnos_trabajo, obtener_checklist_completo,
    guardar_supervision_completa, generar_nuevo_codigo,
    obtener_ultima_supervision_edificio, obtener_borradores_supervisiones,
    obtener_supervision_por_id, eliminar_supervision,
    actualizar_supervision_completa, agregar_edificio, agregar_supervisor
)
from modules.reportes_pdf import generar_pdf_supervision


def guardar_y_optimizar_imagen(imagen_bytes, ruta_destino: str, max_dimension: int = 1400, calidad: int = 85):
    """
    Redimensiona y comprime una imagen fotográfica respetando su orientación física original (EXIF transpose).
    Si la foto fue tomada verticalmente (ej: celular en modo retrato con orientación EXIF 6 u 8),
    se transpone físicamente y se guarda en vertical.
    Si la foto es horizontal, se preserva horizontal.
    """
    try:
        # Soporte para Data URLs (base64) procedentes de PWA o cámaras
        if isinstance(imagen_bytes, str):
            if "," in imagen_bytes:
                imagen_bytes = base64.b64decode(imagen_bytes.split(",", 1)[1])
            else:
                imagen_bytes = base64.b64decode(imagen_bytes)
        elif hasattr(imagen_bytes, "getvalue"):
            imagen_bytes = imagen_bytes.getvalue()
        elif hasattr(imagen_bytes, "read"):
            imagen_bytes = imagen_bytes.read()

        img = Image.open(io.BytesIO(imagen_bytes))

        # 1. Aplicar orientación según metadatos EXIF de la cámara móvil
        img = ImageOps.exif_transpose(img)

        # 2. Convertir a RGB si es necesario (manejar transparencias o paletas)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 3. Redimensionar proporcionalmente respetando la orientación (vertical u horizontal)
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            nuevo_w = max(1, int(w * scale))
            nuevo_h = max(1, int(h * scale))
            img = img.resize((nuevo_w, nuevo_h), Image.Resampling.LANCZOS)

        img.save(ruta_destino, "JPEG", optimize=True, quality=calidad)
    except Exception:
        with open(ruta_destino, "wb") as f_out:
            if isinstance(imagen_bytes, str):
                if "," in imagen_bytes:
                    f_out.write(base64.b64decode(imagen_bytes.split(",", 1)[1]))
                else:
                    f_out.write(base64.b64decode(imagen_bytes))
            elif hasattr(imagen_bytes, "getvalue"):
                f_out.write(imagen_bytes.getvalue())
            elif isinstance(imagen_bytes, bytes):
                f_out.write(imagen_bytes)


def rotar_imagen_guardada(ruta_imagen: str, grados: int = 90) -> bool:
    """Rota una imagen existente en disco 90 grados en sentido horario."""
    if not os.path.exists(ruta_imagen):
        return False
    try:
        with Image.open(ruta_imagen) as img:
            img = ImageOps.exif_transpose(img)
            # grados 90 en sentido horario = ROTATE_270 en PIL
            if grados == 90:
                img_rot = img.transpose(Image.Transpose.ROTATE_270)
            elif grados == 180:
                img_rot = img.transpose(Image.Transpose.ROTATE_180)
            elif grados == 270:
                img_rot = img.transpose(Image.Transpose.ROTATE_90)
            else:
                img_rot = img.rotate(-grados, expand=True)
            if img_rot.mode in ("RGBA", "P"):
                img_rot = img_rot.convert("RGB")
            img_rot.save(ruta_imagen, "JPEG", optimize=True, quality=85)
        return True
    except Exception as e:
        print(f"Error rotando imagen {ruta_imagen}: {e}")
        return False



def normalizar_texto_criterio(texto: str) -> str:
    """Normaliza texto para comparación flexible de nombres de criterios (sin acentos ni puntuación)."""
    if not texto:
        return ""
    import unicodedata
    import re
    t = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8")
    return re.sub(r"[^a-zA-Z0-9]", "", t).lower()


def procesar_importacion_json(pwa_data: dict, checklist_areas: list, edificios: list, supervisores: list, tipos_inspeccion: list, turnos_trabajo: list) -> dict:
    """
    Procesa un archivo JSON (exportado desde PWA offline o descargado desde Historial)
    e inyecta todos sus datos de cabecera, criterios, incidencias y fotos
    en st.session_state para poblar de inmediato el formulario de supervisión.
    """
    cab = pwa_data.get("informe") if isinstance(pwa_data.get("informe"), dict) else pwa_data

    # A. Edificio
    edif_nom = (cab.get("edificio_nombre") or pwa_data.get("edificio_nombre") or "").strip()
    if edif_nom:
        nombres_edif = [e["nombre"] for e in edificios]
        if edif_nom in nombres_edif:
            st.session_state["sel_edificio"] = edif_nom
        else:
            match = next((e_n for e_n in nombres_edif if edif_nom.lower() in e_n.lower() or e_n.lower() in edif_nom.lower()), None)
            if match:
                st.session_state["sel_edificio"] = match
            else:
                try:
                    dir_edif = cab.get("edificio_direccion") or pwa_data.get("edificio_direccion") or "Lima, Perú"
                    admin_edif = cab.get("administrador_contacto") or pwa_data.get("administrador_contacto") or "Administración"
                    agregar_edificio(edif_nom, dir_edif, "Lima", admin_edif, "", 10, 2, 6, "Importado desde PWA/JSON")
                    edificios.clear()
                    edificios.extend(obtener_lista_edificios(solo_activos=True))
                    st.session_state["sel_edificio"] = edif_nom
                except Exception:
                    if nombres_edif:
                        st.session_state["sel_edificio"] = nombres_edif[0]

    # B. Supervisor
    sup_nom = (cab.get("supervisor_nombre") or pwa_data.get("supervisor_nombre") or "").strip()
    if sup_nom:
        nombres_sup = [s["nombre_completo"] for s in supervisores]
        if sup_nom in nombres_sup:
            st.session_state["sel_supervisor"] = sup_nom
        else:
            match_s = next((s_n for s_n in nombres_sup if sup_nom.lower() in s_n.lower() or s_n.lower() in sup_nom.lower()), None)
            if match_s:
                st.session_state["sel_supervisor"] = match_s
            else:
                try:
                    dni_s = cab.get("supervisor_dni") or pwa_data.get("supervisor_dni") or ""
                    agregar_supervisor(sup_nom, dni_s, "Supervisor de Operaciones", "")
                    supervisores.clear()
                    supervisores.extend(obtener_lista_supervisores(solo_activos=True))
                    st.session_state["sel_supervisor"] = sup_nom
                except Exception:
                    if nombres_sup:
                        st.session_state["sel_supervisor"] = nombres_sup[0]

    # C. Tipo de Inspección
    tipo_nom = (cab.get("tipo_inspeccion") or pwa_data.get("tipo_inspeccion") or "").strip()
    if tipo_nom:
        if tipo_nom in tipos_inspeccion:
            st.session_state["sel_tipo_insp"] = tipo_nom
        else:
            match_t = next((t for t in tipos_inspeccion if tipo_nom.lower() in t.lower() or t.lower() in tipo_nom.lower()), None)
            if match_t:
                st.session_state["sel_tipo_insp"] = match_t

    # D. Turno de Trabajo
    turno_nom = (cab.get("turno") or pwa_data.get("turno") or "").strip()
    if turno_nom:
        if turno_nom in turnos_trabajo:
            st.session_state["sel_turno"] = turno_nom
        else:
            match_tr = next((tr for tr in turnos_trabajo if turno_nom.lower() in tr.lower() or tr.lower() in turno_nom.lower() or turno_nom.split()[0].lower() in tr.lower()), None)
            if match_tr:
                st.session_state["sel_turno"] = match_tr

    # E. Fecha de Inspección
    f_raw = cab.get("fecha_inspeccion") or pwa_data.get("fecha_inspeccion")
    if f_raw:
        if isinstance(f_raw, date):
            st.session_state["sel_fecha"] = f_raw
        elif isinstance(f_raw, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                try:
                    st.session_state["sel_fecha"] = datetime.strptime(f_raw.strip()[:10], fmt).date()
                    break
                except Exception:
                    pass

    # F. Horas
    h_ini = cab.get("hora_inicio") or pwa_data.get("hora_inicio")
    if h_ini:
        if isinstance(h_ini, time):
            st.session_state["sel_hini"] = h_ini
        elif isinstance(h_ini, str):
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    st.session_state["sel_hini"] = datetime.strptime(h_ini.strip(), fmt).time()
                    break
                except Exception:
                    pass

    h_fin = cab.get("hora_fin") or pwa_data.get("hora_fin")
    if h_fin:
        if isinstance(h_fin, time):
            st.session_state["sel_hfin"] = h_fin
        elif isinstance(h_fin, str):
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    st.session_state["sel_hfin"] = datetime.strptime(h_fin.strip(), fmt).time()
                    break
                except Exception:
                    pass

    # G. Líder de Cuadrilla
    lider = cab.get("lider_cuadrilla") or pwa_data.get("lider_cuadrilla")
    if lider:
        st.session_state["sel_lider"] = str(lider).strip()

    # H. Personal Programado / Presente
    p_prog = cab.get("personal_programado") if "personal_programado" in cab else pwa_data.get("personal_programado")
    if p_prog is not None:
        try:
            st.session_state["p_prog"] = max(1, int(p_prog))
        except Exception:
            pass

    p_pres = cab.get("personal_presente") if "personal_presente" in cab else pwa_data.get("personal_presente")
    if p_pres is not None:
        try:
            st.session_state["p_pres"] = max(0, int(p_pres))
        except Exception:
            pass

    # I. Observaciones Generales
    obs_gral = cab.get("observaciones_generales") or pwa_data.get("observaciones_generales")
    if obs_gral is not None:
        st.session_state["txt_obs_gral"] = str(obs_gral).strip()

    # J. SST / Equipos
    if "observaciones_sst" in cab or "observaciones_sst" in pwa_data:
        st.session_state["txt_sst"] = str(cab.get("observaciones_sst") or pwa_data.get("observaciones_sst", "")).strip()

    # 2. Checklist / Criterios Técnicos
    crit_map = {crit["id"]: crit for area in checklist_areas for crit in area["criterios"]}
    crit_norm_map = {normalizar_texto_criterio(crit["item"]): crit["id"] for area in checklist_areas for crit in area["criterios"]}

    # Mapeo retrocompatible para IDs de la versión inicial de PWA ("c1" a "c15")
    legacy_map = {
        "c1": "lobby_pisos",
        "c2": "lobby_vidrios",
        "c3": "lobby_counter",
        "c4": "asc_botoneras",
        "c5": "asc_acero",
        "c6": "asc_rieles",
        "c7": "ssh_aparatos",
        "c8": "ssh_lavamanos",
        "c9": "ssh_insumos",
        "c10": "pas_pisos",
        "c11": "pas_extintores",
        "c12": "esc_pasos",
        "c13": "esc_despeje",
        "c14": "res_contenedores",
        "c15": "res_olores"
    }

    items_raw = []
    if "checklist_evaluacion" in pwa_data and isinstance(pwa_data["checklist_evaluacion"], list):
        items_raw.extend(pwa_data["checklist_evaluacion"])
    elif "detalles" in pwa_data and isinstance(pwa_data["detalles"], list):
        items_raw.extend(pwa_data["detalles"])
    elif "detalles" in cab and isinstance(cab["detalles"], list):
        items_raw.extend(cab["detalles"])

    if "evaluacion" in pwa_data:
        ev = pwa_data["evaluacion"]
        if isinstance(ev, dict):
            for k, v in ev.items():
                if isinstance(v, dict):
                    v_copy = dict(v)
                    v_copy["id_criterio"] = k
                    items_raw.append(v_copy)
                elif isinstance(v, str):
                    items_raw.append({"id_criterio": k, "calificacion": v})
        elif isinstance(ev, list):
            items_raw.extend(ev)

    criterios_cargados = 0
    criterios_ya_procesados = set()

    for item in items_raw:
        if not isinstance(item, dict):
            continue

        raw_id = str(item.get("id_criterio") or item.get("id") or "").strip()
        raw_item_txt = str(item.get("item_criterio") or item.get("item") or item.get("desc") or "").strip()
        raw_calif = str(item.get("calificacion") or item.get("calif") or "C").strip().upper()
        if raw_calif not in ("C", "R", "NC", "NA"):
            raw_calif = "C"
        raw_obs = str(item.get("observacion") or item.get("obs") or "").strip()

        target_id = None
        if raw_id in crit_map:
            target_id = raw_id
        elif raw_id in legacy_map and legacy_map[raw_id] in crit_map:
            target_id = legacy_map[raw_id]
        elif raw_item_txt:
            norm_item = normalizar_texto_criterio(raw_item_txt)
            if norm_item in crit_norm_map:
                target_id = crit_norm_map[norm_item]
            else:
                for k_norm, cid_match in crit_norm_map.items():
                    if norm_item and (norm_item in k_norm or k_norm in norm_item):
                        target_id = cid_match
                        break

        if target_id and target_id in st.session_state.evaluacion_temp:
            if target_id not in criterios_ya_procesados:
                st.session_state.evaluacion_temp[target_id]["calificacion"] = raw_calif
                st.session_state.evaluacion_temp[target_id]["observacion"] = raw_obs
                st.session_state[f"rad_{target_id}"] = raw_calif
                st.session_state[f"obs_{target_id}"] = raw_obs
                criterios_ya_procesados.add(target_id)
                criterios_cargados += 1

    # 3. Incidencias CAPA
    inc_raw = pwa_data.get("incidencias") or pwa_data.get("incidencias_capa") or cab.get("incidencias") or []
    if isinstance(inc_raw, list) and inc_raw:
        st.session_state.incidencias_temp = inc_raw

    # 4. Registro Fotográfico
    fotos_raw = pwa_data.get("fotos") or pwa_data.get("registro_fotografico") or cab.get("fotos") or []
    fotos_importadas = 0
    if isinstance(fotos_raw, list) and fotos_raw:
        st.session_state.fotos_temp = []
        st.session_state.fotos_cargadas_ids = set()
        st.session_state["uploader_key_version"] = st.session_state.get("uploader_key_version", 0) + 1
        for k in [k for k in list(st.session_state.keys()) if k.startswith("f_area_") or k.startswith("f_tipo_") or k.startswith("f_desc_") or k.startswith("sub_")]:
            st.session_state.pop(k, None)

        for p_foto in fotos_raw:
            if not isinstance(p_foto, dict):
                continue
            foto_data = p_foto.get("data") or p_foto.get("archivo_data") or p_foto.get("foto_b64")
            ruta_existente = p_foto.get("archivo_ruta") or ""

            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            rand_suffix = uuid.uuid4().hex[:6]
            nom_arch = p_foto.get("archivo_nombre") or f"evidencia_pwa_{ts_str}_{rand_suffix}.jpg"

            if foto_data:
                ruta_arch = str(UPLOADS_DIR / nom_arch)
                guardar_y_optimizar_imagen(foto_data, ruta_arch)
            elif ruta_existente and os.path.exists(ruta_existente):
                ruta_arch = os.path.normpath(ruta_existente)
            else:
                continue

            uid = f"f_{ts_str}_{rand_suffix}"
            area_nom = p_foto.get("area_nombre") or p_foto.get("area") or "General"
            tipo_ev = p_foto.get("tipo_evidencia") or p_foto.get("tipo") or "Hallazgo / No Conforme"
            desc_ev = p_foto.get("descripcion") or ""

            # Importar fotos adicionales vinculadas a esta evidencia si vienen en el JSON
            sub_fotos_importadas = []
            for s_idx, sub_p in enumerate(p_foto.get("fotos_adicionales", [])):
                if not isinstance(sub_p, dict):
                    continue
                sub_data = sub_p.get("data") or sub_p.get("archivo_data") or sub_p.get("foto_b64")
                sub_exist = sub_p.get("archivo_ruta") or ""
                sub_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                sub_rand = uuid.uuid4().hex[:6]
                sub_nom = sub_p.get("archivo_nombre") or f"sub_evidencia_{sub_ts}_{sub_rand}.jpg"
                if sub_data:
                    sub_ruta = str(UPLOADS_DIR / sub_nom)
                    guardar_y_optimizar_imagen(sub_data, sub_ruta)
                elif sub_exist and os.path.exists(sub_exist):
                    sub_ruta = os.path.normpath(sub_exist)
                else:
                    continue
                sub_uid = f"sub_{sub_ts}_{sub_rand}"
                sub_tipo = sub_p.get("tipo_evidencia") or "Después de Limpieza"
                sub_desc = sub_p.get("descripcion") or ""
                sub_fotos_importadas.append({
                    "uid": sub_uid,
                    "foto_padre_uid": uid,
                    "area_nombre": area_nom,
                    "tipo_evidencia": sub_tipo,
                    "archivo_nombre": sub_nom,
                    "archivo_ruta": sub_ruta,
                    "descripcion": sub_desc,
                    "origen": sub_p.get("origen", "FOTO_ADICIONAL")
                })
                st.session_state[f"sub_tipo_{sub_uid}"] = sub_tipo
                st.session_state[f"sub_desc_{sub_uid}"] = sub_desc
                st.session_state.fotos_cargadas_ids.add(sub_ruta)
                st.session_state.fotos_cargadas_ids.add(sub_nom)
                fotos_importadas += 1

            st.session_state.fotos_temp.append({
                "uid": uid,
                "area_nombre": area_nom,
                "tipo_evidencia": tipo_ev,
                "archivo_nombre": nom_arch,
                "archivo_ruta": ruta_arch,
                "descripcion": desc_ev,
                "origen": p_foto.get("origen", "PWA_OFFLINE"),
                "fotos_adicionales": sub_fotos_importadas
            })
            st.session_state[f"f_area_{uid}"] = area_nom
            st.session_state[f"f_tipo_{uid}"] = tipo_ev
            st.session_state[f"f_desc_{uid}"] = desc_ev
            st.session_state.fotos_cargadas_ids.add(ruta_arch)
            st.session_state.fotos_cargadas_ids.add(nom_arch)
            fotos_importadas += 1

    return {
        "ok": True,
        "edificio": st.session_state.get("sel_edificio", ""),
        "supervisor": st.session_state.get("sel_supervisor", ""),
        "fecha": str(st.session_state.get("sel_fecha", "")),
        "criterios_cargados": criterios_cargados,
        "incidencias_cargadas": len(st.session_state.get("incidencias_temp", [])),
        "fotos_cargadas": fotos_importadas
    }


def render_formulario_nueva_supervision():
    """Renderiza el formulario integral de supervisión de limpieza."""
    st.markdown("""
        <div class="header-hero">
            <h1>📋 Nueva Ficha de Supervisión de Limpieza</h1>
            <p>Auditoría técnica de instalaciones, control de dotación, checklist de áreas y emisión de informe oficial.</p>
            <div class="header-badges">
                <span class="badge-tag">🏢 Facility Management</span>
                <span class="badge-tag">🧼 ISSA Cleaning Standard</span>
                <span class="badge-tag">🦺 SST Ley 29783</span>
                <span class="badge-tag">📊 Scoring Ponderado</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Cargar maestros y opciones desplegables desde la Base de Datos
    edificios = obtener_lista_edificios(solo_activos=True)
    supervisores = obtener_lista_supervisores(solo_activos=True)
    tipos_inspeccion = obtener_tipos_inspeccion(solo_activos=True)
    turnos_trabajo = obtener_turnos_trabajo(solo_activos=True)
    checklist_areas = obtener_checklist_completo(solo_activos=True)

    if not edificios:
        st.warning("⚠️ No hay edificios registrados. Registra un edificio primero en la pestaña '⚙️ Configuración & Maestros'.")
        return

    # Inicializar estado en sesión para almacenar la evaluación temporal
    if "evaluacion_temp" not in st.session_state or not st.session_state.evaluacion_temp:
        st.session_state.evaluacion_temp = {}
        for area in checklist_areas:
            for crit in area["criterios"]:
                st.session_state.evaluacion_temp[crit["id"]] = {
                    "id_area": area["id_area"],
                    "nombre_area": area["nombre"],
                    "id_criterio": crit["id"],
                    "item_criterio": crit["item"],
                    "calificacion": "C",
                    "observacion": ""
                }

    # Asegurar que nuevos criterios agregados en el configurador aparezcan en session_state
    for area in checklist_areas:
        for crit in area["criterios"]:
            if crit["id"] not in st.session_state.evaluacion_temp:
                st.session_state.evaluacion_temp[crit["id"]] = {
                    "id_area": area["id_area"],
                    "nombre_area": area["nombre"],
                    "id_criterio": crit["id"],
                    "item_criterio": crit["item"],
                    "calificacion": "C",
                    "observacion": ""
                }

    if "incidencias_temp" not in st.session_state:
        st.session_state.incidencias_temp = []

    if "fotos_temp" not in st.session_state:
        st.session_state.fotos_temp = []

    if "fotos_cargadas_ids" not in st.session_state:
        st.session_state.fotos_cargadas_ids = set()

    if "inc_uploader_ver" not in st.session_state:
        st.session_state.inc_uploader_ver = 0

    if "uploader_key_version" not in st.session_state:
        st.session_state.uploader_key_version = 0

    # Inicializar llaves de cabecera en session_state si no existen
    if "sel_edificio" not in st.session_state and edificios:
        st.session_state["sel_edificio"] = edificios[0]["nombre"]
    if "sel_tipo_insp" not in st.session_state and tipos_inspeccion:
        st.session_state["sel_tipo_insp"] = tipos_inspeccion[0]
    if "sel_supervisor" not in st.session_state and supervisores:
        st.session_state["sel_supervisor"] = supervisores[0]["nombre_completo"]
    if "sel_turno" not in st.session_state and turnos_trabajo:
        st.session_state["sel_turno"] = turnos_trabajo[0]
    if "sel_fecha" not in st.session_state:
        st.session_state["sel_fecha"] = date.today()
    if "sel_hini" not in st.session_state:
        st.session_state["sel_hini"] = time(8, 0)
    if "sel_hfin" not in st.session_state:
        st.session_state["sel_hfin"] = time(9, 30)
    if "sel_lider" not in st.session_state:
        st.session_state["sel_lider"] = "Técnico Líder en Turno"
    if "p_prog" not in st.session_state:
        st.session_state["p_prog"] = 4
    if "p_pres" not in st.session_state:
        st.session_state["p_pres"] = 4

    # 1. GESTIÓN DE BORRADORES PENDIENTES
    borradores = obtener_borradores_supervisiones()
    if borradores:
        st.warning(f"⚠️ **Atención:** Se encontraron **{len(borradores)} borrador(es)** de supervisión guardados previamente. Su avance está 100% seguro en la base de datos.")
        with st.expander(f"📂 Ver y Retomar Borradores Pendientes ({len(borradores)} disponible(s))", expanded=True):
            for b in borradores:
                cb1, cb2, cb3 = st.columns([3.2, 1.3, 0.8])
                with cb1:
                    st.markdown(f"**{b['codigo_informe']}** — 🏢 **{b['edificio_nombre']}**")
                    st.caption(f"📅 Fecha: `{b['fecha_inspeccion']}` | 👷 Supervisor: {b['supervisor_nombre']} | ⭐ Score Parcial: `{b['score_global']:.1f}%`")
                with cb2:
                    if st.button("📂 Retomar Borrador", key=f"btn_load_dr_{b['id']}", type="primary", use_container_width=True):
                        datos_b = obtener_supervision_por_id(b["id"])
                        if datos_b:
                            cab = datos_b["cabecera"]

                            # 1. Actualizar controles principales en session_state
                            st.session_state["sel_edificio"] = cab["edificio_nombre"]
                            st.session_state["sel_tipo_insp"] = cab["tipo_inspeccion"]
                            st.session_state["sel_supervisor"] = cab["supervisor_nombre"]
                            st.session_state["sel_turno"] = cab["turno"]
                            try:
                                st.session_state["sel_fecha"] = datetime.strptime(cab["fecha_inspeccion"], "%Y-%m-%d").date()
                            except Exception:
                                pass
                            try:
                                st.session_state["sel_hini"] = datetime.strptime(cab.get("hora_inicio", "08:00"), "%H:%M").time()
                            except Exception:
                                pass
                            try:
                                st.session_state["sel_hfin"] = datetime.strptime(cab.get("hora_fin", "09:30"), "%H:%M").time()
                            except Exception:
                                pass
                            st.session_state["sel_lider"] = cab.get("lider_cuadrilla", "Técnico Líder en Turno")
                            st.session_state["p_prog"] = int(cab.get("personal_programado", 4))
                            st.session_state["p_pres"] = int(cab.get("personal_presente", 4))
                            st.session_state["txt_obs_gral"] = cab.get("observaciones_generales", "")

                            # 2. Cargar detalles del checklist y fijar las llaves de los widgets
                            st.session_state.evaluacion_temp = {}
                            for d in datos_b.get("detalles", []):
                                cid = d["id_criterio"]
                                cal_val = d["calificacion"]
                                obs_val = d.get("observacion", "")
                                st.session_state.evaluacion_temp[cid] = {
                                    "id_area": d["id_area"],
                                    "nombre_area": d["nombre_area"],
                                    "id_criterio": cid,
                                    "item_criterio": d["item_criterio"],
                                    "calificacion": cal_val,
                                    "observacion": obs_val
                                }
                                st.session_state[f"rad_{cid}"] = cal_val
                                st.session_state[f"obs_{cid}"] = obs_val

                            # 3. Cargar incidencias, fotos y estado activo
                            st.session_state.incidencias_temp = datos_b.get("incidencias", [])
                            st.session_state.fotos_temp = []
                            st.session_state.fotos_cargadas_ids = set()
                            st.session_state["uploader_key_version"] = st.session_state.get("uploader_key_version", 0) + 1

                            # Limpiar llaves residuales anteriores de fotos
                            for k in [k for k in list(st.session_state.keys()) if k.startswith("f_area_") or k.startswith("f_tipo_") or k.startswith("f_desc_") or k.startswith("sub_")]:
                                st.session_state.pop(k, None)

                            rutas_vistas = set()
                            for idx_f, f in enumerate(datos_b.get("fotos", [])):
                                ruta_f = f.get("archivo_ruta", "")
                                if ruta_f:
                                    ruta_norm = os.path.normpath(ruta_f)
                                    if os.path.exists(ruta_norm) and ruta_norm not in rutas_vistas:
                                        rutas_vistas.add(ruta_norm)
                                        uid = f.get("uid") or f"f_{idx_f}_{uuid.uuid4().hex[:6]}"
                                        nom_arch = f.get("archivo_nombre") or os.path.basename(ruta_norm)
                                        area_val = f.get("area_nombre", "General")
                                        tipo_val = f.get("tipo_evidencia", "Hallazgo / No Conforme")
                                        desc_val = f.get("descripcion", "")

                                        # Restaurar fotos adicionales vinculadas a este borrador
                                        sub_fotos_recup = []
                                        for s_idx, sub_item in enumerate(f.get("fotos_adicionales", [])):
                                            s_ruta = sub_item.get("archivo_ruta", "")
                                            if s_ruta:
                                                s_norm = os.path.normpath(s_ruta)
                                                if os.path.exists(s_norm) and s_norm not in rutas_vistas:
                                                    rutas_vistas.add(s_norm)
                                                    s_uid = sub_item.get("uid") or f"sub_{uid}_{s_idx}_{uuid.uuid4().hex[:6]}"
                                                    s_nom = sub_item.get("archivo_nombre") or os.path.basename(s_norm)
                                                    s_tipo = sub_item.get("tipo_evidencia", "Después de Limpieza")
                                                    s_desc = sub_item.get("descripcion", "")
                                                    sub_fotos_recup.append({
                                                        "uid": s_uid,
                                                        "foto_padre_uid": uid,
                                                        "area_nombre": area_val,
                                                        "tipo_evidencia": s_tipo,
                                                        "archivo_nombre": s_nom,
                                                        "archivo_ruta": s_norm,
                                                        "descripcion": s_desc,
                                                        "origen": sub_item.get("origen", "FOTO_ADICIONAL")
                                                    })
                                                    st.session_state[f"sub_tipo_{s_uid}"] = s_tipo
                                                    st.session_state[f"sub_desc_{s_uid}"] = s_desc
                                                    st.session_state.fotos_cargadas_ids.add(s_norm)
                                                    st.session_state.fotos_cargadas_ids.add(s_nom)

                                        st.session_state.fotos_temp.append({
                                            "uid": uid,
                                            "area_nombre": area_val,
                                            "tipo_evidencia": tipo_val,
                                            "archivo_nombre": nom_arch,
                                            "archivo_ruta": ruta_norm,
                                            "descripcion": desc_val,
                                            "origen": f.get("origen", "REGISTRO_FOTOGRAFICO"),
                                            "fotos_adicionales": sub_fotos_recup
                                        })
                                        st.session_state[f"f_area_{uid}"] = area_val
                                        st.session_state[f"f_tipo_{uid}"] = tipo_val
                                        st.session_state[f"f_desc_{uid}"] = desc_val
                                        st.session_state.fotos_cargadas_ids.add(ruta_norm)
                                        st.session_state.fotos_cargadas_ids.add(nom_arch)

                            st.session_state["borrador_id_activo"] = b["id"]
                            st.session_state["borrador_codigo_activo"] = b["codigo_informe"]
                            st.rerun()
                with cb3:
                    if st.button("🗑️", key=f"btn_del_dr_{b['id']}", help="Eliminar este borrador", use_container_width=True):
                        eliminar_supervision(b["id"])
                        if st.session_state.get("borrador_id_activo") == b["id"]:
                            st.session_state.pop("borrador_id_activo", None)
                            st.session_state.pop("borrador_codigo_activo", None)
                        st.rerun()

    # Barra informativa si hay un borrador activo cargado
    if st.session_state.get("borrador_id_activo"):
        b_act_id = st.session_state["borrador_id_activo"]
        b_act_cod = st.session_state.get("borrador_codigo_activo", f"ID {b_act_id}")
        c_bact1, c_bact2 = st.columns([4, 1.4])
        with c_bact1:
            st.info(f"📝 **Editando Borrador Activo:** `{b_act_cod}` — **{st.session_state.get('sel_edificio', '')}** (Fecha: `{st.session_state.get('sel_fecha', '')}`). Al guardar se actualizará este mismo avance.")
        with c_bact2:
            if st.button("✖️ Cancelar Borrador", key="btn_cancel_draft_active", use_container_width=True, help="Descartar edición del borrador y volver al formulario vacío"):
                st.session_state.pop("borrador_id_activo", None)
                st.session_state.pop("borrador_codigo_activo", None)
                st.session_state.evaluacion_temp = {}
                st.session_state.incidencias_temp = []
                st.session_state.fotos_temp = []
                st.session_state.pop("fotos_cargadas_ids", None)
                st.session_state["uploader_key_version"] = st.session_state.get("uploader_key_version", 0) + 1
                keys_to_del = [k for k in list(st.session_state.keys()) if k.startswith("rad_") or k.startswith("obs_") or k.startswith("sel_") or k.startswith("p_") or k.startswith("f_")]
                for k in keys_to_del:
                    st.session_state.pop(k, None)
                st.rerun()

    # 2. IMPORTACIÓN DESDE PWA OFFLINE O HISTORIAL (JSON)
    with st.expander("📲 Importar Supervisión desde Archivo JSON (PWA Móvil / Historial)", expanded=False):
        st.markdown("""
            Cargue aquí el archivo **`.json`** exportado desde la aplicación móvil PWA offline o descargado desde el Historial.
            Se poblarán automáticamente la **sede**, **fecha**, **turno**, **dotación**, **checklist con calificaciones y observaciones**, **incidencias CAPA** y **fotografías** con su orientación original.
        """)
        json_supervision_file = st.file_uploader("Seleccione o arrastre el archivo JSON de supervisión:", type=["json"], key="up_json_supervision_main")
        if json_supervision_file:
            try:
                data_parsed = json.loads(json_supervision_file.getvalue().decode("utf-8"))
                cab_prev = data_parsed.get("informe") if isinstance(data_parsed.get("informe"), dict) else data_parsed
                p_edif = cab_prev.get("edificio_nombre") or data_parsed.get("edificio_nombre", "Sede")
                p_sup = cab_prev.get("supervisor_nombre") or data_parsed.get("supervisor_nombre", "Supervisor")
                p_fec = cab_prev.get("fecha_inspeccion") or data_parsed.get("fecha_inspeccion", "Fecha")
                p_crit_n = len(data_parsed.get("checklist_evaluacion") or data_parsed.get("detalles") or data_parsed.get("evaluacion") or [])
                p_foto_n = len(data_parsed.get("fotos") or data_parsed.get("registro_fotografico") or [])

                col_prev1, col_prev2 = st.columns([3, 1.2])
                with col_prev1:
                    st.info(f"📄 **Archivo Detectado:** 🏢 `{p_edif}` | 👷 `{p_sup}` | 📅 `{p_fec}` | 🔍 `{p_crit_n}` criterios | 📸 `{p_foto_n}` foto(s)")
                with col_prev2:
                    if st.button("📥 Importar al Formulario", key="btn_do_import_json", type="primary", use_container_width=True):
                        res_imp = procesar_importacion_json(data_parsed, checklist_areas, edificios, supervisores, tipos_inspeccion, turnos_trabajo)
                        st.success(f"✅ ¡Supervisión importada exitosamente! Se cargaron {res_imp['criterios_cargados']} criterios y {res_imp['fotos_cargadas']} foto(s) para {res_imp['edificio']}.")
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error al interpretar el archivo JSON: {e}")

    # Estructura en 5 Secciones principales (Tabs)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1️⃣ Datos Generales & Personal",
        "2️⃣ Checklist por Zonas",
        "3️⃣ EPP, Equipos & Químicos",
        "4️⃣ Incidencias & Fotos",
        "5️⃣ Calificación & Cierre"
    ])

    # -------------------------------------------------------------
    # TAB 1: DATOS GENERALES Y PERSONAL
    # -------------------------------------------------------------
    with tab1:
        st.markdown("### 🏢 Datos de la Sede y Turno Operativo")
        
        col_edif, col_tipo = st.columns([2, 1])
        with col_edif:
            nombres_edificios = [e["nombre"] for e in edificios]
            if st.session_state.get("sel_edificio") not in nombres_edificios and nombres_edificios:
                st.session_state["sel_edificio"] = nombres_edificios[0]
            edificio_sel_nom = st.selectbox("Seleccionar Edificio / Centro Empresarial / Condominio:", nombres_edificios, key="sel_edificio")
            edificio_info = next((e for e in edificios if e["nombre"] == edificio_sel_nom), edificios[0])
            st.info(f"📍 **Dirección:** {edificio_info['direccion']} ({edificio_info.get('distrito_ciudad', 'Lima')}) | **Administrador:** {edificio_info.get('administrador_contacto', 'N/A')}")
            
            # Histórico comparativo previo del edificio
            ult_sup = obtener_ultima_supervision_edificio(edificio_info["nombre"])
            if ult_sup:
                st.warning(f"📊 **Historial Previo de Sede:** Última inspección el `{ult_sup['fecha_inspeccion']}` ({ult_sup['codigo_informe']}) obtuvo **{ult_sup['score_global']:.1f}% ({ult_sup['nivel_calidad']})** con {ult_sup.get('total_no_conformes', 0)} no conformidades. Por favor verificar avances.")
        
        with col_tipo:
            if st.session_state.get("sel_tipo_insp") not in tipos_inspeccion and tipos_inspeccion:
                st.session_state["sel_tipo_insp"] = tipos_inspeccion[0]
            tipo_insp = st.selectbox("Tipo de Inspección:", tipos_inspeccion, key="sel_tipo_insp")

        col_sup, col_turno, col_fecha = st.columns([1.5, 1.5, 1])
        with col_sup:
            nombres_sup = [s["nombre_completo"] for s in supervisores] if supervisores else ["Supervisor de Guardia"]
            if st.session_state.get("sel_supervisor") not in nombres_sup and nombres_sup:
                st.session_state["sel_supervisor"] = nombres_sup[0]
            supervisor_sel_nom = st.selectbox("Supervisor Responsable:", nombres_sup, key="sel_supervisor")
            supervisor_info = next((s for s in supervisores if s["nombre_completo"] == supervisor_sel_nom), None)
            supervisor_dni = supervisor_info["dni_ce"] if supervisor_info else ""
        
        with col_turno:
            if st.session_state.get("sel_turno") not in turnos_trabajo and turnos_trabajo:
                st.session_state["sel_turno"] = turnos_trabajo[0]
            turno_sel = st.selectbox("Turno de Trabajo:", turnos_trabajo, key="sel_turno")
        
        with col_fecha:
            fecha_insp = st.date_input("Fecha:", key="sel_fecha")

        col_hini, col_hfin, col_lider = st.columns([1, 1, 2])
        with col_hini:
            hora_inicio = st.time_input("Hora Inicio:", key="sel_hini")
        with col_hfin:
            hora_fin = st.time_input("Hora Fin:", key="sel_hfin")
        with col_lider:
            lider_cuadrilla = st.text_input("Líder de Cuadrilla / Encargado de Sede:", key="sel_lider")

        st.markdown("---")
        st.markdown("### 👥 Control de Dotación y Asistencia de la Cuadrilla")
        
        col_p_prog, col_p_pres, col_p_falt = st.columns(3)
        with col_p_prog:
            personal_programado = st.number_input("Personal Programado:", min_value=1, max_value=100, key="p_prog")
        with col_p_pres:
            personal_presente = st.number_input("Personal Presente:", min_value=0, max_value=100, key="p_pres")
        with col_p_falt:
            personal_faltante = max(0, personal_programado - personal_presente)
            st.metric("Personal Faltante / Ausencias", f"{personal_faltante} operarios", delta=-personal_faltante if personal_faltante > 0 else 0, delta_color="inverse")

    # -------------------------------------------------------------
    # TAB 2: CHECKLIST TÉCNICO POR ZONAS
    # -------------------------------------------------------------
    with tab2:
        st.markdown("### 🔍 Checklist de Inspección por Zonas del Inmueble")
        st.caption("Evalúe cada elemento: **C (Conforme 100 pts)** | **AD (Adecuado 80 pts)** | **R (Regular 60 pts)** | **NC (No Conforme 0 pts)** | **NA (No Aplica)**")

        # Botones rápidos para marcar todo
        col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 3])
        with col_btn1:
            if st.button("✅ Marcar Todo Conforme (C)", use_container_width=True):
                for k in st.session_state.evaluacion_temp:
                    st.session_state.evaluacion_temp[k]["calificacion"] = "C"
                    st.session_state[f"rad_{k}"] = "C"
                st.rerun()
        with col_btn2:
            if st.button("⚪ Marcar Todo N/A", use_container_width=True):
                for k in st.session_state.evaluacion_temp:
                    st.session_state.evaluacion_temp[k]["calificacion"] = "NA"
                    st.session_state[f"rad_{k}"] = "NA"
                st.rerun()

        # Iterar por cada área definida dinámicamente en la base de datos
        for area in checklist_areas:
            # Calcular score del área en tiempo real
            pts_area = 0.0
            posibles_area = 0.0
            a_c, a_ad, a_r, a_nc, a_na = 0, 0, 0, 0, 0
            for crit in area["criterios"]:
                cid = crit["id"]
                val = st.session_state.get(f"rad_{cid}", st.session_state.evaluacion_temp.get(cid, {}).get("calificacion", "C"))
                if val == "C":
                    a_c += 1
                    pts_area += 100
                    posibles_area += 100
                elif val in ["AD", "A"]:
                    a_ad += 1
                    pts_area += 80
                    posibles_area += 100
                elif val == "R":
                    a_r += 1
                    pts_area += 60
                    posibles_area += 100
                elif val == "NC":
                    a_nc += 1
                    pts_area += 0
                    posibles_area += 100
                elif val == "NA":
                    a_na += 1

            if posibles_area > 0:
                score_area = (pts_area / posibles_area * 100.0)
                cal_info_area = clasificar_calidad(score_area)
                titulo_expander = f"{area['icono']} {area['nombre']} — 🎯 {score_area:.1f}% ({cal_info_area['nivel']})"
                desempeno_html = f"**Desempeño de Zona:** <span style='color:{cal_info_area['color']}; font-weight:800; font-size:1.05rem;'>{score_area:.1f}% ({cal_info_area['nivel']})</span> &nbsp;•&nbsp; 🟢 C: {a_c} | 🔵 AD: {a_ad} | 🟡 R: {a_r} | 🔴 NC: {a_nc} | ⚪ NA: {a_na}"
                progreso_val = score_area / 100.0
            else:
                score_area = None
                cal_info_area = {"nivel": "N.A.", "color": "#64748B", "estado": "No Aplica"}
                titulo_expander = f"{area['icono']} {area['nombre']} — ⚪ N.A. (No Aplica)"
                desempeno_html = f"**Desempeño de Zona:** <span style='color:#64748B; font-weight:800; font-size:1.05rem;'>N.A. (No Aplica)</span> &nbsp;•&nbsp; 🟢 C: 0 | 🔵 AD: 0 | 🟡 R: 0 | 🔴 NC: 0 | ⚪ NA: {a_na}"
                progreso_val = 0.0

            with st.expander(titulo_expander, expanded=True):
                c_sb1, c_sb2 = st.columns([3, 1.2])
                with c_sb1:
                    st.markdown(desempeno_html, unsafe_allow_html=True)
                with c_sb2:
                    st.progress(progreso_val)

                for crit in area["criterios"]:
                    cid = crit["id"]
                    curr_val = st.session_state.evaluacion_temp.get(cid, {}).get("calificacion", "C")
                    curr_obs = st.session_state.evaluacion_temp.get(cid, {}).get("observacion", "")
                    if f"rad_{cid}" not in st.session_state:
                        st.session_state[f"rad_{cid}"] = curr_val
                    if f"obs_{cid}" not in st.session_state:
                        st.session_state[f"obs_{cid}"] = curr_obs

                    c_col1, c_col2, c_col3 = st.columns([2.5, 1.8, 2.5])
                    with c_col1:
                        st.markdown(f"**{crit['item']}**")
                        st.caption(crit["descripcion"])
                    with c_col2:
                        opciones_calif = ["C", "AD", "R", "NC", "NA"]
                        nueva_calif = st.radio(
                            f"Calif-{cid}",
                            options=opciones_calif,
                            horizontal=True,
                            key=f"rad_{cid}",
                            label_visibility="collapsed"
                        )
                        st.session_state.evaluacion_temp[cid]["calificacion"] = nueva_calif
                    with c_col3:
                        nueva_obs = st.text_input(
                            f"Obs-{cid}",
                            placeholder="Observación técnica puntual...",
                            key=f"obs_{cid}",
                            label_visibility="collapsed"
                        )
                        st.session_state.evaluacion_temp[cid]["observacion"] = nueva_obs
                    st.divider()

    # -------------------------------------------------------------
    # TAB 3: EPP, EQUIPOS Y QUÍMICOS
    # -------------------------------------------------------------
    with tab3:
        st.markdown("### 🦺 Control de Seguridad, Salud en el Trabajo (SST) y Recursos")
        
        col_epp, col_maq = st.columns(2)
        with col_epp:
            st.markdown("#### 🦺 Elementos de Protección Personal (EPP)")
            epp_checks = {}
            for item in ITEMS_EPP:
                epp_checks[item["id"]] = st.checkbox(item["item"], value=True, key=f"chk_{item['id']}")
            
            todos_epp = all(epp_checks.values())
            if todos_epp:
                st.success("✅ Dotación y uso de EPPs al 100% conforme.")
            else:
                st.warning("⚠️ Se detectaron omisiones en el uso o estado de EPPs.")

        with col_maq:
            st.markdown("#### ⚙️ Maquinarias y Productos Químicos")
            maq_conforme = st.checkbox("Maquinaria Operativa (Lustradoras, Aspiradoras con cables e inspección OK)", value=True, key="chk_maq")
            quimicos_conforme = st.checkbox("Insumos Químicos rotulados, dosificados y con Fichas de Seguridad (MSDS)", value=True, key="chk_quim")
            orden_office = st.checkbox("Cuarto de Limpieza (Office) limpio, ventilado y ordenado", value=True, key="chk_office")

            st.markdown("#### 📝 Observación de Recursos y SST")
            obs_sst = st.text_area("Comentarios sobre equipos o condiciones de seguridad:", placeholder="Ej: Lustradora requiere cambio preventivo de carbones; stock de bolsas negras completo.", key="txt_sst")

    # -------------------------------------------------------------
    # TAB 4: INCIDENCIAS & FOTOS DE EVIDENCIA
    # -------------------------------------------------------------
    with tab4:
        st.markdown("### ⚠️ Registro de Incidencias / No Conformidades (CAPA)")
        st.caption("Registre las observaciones que ameritan un plan de acción correctivo inmediato con plazo y evidencia fotográfica.")

        if "inc_uploader_ver" not in st.session_state:
            st.session_state.inc_uploader_ver = 0
        if "fotos_temp" not in st.session_state:
            st.session_state.fotos_temp = []
        if "fotos_cargadas_ids" not in st.session_state:
            st.session_state.fotos_cargadas_ids = set()

        with st.form("form_incidencia", clear_on_submit=True):
            col_i_area, col_i_sev = st.columns([2, 1])
            with col_i_area:
                area_inc = st.selectbox("Área con Incidencia:", [a["nombre"] for a in checklist_areas] + ["General / Cuadrilla"], key="inc_area")
            with col_i_sev:
                sev_inc = st.selectbox("Severidad:", ["Baja", "Media", "Alta", "Inmediata / Crítica"], index=1, key="inc_sev")

            desc_inc = st.text_input("Descripción del Hallazgo / No Conformidad:", placeholder="Ej: Mancha persistente de óxido en riel de ascensor N° 2", key="inc_desc")
            
            col_i_act, col_i_plz, col_i_resp = st.columns([2, 1, 1])
            with col_i_act:
                act_inc = st.text_input("Acción Correctiva Inmediata:", placeholder="Ej: Aplicar desoxidante industrial y pulir con paño abrasivo", key="inc_act")
            with col_i_plz:
                plz_inc = st.selectbox("Plazo de Subsanación:", ["Inmediato (mismo turno)", "2 Horas", "24 Horas", "48 Horas"], key="inc_plz")
            with col_i_resp:
                resp_inc = st.text_input("Responsable:", value="Líder de Cuadrilla", key="inc_resp")

            st.markdown("#### 📸 Registro Fotográfico del Hallazgo (Evidencia)")
            st.caption("Cargue fotografías del hallazgo. Se incorporarán automáticamente al **Registro Fotográfico de Evidencias** con el **Área con Incidencia** y la **Descripción del Hallazgo**.")

            col_fi1, col_fi2 = st.columns([1.5, 1.2])
            with col_fi1:
                fotos_inc_archivos = st.file_uploader(
                    "Cargar Fotografía(s) del Hallazgo:",
                    type=["png", "jpg", "jpeg"],
                    accept_multiple_files=True,
                    key=f"inc_fotos_up_{st.session_state.get('inc_uploader_ver', 0)}",
                    help="Cargue una o más fotos del hallazgo. Se colocarán en el Registro Fotográfico con el Área y Descripción de esta incidencia."
                )
            with col_fi2:
                foto_inc_cam = st.camera_input(
                    "O Tomar Foto con Cámara:",
                    key=f"inc_foto_cam_{st.session_state.get('inc_uploader_ver', 0)}"
                )

            if st.form_submit_button("➕ Agregar Incidencia a la Lista", type="primary", use_container_width=True):
                if desc_inc.strip():
                    # Recoger archivos fotográficos subidos en el formulario
                    archivos_fotos_inc = []
                    if fotos_inc_archivos:
                        if isinstance(fotos_inc_archivos, list):
                            archivos_fotos_inc.extend(fotos_inc_archivos)
                        else:
                            archivos_fotos_inc.append(fotos_inc_archivos)
                    if foto_inc_cam:
                        archivos_fotos_inc.append(foto_inc_cam)

                    fotos_agregadas_inc = []
                    for file in archivos_fotos_inc:
                        content = file.getvalue()
                        if not content:
                            continue
                        f_hash = hashlib.md5(content).hexdigest()
                        if f_hash in st.session_state.fotos_cargadas_ids:
                            continue

                        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        rand_suffix = uuid.uuid4().hex[:6]
                        nombre_archivo = f"evidencia_incidencia_{ts_str}_{rand_suffix}.jpg"
                        ruta_archivo = str(UPLOADS_DIR / nombre_archivo)
                        guardar_y_optimizar_imagen(content, ruta_archivo)

                        uid = f"f_{ts_str}_{rand_suffix}"

                        # Integrar en Registro Fotográfico de Evidencias con Área y Descripción del Hallazgo
                        st.session_state.fotos_temp.append({
                            "uid": uid,
                            "area_nombre": area_inc,
                            "tipo_evidencia": "Hallazgo / No Conforme",
                            "archivo_nombre": nombre_archivo,
                            "archivo_ruta": ruta_archivo,
                            "descripcion": desc_inc.strip(),
                            "origen": "CAPA"
                        })
                        st.session_state[f"f_area_{uid}"] = area_inc
                        st.session_state[f"f_tipo_{uid}"] = "Hallazgo / No Conforme"
                        st.session_state[f"f_desc_{uid}"] = desc_inc.strip()
                        st.session_state.fotos_cargadas_ids.add(f_hash)
                        st.session_state.fotos_cargadas_ids.add(ruta_archivo)
                        st.session_state.fotos_cargadas_ids.add(nombre_archivo)
                        fotos_agregadas_inc.append(ruta_archivo)

                    st.session_state.incidencias_temp.append({
                        "area_nombre": area_inc,
                        "descripcion_hallazgo": desc_inc.strip(),
                        "severidad": sev_inc,
                        "accion_correctiva": act_inc.strip(),
                        "plazo_subsanacion": plz_inc,
                        "responsable": resp_inc.strip(),
                        "estado_subsanacion": "Pendiente",
                        "foto_ruta": fotos_agregadas_inc[0] if fotos_agregadas_inc else "",
                        "fotos": fotos_agregadas_inc
                    })
                    st.session_state["inc_uploader_ver"] = st.session_state.get("inc_uploader_ver", 0) + 1

                    if fotos_agregadas_inc:
                        st.success(f"✅ Incidencia registrada y {len(fotos_agregadas_inc)} fotografía(s) integrada(s) en el **Registro Fotográfico de Evidencias** (Área: {area_inc}).")
                    else:
                        st.success("✅ Incidencia agregada correctamente a la lista.")
                    st.rerun()
                else:
                    st.error("Ingrese una descripción para el hallazgo / no conformidad.")

        # Tabla de Incidencias registradas
        if st.session_state.incidencias_temp:
            st.markdown("#### 📋 Incidencias Registradas para el Informe:")
            for idx, inc in enumerate(st.session_state.incidencias_temp):
                c1, c2, c3, c4 = st.columns([2, 3, 1.5, 0.8])
                with c1:
                    st.markdown(f"**{inc['area_nombre']}**")
                    st.caption(f"Severidad: {inc['severidad']} | Plazo: {inc['plazo_subsanacion']}")
                    if inc.get("fotos"):
                        st.caption(f"📸 {len(inc['fotos'])} evidencia(s) fotográfica(s) vinculada(s)")
                with c2:
                    st.markdown(f"**Hallazgo:** {inc['descripcion_hallazgo']}")
                    st.caption(f"Acción: {inc['accion_correctiva']} (Resp: {inc['responsable']})")
                    if inc.get("fotos"):
                        c_tcols = st.columns(min(len(inc["fotos"]), 3))
                        for t_i, r_f in enumerate(inc["fotos"][:3]):
                            if os.path.exists(r_f):
                                with c_tcols[t_i]:
                                    st.image(r_f, width=90)
                with c3:
                    st.warning(f"Estado: {inc['estado_subsanacion']}")
                with c4:
                    if st.button("🗑️", key=f"del_inc_{idx}", help="Eliminar incidencia y sus fotos asociadas"):
                        inc_del = st.session_state.incidencias_temp.pop(idx)
                        fotos_a_borrar = set(inc_del.get("fotos", []))
                        if fotos_a_borrar:
                            nuevas_fotos = []
                            for f in st.session_state.fotos_temp:
                                if f.get("archivo_ruta") in fotos_a_borrar:
                                    u = f.get("uid")
                                    if u:
                                        st.session_state.pop(f"f_area_{u}", None)
                                        st.session_state.pop(f"f_tipo_{u}", None)
                                        st.session_state.pop(f"f_desc_{u}", None)
                                    st.session_state.fotos_cargadas_ids.discard(f.get("archivo_ruta"))
                                    st.session_state.fotos_cargadas_ids.discard(f.get("archivo_nombre"))
                                    if os.path.exists(f.get("archivo_ruta", "")):
                                        try:
                                            os.remove(f["archivo_ruta"])
                                        except Exception:
                                            pass
                                else:
                                    nuevas_fotos.append(f)
                            st.session_state.fotos_temp = nuevas_fotos
                        st.rerun()
        else:
            st.info("No se han registrado incidencias críticas en esta supervisión.")

        st.markdown("---")
        st.markdown("### 📸 Registro Fotográfico de Evidencias")
        st.caption("Cargue fotografías de hallazgos, estado antes/después o panorámica general. Se guardarán en el borrador y se incluirán en el informe oficial.")

        if "fotos_temp" not in st.session_state:
            st.session_state.fotos_temp = []
        if "fotos_cargadas_ids" not in st.session_state:
            st.session_state.fotos_cargadas_ids = set()
        if "uploader_key_version" not in st.session_state:
            st.session_state.uploader_key_version = 0

        col_met1, col_met2 = st.columns([2, 1.5])
        with col_met1:
            metodo_foto = st.radio("Método de captura de evidencia adicional:", ["📁 Cargar desde Archivos / Galería", "📸 Tomar Foto Directa con Cámara"], horizontal=True, key="rad_metodo_foto")

        uploader_ver = st.session_state.uploader_key_version
        archivos_subidos = []
        if metodo_foto == "📁 Cargar desde Archivos / Galería":
            archivos_subidos = st.file_uploader(
                "Cargar Fotos de Inspección (Antes / Después / Hallazgo):",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key=f"uploader_fotos_{uploader_ver}"
            )
        else:
            foto_cam = st.camera_input("Capturar foto instantánea de evidencia en campo:", key=f"cam_evidencia_field_{uploader_ver}")
            if foto_cam:
                archivos_subidos = [foto_cam]

        # Procesar e integrar de inmediato cualquier foto nueva cargada
        if archivos_subidos:
            nuevas_fotos = 0
            for idx_f, file in enumerate(archivos_subidos):
                content = file.getvalue()
                if not content:
                    continue
                f_hash = hashlib.md5(content).hexdigest()
                if f_hash in st.session_state.fotos_cargadas_ids:
                    continue

                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                rand_suffix = uuid.uuid4().hex[:6]
                nombre_archivo = f"evidencia_{ts_str}_{rand_suffix}.jpg"
                ruta_archivo = str(UPLOADS_DIR / nombre_archivo)
                guardar_y_optimizar_imagen(content, ruta_archivo)

                area_defecto = [a["nombre"] for a in checklist_areas][0] if checklist_areas else "General"
                uid = f"f_{ts_str}_{rand_suffix}"
                st.session_state.fotos_temp.append({
                    "uid": uid,
                    "area_nombre": area_defecto,
                    "tipo_evidencia": "Hallazgo / No Conforme",
                    "archivo_nombre": nombre_archivo,
                    "archivo_ruta": ruta_archivo,
                    "descripcion": "",
                    "origen": "REGISTRO_FOTOGRAFICO"
                })
                st.session_state[f"f_area_{uid}"] = area_defecto
                st.session_state[f"f_tipo_{uid}"] = "Hallazgo / No Conforme"
                st.session_state[f"f_desc_{uid}"] = ""
                st.session_state.fotos_cargadas_ids.add(f_hash)
                st.session_state.fotos_cargadas_ids.add(ruta_archivo)
                st.session_state.fotos_cargadas_ids.add(nombre_archivo)
                nuevas_fotos += 1

            if nuevas_fotos > 0:
                st.session_state.uploader_key_version += 1
                st.success(f"✅ Se agregaron {nuevas_fotos} foto(s) a la galería de evidencias.")
                st.rerun()

        # Galería de Fotos Registradas (Cargadas o Traídas del Borrador)
        if st.session_state.fotos_temp:
            total_adicionales = sum(len(f.get("fotos_adicionales", [])) for f in st.session_state.fotos_temp)
            total_fotos = len(st.session_state.fotos_temp) + total_adicionales
            badge_info = f" ({len(st.session_state.fotos_temp)} principales" + (f" + {total_adicionales} adicionales" if total_adicionales > 0 else "") + f" — {total_fotos} total)"
            st.markdown(f"#### 🖼️ Evidencias Fotográficas del Informe{badge_info}:")
            indices_a_eliminar = []
            nombres_areas = [a["nombre"] for a in checklist_areas] if checklist_areas else []
            for extra_a in ["General / Cuadrilla", "General"]:
                if extra_a not in nombres_areas:
                    nombres_areas.append(extra_a)
            tipos_evidencia = ["Hallazgo / No Conforme", "Antes de Limpieza", "Después de Limpieza", "General de Calidad"]

            for idx, foto in enumerate(st.session_state.fotos_temp):
                uid = foto.get("uid")
                if not uid:
                    uid = f"f_{idx}_{uuid.uuid4().hex[:6]}"
                    foto["uid"] = uid
                if "fotos_adicionales" not in foto:
                    foto["fotos_adicionales"] = []

                with st.container():
                    col_img, col_meta, col_actions = st.columns([1.3, 2.7, 0.5])
                    with col_img:
                        if os.path.exists(foto.get("archivo_ruta", "")):
                            st.image(foto["archivo_ruta"], use_container_width=True)
                            try:
                                with Image.open(foto["archivo_ruta"]) as t_img:
                                    es_v = t_img.size[1] > t_img.size[0]
                                    tag_orient = "📱 Vertical" if es_v else "💻 Horizontal"
                                    st.caption(f"Posición: **{tag_orient}** ({t_img.size[0]}x{t_img.size[1]})")
                            except Exception:
                                pass
                        else:
                            st.warning("⚠️ Archivo no encontrado")
                    with col_meta:
                        orig_f = foto.get("origen", "REGISTRO_FOTOGRAFICO")
                        if orig_f == "CAPA":
                            st.markdown("<span style='background:#FEE2E2; color:#B91C1C; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.78rem;'>⚠️ Origen: Incidencia / No Conformidad (CAPA)</span>", unsafe_allow_html=True)
                        elif orig_f == "PWA_OFFLINE":
                            st.markdown("<span style='background:#DCFCE7; color:#15803D; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.78rem;'>📲 Origen: App Móvil PWA Offline</span>", unsafe_allow_html=True)
                        else:
                            st.markdown("<span style='background:#E0F2FE; color:#0369A1; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.78rem;'>📸 Origen: Registro Fotográfico de Calidad</span>", unsafe_allow_html=True)

                        curr_area = foto.get("area_nombre", nombres_areas[0])
                        if curr_area not in nombres_areas:
                            nombres_areas.append(curr_area)
                        idx_area = nombres_areas.index(curr_area)
                        sel_a = st.selectbox(f"Área (Foto #{idx+1}):", nombres_areas, index=idx_area, key=f"f_area_{uid}")
                        foto["area_nombre"] = sel_a

                        curr_tipo = foto.get("tipo_evidencia", tipos_evidencia[0])
                        idx_tipo = tipos_evidencia.index(curr_tipo) if curr_tipo in tipos_evidencia else 0
                        sel_t = st.selectbox(f"Tipo Evidencia (Foto #{idx+1}):", tipos_evidencia, index=idx_tipo, key=f"f_tipo_{uid}")
                        foto["tipo_evidencia"] = sel_t

                        curr_desc = foto.get("descripcion", "")
                        sel_d = st.text_input(f"Descripción Técnica (Foto #{idx+1}):", value=curr_desc, placeholder="Ej: Mancha tratada en piso con desengrasante...", key=f"f_desc_{uid}")
                        foto["descripcion"] = sel_d
                    with col_actions:
                        st.markdown("<br/>", unsafe_allow_html=True)
                        if st.button("🔄", key=f"btn_rot_foto_{uid}", help="Rotar foto 90° horario si la tomó invertida"):
                            if rotar_imagen_guardada(foto.get("archivo_ruta", ""), 90):
                                st.rerun()
                        if st.button("🗑️", key=f"btn_del_foto_{uid}", help="Eliminar esta foto"):
                            indices_a_eliminar.append(idx)

                    # Sub-sección: Fotos adicionales vinculadas a esta evidencia si existen
                    sub_del_indices = []
                    if foto.get("fotos_adicionales"):
                        st.markdown(f"**📸 Fotos Adicionales / Complementarias vinculadas ({len(foto['fotos_adicionales'])}):**")
                        tipos_adicionales = [
                            "Después de Limpieza",
                            "Detalle / Acercamiento",
                            "Ángulo Adicional",
                            "Subsanación de Hallazgo",
                            "Antes de Limpieza",
                            "General de Calidad"
                        ]
                        for s_i, sub_f in enumerate(foto["fotos_adicionales"]):
                            sub_uid = sub_f.get("uid") or f"sub_{uid}_{s_i}"
                            sub_f["uid"] = sub_uid
                            with st.container():
                                c_simg, c_smeta, c_sact = st.columns([1.1, 2.9, 0.5])
                                with c_simg:
                                    if os.path.exists(sub_f.get("archivo_ruta", "")):
                                        st.image(sub_f["archivo_ruta"], use_container_width=True)
                                        try:
                                            with Image.open(sub_f["archivo_ruta"]) as s_img:
                                                s_es_v = s_img.size[1] > s_img.size[0]
                                                s_orient = "📱 Vertical" if s_es_v else "💻 Horizontal"
                                                st.caption(f"**{s_orient}** ({s_img.size[0]}x{s_img.size[1]})")
                                        except Exception:
                                            pass
                                    else:
                                        st.warning("⚠️ Archivo no encontrado")
                                with c_smeta:
                                    st.markdown("<span style='background:#F0FDF4; color:#166534; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.75rem; border:1px solid #BBF7D0;'>📸 Evidencia Adicional / Complementaria</span>", unsafe_allow_html=True)
                                    cur_stipo = sub_f.get("tipo_evidencia", "Después de Limpieza")
                                    if cur_stipo not in tipos_adicionales:
                                        tipos_adicionales.append(cur_stipo)
                                    idx_st = tipos_adicionales.index(cur_stipo)
                                    sel_st = st.selectbox(
                                        f"Tipo Adicional (#{idx+1}.{s_i+1}):",
                                        tipos_adicionales,
                                        index=idx_st,
                                        key=f"sub_tipo_{sub_uid}"
                                    )
                                    sub_f["tipo_evidencia"] = sel_st

                                    cur_sdesc = sub_f.get("descripcion", "")
                                    sel_sd = st.text_input(
                                        f"Descripción Adicional (#{idx+1}.{s_i+1}):",
                                        value=cur_sdesc,
                                        placeholder="Ej: Estado después de pulido / Segunda vista...",
                                        key=f"sub_desc_{sub_uid}"
                                    )
                                    sub_f["descripcion"] = sel_sd
                                with c_sact:
                                    st.markdown("<br/>", unsafe_allow_html=True)
                                    if st.button("🔄", key=f"btn_rot_sub_{sub_uid}", help="Rotar 90° horario esta foto adicional"):
                                        if rotar_imagen_guardada(sub_f.get("archivo_ruta", ""), 90):
                                            st.rerun()
                                    if st.button("🗑️", key=f"btn_del_sub_{sub_uid}", help="Eliminar esta foto adicional"):
                                        sub_del_indices.append(s_i)

                    if sub_del_indices:
                        for s_del_i in sorted(sub_del_indices, reverse=True):
                            s_del_item = foto["fotos_adicionales"].pop(s_del_i)
                            s_del_u = s_del_item.get("uid")
                            if s_del_u:
                                st.session_state.pop(f"sub_tipo_{s_del_u}", None)
                                st.session_state.pop(f"sub_desc_{s_del_u}", None)
                            s_del_r = s_del_item.get("archivo_ruta", "")
                            if s_del_r and os.path.exists(s_del_r):
                                try:
                                    os.remove(s_del_r)
                                except Exception:
                                    pass
                        st.rerun()

                    # Control interactivo para agregar fotos adicionales a esta evidencia
                    with st.expander(f"➕ Agregar Foto Adicional a esta Evidencia (#{idx+1} — {foto.get('area_nombre', '')})", expanded=False):
                        c_smet1, c_smet2 = st.columns([2, 1.5])
                        with c_smet1:
                            sub_metodo = st.radio(
                                f"Método de captura (Foto #{idx+1}):",
                                ["📁 Cargar desde Archivos / Galería", "📸 Tomar con Cámara"],
                                horizontal=True,
                                key=f"sub_metodo_{uid}"
                            )
                        sub_ver = st.session_state.get(f"sub_ver_{uid}", 0)
                        archivos_sub_nuevos = []
                        if sub_metodo == "📁 Cargar desde Archivos / Galería":
                            archivos_sub_nuevos = st.file_uploader(
                                f"Seleccionar foto(s) adicional(es) para evidencia #{idx+1}:",
                                type=["png", "jpg", "jpeg"],
                                accept_multiple_files=True,
                                key=f"up_sub_{uid}_{sub_ver}"
                            )
                        else:
                            sub_cam_inp = st.camera_input(
                                f"Capturar foto adicional en vivo para evidencia #{idx+1}:",
                                key=f"cam_sub_{uid}_{sub_ver}"
                            )
                            if sub_cam_inp:
                                archivos_sub_nuevos = [sub_cam_inp]

                        if archivos_sub_nuevos:
                            agregadas_sub = 0
                            for sf in archivos_sub_nuevos:
                                sf_bytes = sf.getvalue()
                                if not sf_bytes:
                                    continue
                                sf_hash = hashlib.md5(sf_bytes).hexdigest()
                                if sf_hash in st.session_state.fotos_cargadas_ids:
                                    continue

                                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                                rand_suffix = uuid.uuid4().hex[:6]
                                sub_nom = f"evidencia_adicional_{ts_str}_{rand_suffix}.jpg"
                                sub_ruta = str(UPLOADS_DIR / sub_nom)
                                guardar_y_optimizar_imagen(sf_bytes, sub_ruta)

                                new_sub_uid = f"sub_{ts_str}_{rand_suffix}"
                                def_tipo = "Después de Limpieza" if "Antes" in foto.get("tipo_evidencia", "") or "Hallazgo" in foto.get("tipo_evidencia", "") else "Ángulo Adicional"
                                def_desc = f"Foto adicional ({def_tipo})"

                                foto.setdefault("fotos_adicionales", []).append({
                                    "uid": new_sub_uid,
                                    "foto_padre_uid": uid,
                                    "area_nombre": foto.get("area_nombre", "General"),
                                    "tipo_evidencia": def_tipo,
                                    "archivo_nombre": sub_nom,
                                    "archivo_ruta": sub_ruta,
                                    "descripcion": def_desc,
                                    "origen": "FOTO_ADICIONAL"
                                })
                                st.session_state[f"sub_tipo_{new_sub_uid}"] = def_tipo
                                st.session_state[f"sub_desc_{new_sub_uid}"] = def_desc
                                st.session_state.fotos_cargadas_ids.add(sf_hash)
                                st.session_state.fotos_cargadas_ids.add(sub_ruta)
                                st.session_state.fotos_cargadas_ids.add(sub_nom)
                                agregadas_sub += 1

                            if agregadas_sub > 0:
                                st.session_state[f"sub_ver_{uid}"] = sub_ver + 1
                                st.success(f"✅ Se agregó(aron) {agregadas_sub} foto(s) adicional(es) a la evidencia #{idx+1}.")
                                st.rerun()

                    st.divider()

            if indices_a_eliminar:
                for del_i in sorted(indices_a_eliminar, reverse=True):
                    f_del = st.session_state.fotos_temp.pop(del_i)
                    uid_del = f_del.get("uid")
                    if uid_del:
                        st.session_state.pop(f"f_area_{uid_del}", None)
                        st.session_state.pop(f"f_tipo_{uid_del}", None)
                        st.session_state.pop(f"f_desc_{uid_del}", None)
                        st.session_state.pop(f"sub_ver_{uid_del}", None)
                        st.session_state.pop(f"sub_metodo_{uid_del}", None)
                    r_del = f_del.get("archivo_ruta", "")
                    if r_del and os.path.exists(r_del):
                        try:
                            os.remove(r_del)
                        except Exception:
                            pass
                    for sub_del in f_del.get("fotos_adicionales", []):
                        sub_u = sub_del.get("uid")
                        if sub_u:
                            st.session_state.pop(f"sub_tipo_{sub_u}", None)
                            st.session_state.pop(f"sub_desc_{sub_u}", None)
                        s_r = sub_del.get("archivo_ruta", "")
                        if s_r and os.path.exists(s_r):
                            try:
                                os.remove(s_r)
                            except Exception:
                                pass
                st.rerun()
        else:
            st.info("ℹ️ Aún no hay fotografías cargadas. Use el selector arriba para agregar evidencias.")

    # -------------------------------------------------------------
    # TAB 5: CALIFICACIÓN, FIRMAS Y CIERRE
    # -------------------------------------------------------------
    with tab5:
        st.markdown("### 📊 Cálculo en Tiempo Real y Cierre de Auditoría")

        # Realizar cálculo de puntajes
        total_puntos = 0.0
        puntos_posibles = 0.0
        conteo_c = 0
        conteo_ad = 0
        conteo_r = 0
        conteo_nc = 0
        conteo_na = 0

        detalles_lista = []
        for k, v in st.session_state.evaluacion_temp.items():
            cal = v["calificacion"]
            pts = PUNTAJES.get(cal, {}).get("puntos", 0) if cal in PUNTAJES else 0
            detalles_lista.append({
                "id_area": v["id_area"],
                "nombre_area": v["nombre_area"],
                "id_criterio": v["id_criterio"],
                "item_criterio": v["item_criterio"],
                "calificacion": cal,
                "puntos": pts,
                "observacion": v["observacion"]
            })

            if cal == "C":
                conteo_c += 1
                total_puntos += pts
                puntos_posibles += 100
            elif cal in ["AD", "A"]:
                conteo_ad += 1
                total_puntos += pts
                puntos_posibles += 100
            elif cal == "R":
                conteo_r += 1
                total_puntos += pts
                puntos_posibles += 100
            elif cal == "NC":
                conteo_nc += 1
                total_puntos += pts
                puntos_posibles += 100
            elif cal == "NA":
                conteo_na += 1

        if puntos_posibles > 0:
            score_calculado = (total_puntos / puntos_posibles * 100.0)
            calidad_info = clasificar_calidad(score_calculado)
            score_display_txt = f"{score_calculado:.1f}%"
            score_prog = score_calculado / 100.0
        else:
            score_calculado = 0.0
            calidad_info = {
                "nivel": "N.A.",
                "color": "#64748B",
                "estado": "No Aplica",
                "descripcion": "Todos los ítems de esta supervisión fueron marcados como No Aplica (N/A)."
            }
            score_display_txt = "N.A."
            score_prog = 0.0

        # Banner de Score
        col_sc1, col_sc2 = st.columns([1.5, 2.5])
        with col_sc1:
            st.markdown(f"""
                <div style="background:{calidad_info['color']}; padding:20px; border-radius:14px; color:white; text-align:center;">
                    <div style="font-size:0.9rem; text-transform:uppercase; font-weight:700;">Calificación Global</div>
                    <div style="font-size:2.8rem; font-weight:800; margin:6px 0;">{score_display_txt}</div>
                    <div style="font-size:1.05rem; font-weight:700;">{calidad_info['nivel']}</div>
                    <div style="font-size:0.85rem; margin-top:4px;">{calidad_info['estado']}</div>
                </div>
            """, unsafe_allow_html=True)

        with col_sc2:
            st.markdown(f"**Evaluación:** {calidad_info['descripcion']}")
            st.progress(score_prog)
            
            c_k1, c_k2, c_k3, c_k4, c_k5 = st.columns(5)
            c_k1.metric("🟢 Conformes", f"{conteo_c}")
            c_k2.metric("🔵 Adecuados", f"{conteo_ad}")
            c_k3.metric("🟡 Regulares", f"{conteo_r}")
            c_k4.metric("🔴 No Conformes", f"{conteo_nc}")
            c_k5.metric("⚪ No Aplica", f"{conteo_na}")

        # Tabla resumen de desempeño por zona en tiempo real
        st.markdown("---")
        st.markdown("#### 🏢 Desglose Ejecutivo de Desempeño por Área / Zona")
        filas_resumen = []
        for area in checklist_areas:
            a_pts = 0.0
            a_pos = 0.0
            a_c, a_ad, a_r, a_nc, a_na = 0, 0, 0, 0, 0
            for crit in area["criterios"]:
                cid = crit["id"]
                v_cal = st.session_state.evaluacion_temp.get(cid, {}).get("calificacion", "C")
                if v_cal == "C":
                    a_c += 1
                    a_pts += 100
                    a_pos += 100
                elif v_cal in ["AD", "A"]:
                    a_ad += 1
                    a_pts += 80
                    a_pos += 100
                elif v_cal == "R":
                    a_r += 1
                    a_pts += 60
                    a_pos += 100
                elif v_cal == "NC":
                    a_nc += 1
                    a_pts += 0
                    a_pos += 100
                elif v_cal == "NA":
                    a_na += 1

            if a_pos > 0:
                sc_a = (a_pts / a_pos * 100.0)
                inf_a = clasificar_calidad(sc_a)
                sc_str = f"{sc_a:.1f}%"
                nivel_str = inf_a["nivel"]
                dictamen_str = inf_a["estado"]
            else:
                sc_str = "N.A."
                nivel_str = "N.A."
                dictamen_str = "No Aplica / No Evaluada"

            filas_resumen.append({
                "Zona / Área": f"{area['icono']} {area['nombre']}",
                "🟢 C": a_c,
                "🔵 AD": a_ad,
                "🟡 R": a_r,
                "🔴 NC": a_nc,
                "⚪ NA": a_na,
                "Score (%)": sc_str,
                "Nivel": nivel_str,
                "Dictamen": dictamen_str
            })

        df_resumen_areas = pd.DataFrame(filas_resumen)
        st.dataframe(df_resumen_areas, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("### ✍️ Conclusiones y Firmas de Conformidad")

        if "txt_obs_gral" not in st.session_state:
            st.session_state["txt_obs_gral"] = f"Supervisión ejecutada en el turno {turno_sel}. Se constató un nivel de limpieza {calidad_info['nivel']}. Se coordinó con el líder de cuadrilla el cumplimiento del plan de acción."
        obs_generales = st.text_area(
            "Observaciones Generales y Recomendaciones para la Sede:",
            key="txt_obs_gral"
        )

        incluir_firmas = st.checkbox(
            "📌 Habilitar / Incluir '6. Acta de Conformidad y Firmas' en el reporte",
            value=True,
            help="Si se desmarca, el reporte PDF se generará sin el cuadro de firmas de conformidad.",
            key="chk_incluir_firmas"
        )

        firma_sup_b64 = ""
        firma_cli_b64 = ""
        firmante_cli_nom = edificio_info.get("administrador_contacto", "Administración")
        firmante_cli_cargo = "Administrador / Recepción"

        if incluir_firmas:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown("#### ✍️ Firma del Supervisor Responsable")
                st.caption(f"**Supervisor:** {supervisor_sel_nom} (DNI: {supervisor_dni})")
                
                tipo_firma_sup = st.radio(
                    "Método de firma supervisor:",
                    ["🔏 Firma Electrónica Certificada con DNI", "📁 Cargar Imagen de Firma (PNG/JPG)", "📷 Capturar con Cámara"],
                    index=0,
                    key="rad_tipo_firma_sup"
                )
                
                if tipo_firma_sup == "📁 Cargar Imagen de Firma (PNG/JPG)":
                    file_sig_sup = st.file_uploader("Subir archivo de firma:", type=["png", "jpg", "jpeg"], key="up_sig_sup")
                    if file_sig_sup:
                        firma_sup_b64 = f"data:image/png;base64,{base64.b64encode(file_sig_sup.getvalue()).decode('utf-8')}"
                        st.image(file_sig_sup, width=180, caption="Vista previa de firma")
                elif tipo_firma_sup == "📷 Capturar con Cámara":
                    cam_sig_sup = st.camera_input("Firmar en papel y capturar:", key="cam_sig_sup")
                    if cam_sig_sup:
                        firma_sup_b64 = f"data:image/png;base64,{base64.b64encode(cam_sig_sup.getvalue()).decode('utf-8')}"
                        st.image(cam_sig_sup, width=180, caption="Firma capturada")
                else:
                    st.info(f"✅ Se estampará firma digital certificada de **{supervisor_sel_nom}** con DNI `{supervisor_dni}` en el informe PDF.")

            with col_f2:
                st.markdown("#### ✍️ Firma / Recepción del Cliente o Administrador")
                firmante_cli_nom = st.text_input("Nombre de quien recepciona:", value=edificio_info.get("administrador_contacto", "Administración"), key="firm_cli_nom")
                firmante_cli_cargo = st.text_input("Cargo:", value="Administrador / Recepción", key="firm_cli_cargo")
                
                tipo_firma_cli = st.radio(
                    "Método de firma cliente:",
                    ["🔏 Recepción Formal en Sede", "📁 Cargar Imagen de Sello/Firma", "📷 Capturar con Cámara"],
                    index=0,
                    key="rad_tipo_firma_cli"
                )
                
                if tipo_firma_cli == "📁 Cargar Imagen de Sello/Firma":
                    file_sig_cli = st.file_uploader("Subir archivo de sello/firma:", type=["png", "jpg", "jpeg"], key="up_sig_cli")
                    if file_sig_cli:
                        firma_cli_b64 = f"data:image/png;base64,{base64.b64encode(file_sig_cli.getvalue()).decode('utf-8')}"
                        st.image(file_sig_cli, width=180, caption="Vista previa de sello/firma")
                elif tipo_firma_cli == "📷 Capturar con Cámara":
                    cam_sig_cli = st.camera_input("Capturar sello/firma del cliente:", key="cam_sig_cli")
                    if cam_sig_cli:
                        firma_cli_b64 = f"data:image/png;base64,{base64.b64encode(cam_sig_cli.getvalue()).decode('utf-8')}"
                        st.image(cam_sig_cli, width=180, caption="Sello/Firma capturada")
                else:
                    st.info(f"✅ Se registrará acta de recepción formal a nombre de **{firmante_cli_nom}** ({firmante_cli_cargo}).")
        else:
            st.info("ℹ️ La sección de firmas de conformidad ha sido deshabilitada. El reporte PDF se generará sin la sección 6.")

        st.markdown("---")
        
        # Botones para Finalizar o Guardar como Borrador
        col_btn_oficial, col_btn_borrador = st.columns(2)
        with col_btn_oficial:
            btn_guardar_oficial = st.button("🚀 GUARDAR Y EMITIR INFORME OFICIAL", type="primary", use_container_width=True)
        with col_btn_borrador:
            btn_guardar_borrador = st.button("💾 GUARDAR COMO BORRADOR (Continuar más tarde)", use_container_width=True)

        if btn_guardar_oficial or btn_guardar_borrador:
            es_borrador = bool(btn_guardar_borrador)
            with st.spinner("Procesando auditoría y optimizando archivos..."):
                borrador_id = st.session_state.get("borrador_id_activo")
                if borrador_id:
                    codigo_informe = st.session_state.get("borrador_codigo_activo", generar_nuevo_codigo())
                else:
                    codigo_informe = generar_nuevo_codigo()
                
                # Procesar fotos activas desde fotos_temp (tanto nuevas como restauradas del borrador)
                fotos_a_guardar = []
                rutas_procesadas = set()
                for idx, f in enumerate(st.session_state.get("fotos_temp", [])):
                    uid = f.get("uid", str(idx))
                    f_area = st.session_state.get(f"f_area_{uid}", f.get("area_nombre", "General"))
                    f_tipo = st.session_state.get(f"f_tipo_{uid}", f.get("tipo_evidencia", "Hallazgo / No Conforme"))
                    f_desc = st.session_state.get(f"f_desc_{uid}", f.get("descripcion", ""))
                    ruta_arch = f.get("archivo_ruta", "")
                    if not ruta_arch:
                        continue
                    ruta_norm = os.path.normpath(ruta_arch)
                    if not os.path.exists(ruta_norm) or ruta_norm in rutas_procesadas:
                        continue
                    rutas_procesadas.add(ruta_norm)

                    nom_arch = f.get("archivo_nombre") or os.path.basename(ruta_norm)

                    # Procesar fotos adicionales vinculadas a esta evidencia
                    sub_a_guardar = []
                    for s_idx, sub_f in enumerate(f.get("fotos_adicionales", [])):
                        sub_uid = sub_f.get("uid", f"sub_{uid}_{s_idx}")
                        sub_r = sub_f.get("archivo_ruta", "")
                        if not sub_r:
                            continue
                        sub_r_norm = os.path.normpath(sub_r)
                        if not os.path.exists(sub_r_norm) or sub_r_norm in rutas_procesadas:
                            continue
                        rutas_procesadas.add(sub_r_norm)
                        sub_nom = sub_f.get("archivo_nombre") or os.path.basename(sub_r_norm)
                        sub_t = st.session_state.get(f"sub_tipo_{sub_uid}", sub_f.get("tipo_evidencia", "Después de Limpieza"))
                        sub_d = st.session_state.get(f"sub_desc_{sub_uid}", sub_f.get("descripcion", ""))
                        sub_a_guardar.append({
                            "uid": sub_uid,
                            "foto_padre_uid": uid,
                            "area_nombre": f_area,
                            "tipo_evidencia": sub_t,
                            "archivo_nombre": sub_nom,
                            "archivo_ruta": sub_r_norm,
                            "descripcion": sub_d,
                            "origen": sub_f.get("origen", "FOTO_ADICIONAL")
                        })

                    fotos_a_guardar.append({
                        "uid": uid,
                        "area_nombre": f_area,
                        "tipo_evidencia": f_tipo,
                        "archivo_nombre": nom_arch,
                        "archivo_ruta": ruta_norm,
                        "descripcion": f_desc,
                        "origen": f.get("origen", "REGISTRO_FOTOGRAFICO"),
                        "fotos_adicionales": sub_a_guardar
                    })

                # Preparar datos generales
                datos_gral = {
                    "codigo_informe": codigo_informe,
                    "fecha_inspeccion": str(fecha_insp),
                    "hora_inicio": hora_inicio.strftime("%H:%M"),
                    "hora_fin": hora_fin.strftime("%H:%M"),
                    "tipo_inspeccion": tipo_insp,
                    "turno": turno_sel,
                    "edificio_id": edificio_info["id"],
                    "edificio_nombre": edificio_info["nombre"],
                    "edificio_direccion": edificio_info["direccion"],
                    "administrador_nombre": edificio_info.get("administrador_contacto", ""),
                    "supervisor_id": supervisor_info["id"] if supervisor_info else None,
                    "supervisor_nombre": supervisor_sel_nom,
                    "supervisor_dni": supervisor_dni,
                    "lider_cuadrilla": lider_cuadrilla,
                    "personal_programado": int(personal_programado),
                    "personal_presente": int(personal_presente),
                    "personal_faltante": int(personal_faltante),
                    "score_global": round(score_calculado, 2),
                    "nivel_calidad": calidad_info["nivel"],
                    "estado_aprobacion": calidad_info["estado"],
                    "total_items_evaluados": len(detalles_lista),
                    "total_conformes": conteo_c,
                    "total_adecuados": conteo_ad,
                    "total_regulares": conteo_r,
                    "total_no_conformes": conteo_nc,
                    "total_no_aplica": conteo_na,
                    "epp_conforme": 1 if todos_epp else 0,
                    "maquinaria_conforme": 1 if maq_conforme else 0,
                    "insumos_conforme": 1 if quimicos_conforme else 0,
                    "incluir_firmas": 1 if incluir_firmas else 0,
                    "observaciones_generales": obs_generales,
                    "plan_accion_resumen": f"{len(st.session_state.incidencias_temp)} incidencias registradas",
                    "firma_supervisor_data": firma_sup_b64 if incluir_firmas else "",
                    "firma_cliente_data": firma_cli_b64 if incluir_firmas else "",
                    "firmante_cliente_nombre": firmante_cli_nom if incluir_firmas else "",
                    "firmante_cliente_cargo": firmante_cli_cargo if incluir_firmas else "",
                    "estado_informe": "BORRADOR" if es_borrador else "FINALIZADO"
                }

                # Guardar en SQLite (Actualizar si ya era borrador, o Insertar nuevo)
                if borrador_id:
                    actualizar_supervision_completa(
                        supervision_id=borrador_id,
                        datos_gral=datos_gral,
                        detalles_evaluacion=detalles_lista,
                        incidencias=st.session_state.incidencias_temp,
                        fotos_guardadas=fotos_a_guardar
                    )
                    supervision_id = borrador_id
                    cod_gen = codigo_informe
                    if not es_borrador:
                        st.session_state.pop("borrador_id_activo", None)
                        st.session_state.pop("borrador_codigo_activo", None)
                else:
                    supervision_id, cod_gen = guardar_supervision_completa(
                        datos_gral=datos_gral,
                        detalles_evaluacion=detalles_lista,
                        incidencias=st.session_state.incidencias_temp,
                        fotos_guardadas=fotos_a_guardar
                    )
                    if es_borrador:
                        st.session_state["borrador_id_activo"] = supervision_id
                        st.session_state["borrador_codigo_activo"] = cod_gen

                if es_borrador:
                    st.session_state.fotos_temp = [dict(x) for x in fotos_a_guardar]
                    st.session_state.fotos_cargadas_ids = set(rutas_procesadas)
                    for it_f in fotos_a_guardar:
                        u = it_f["uid"]
                        st.session_state[f"f_area_{u}"] = it_f["area_nombre"]
                        st.session_state[f"f_tipo_{u}"] = it_f["tipo_evidencia"]
                        st.session_state[f"f_desc_{u}"] = it_f["descripcion"]
                        for it_sub in it_f.get("fotos_adicionales", []):
                            su = it_sub["uid"]
                            st.session_state[f"sub_tipo_{su}"] = it_sub["tipo_evidencia"]
                            st.session_state[f"sub_desc_{su}"] = it_sub["descripcion"]
                    st.info(f"💾 Avance guardado como **BORRADOR** con código: `{cod_gen}`. Su trabajo continúa a salvo.")
                else:
                    # Generar PDF inmediatamente para descarga
                    data_para_pdf = {
                        "cabecera": datos_gral,
                        "detalles": detalles_lista,
                        "incidencias": st.session_state.incidencias_temp,
                        "fotos": fotos_a_guardar
                    }
                    pdf_bytes = generar_pdf_supervision(data_para_pdf)

                    st.success(f"🎉 ¡Supervisión finalizada y emitida con Código: **{cod_gen}**!")
                    
                    st.download_button(
                        label=f"📥 DESCARGAR INFORME TÉCNICO EN PDF ({cod_gen}.pdf)",
                        data=pdf_bytes,
                        file_name=f"{cod_gen}_Supervision_{edificio_info['nombre'].replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )

                # Limpiar temporales si fue finalizado
                if not es_borrador:
                    st.session_state.incidencias_temp = []
                    st.session_state.fotos_temp = []
                    st.session_state.pop("fotos_cargadas_ids", None)
                    st.session_state["uploader_key_version"] = st.session_state.get("uploader_key_version", 0) + 1
                    st.session_state["inc_uploader_ver"] = st.session_state.get("inc_uploader_ver", 0) + 1
                    keys_to_del = [k for k in list(st.session_state.keys()) if k.startswith("rad_") or k.startswith("obs_") or k.startswith("sel_") or k.startswith("p_") or k.startswith("f_") or k.startswith("sub_") or (k.startswith("inc_") and k != "inc_uploader_ver")]
                    for k in keys_to_del:
                        st.session_state.pop(k, None)

