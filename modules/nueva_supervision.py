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
    actualizar_supervision_completa, agregar_edificio, agregar_supervisor,
    obtener_supervision_por_codigo, existe_codigo_informe
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

    # 0. Código de Informe (si viene en el archivo importado)
    cod_inf_json = (cab.get("codigo_informe") or pwa_data.get("codigo_informe") or "").strip()
    if cod_inf_json:
        st.session_state["inp_codigo_informe"] = cod_inf_json

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
    crit_map_lower = {crit["id"].lower(): crit["id"] for area in checklist_areas for crit in area["criterios"]}
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
        raw_calif = str(item.get("calificacion") or item.get("calif") or "").strip().upper()

        # Si viene puntaje numérico en lugar de calificación textual
        if not raw_calif and "puntos" in item and item["puntos"] is not None:
            try:
                pts_num = float(item["puntos"])
                if pts_num >= 95:
                    raw_calif = "C"
                elif pts_num >= 75:
                    raw_calif = "AD"
                elif pts_num >= 50:
                    raw_calif = "R"
                else:
                    raw_calif = "NC"
            except (ValueError, TypeError):
                raw_calif = "C"

        # Normalización robusta de escalas técnicas (AD=80, C=100, R=60, NC=0, NA=N/A)
        if raw_calif in ("AD", "A", "ADECUADO", "ADECUADA", "80", "80.0"):
            raw_calif = "AD"
        elif raw_calif in ("NA", "N/A", "N.A.", "NO APLICA", "NOAPLICA", "NONE", "NULL"):
            raw_calif = "NA"
        elif raw_calif in ("NC", "NO CONFORME", "NOCONFORME", "NO-CONFORME", "0", "0.0"):
            raw_calif = "NC"
        elif raw_calif in ("R", "REGULAR", "60", "60.0"):
            raw_calif = "R"
        elif raw_calif in ("C", "CONFORME", "100", "100.0", "OK", "BUENO"):
            raw_calif = "C"
        else:
            raw_calif = "C"

        raw_obs = str(item.get("observacion") or item.get("obs") or "").strip()

        target_id = None
        if raw_id in crit_map:
            target_id = raw_id
        elif raw_id.lower() in crit_map_lower:
            target_id = crit_map_lower[raw_id.lower()]
        elif raw_id.lower() in legacy_map and legacy_map[raw_id.lower()] in crit_map:
            target_id = legacy_map[raw_id.lower()]
        elif raw_item_txt:
            norm_item = normalizar_texto_criterio(raw_item_txt)
            if norm_item in crit_norm_map:
                target_id = crit_norm_map[norm_item]
            else:
                for k_norm, cid_match in crit_norm_map.items():
                    if norm_item and (norm_item in k_norm or k_norm in norm_item):
                        target_id = cid_match
                        break

        if target_id:
            if target_id not in st.session_state.evaluacion_temp:
                crit_obj = crit_map.get(target_id, {})
                area_obj = next((a for a in checklist_areas if any(c["id"] == target_id for c in a["criterios"])), None)
                st.session_state.evaluacion_temp[target_id] = {
                    "id_area": area_obj["id_area"] if area_obj else "",
                    "nombre_area": area_obj["nombre"] if area_obj else "",
                    "id_criterio": target_id,
                    "item_criterio": crit_obj.get("item", target_id),
                    "calificacion": raw_calif,
                    "observacion": raw_obs
                }
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


def generar_accion_correctiva_sugerida(area_nom: str, item_nom: str, obs_texto: str) -> str:
    """Genera una acción correctiva técnica sugerida según el área y tipo de hallazgo."""
    texto_comb = f"{area_nom} {item_nom} {obs_texto}".lower()
    if any(w in texto_comb for w in ["sarro", "urinario", "inodoro", "sanitari", "grifer"]):
        return "Aplicar desincrustante ácido industrial, frotar con fibra abrasiva y neutralizar con abundante agua"
    elif any(w in texto_comb for w in ["piso", "alfombra", "mopa", "mancha", "grasa", "óxido"]):
        return "Desmanchar con máquina rotativa y desengrasante neutro; pulir y abrillantar superficie"
    elif any(w in texto_comb for w in ["vidrio", "cristal", "espejo", "mampara"]):
        return "Limpieza técnica con microfibra, solución limpiavidrios antiestática y jalador de goma"
    elif any(w in texto_comb for w in ["tacho", "basura", "bolsa", "residuo", "papelera"]):
        return "Evacuar residuos inmediatamente al cuarto de acopio y reponer bolsa plástica normada"
    elif any(w in texto_comb for w in ["polvo", "telaraña", "zócalo", "rejilla", "techo"]):
        return "Desempolvado profundo con paño electrostático en zócalos, esquinas y rejillas de ventilación"
    elif any(w in texto_comb for w in ["insumo", "jabón", "papel higiénico", "dispensador"]):
        return "Reponer inmediatamente los dispensadores desabastecidos desde el almacén de sede"
    elif any(w in texto_comb for w in ["olor", "desinfección", "bacter"]):
        return "Reforzar desinfección con amonio cuaternario y aplicar neutralizador de olores en ductos"
    else:
        return "Subsanar hallazgo según estándar técnico de sede y verificar conformidad con cuadrilla"


def sincronizar_incidencias_desde_checklist():
    """
    Sincroniza en tiempo real las No Conformidades (NC) y Regulares (R) del Checklist por Zonas
    con la lista de Incidencias CAPA (Tab 4).
    Vincula automáticamente la observación técnica, área y evidencia fotográfica directa sin duplicar digitación.
    """
    if "incidencias_temp" not in st.session_state:
        st.session_state.incidencias_temp = []
    if "fotos_temp" not in st.session_state:
        st.session_state.fotos_temp = []
    if "evaluacion_temp" not in st.session_state:
        return
    if "incidencias_descartadas_cids" not in st.session_state:
        st.session_state.incidencias_descartadas_cids = set()

    # 1. Mapear criterios que califican para CAPA (NC o R)
    criterios_capa = {}
    for cid, item in st.session_state.evaluacion_temp.items():
        if cid in st.session_state.incidencias_descartadas_cids:
            continue
        cal = st.session_state.get(f"rad_{cid}", item.get("calificacion", "C"))
        obs = st.session_state.get(f"obs_{cid}", item.get("observacion", "")).strip()
        if cal in ["NC", "R"]:
            # Buscar fotos asociadas a este criterio en fotos_temp
            fotos_asoc = []
            for f in st.session_state.fotos_temp:
                if f.get("criterio_id") == cid or (f.get("area_nombre") == item.get("nombre_area") and item.get("item_criterio", "") in f.get("descripcion", "")):
                    r_f = f.get("archivo_ruta", "")
                    if r_f and os.path.exists(r_f) and r_f not in fotos_asoc:
                        fotos_asoc.append(r_f)

            criterios_capa[cid] = {
                "cid": cid,
                "id_area": item.get("id_area"),
                "nombre_area": item.get("nombre_area"),
                "item_criterio": item.get("item_criterio"),
                "calificacion": cal,
                "observacion": obs,
                "fotos": fotos_asoc
            }

    # 2. Actualizar incidencias existentes o preservar manuales
    nuevas_incidencias = []
    cids_procesados = set()

    for inc in st.session_state.incidencias_temp:
        c_id = inc.get("criterio_id")
        # Si no tiene criterio_id o es de origen manual, preservarla y sincronizar sus fotos activas
        if not c_id or inc.get("origen") == "MANUAL":
            fotos_existentes = [r for r in inc.get("fotos", []) if r and os.path.exists(r)]
            for f in st.session_state.fotos_temp:
                r_f = f.get("archivo_ruta", "")
                if r_f and os.path.exists(r_f) and f.get("area_nombre") == inc.get("area_nombre") and f.get("descripcion", "").strip().lower() == inc.get("descripcion_hallazgo", "").strip().lower():
                    if r_f not in fotos_existentes:
                        fotos_existentes.append(r_f)
            inc["fotos"] = fotos_existentes
            inc["foto_ruta"] = fotos_existentes[0] if fotos_existentes else ""
            nuevas_incidencias.append(inc)
            continue

        if c_id in criterios_capa:
            info_c = criterios_capa[c_id]
            cal_label = "No Conforme (0 pts)" if info_c["calificacion"] == "NC" else "Regular (60 pts)"
            obs_txt = f": {info_c['observacion']}" if info_c["observacion"] else f" ({cal_label})"
            desc_calc = f"[{info_c['item_criterio']}]{obs_txt}"

            inc["area_nombre"] = info_c["nombre_area"]
            if not inc.get("desc_personalizada", False):
                inc["descripcion_hallazgo"] = desc_calc

            if not inc.get("sev_personalizada", False):
                inc["severidad"] = "Alta" if info_c["calificacion"] == "NC" else "Media"

            # Sincronizar fotos
            for r_pic in info_c["fotos"]:
                if r_pic not in inc.get("fotos", []):
                    inc.setdefault("fotos", []).append(r_pic)
            if inc.get("fotos") and not inc.get("foto_ruta"):
                inc["foto_ruta"] = inc["fotos"][0]

            nuevas_incidencias.append(inc)
            cids_procesados.add(c_id)
        else:
            # El criterio fue subsanado a C, AD o NA en Tab 2: se retira de la lista CAPA
            pass

    # 3. Insertar nuevas incidencias para criterios que no estaban en la lista
    for cid, info_c in criterios_capa.items():
        if cid in cids_procesados:
            continue

        cal_label = "No Conforme (0 pts)" if info_c["calificacion"] == "NC" else "Regular (60 pts)"
        obs_txt = f": {info_c['observacion']}" if info_c["observacion"] else f" ({cal_label})"
        desc_hallazgo = f"[{info_c['item_criterio']}]{obs_txt}"

        accion_sug = generar_accion_correctiva_sugerida(info_c["nombre_area"], info_c["item_criterio"], info_c["observacion"])
        sev_sug = "Alta" if info_c["calificacion"] == "NC" else "Media"
        plz_sug = "24 Horas" if info_c["calificacion"] == "NC" else "48 Horas"

        nuevas_incidencias.append({
            "criterio_id": cid,
            "area_nombre": info_c["nombre_area"],
            "descripcion_hallazgo": desc_hallazgo,
            "severidad": sev_sug,
            "accion_correctiva": accion_sug,
            "plazo_subsanacion": plz_sug,
            "responsable": "Líder de Cuadrilla / Operario Asignado",
            "estado_subsanacion": "Pendiente",
            "foto_ruta": info_c["fotos"][0] if info_c["fotos"] else "",
            "fotos": list(info_c["fotos"]),
            "origen": "CHECKLIST_AUTO",
            "desc_personalizada": False,
            "sev_personalizada": False
        })

    st.session_state.incidencias_temp = nuevas_incidencias


PLANTILLAS_HALLAZGOS = {
    "— Escribir hallazgo manualmente —": {
        "desc": "", "act": "", "plz": "24 Horas", "sev": "Media"
    },
    "🧼 Mancha persistente en piso o alfombra": {
        "desc": "Mancha o suciedad persistente adherida en superficie / piso / alfombra de la zona",
        "act": "Lavar con máquina rotativa / inyección-extracción y aplicar desengrasante industrial",
        "plz": "24 Horas", "sev": "Media"
    },
    "🚽 Sarro / Incrustaciones en aparatos sanitarios": {
        "desc": "Incrustación de sarro y marcas minerales en inodoros, urinarios o griferías",
        "act": "Aplicar desincrustante ácido industrial, frotar con fibra abrasiva y neutralizar con abundante agua",
        "plz": "2 Horas", "sev": "Alta"
    },
    "🪟 Huellas dactilares o polvo marcado en mamparas/vidrios": {
        "desc": "Mamparas de cristal templado y espejos con huellas marcadas y opacidad por polvo",
        "act": "Limpieza técnica con paño de microfibra, solución limpiavidrios antiestática y jalador de goma",
        "plz": "Inmediato (mismo turno)", "sev": "Media"
    },
    "🗑️ Tachos de basura saturados / Sin bolsa reglamentaria": {
        "desc": "Tachos de residuos colapsados al 100% y/o sin bolsa plástica de color normado",
        "act": "Evacuar residuos inmediatamente al cuarto de acopio y reponer bolsa plástica según código de colores",
        "plz": "Inmediato (mismo turno)", "sev": "Inmediata / Crítica"
    },
    "🧴 Desabastecimiento de insumos higiénicos en baños": {
        "desc": "Dispensadores de jabón líquido, papel higiénico o papel toalla vacíos",
        "act": "Reponer inmediatamente los dispensadores desde el stock del almacén de sede",
        "plz": "Inmediato (mismo turno)", "sev": "Alta"
    },
    "🕷️ Polvo y telarañas en zonas altas o rejillas de ventilación": {
        "desc": "Polvo acumulado y telarañas visibles en rejillas de extracción, cornisas y luminarias altas",
        "act": "Ejecutar desempolvado en altura con plumero telescópico y paño electrostático",
        "plz": "24 Horas", "sev": "Baja"
    },
    "👞 Marcas negras de calzado en zócalos o puertas": {
        "desc": "Marcas de rozaduras de calzado y manchas de arrastre en zócalos, marcos y puertas",
        "act": "Frotar con esponja melamínica humedecida y desengrasante neutro multisuperficies",
        "plz": "48 Horas", "sev": "Baja"
    }
}


def registrar_incidencia_manual_vinculada(
    area_nombre: str,
    descripcion_hallazgo: str,
    severidad: str = "Media",
    accion_correctiva: str = "",
    plazo_subsanacion: str = "24 Horas",
    responsable: str = "Líder de Cuadrilla",
    archivos_fotos: list = None
) -> dict:
    """
    Registra o actualiza una incidencia manual (desde 2) Checklist por Zonas o 4) Incidencias & Fotos)
    vinculándola directamente con el listado CAPA y el Registro Fotográfico de Evidencias sin duplicidad.
    """
    desc_clean = (descripcion_hallazgo or "").strip()
    if not desc_clean:
        return {"ok": False, "error": "Ingrese una descripción para el hallazgo / no conformidad."}

    if "incidencias_temp" not in st.session_state:
        st.session_state.incidencias_temp = []
    if "fotos_temp" not in st.session_state:
        st.session_state.fotos_temp = []
    if "fotos_cargadas_ids" not in st.session_state:
        st.session_state.fotos_cargadas_ids = set()

    act_clean = (accion_correctiva or "").strip()
    if not act_clean:
        act_clean = generar_accion_correctiva_sugerida(area_nombre, "Hallazgo Manual", desc_clean)

    resp_clean = (responsable or "").strip() or "Líder de Cuadrilla"

    # 1. Procesar fotografías adjuntas evitando duplicidad por hash MD5
    fotos_agregadas_inc = []
    for file in (archivos_fotos or []):
        if file is None:
            continue
        content = file.getvalue() if hasattr(file, "getvalue") else (file if isinstance(file, bytes) else None)
        if not content:
            continue
        f_hash = hashlib.md5(content).hexdigest()
        if f_hash in st.session_state.fotos_cargadas_ids:
            # Si la foto ya fue cargada antes, buscar su ruta existente para vincularla sin duplicar archivo
            existente_f = next(
                (f["archivo_ruta"] for f in st.session_state.fotos_temp if f.get("area_nombre") == area_nombre and f.get("descripcion", "").strip().lower() == desc_clean.lower()),
                None
            )
            if existente_f and existente_f not in fotos_agregadas_inc:
                fotos_agregadas_inc.append(existente_f)
            continue

        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_suffix = uuid.uuid4().hex[:6]
        nombre_archivo = f"evidencia_incidencia_{ts_str}_{rand_suffix}.jpg"
        ruta_archivo = str(UPLOADS_DIR / nombre_archivo)
        guardar_y_optimizar_imagen(content, ruta_archivo)

        uid = f"f_{ts_str}_{rand_suffix}"

        st.session_state.fotos_temp.append({
            "uid": uid,
            "area_nombre": area_nombre,
            "tipo_evidencia": "Hallazgo / No Conforme",
            "archivo_nombre": nombre_archivo,
            "archivo_ruta": ruta_archivo,
            "descripcion": desc_clean,
            "origen": "CAPA"
        })
        st.session_state[f"f_area_{uid}"] = area_nombre
        st.session_state[f"f_tipo_{uid}"] = "Hallazgo / No Conforme"
        st.session_state[f"f_desc_{uid}"] = desc_clean
        st.session_state.fotos_cargadas_ids.add(f_hash)
        st.session_state.fotos_cargadas_ids.add(ruta_archivo)
        st.session_state.fotos_cargadas_ids.add(nombre_archivo)
        fotos_agregadas_inc.append(ruta_archivo)

    # 2. Verificar si ya existe una incidencia con la misma área y descripción para evitar duplicidad
    desc_norm = normalizar_texto_criterio(desc_clean)
    inc_existente = next(
        (
            inc for inc in st.session_state.incidencias_temp
            if inc.get("area_nombre") == area_nombre
            and normalizar_texto_criterio(inc.get("descripcion_hallazgo", "")) == desc_norm
        ),
        None
    )

    if inc_existente is not None:
        inc_existente["severidad"] = severidad
        inc_existente["accion_correctiva"] = act_clean
        inc_existente["plazo_subsanacion"] = plazo_subsanacion
        inc_existente["responsable"] = resp_clean
        inc_existente["desc_personalizada"] = True
        inc_existente["sev_personalizada"] = True
        for r_pic in fotos_agregadas_inc:
            if r_pic not in inc_existente.setdefault("fotos", []):
                inc_existente["fotos"].append(r_pic)
        if inc_existente.get("fotos") and not inc_existente.get("foto_ruta"):
            inc_existente["foto_ruta"] = inc_existente["fotos"][0]
        return {
            "ok": True,
            "actualizada": True,
            "incidencia": inc_existente,
            "fotos_agregadas": len(fotos_agregadas_inc)
        }

    nueva_inc = {
        "area_nombre": area_nombre,
        "descripcion_hallazgo": desc_clean,
        "severidad": severidad,
        "accion_correctiva": act_clean,
        "plazo_subsanacion": plazo_subsanacion,
        "responsable": resp_clean,
        "estado_subsanacion": "Pendiente",
        "foto_ruta": fotos_agregadas_inc[0] if fotos_agregadas_inc else "",
        "fotos": list(fotos_agregadas_inc),
        "origen": "MANUAL",
        "desc_personalizada": True,
        "sev_personalizada": True
    }
    st.session_state.incidencias_temp.append(nueva_inc)
    return {
        "ok": True,
        "actualizada": False,
        "incidencia": nueva_inc,
        "fotos_agregadas": len(fotos_agregadas_inc)
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
    if "inp_codigo_informe" not in st.session_state or not st.session_state["inp_codigo_informe"]:
        st.session_state["inp_codigo_informe"] = st.session_state.get("borrador_codigo_activo") or generar_nuevo_codigo()

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
                            st.session_state["inp_codigo_informe"] = b["codigo_informe"]
                            st.rerun()
                with cb3:
                    if st.button("🗑️", key=f"btn_del_dr_{b['id']}", help="Eliminar este borrador", use_container_width=True):
                        eliminar_supervision(b["id"])
                        if st.session_state.get("borrador_id_activo") == b["id"]:
                            st.session_state.pop("borrador_id_activo", None)
                            st.session_state.pop("borrador_codigo_activo", None)
                            st.session_state["inp_codigo_informe"] = generar_nuevo_codigo()
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
                st.session_state["inp_codigo_informe"] = generar_nuevo_codigo()
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

    def guardar_avance_borrador() -> str:
        """
        Guarda o actualiza el estado completo actual del formulario como BORRADOR.
        Sincroniza criterios de todas las zonas, fotos e incidencias sin provocar conflictos de widgets.
        Retorna el código de informe generado o actualizado.
        """
        # Sincronizar incidencias antes de guardar para asegurar la última versión
        sincronizar_incidencias_desde_checklist()

        # 1. Obtener datos de cabecera con respaldo seguro
        edif_nom = st.session_state.get("sel_edificio", edificios[0]["nombre"] if edificios else "")
        edif_info = next((e for e in edificios if e["nombre"] == edif_nom), edificios[0] if edificios else {"id": 1, "nombre": "Sede", "direccion": ""})
        
        sup_nom = st.session_state.get("sel_supervisor", supervisores[0]["nombre_completo"] if supervisores else "Supervisor de Guardia")
        sup_info = next((s for s in supervisores if s["nombre_completo"] == sup_nom), None)
        sup_dni = sup_info["dni_ce"] if sup_info else ""
        
        tipo_i = st.session_state.get("sel_tipo_insp", tipos_inspeccion[0] if tipos_inspeccion else "Supervisión Rutinaria")
        turno_s = st.session_state.get("sel_turno", turnos_trabajo[0] if turnos_trabajo else "Turno Mañana")
        fec_i = st.session_state.get("sel_fecha", date.today())
        h_ini = st.session_state.get("sel_hini", time(8, 0))
        h_fin = st.session_state.get("sel_hfin", time(9, 30))
        h_ini_str = h_ini.strftime("%H:%M") if hasattr(h_ini, "strftime") else str(h_ini)
        h_fin_str = h_fin.strftime("%H:%M") if hasattr(h_fin, "strftime") else str(h_fin)
        lider_c = st.session_state.get("sel_lider", "Técnico Líder en Turno")
        p_prog = int(st.session_state.get("p_prog", 4))
        p_pres = int(st.session_state.get("p_pres", 4))
        p_falt = max(0, p_prog - p_pres)

        # 2. Sincronizar todos los criterios desde widgets si existen y calcular puntuaciones
        detalles_lista = []
        total_puntos = 0
        puntos_posibles = 0
        conteo_c, conteo_ad, conteo_r, conteo_nc, conteo_na = 0, 0, 0, 0, 0

        for area_item in checklist_areas:
            for crit_item in area_item["criterios"]:
                cid = crit_item["id"]
                if cid in st.session_state.evaluacion_temp:
                    cal = st.session_state.get(f"rad_{cid}", st.session_state.evaluacion_temp[cid].get("calificacion", "C"))
                    obs = st.session_state.get(f"obs_{cid}", st.session_state.evaluacion_temp[cid].get("observacion", ""))
                    st.session_state.evaluacion_temp[cid]["calificacion"] = cal
                    st.session_state.evaluacion_temp[cid]["observacion"] = obs
                else:
                    cal = st.session_state.get(f"rad_{cid}", "C")
                    obs = st.session_state.get(f"obs_{cid}", "")
                    st.session_state.evaluacion_temp[cid] = {
                        "id_area": area_item["id_area"],
                        "nombre_area": area_item["nombre"],
                        "id_criterio": cid,
                        "item_criterio": crit_item["item"],
                        "calificacion": cal,
                        "observacion": obs
                    }

        for k, v in st.session_state.evaluacion_temp.items():
            cal = v.get("calificacion", "C")
            pts = PUNTAJES.get(cal, {}).get("puntos", 0) if cal in PUNTAJES else 0
            detalles_lista.append({
                "id_area": v.get("id_area", "general"),
                "nombre_area": v.get("nombre_area", "General"),
                "id_criterio": v.get("id_criterio", k),
                "item_criterio": v.get("item_criterio", k),
                "calificacion": cal,
                "puntos": pts,
                "observacion": v.get("observacion", "")
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
            score_calc = (total_puntos / puntos_posibles * 100.0)
            calidad_i = clasificar_calidad(score_calc)
        else:
            score_calc = 0.0
            calidad_i = {"nivel": "N.A.", "color": "#64748B", "estado": "No Aplica"}

        # 3. Procesar fotos temporales activas
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

        # 4. Código del borrador / informe oficial
        cod_usuario = (st.session_state.get("inp_codigo_informe") or "").strip()
        borrador_id = st.session_state.get("borrador_id_activo")
        if cod_usuario:
            codigo_informe = cod_usuario
        elif borrador_id:
            codigo_informe = st.session_state.get("borrador_codigo_activo") or generar_nuevo_codigo()
        else:
            codigo_informe = generar_nuevo_codigo()

        # Si no había borrador_id activo pero el código ya existe en BD, actualizar para evitar colisión UNIQUE
        if not borrador_id:
            rec_existente = existe_codigo_informe(codigo_informe)
            if rec_existente:
                borrador_id = rec_existente["id"]
                st.session_state["borrador_id_activo"] = borrador_id
                st.session_state["borrador_codigo_activo"] = codigo_informe

        chk_epp_all = all([st.session_state.get(f"chk_{item['id']}", True) for item in ITEMS_EPP])
        chk_maq_val = 1 if st.session_state.get("chk_maq", True) else 0
        chk_quim_val = 1 if st.session_state.get("chk_quim", True) else 0
        inc_firmas_val = 1 if st.session_state.get("chk_incluir_firmas", True) else 0
        obs_gen_val = st.session_state.get("txt_obs_gral", f"Supervisión ejecutada en el turno {turno_s}. Se constató un nivel de limpieza {calidad_i['nivel']}. Se coordinó con el líder de cuadrilla el cumplimiento del plan de acción.")

        datos_gral = {
            "codigo_informe": codigo_informe,
            "fecha_inspeccion": str(fec_i),
            "hora_inicio": h_ini_str,
            "hora_fin": h_fin_str,
            "tipo_inspeccion": tipo_i,
            "turno": turno_s,
            "edificio_id": edif_info["id"],
            "edificio_nombre": edif_info["nombre"],
            "edificio_direccion": edif_info["direccion"],
            "administrador_nombre": edif_info.get("administrador_contacto", ""),
            "supervisor_id": sup_info["id"] if sup_info else None,
            "supervisor_nombre": sup_nom,
            "supervisor_dni": sup_dni,
            "lider_cuadrilla": lider_c,
            "personal_programado": p_prog,
            "personal_presente": p_pres,
            "personal_faltante": p_falt,
            "score_global": round(score_calc, 2),
            "nivel_calidad": calidad_i["nivel"],
            "estado_aprobacion": calidad_i["estado"],
            "total_items_evaluados": len(detalles_lista),
            "total_conformes": conteo_c,
            "total_adecuados": conteo_ad,
            "total_regulares": conteo_r,
            "total_no_conformes": conteo_nc,
            "total_no_aplica": conteo_na,
            "epp_conforme": 1 if chk_epp_all else 0,
            "maquinaria_conforme": chk_maq_val,
            "insumos_conforme": chk_quim_val,
            "incluir_firmas": inc_firmas_val,
            "observaciones_generales": obs_gen_val,
            "plan_accion_resumen": f"{len(st.session_state.incidencias_temp)} incidencias registradas",
            "firma_supervisor_data": "",
            "firma_cliente_data": "",
            "firmante_cliente_nombre": st.session_state.get("firm_cli_nom", edif_info.get("administrador_contacto", "Administración")),
            "firmante_cliente_cargo": st.session_state.get("firm_cli_cargo", "Administrador / Recepción"),
            "estado_informe": "BORRADOR"
        }

        if borrador_id:
            actualizar_supervision_completa(
                supervision_id=borrador_id,
                datos_gral=datos_gral,
                detalles_evaluacion=detalles_lista,
                incidencias=st.session_state.incidencias_temp,
                fotos_guardadas=fotos_a_guardar
            )
            cod_gen = codigo_informe
        else:
            supervision_id, cod_gen = guardar_supervision_completa(
                datos_gral=datos_gral,
                detalles_evaluacion=detalles_lista,
                incidencias=st.session_state.incidencias_temp,
                fotos_guardadas=fotos_a_guardar
            )
            st.session_state["borrador_id_activo"] = supervision_id
            st.session_state["borrador_codigo_activo"] = cod_gen

        st.session_state.fotos_temp = [dict(x) for x in fotos_a_guardar]
        st.session_state.fotos_cargadas_ids = set(rutas_procesadas)
        return cod_gen

    # Callbacks de apoyo para el Checklist por Zonas (Tab 2)
    def callback_set_observacion(c_id, texto):
        st.session_state[f"obs_{c_id}"] = texto
        if c_id in st.session_state.evaluacion_temp:
            st.session_state.evaluacion_temp[c_id]["observacion"] = texto

    def callback_marcar_zona(criterios_lista, calif):
        for cr in criterios_lista:
            c_id = cr["id"]
            st.session_state[f"rad_{c_id}"] = calif
            if c_id in st.session_state.evaluacion_temp:
                st.session_state.evaluacion_temp[c_id]["calificacion"] = calif

    def callback_marcar_todo(calif):
        for k in st.session_state.evaluacion_temp:
            st.session_state[f"rad_{k}"] = calif
            st.session_state.evaluacion_temp[k]["calificacion"] = calif

    FRASES_RAPIDAS_LIMPIEZA = {
        "general": [
            "Pisos manchados / requiere desmanchado y pulido",
            "Polvo visible en zócalos, cornisas o marcos",
            "Tacho de basura lleno / bolsa rota o sin recambio",
            "Huellas y marcas dactilares en vidrios / mamparas",
            "Telarañas visibles en techos o esquinas superiores",
            "Olor persistente / requiere refuerzo de desinfección",
            "Superficie húmeda sin señalética de piso mojado",
            "Falta reposición de insumos o materiales de higiene"
        ],
        "baños": [
            "Dispensador de jabón o papel higiénico desabastecido",
            "Sarro / manchas amarillentas en urinarios o inodoros",
            "Espejo con salpicaduras de agua, jabón o marcas",
            "Lavatorio con acumulación de sarro en grifería",
            "Piso húmedo con residuos de papel o cabello",
            "Tacho de toallas sanitarias saturado sin cambio de bolsa",
            "Olor desagradable proveniente de ducto o sumidero"
        ],
        "ascensores": [
            "Botoneras y pantallas con marcas dactilares y grasa",
            "Paneles de acero inoxidable opacos / requiere abrillantador",
            "Rieles de puertas con polvo, pelusas y residuos atorados",
            "Piso de cabina con manchas de pisadas o suciedad pegada",
            "Espejo de cabina con marcas y huellas visibles"
        ],
        "vidrios": [
            "Marcas de manos en puertas batientes y manijas",
            "Vidrios exteriores opacos por acumulación de smog y polvo",
            "Marcos de aluminio o rieles con polvo acumulado"
        ]
    }

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
        # Control y Edición del Código Oficial de Informe
        st.markdown("### 📄 Código de Informe Oficial")
        st.caption("Código correlativo único del informe. Si necesita registrar o recuperar un informe presentado previamente para actualizar información perdida, puede editar este código libremente.")

        col_cod1, col_cod2 = st.columns([3, 1.3])
        with col_cod1:
            st.text_input(
                "Código de Informe Oficial:",
                key="inp_codigo_informe",
                help="Código oficial único. Puede editarlo para recuperar o sincronizar un informe con código preexistente."
            )
        with col_cod2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Generar Correlativo", key="btn_regen_cod_tab1", use_container_width=True, help="Generar un nuevo código correlativo automático según la numeración oficial"):
                st.session_state["inp_codigo_informe"] = generar_nuevo_codigo()
                st.rerun()

        # Detección en tiempo real de existencia del código en la Base de Datos
        cod_actual_val = (st.session_state.get("inp_codigo_informe") or "").strip()
        b_id_actual = st.session_state.get("borrador_id_activo")
        if cod_actual_val:
            info_existente = existe_codigo_informe(cod_actual_val, excluir_id=b_id_actual)
            if info_existente:
                c_inf1, c_inf2 = st.columns([3.5, 1.5])
                with c_inf1:
                    st.warning(
                        f"⚠️ **Código ya registrado en el Sistema:** `{cod_actual_val}` ya existe en la base de datos "
                        f"como **{info_existente['estado_informe']}** para la sede **{info_existente['edificio_nombre']}** (Fecha: {info_existente['fecha_inspeccion']}). "
                        f"Al guardar este informe, **se actualizarán los datos de este mismo código oficial** sin duplicar ni generar errores."
                    )
                with c_inf2:
                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    if st.button("📂 Cargar Datos de este Informe", key=f"btn_cargar_datos_exist_{info_existente['id']}", use_container_width=True, help="Cargar en el formulario los datos guardados previamente para este código de informe"):
                        datos_b = obtener_supervision_por_codigo(cod_actual_val)
                        if datos_b:
                            cab = datos_b["cabecera"]
                            st.session_state["sel_edificio"] = cab.get("edificio_nombre", st.session_state.get("sel_edificio"))
                            st.session_state["sel_tipo_insp"] = cab.get("tipo_inspeccion", st.session_state.get("sel_tipo_insp"))
                            st.session_state["sel_supervisor"] = cab.get("supervisor_nombre", st.session_state.get("sel_supervisor"))
                            st.session_state["sel_turno"] = cab.get("turno", st.session_state.get("sel_turno"))
                            try:
                                st.session_state["sel_fecha"] = datetime.strptime(cab["fecha_inspeccion"], "%Y-%m-%d").date()
                            except Exception:
                                pass
                            st.session_state["sel_lider"] = cab.get("lider_cuadrilla", st.session_state.get("sel_lider"))
                            st.session_state["p_prog"] = int(cab.get("personal_programado", 4))
                            st.session_state["p_pres"] = int(cab.get("personal_presente", 4))
                            st.session_state["txt_obs_gral"] = cab.get("observaciones_generales", "")
                            st.session_state["borrador_id_activo"] = info_existente["id"]
                            st.session_state["borrador_codigo_activo"] = cod_actual_val
                            st.rerun()
            else:
                st.caption(f"🟢 **Código disponible:** Se guardará como un registro oficial nuevo (`{cod_actual_val}`).")

        st.markdown("---")
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

        # 1. CÁLCULO GLOBAL EN TIEMPO REAL PARA TABLERO KPI SUPERIOR (Mejora 2)
        tot_pts_live = 0.0
        tot_posib_live = 0.0
        c_c, c_ad, c_r, c_nc, c_na = 0, 0, 0, 0, 0
        zonas_con_nc = set()
        zonas_con_r = set()
        zonas_evaluadas = set()

        for a_chk in checklist_areas:
            a_nom = a_chk["nombre"]
            for cr_chk in a_chk["criterios"]:
                c_id_chk = cr_chk["id"]
                val_c = st.session_state.get(f"rad_{c_id_chk}", st.session_state.evaluacion_temp.get(c_id_chk, {}).get("calificacion", "C"))
                if val_c == "C":
                    c_c += 1
                    tot_pts_live += 100
                    tot_posib_live += 100
                    zonas_evaluadas.add(a_nom)
                elif val_c in ["AD", "A"]:
                    c_ad += 1
                    tot_pts_live += 80
                    tot_posib_live += 100
                    zonas_evaluadas.add(a_nom)
                elif val_c == "R":
                    c_r += 1
                    tot_pts_live += 60
                    tot_posib_live += 100
                    zonas_evaluadas.add(a_nom)
                    zonas_con_r.add(a_nom)
                elif val_c == "NC":
                    c_nc += 1
                    tot_pts_live += 0
                    tot_posib_live += 100
                    zonas_evaluadas.add(a_nom)
                    zonas_con_nc.add(a_nom)
                elif val_c == "NA":
                    c_na += 1

        score_live = (tot_pts_live / tot_posib_live * 100.0) if tot_posib_live > 0 else 0.0
        cal_live = clasificar_calidad(score_live)

        # Tablero de Control de Desempeño en Vivo
        with st.container(border=True):
            kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns([1.6, 1.2, 1.4, 1.4])
            with kpi_c1:
                st.markdown(
                    f"<div style='font-size:0.8rem; color:#6B7280; font-weight:700; text-transform:uppercase;'>Puntaje Estimado en Vivo:</div>"
                    f"<div style='font-size:1.6rem; font-weight:900; color:{cal_live['color']}; margin-top:-2px;'>{score_live:.1f}% "
                    f"<span style='font-size:0.8rem; background:{cal_live['color']}22; color:{cal_live['color']}; padding:3px 8px; border-radius:6px; font-weight:800; vertical-align:middle;'>{cal_live['nivel']}</span></div>",
                    unsafe_allow_html=True
                )
            with kpi_c2:
                pct_cob = (len(zonas_evaluadas) / len(checklist_areas) * 100) if checklist_areas else 0
                st.metric("Zonas Evaluadas", f"{len(zonas_evaluadas)} / {len(checklist_areas)}", f"{pct_cob:.0f}% cubierto")
            with kpi_c3:
                st.metric("Conformes", f"{c_c + c_ad} ítems", f"🟢 C: {c_c} | 🔵 AD: {c_ad}", delta_color="normal")
            with kpi_c4:
                st.metric("Desviaciones", f"{c_nc + c_r} hallazgos", f"🔴 NC: {c_nc} | 🟡 R: {c_r}", delta_color="inverse")
            
            st.progress(score_live / 100.0)

        # 2. BARRA DE NAVEGACIÓN RÁPIDA, FILTROS Y ACCIONES GLOBALES
        c_nav1, c_nav2, c_nav3, c_nav4 = st.columns([1.3, 1.3, 1.1, 1.7])
        with c_nav1:
            st.button("✅ Todo Conforme (C)", key="btn_todo_c_top", use_container_width=True, help="Marcar todas las zonas y criterios del edificio como Conforme (100 pts)", on_click=callback_marcar_todo, args=("C",))
        with c_nav2:
            st.button("⚪ Todo N/A (Descartar)", key="btn_todo_na_top", use_container_width=True, help="Marcar todas las zonas como No Aplica (no afectará el puntaje)", on_click=callback_marcar_todo, args=("NA",))
        with c_nav3:
            expandir_todo = st.toggle("📂 Expandir todo", value=True, key="tog_expandir_zonas")
        with c_nav4:
            opciones_filtro_vista = ["🏢 Mostrar Todas las Zonas", "⚠️ Solo Zonas con Hallazgos (NC / R)"] + [f"🎯 {a['nombre']}" for a in checklist_areas]
            filtro_zonas_sel = st.selectbox(
                "Filtrar Zonas:",
                opciones_filtro_vista,
                key="sel_filtro_vista_zonas",
                label_visibility="collapsed"
            )

        # 3. ITERAR POR CADA ÁREA CON ACCIONES LOCALES Y TARJETAS ENRIQUECIDAS
        zonas_renderizadas = 0
        for area in checklist_areas:
            # Filtro de visualización
            tiene_alertas = (area["nombre"] in zonas_con_nc) or (area["nombre"] in zonas_con_r)
            if filtro_zonas_sel == "⚠️ Solo Zonas con Hallazgos (NC / R)" and not tiene_alertas:
                continue
            if filtro_zonas_sel.startswith("🎯 ") and filtro_zonas_sel.replace("🎯 ", "") != area["nombre"]:
                continue

            zonas_renderizadas += 1

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
                alert_icon = " ⚠️" if (a_nc > 0 or a_r > 0) else ""
                titulo_expander = f"{area['icono']} {area['nombre']}{alert_icon} — 🎯 {score_area:.1f}% ({cal_info_area['nivel']})"
                desempeno_html = f"**Desempeño de Zona:** <span style='color:{cal_info_area['color']}; font-weight:800; font-size:1.02rem;'>{score_area:.1f}% ({cal_info_area['nivel']})</span> &nbsp;•&nbsp; 🟢 C: {a_c} | 🔵 AD: {a_ad} | 🟡 R: {a_r} | 🔴 NC: {a_nc} | ⚪ NA: {a_na}"
                progreso_val = score_area / 100.0
            else:
                score_area = None
                cal_info_area = {"nivel": "N.A.", "color": "#64748B", "estado": "No Aplica"}
                titulo_expander = f"{area['icono']} {area['nombre']} — ⚪ N.A. (No Aplica)"
                desempeno_html = f"**Desempeño de Zona:** <span style='color:#64748B; font-weight:800; font-size:1.02rem;'>N.A. (No Aplica)</span> &nbsp;•&nbsp; 🟢 C: 0 | 🔵 AD: 0 | 🟡 R: 0 | 🔴 NC: 0 | ⚪ NA: {a_na}"
                progreso_val = 0.0

            esta_expandido = expandir_todo or (a_nc > 0) or (filtro_zonas_sel.startswith("🎯 "))

            with st.expander(titulo_expander, expanded=esta_expandido):
                c_sb1, c_sb2 = st.columns([2.4, 1.6])
                with c_sb1:
                    st.markdown(desempeno_html, unsafe_allow_html=True)
                    st.progress(progreso_val)
                with c_sb2:
                    # Acciones rápidas a nivel de esta zona específica
                    c_za1, c_za2 = st.columns(2)
                    with c_za1:
                        st.button(
                            "✅ Zona Conforme",
                            key=f"btn_c_zone_{area['id_area']}",
                            use_container_width=True,
                            help=f"Marcar todos los ítems de {area['nombre']} como Conforme (100 pts)",
                            on_click=callback_marcar_zona,
                            args=(area["criterios"], "C")
                        )
                    with c_za2:
                        st.button(
                            "⚪ Zona N/A",
                            key=f"btn_na_zone_{area['id_area']}",
                            use_container_width=True,
                            help=f"Marcar {area['nombre']} como No Aplica (no afectará el score)",
                            on_click=callback_marcar_zona,
                            args=(area["criterios"], "NA")
                        )

                st.markdown("<hr style='margin:8px 0 14px 0;'/>", unsafe_allow_html=True)

                for crit in area["criterios"]:
                    cid = crit["id"]
                    curr_val = st.session_state.evaluacion_temp.get(cid, {}).get("calificacion", "C")
                    curr_obs = st.session_state.evaluacion_temp.get(cid, {}).get("observacion", "")
                    if f"rad_{cid}" not in st.session_state:
                        st.session_state[f"rad_{cid}"] = curr_val
                    if f"obs_{cid}" not in st.session_state:
                        st.session_state[f"obs_{cid}"] = curr_obs

                    val_crit = st.session_state.get(f"rad_{cid}", curr_val)

                    # Contenedor estilizado con borde para cada criterio
                    with st.container(border=True):
                        c_col1, c_col2, c_col3 = st.columns([2.5, 1.8, 2.7])
                        with c_col1:
                            if val_crit == "NC":
                                st.markdown("<span style='background:#FEE2E2; color:#B91C1C; padding:2px 8px; border-radius:6px; font-weight:800; font-size:0.75rem; border:1px solid #FCA5A5;'>🔴 NO CONFORME (0 pts)</span>", unsafe_allow_html=True)
                            elif val_crit == "R":
                                st.markdown("<span style='background:#FEF3C7; color:#B45309; padding:2px 8px; border-radius:6px; font-weight:800; font-size:0.75rem; border:1px solid #FCD34D;'>🟡 REGULAR (60 pts)</span>", unsafe_allow_html=True)
                            elif val_crit in ["AD", "A"]:
                                st.markdown("<span style='background:#E0F2FE; color:#0369A1; padding:2px 8px; border-radius:6px; font-weight:800; font-size:0.75rem; border:1px solid #BAE6FD;'>🔵 ADECUADO (80 pts)</span>", unsafe_allow_html=True)
                            elif val_crit == "C":
                                st.markdown("<span style='background:#DCFCE7; color:#15803D; padding:2px 8px; border-radius:6px; font-weight:800; font-size:0.75rem; border:1px solid #BBF7D0;'>🟢 CONFORME (100 pts)</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<span style='background:#F1F5F9; color:#64748B; padding:2px 8px; border-radius:6px; font-weight:800; font-size:0.75rem; border:1px solid #CBD5E1;'>⚪ NO APLICA</span>", unsafe_allow_html=True)

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

                            # Alerta si es NC y no tiene observación
                            if nueva_calif == "NC" and not (nueva_obs and nueva_obs.strip()):
                                st.caption("⚠️ :red[**Hallazgo crítico sin observación. Se sugiere indicar el motivo.**]")

                            # Barra de acciones rápidas para este criterio: Frases Rápidas + Foto de Evidencia
                            c_act1, c_act2 = st.columns([1, 1])
                            with c_act1:
                                with st.popover("⚡ Frases", use_container_width=True):
                                    st.caption(f"Frases rápidas para **{crit['item']}**:")
                                    frases_lista = list(FRASES_RAPIDAS_LIMPIEZA["general"])
                                    nom_b = area["nombre"].lower()
                                    if "baño" in nom_b or "sanitari" in nom_b:
                                        frases_lista = FRASES_RAPIDAS_LIMPIEZA["baños"] + frases_lista
                                    elif "ascensor" in nom_b:
                                        frases_lista = FRASES_RAPIDAS_LIMPIEZA["ascensores"] + frases_lista
                                    elif "vidrio" in nom_b or "cristal" in nom_b:
                                        frases_lista = FRASES_RAPIDAS_LIMPIEZA["vidrios"] + frases_lista

                                    for fr in frases_lista[:7]:
                                        st.button(
                                            f"📝 {fr}",
                                            key=f"bfr_{cid}_{hashlib.md5(fr.encode()).hexdigest()[:6]}",
                                            use_container_width=True,
                                            on_click=callback_set_observacion,
                                            args=(cid, fr)
                                        )

                            with c_act2:
                                # Comprobar si ya existe evidencia vinculada a este criterio
                                foto_adj = next((f for f in st.session_state.fotos_temp if f.get("criterio_id") == cid or (f.get("area_nombre") == area["nombre"] and crit["item"] in f.get("descripcion", ""))), None)
                                lbl_foto = "📸 Foto (1)" if foto_adj else "📸 Foto"
                                with st.popover(lbl_foto, use_container_width=True):
                                    if foto_adj and os.path.exists(foto_adj.get("archivo_ruta", "")):
                                        st.image(foto_adj["archivo_ruta"], width=130)
                                        st.caption(f"✅ Evidencia vinculada ({foto_adj.get('tipo_evidencia', '')})")
                                    
                                    st.caption(f"Adjuntar evidencia fotográfica a **{crit['item']}**:")
                                    up_chk = st.file_uploader("Cargar foto:", type=["png", "jpg", "jpeg"], key=f"up_fchk_{cid}")
                                    cam_chk = st.camera_input("Tomar foto con cámara:", key=f"cam_fchk_{cid}")
                                    nueva_foto_obj = up_chk or cam_chk
                                    if nueva_foto_obj:
                                        f_bytes = nueva_foto_obj.getvalue()
                                        if f_bytes:
                                            h_f = hashlib.md5(f_bytes).hexdigest()
                                            if h_f not in st.session_state.fotos_cargadas_ids:
                                                ts_s = datetime.now().strftime("%Y%m%d_%H%M%S")
                                                rnd_s = uuid.uuid4().hex[:6]
                                                nom_f = f"evidencia_chk_{ts_s}_{rnd_s}.jpg"
                                                rut_f = str(UPLOADS_DIR / nom_f)
                                                guardar_y_optimizar_imagen(f_bytes, rut_f)
                                                uid_f = f"f_chk_{ts_s}_{rnd_s}"
                                                t_ev = "Hallazgo / No Conforme" if nueva_calif == "NC" else ("Antes de Limpieza" if nueva_calif == "R" else "General de Calidad")
                                                d_ev = f"{crit['item']}: {nueva_obs.strip() or 'Evidencia registrada en checklist'}"
                                                st.session_state.fotos_temp.append({
                                                    "uid": uid_f,
                                                    "area_nombre": area["nombre"],
                                                    "tipo_evidencia": t_ev,
                                                    "archivo_nombre": nom_f,
                                                    "archivo_ruta": rut_f,
                                                    "descripcion": d_ev,
                                                    "origen": "CHECKLIST_NC" if nueva_calif in ["NC", "R"] else "REGISTRO_FOTOGRAFICO",
                                                    "criterio_id": cid
                                                })
                                                st.session_state[f"f_area_{uid_f}"] = area["nombre"]
                                                st.session_state[f"f_tipo_{uid_f}"] = t_ev
                                                st.session_state[f"f_desc_{uid_f}"] = d_ev
                                                st.session_state.fotos_cargadas_ids.add(h_f)
                                                st.session_state.fotos_cargadas_ids.add(rut_f)
                                                st.session_state.fotos_cargadas_ids.add(nom_f)
                                                st.toast(f"📸 ¡Foto vinculada con éxito a {crit['item']}!", icon="✅")
                                                st.rerun()

                # -------------------------------------------------------------
                # SECCIÓN AL FINAL DE CADA ZONA: INCIDENCIA MANUAL ADICIONAL VINCULADA CON 4) INCIDENCIAS & FOTOS
                # -------------------------------------------------------------
                id_a = area["id_area"]
                incidencias_man_zona = [
                    (idx_inc_g, inc_g)
                    for idx_inc_g, inc_g in enumerate(st.session_state.get("incidencias_temp", []))
                    if inc_g.get("area_nombre") == area["nombre"] and (inc_g.get("origen") == "MANUAL" or not inc_g.get("criterio_id"))
                ]

                if incidencias_man_zona:
                    st.markdown(
                        f"<div style='background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px; padding:8px 12px; margin:8px 0;'>"
                        f"<strong style='color:#92400E; font-size:0.86rem;'>🔗 Incidencias Manuales Extraordinarias en {area['nombre']} ({len(incidencias_man_zona)}) — Sincronizadas con 4) Incidencias & Fotos:</strong>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    for idx_inc_g, inc_z in incidencias_man_zona:
                        with st.container(border=True):
                            cz_1, cz_2, cz_3 = st.columns([3.0, 1.2, 0.5])
                            with cz_1:
                                st.markdown(f"**👤 Hallazgo Manual:** {inc_z['descripcion_hallazgo']}")
                                st.caption(f"🔥 Severidad: **{inc_z['severidad']}** | ⏱️ Plazo: **{inc_z['plazo_subsanacion']}** | 🛠️ Acción: _{inc_z['accion_correctiva']}_")
                            with cz_2:
                                fotos_z = [r for r in inc_z.get("fotos", []) if r and os.path.exists(r)]
                                if fotos_z:
                                    st.image(fotos_z[0], width=65)
                                    st.caption(f"📸 {len(fotos_z)} foto(s) en Tab 4")
                                else:
                                    st.caption("📷 _Sin foto_")
                            with cz_3:
                                if st.button("🗑️", key=f"del_inc_zone_{id_a}_{idx_inc_g}", help="Eliminar esta incidencia manual (se retirará también de 4) Incidencias & Fotos)"):
                                    inc_del_z = st.session_state.incidencias_temp.pop(idx_inc_g)
                                    fotos_borrar_z = set(inc_del_z.get("fotos", []))
                                    if fotos_borrar_z:
                                        nuevas_f_z = []
                                        for f_item in st.session_state.fotos_temp:
                                            if f_item.get("archivo_ruta") in fotos_borrar_z:
                                                u_z = f_item.get("uid")
                                                if u_z:
                                                    st.session_state.pop(f"f_area_{u_z}", None)
                                                    st.session_state.pop(f"f_tipo_{u_z}", None)
                                                    st.session_state.pop(f"f_desc_{u_z}", None)
                                                st.session_state.fotos_cargadas_ids.discard(f_item.get("archivo_ruta"))
                                                st.session_state.fotos_cargadas_ids.discard(f_item.get("archivo_nombre"))
                                                if os.path.exists(f_item.get("archivo_ruta", "")):
                                                    try:
                                                        os.remove(f_item["archivo_ruta"])
                                                    except Exception:
                                                        pass
                                            else:
                                                nuevas_f_z.append(f_item)
                                        st.session_state.fotos_temp = nuevas_f_z
                                    st.toast("🗑️ Incidencia manual retirada de esta zona y de 4) Incidencias & Fotos", icon="ℹ️")
                                    st.rerun()

                # Botones de pie de zona: Registrar Incidencia Manual Adicional + Guardar Avance como Borrador
                c_z_inc_btn, c_z_btn = st.columns([2.6, 2.2])
                with c_z_inc_btn:
                    if st.button(
                        "➕ Registrar Incidencia Manual Adicional (Fuera de Checklist / Extraordinaria)",
                        key=f"btn_toggle_inc_man_zone_{id_a}",
                        use_container_width=True,
                        help=f"Registrar un hallazgo extraordinario en {area['nombre']} vinculado directamente con 4) Incidencias & Fotos sin escribir dos veces"
                    ):
                        st.session_state[f"open_inc_man_zone_{id_a}"] = not st.session_state.get(f"open_inc_man_zone_{id_a}", False)

                with c_z_btn:
                    if st.button("💾 Guardar Avance como Borrador", key=f"btn_draft_zone_{id_a}", use_container_width=True, help=f"Guarda las calificaciones de {area['nombre']} y todo el formulario actual como borrador"):
                        cod_b = guardar_avance_borrador()
                        st.toast(f"💾 ¡Avance de {area['nombre']} guardado como Borrador ({cod_b})!", icon="✅")
                        st.success(f"💾 ¡Progreso guardado como **BORRADOR** con código `{cod_b}`! Las calificaciones de **{area['nombre']}** han quedado registradas.")

                # Panel desplegable inline de Registro de Incidencia Manual vinculado a 4) Incidencias & Fotos
                if st.session_state.get(f"open_inc_man_zone_{id_a}", False):
                    with st.container(border=True):
                        st.markdown(f"#### ➕ Registrar Incidencia Manual Adicional — **{area['nombre']}**")
                        st.caption("🔗 **Vinculado automáticamente con 4) Incidencias & Fotos:** Todo lo que registre aquí (hallazgo, plan de acción y fotografías) aparecerá automáticamente en la pestaña **4) Incidencias & Fotos** sin duplicidad ni necesidad de volver a escribirlo.")

                        def _aplicar_plantilla_zona(zona_id=id_a):
                            pl_key = st.session_state.get(f"z_sel_pl_{zona_id}", "")
                            if pl_key in PLANTILLAS_HALLAZGOS and pl_key != "— Escribir hallazgo manualmente —":
                                p_d = PLANTILLAS_HALLAZGOS[pl_key]
                                st.session_state[f"z_inc_desc_{zona_id}"] = p_d["desc"]
                                st.session_state[f"z_inc_act_{zona_id}"] = p_d["act"]
                                st.session_state[f"z_inc_plz_{zona_id}"] = p_d["plz"]
                                st.session_state[f"z_inc_sev_{zona_id}"] = p_d["sev"]

                        st.selectbox(
                            "⚡ Plantillas Rápidas de Hallazgos (Opcional — autocompleta los campos):",
                            options=list(PLANTILLAS_HALLAZGOS.keys()),
                            key=f"z_sel_pl_{id_a}",
                            on_change=_aplicar_plantilla_zona,
                            kwargs={"zona_id": id_a}
                        )

                        cz_f1, cz_f2, cz_f3 = st.columns([2.2, 1.2, 1.2])
                        with cz_f1:
                            z_desc = st.text_input(
                                "Descripción del Hallazgo / No Conformidad Extraordinaria:",
                                placeholder=f"Ej: Filtración de agua o rotura de accesorio en {area['nombre']}...",
                                key=f"z_inc_desc_{id_a}"
                            )
                        with cz_f2:
                            z_sev = st.selectbox(
                                "Severidad:",
                                ["Baja", "Media", "Alta", "Inmediata / Crítica"],
                                index=1,
                                key=f"z_inc_sev_{id_a}"
                            )
                        with cz_f3:
                            z_plz = st.selectbox(
                                "Plazo de Subsanación:",
                                ["Inmediato (mismo turno)", "2 Horas", "24 Horas", "48 Horas"],
                                index=2,
                                key=f"z_inc_plz_{id_a}"
                            )

                        cz_a1, cz_a2 = st.columns([2.6, 1.4])
                        with cz_a1:
                            z_act = st.text_input(
                                "Acción Correctiva Inmediata (se sugiere automáticamente si lo deja en blanco):",
                                placeholder="Ej: Aislar zona, secar superficie y reportar a mantenimiento...",
                                key=f"z_inc_act_{id_a}"
                            )
                        with cz_a2:
                            z_resp = st.text_input(
                                "Responsable:",
                                value="Líder de Cuadrilla",
                                key=f"z_inc_resp_{id_a}"
                            )

                        z_up_ver = st.session_state.get(f"z_inc_up_ver_{id_a}", 0)
                        cz_p1, cz_p2 = st.columns([1.6, 1.4])
                        with cz_p1:
                            z_fotos_up = st.file_uploader(
                                f"📸 Cargar Fotografía(s) del Hallazgo ({area['nombre']}):",
                                type=["png", "jpg", "jpeg"],
                                accept_multiple_files=True,
                                key=f"z_inc_fup_{id_a}_{z_up_ver}"
                            )
                        with cz_p2:
                            z_foto_cam = st.camera_input(
                                f"📷 O Tomar Foto con Cámara ({area['nombre']}):",
                                key=f"z_inc_fcam_{id_a}_{z_up_ver}"
                            )

                        cz_b1, cz_b2 = st.columns([2.5, 1.0])
                        with cz_b1:
                            if st.button(
                                "➕ Guardar y Vincular con 4) Incidencias & Fotos",
                                key=f"btn_save_inc_man_zone_{id_a}",
                                type="primary",
                                use_container_width=True
                            ):
                                archivos_z = []
                                if z_fotos_up:
                                    if isinstance(z_fotos_up, list):
                                        archivos_z.extend(z_fotos_up)
                                    else:
                                        archivos_z.append(z_fotos_up)
                                if z_foto_cam:
                                    archivos_z.append(z_foto_cam)

                                res_reg = registrar_incidencia_manual_vinculada(
                                    area_nombre=area["nombre"],
                                    descripcion_hallazgo=z_desc,
                                    severidad=z_sev,
                                    accion_correctiva=z_act,
                                    plazo_subsanacion=z_plz,
                                    responsable=z_resp,
                                    archivos_fotos=archivos_z
                                )
                                if res_reg["ok"]:
                                    st.session_state[f"z_inc_up_ver_{id_a}"] = z_up_ver + 1
                                    st.session_state.pop(f"z_inc_desc_{id_a}", None)
                                    st.session_state.pop(f"z_inc_act_{id_a}", None)
                                    st.session_state.pop(f"z_sel_pl_{id_a}", None)
                                    st.session_state[f"open_inc_man_zone_{id_a}"] = False
                                    accion_msg = "actualizada (evitando duplicidad)" if res_reg["actualizada"] else "registrada"
                                    st.toast(f"✅ Incidencia manual {accion_msg} y vinculada con 4) Incidencias & Fotos", icon="✅")
                                    st.rerun()
                                else:
                                    st.error(res_reg["error"])
                        with cz_b2:
                            if st.button("✖️ Cerrar", key=f"btn_close_inc_man_zone_{id_a}", use_container_width=True):
                                st.session_state[f"open_inc_man_zone_{id_a}"] = False
                                st.rerun()

        if zonas_renderizadas == 0:
            st.info(f"ℹ️ Ninguna zona coincide con el filtro seleccionado: **{filtro_zonas_sel}**.")


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
        if "incidencias_descartadas_cids" not in st.session_state:
            st.session_state.incidencias_descartadas_cids = set()

        # 1. SINCRONIZACIÓN AUTOMÁTICA EN TIEMPO REAL DESDE CHECKLIST POR ZONAS (Recomendación de Implementación)
        sincronizar_incidencias_desde_checklist()

        n_auto = sum(1 for i in st.session_state.incidencias_temp if i.get("origen") == "CHECKLIST_AUTO")
        n_manual = sum(1 for i in st.session_state.incidencias_temp if i.get("origen") == "MANUAL" or not i.get("criterio_id"))
        total_inc = len(st.session_state.incidencias_temp)

        # Panel de Estado de Sincronización
        col_sync1, col_sync2 = st.columns([3, 1.5])
        with col_sync1:
            if total_inc > 0:
                st.info(
                    f"⚡ **Sincronización Inteligente en Tiempo Real Activa:** "
                    f"**{n_auto}** no conformidad(es) vinculada(s) automáticamente desde el Checklist por Zonas | "
                    f"**{n_manual}** incidencia(s) manual(es) adicional(es)."
                )
            else:
                st.success("✅ **Sin No Conformidades:** Todos los criterios evaluados en el Checklist por Zonas son Conformes (C) o N/A. No se requieren acciones correctivas por el momento.")
        with col_sync2:
            if st.button("🔄 Actualizar Sincronización", key="btn_force_sync_capa", use_container_width=True, help="Refresca los datos del checklist e incorpora nuevos hallazgos u observaciones del checklist"):
                st.session_state.incidencias_descartadas_cids.clear()
                sincronizar_incidencias_desde_checklist()
                st.toast("⚡ Sincronización actualizada con el Checklist", icon="✅")
                st.rerun()

        # 2. LISTA Y GESTIÓN DE INCIDENCIAS REGISTRADAS (Visualización Directa)
        if st.session_state.incidencias_temp:
            st.markdown("#### 📋 Plan de Acción y Hallazgos Registrados (CAPA):")
            for idx, inc in enumerate(st.session_state.incidencias_temp):
                es_auto = inc.get("origen") == "CHECKLIST_AUTO"
                badge_orig = "⚡ Checklist (Auto)" if es_auto else "👤 Manual"
                sev_icon = {
                    "Inmediata / Crítica": "🚨",
                    "Alta": "🔴",
                    "Media": "🟠",
                    "Baja": "🟡"
                }.get(inc.get("severidad"), "⚪")

                with st.container(border=True):
                    # Cabecera de la ficha
                    c_h1, c_h2 = st.columns([3, 1.2])
                    with c_h1:
                        st.markdown(
                            f"**{inc['area_nombre']}** &nbsp;•&nbsp; `{badge_orig}` &nbsp;•&nbsp; "
                            f"{sev_icon} **Severidad {inc['severidad']}** &nbsp;•&nbsp; ⏱️ **Plazo:** {inc['plazo_subsanacion']}"
                        )
                    with c_h2:
                        st.caption(f"👤 Resp: {inc.get('responsable', 'Líder de Cuadrilla')}")

                    # Contenido de la incidencia: Descripción, Acción, Evidencia y Acciones
                    c_b1, c_b2, c_b3 = st.columns([2.4, 1.2, 0.8])
                    with c_b1:
                        st.markdown(f"**Hallazgo:** {inc['descripcion_hallazgo']}")
                        st.markdown(f"**Acción Correctiva Sugerida:** _{inc['accion_correctiva']}_")
                    with c_b2:
                        fotos_inc = inc.get("fotos", [])
                        if fotos_inc:
                            st.caption(f"📸 {len(fotos_inc)} evidencia(s) vinculada(s):")
                            c_fcols = st.columns(min(len(fotos_inc), 3))
                            for f_i, r_f in enumerate(fotos_inc[:3]):
                                if os.path.exists(r_f):
                                    with c_fcols[f_i]:
                                        st.image(r_f, width=80)
                        else:
                            st.caption("📷 _Sin foto adjunta (puede añadirla en Tab 2 o en Registro Fotográfico)._")
                    with c_b3:
                        # Botones inline: Editar Ajustes y Eliminar
                        c_bed, c_bdel = st.columns(2)
                        with c_bed:
                            with st.popover("✏️", help="Ajustar acción correctiva, plazo o severidad"):
                                st.markdown(f"**Ajustar Incidencia — {inc['area_nombre']}**")
                                ed_desc = st.text_input("Descripción del Hallazgo:", value=inc["descripcion_hallazgo"], key=f"ed_desc_{idx}")
                                ed_sev = st.selectbox(
                                    "Severidad:",
                                    ["Baja", "Media", "Alta", "Inmediata / Crítica"],
                                    index=["Baja", "Media", "Alta", "Inmediata / Crítica"].index(inc["severidad"]) if inc["severidad"] in ["Baja", "Media", "Alta", "Inmediata / Crítica"] else 1,
                                    key=f"ed_sev_{idx}"
                                )
                                ed_act = st.text_area("Acción Correctiva:", value=inc["accion_correctiva"], key=f"ed_act_{idx}")
                                ed_plz = st.selectbox(
                                    "Plazo de Subsanación:",
                                    ["Inmediato (mismo turno)", "2 Horas", "24 Horas", "48 Horas"],
                                    index=["Inmediato (mismo turno)", "2 Horas", "24 Horas", "48 Horas"].index(inc["plazo_subsanacion"]) if inc["plazo_subsanacion"] in ["Inmediato (mismo turno)", "2 Horas", "24 Horas", "48 Horas"] else 2,
                                    key=f"ed_plz_{idx}"
                                )
                                ed_resp = st.text_input("Responsable:", value=inc.get("responsable", "Líder de Cuadrilla"), key=f"ed_resp_{idx}")
                                if st.button("💾 Guardar Ajustes", key=f"btn_save_ed_{idx}", type="primary", use_container_width=True):
                                    inc["descripcion_hallazgo"] = ed_desc.strip()
                                    inc["severidad"] = ed_sev
                                    inc["accion_correctiva"] = ed_act.strip()
                                    inc["plazo_subsanacion"] = ed_plz
                                    inc["responsable"] = ed_resp.strip()
                                    inc["desc_personalizada"] = True
                                    inc["sev_personalizada"] = True
                                    st.toast("✅ Incidencia actualizada", icon="✅")
                                    st.rerun()

                        with c_bdel:
                            if st.button("🗑️", key=f"del_inc_{idx}", help="Eliminar o retirar esta incidencia"):
                                inc_del = st.session_state.incidencias_temp.pop(idx)
                                cid_del = inc_del.get("criterio_id")
                                if cid_del:
                                    st.session_state.setdefault("incidencias_descartadas_cids", set()).add(cid_del)
                                if inc_del.get("origen") == "MANUAL":
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
                                st.toast("🗑️ Incidencia retirada", icon="ℹ️")
                                st.rerun()
        else:
            st.info("ℹ️ No hay incidencias pendientes en esta supervisión.")

        # 3. REGISTRO DE INCIDENCIA MANUAL ADICIONAL (En Expander sincronizado con el botón de cada zona en Tab 2)
        with st.expander("➕ Registrar Incidencia Manual Adicional (Fuera de Checklist / Extraordinaria)", expanded=False):
            st.caption("🔗 **Sincronizado con 2) Checklist por Zonas:** Las incidencias registradas desde el botón al final de cada zona en la pestaña 2 ya aparecen listadas arriba. Use este formulario solo si desea agregar otra incidencia manual desde aquí.")

            col_pl1, col_pl2 = st.columns([3, 1.2])
            with col_pl1:
                plantilla_sel = st.selectbox(
                    "⚡ Plantillas de Hallazgos Frecuentes:",
                    options=list(PLANTILLAS_HALLAZGOS.keys()),
                    key="sel_plantilla_incidencia"
                )
            with col_pl2:
                st.markdown("<br/>", unsafe_allow_html=True)
                if st.button("📋 Cargar Plantilla", key="btn_aplicar_plantilla", use_container_width=True):
                    if plantilla_sel in PLANTILLAS_HALLAZGOS and plantilla_sel != "— Escribir hallazgo manualmente —":
                        p_data = PLANTILLAS_HALLAZGOS[plantilla_sel]
                        st.session_state["inc_desc"] = p_data["desc"]
                        st.session_state["inc_act"] = p_data["act"]
                        st.session_state["inc_plz"] = p_data["plz"]
                        st.session_state["inc_sev"] = p_data["sev"]
                        st.rerun()

            with st.form("form_incidencia_manual", clear_on_submit=True):
                col_i_area, col_i_sev = st.columns([2, 1])
                with col_i_area:
                    area_inc = st.selectbox("Área con Incidencia:", [a["nombre"] for a in checklist_areas] + ["General / Cuadrilla"], key="inc_area")
                with col_i_sev:
                    sev_inc = st.selectbox("Severidad:", ["Baja", "Media", "Alta", "Inmediata / Crítica"], index=1, key="inc_sev")

                desc_inc = st.text_input("Descripción del Hallazgo / No Conformidad:", placeholder="Ej: Fuga de agua en tubería empotrada de sótano", key="inc_desc")
                
                col_i_act, col_i_plz, col_i_resp = st.columns([2, 1, 1])
                with col_i_act:
                    act_inc = st.text_input("Acción Correctiva Inmediata:", placeholder="Ej: Notificar a mantenimiento y aislar zona", key="inc_act")
                with col_i_plz:
                    plz_inc = st.selectbox("Plazo de Subsanación:", ["Inmediato (mismo turno)", "2 Horas", "24 Horas", "48 Horas"], key="inc_plz")
                with col_i_resp:
                    resp_inc = st.text_input("Responsable:", value="Líder de Cuadrilla", key="inc_resp")

                st.markdown("#### 📸 Evidencia Fotográfica del Hallazgo Manual")
                col_fi1, col_fi2 = st.columns([1.5, 1.2])
                with col_fi1:
                    fotos_inc_archivos = st.file_uploader(
                        "Cargar Fotografía(s) del Hallazgo:",
                        type=["png", "jpg", "jpeg"],
                        accept_multiple_files=True,
                        key=f"inc_fotos_up_{st.session_state.get('inc_uploader_ver', 0)}"
                    )
                with col_fi2:
                    foto_inc_cam = st.camera_input(
                        "O Tomar Foto con Cámara:",
                        key=f"inc_foto_cam_{st.session_state.get('inc_uploader_ver', 0)}"
                    )

                if st.form_submit_button("➕ Agregar Incidencia Manual", type="primary", use_container_width=True):
                    archivos_fotos_inc = []
                    if fotos_inc_archivos:
                        if isinstance(fotos_inc_archivos, list):
                            archivos_fotos_inc.extend(fotos_inc_archivos)
                        else:
                            archivos_fotos_inc.append(fotos_inc_archivos)
                    if foto_inc_cam:
                        archivos_fotos_inc.append(foto_inc_cam)

                    res_manual = registrar_incidencia_manual_vinculada(
                        area_nombre=area_inc,
                        descripcion_hallazgo=desc_inc,
                        severidad=sev_inc,
                        accion_correctiva=act_inc,
                        plazo_subsanacion=plz_inc,
                        responsable=resp_inc,
                        archivos_fotos=archivos_fotos_inc
                    )
                    if res_manual["ok"]:
                        st.session_state["inc_uploader_ver"] = st.session_state.get("inc_uploader_ver", 0) + 1
                        if res_manual["fotos_agregadas"] > 0:
                            st.success(f"✅ Incidencia manual registrada y {res_manual['fotos_agregadas']} fotografía(s) integrada(s) en el **Registro Fotográfico de Evidencias** (Área: {area_inc}).")
                        else:
                            st.success("✅ Incidencia manual agregada correctamente a la lista (sin duplicidad).")
                        st.rerun()
                    else:
                        st.error(res_manual["error"])

        # Guardado de avance como borrador para incidencias (Mejora 6)
        c_inc_save_sp, c_inc_save_btn = st.columns([3, 1.8])
        with c_inc_save_sp:
            st.caption("💾 Guarde sus hallazgos e incidencias en el borrador en cualquier momento.")
        with c_inc_save_btn:
            if st.button("💾 Guardar Incidencias en Borrador", key="btn_draft_incidencias", use_container_width=True, help="Guarda las incidencias registradas y todo el avance actual como borrador"):
                cod_b = guardar_avance_borrador()
                st.toast(f"💾 ¡Incidencias guardadas en Borrador ({cod_b})!", icon="✅")
                st.success(f"💾 ¡Progreso guardado como **BORRADOR** con código `{cod_b}`! Las incidencias han quedado aseguradas.")

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

        # -------------------------------------------------------------
        # 2. COMPARADOR VISUAL INTERACTIVO "ANTES VS. DESPUÉS" (Mejora 2)
        # -------------------------------------------------------------
        if st.session_state.fotos_temp:
            with st.expander("🔄 Comparador Visual Interactivo: Estado Inicial (Antes) vs. Resultado (Después)", expanded=False):
                st.caption("Compare visualmente dos evidencias fotográficas lado a lado para verificar la eficacia de las acciones de limpieza o subsanación de hallazgos.")
                
                # Lista unificada de todas las fotos válidas (principales + adicionales)
                todas_las_fotos_validas = []
                for idx_v, f_v in enumerate(st.session_state.fotos_temp):
                    if f_v.get("archivo_ruta") and os.path.exists(f_v["archivo_ruta"]):
                        d_txt = f" - {f_v.get('descripcion')[:30]}..." if f_v.get("descripcion") else ""
                        todas_las_fotos_validas.append({
                            "id": f"p_{idx_v}",
                            "nombre": f"Foto #{idx_v+1} [{f_v.get('area_nombre', 'General')}] {f_v.get('tipo_evidencia', '')}{d_txt}",
                            "ruta": f_v["archivo_ruta"],
                            "area": f_v.get("area_nombre", "General"),
                            "tipo": f_v.get("tipo_evidencia", "Evidencia"),
                            "desc": f_v.get("descripcion", "Sin descripción registrada")
                        })
                    for s_idx, s_v in enumerate(f_v.get("fotos_adicionales", [])):
                        if s_v.get("archivo_ruta") and os.path.exists(s_v["archivo_ruta"]):
                            s_area = s_v.get("area_nombre") or f_v.get("area_nombre", "General")
                            sd_txt = f" - {s_v.get('descripcion')[:30]}..." if s_v.get("descripcion") else ""
                            todas_las_fotos_validas.append({
                                "id": f"s_{idx_v}_{s_idx}",
                                "nombre": f"Foto #{idx_v+1}.{s_idx+1} [Adicional: {s_area}] {s_v.get('tipo_evidencia', '')}{sd_txt}",
                                "ruta": s_v["archivo_ruta"],
                                "area": s_area,
                                "tipo": s_v.get("tipo_evidencia", "Adicional"),
                                "desc": s_v.get("descripcion", "Sin descripción registrada")
                            })

                if len(todas_las_fotos_validas) >= 2:
                    c_cmp_sel1, c_cmp_sel2 = st.columns(2)
                    opciones_nombres = [item["nombre"] for item in todas_las_fotos_validas]
                    
                    # Índices sugeridos por defecto
                    def_idx_antes = 0
                    def_idx_despues = min(1, len(opciones_nombres) - 1)
                    for i_f, f_item in enumerate(todas_las_fotos_validas):
                        if "Antes" in f_item["tipo"] or "Hallazgo" in f_item["tipo"]:
                            def_idx_antes = i_f
                            break
                    for i_f, f_item in enumerate(todas_las_fotos_validas):
                        if ("Después" in f_item["tipo"] or "Subsanación" in f_item["tipo"]) and i_f != def_idx_antes:
                            def_idx_despues = i_f
                            break

                    with c_cmp_sel1:
                        sel_nom_antes = st.selectbox("🔴 Evidencia de Estado Inicial (Antes de Limpieza / Hallazgo):", opciones_nombres, index=def_idx_antes, key="sel_cmp_antes")
                        item_antes = next((x for x in todas_las_fotos_validas if x["nombre"] == sel_nom_antes), todas_las_fotos_validas[0])
                    with c_cmp_sel2:
                        sel_nom_despues = st.selectbox("🟢 Evidencia de Resultado Final (Después de Limpieza / Subsanado):", opciones_nombres, index=def_idx_despues, key="sel_cmp_despues")
                        item_despues = next((x for x in todas_las_fotos_validas if x["nombre"] == sel_nom_despues), todas_las_fotos_validas[min(1, len(todas_las_fotos_validas)-1)])

                    # Renderizado Lado a Lado
                    col_v_antes, col_v_desp = st.columns(2)
                    with col_v_antes:
                        st.markdown(
                            f"<div style='border:2px solid #EF4444; border-radius:10px; padding:10px; background-color:#FEF2F2; text-align:center; margin-bottom:8px;'>"
                            f"<span style='color:#B91C1C; font-weight:800; font-size:0.92rem;'>🔴 ESTADO INICIAL / ANTES</span><br/>"
                            f"<strong style='color:#1F2937;'>{item_antes['area']}</strong> — <em style='color:#4B5563;'>{item_antes['tipo']}</em>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        st.image(item_antes["ruta"], use_container_width=True)
                        st.caption(f"📝 **Detalle:** {item_antes['desc']}")

                    with col_v_desp:
                        st.markdown(
                            f"<div style='border:2px solid #10B981; border-radius:10px; padding:10px; background-color:#ECFDF5; text-align:center; margin-bottom:8px;'>"
                            f"<span style='color:#047857; font-weight:800; font-size:0.92rem;'>🟢 RESULTADO / DESPUÉS</span><br/>"
                            f"<strong style='color:#1F2937;'>{item_despues['area']}</strong> — <em style='color:#4B5563;'>{item_despues['tipo']}</em>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        st.image(item_despues["ruta"], use_container_width=True)
                        st.caption(f"📝 **Detalle:** {item_despues['desc']}")

                    if item_antes["area"] == item_despues["area"]:
                        st.success(f"✨ **Comparación coherente por zona:** Ambas evidencias pertenecen a **{item_antes['area']}**. Esta relación demuestra la efectividad de la limpieza.")
                    else:
                        st.info(f"💡 Comparando fotos de diferentes zonas: **{item_antes['area']}** vs. **{item_despues['area']}**.")
                else:
                    st.info("ℹ️ Cargue al menos 2 fotografías (o agregue una foto complementaria a una evidencia) para habilitar la comparación interactiva lado a lado.")

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

            # Barra de Herramientas: Filtros y Selector de Modo de Vista (Mejora 4)
            c_f_fil1, c_f_fil2, c_f_modo = st.columns([1.5, 1.5, 1.4])
            areas_presentes = sorted(list(set(f.get("area_nombre", "General") for f in st.session_state.fotos_temp)))
            opciones_f_area = ["Todas las Áreas"] + areas_presentes
            with c_f_fil1:
                filtro_area_sel = st.selectbox("🔍 Filtrar por Área:", opciones_f_area, key="fil_galeria_area")
            with c_f_fil2:
                opciones_f_tipo = ["Todos los Tipos"] + tipos_evidencia
                filtro_tipo_sel = st.selectbox("🏷️ Filtrar por Tipo:", opciones_f_tipo, key="fil_galeria_tipo")
            with c_f_modo:
                modo_vista_galeria = st.radio(
                    "📐 Modo de Vista:",
                    ["📑 Vista Detallada", "🔲 Cuadrícula (Grid)"],
                    horizontal=True,
                    key="rad_modo_vista_galeria"
                )

            # Filtrar fotos a mostrar
            fotos_visibles = []
            for idx, foto in enumerate(st.session_state.fotos_temp):
                if filtro_area_sel != "Todas las Áreas" and foto.get("area_nombre") != filtro_area_sel:
                    continue
                if filtro_tipo_sel != "Todos los Tipos" and foto.get("tipo_evidencia") != filtro_tipo_sel:
                    continue
                fotos_visibles.append((idx, foto))

            if not fotos_visibles:
                st.info(f"🔍 No hay fotografías que coincidan con los filtros seleccionados (Área: **{filtro_area_sel}**, Tipo: **{filtro_tipo_sel}**).")
            elif modo_vista_galeria == "🔲 Cuadrícula (Grid)":
                st.caption(f"Mostrando **{len(fotos_visibles)}** de {len(st.session_state.fotos_temp)} fotos en cuadrícula compacta de 3 columnas.")
                grid_cols = st.columns(3)
                for g_i, (idx, foto) in enumerate(fotos_visibles):
                    col_target = grid_cols[g_i % 3]
                    uid = foto.get("uid") or f"f_grid_{idx}"
                    with col_target:
                        with st.container(border=True):
                            r_img = foto.get("archivo_ruta", "")
                            if r_img and os.path.exists(r_img):
                                st.image(r_img, use_container_width=True)
                            else:
                                st.warning("⚠️ Sin archivo")

                            t_evid = foto.get("tipo_evidencia", "Evidencia")
                            bg_c = "#FEE2E2" if "Hallazgo" in t_evid else ("#FEF3C7" if "Antes" in t_evid else ("#DCFCE7" if "Después" in t_evid else "#E0F2FE"))
                            fg_c = "#991B1B" if "Hallazgo" in t_evid else ("#92400E" if "Antes" in t_evid else ("#166534" if "Después" in t_evid else "#0369A1"))
                            st.markdown(
                                f"<div style='margin-bottom:6px;'>"
                                f"<strong style='font-size:0.85rem; color:#1F2937;'>{foto.get('area_nombre', 'General')}</strong><br/>"
                                f"<span style='background:{bg_c}; color:{fg_c}; padding:1px 6px; border-radius:4px; font-weight:700; font-size:0.72rem;'>{t_evid}</span>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if foto.get("descripcion"):
                                st.caption(f"📝 {foto['descripcion'][:45]}...")
                            num_subs = len(foto.get("fotos_adicionales", []))
                            if num_subs > 0:
                                st.caption(f"📸 +{num_subs} complementaria(s)")

                            c_b1, c_b2 = st.columns([1, 1])
                            with c_b1:
                                if st.button("🔄 Rotar", key=f"btn_grid_rot_{uid}", use_container_width=True, help="Rotar 90° horario"):
                                    if rotar_imagen_guardada(foto.get("archivo_ruta", ""), 90):
                                        st.rerun()
                            with c_b2:
                                if st.button("🗑️ Borrar", key=f"btn_grid_del_{uid}", use_container_width=True, help="Eliminar esta foto"):
                                    indices_a_eliminar.append(idx)

            lista_fotos_iter = fotos_visibles if modo_vista_galeria == "📑 Vista Detallada" else []
            for idx, foto in lista_fotos_iter:
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

        # Guardado de avance como borrador para evidencias fotográficas (Mejora 6 Parte B)
        st.divider()
        c_f_save_sp, c_f_save_btn = st.columns([3, 1.8])
        with c_f_save_sp:
            st.caption("💾 Guarde todas las fotos, evidencias e incidencias registradas en el borrador.")
        with c_f_save_btn:
            if st.button("💾 Guardar Fotos y Avance en Borrador", key="btn_draft_fotos_footer", use_container_width=True, help="Guarda todas las fotos, evidencias y avance actual como borrador"):
                cod_b = guardar_avance_borrador()
                st.toast(f"💾 ¡Fotos y evidencias guardadas en Borrador ({cod_b})!", icon="✅")
                st.success(f"💾 ¡Progreso guardado como **BORRADOR** con código `{cod_b}`! Las fotos y evidencias han quedado aseguradas.")

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

        if btn_guardar_borrador:
            with st.spinner("Guardando avance como borrador en base de datos..."):
                cod_gen = guardar_avance_borrador()
                st.toast(f"💾 ¡Avance guardado como Borrador ({cod_gen})!", icon="✅")
                st.info(f"💾 Avance guardado como **BORRADOR** con código: `{cod_gen}`. Su trabajo continúa a salvo en la base de datos.")

        if btn_guardar_oficial:
            with st.spinner("Procesando auditoría y optimizando archivos..."):
                cod_usuario = (st.session_state.get("inp_codigo_informe") or "").strip()
                borrador_id = st.session_state.get("borrador_id_activo")
                if cod_usuario:
                    codigo_informe = cod_usuario
                elif borrador_id:
                    codigo_informe = st.session_state.get("borrador_codigo_activo") or generar_nuevo_codigo()
                else:
                    codigo_informe = generar_nuevo_codigo()

                # Si no había borrador_id activo pero el código ya existe en BD, actualizar para evitar colisión UNIQUE
                if not borrador_id:
                    rec_existente = existe_codigo_informe(codigo_informe)
                    if rec_existente:
                        borrador_id = rec_existente["id"]
                
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
                    "estado_informe": "FINALIZADO"
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
                    st.session_state.pop("borrador_id_activo", None)
                    st.session_state.pop("borrador_codigo_activo", None)
                else:
                    supervision_id, cod_gen = guardar_supervision_completa(
                        datos_gral=datos_gral,
                        detalles_evaluacion=detalles_lista,
                        incidencias=st.session_state.incidencias_temp,
                        fotos_guardadas=fotos_a_guardar
                    )

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
                st.session_state.incidencias_temp = []
                st.session_state.fotos_temp = []
                st.session_state.pop("fotos_cargadas_ids", None)
                st.session_state["uploader_key_version"] = st.session_state.get("uploader_key_version", 0) + 1
                st.session_state["inc_uploader_ver"] = st.session_state.get("inc_uploader_ver", 0) + 1
                keys_to_del = [k for k in list(st.session_state.keys()) if k.startswith("rad_") or k.startswith("obs_") or k.startswith("sel_") or k.startswith("p_") or k.startswith("f_") or k.startswith("sub_") or (k.startswith("inc_") and k != "inc_uploader_ver")]
                for k in keys_to_del:
                    st.session_state.pop(k, None)
                st.session_state.pop("inp_codigo_informe", None)

