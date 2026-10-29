"""
Módulo de Generación de Informes Técnicos en PDF (ReportLab).
Produce un reporte formal ejecutivo sin QR, con membrete corporativo editable,
título 'REPORTE DE SUPERVISIÓN DE LIMPIEZA', fotos en proporción original,
semáforo de calidad de 5 niveles y sección de firmas configurable.
"""
import io
import os
import base64
from PIL import Image as PILImage, ImageOps
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable, PageBreak
)
from reportlab.pdfgen import canvas

from config import SYSTEM_TITLE, FORMAT_CODE, FORMAT_VERSION, COMPANY_NAME, clasificar_calidad
from database import obtener_parametro, obtener_logo_empresa


class NumberedCanvas(canvas.Canvas):
    """Canvas personalizado para numeración de páginas 'Página X de Y' y pie de página corporativo."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        empresa_nombre = obtener_parametro("empresa_nombre", COMPANY_NAME)
        formato_cod = obtener_parametro("formato_codigo", FORMAT_CODE)
        formato_ver = obtener_parametro("formato_version", FORMAT_VERSION)

        # Línea superior de pie de página
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 40, 576, 40)
        
        # Texto de pie de página
        footer_text = f"{empresa_nombre} | {formato_cod} Rev. {formato_ver} | ISSA CIMS - OSHA - Ley N° 29783"
        self.drawString(36, 28, footer_text)
        
        # Número de página
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(576, 28, page_str)
        self.restoreState()


def generar_pdf_supervision(supervision_data: dict) -> bytes:
    """
    Genera el PDF completo del reporte de supervisión y retorna los bytes en memoria.
    """
    cabecera = supervision_data["cabecera"]
    detalles = supervision_data.get("detalles", [])
    incidencias = supervision_data.get("incidencias", [])
    fotos = supervision_data.get("fotos", [])

    # Obtener parámetros editables de empresa
    empresa_nombre = obtener_parametro("empresa_nombre", COMPANY_NAME)
    empresa_subtitulo = obtener_parametro("empresa_subtitulo", "Control de Calidad, Estándares de Higiene y Cumplimiento de Servicio")
    formato_cod = obtener_parametro("formato_codigo", FORMAT_CODE)
    formato_ver = obtener_parametro("formato_version", FORMAT_VERSION)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos personalizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0284C7"),
        spaceAfter=4
    )
    sub_heading = ParagraphStyle(
        'SubSectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=6,
        spaceAfter=3
    )
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1E293B")
    )
    body_bold = ParagraphStyle(
        'BodyDarkBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#0F172A")
    )
    badge_c = ParagraphStyle('BadgeC', parent=body_bold, textColor=colors.HexColor("#047857"), alignment=1)
    badge_ad = ParagraphStyle('BadgeAD', parent=body_bold, textColor=colors.HexColor("#0284C7"), alignment=1)
    badge_r = ParagraphStyle('BadgeR', parent=body_bold, textColor=colors.HexColor("#B45309"), alignment=1)
    badge_nc = ParagraphStyle('BadgeNC', parent=body_bold, textColor=colors.HexColor("#B91C1C"), alignment=1)
    badge_na = ParagraphStyle('BadgeNA', parent=body_bold, textColor=colors.HexColor("#64748B"), alignment=1)
    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white
    )
    th_center = ParagraphStyle(
        'TableHeaderCenter',
        parent=th_style,
        alignment=1
    )

    story = []

    # 1. ENCABEZADO CORPORATIVO CON LOGO Y TÍTULO SOLICITADO
    header_text = f"""
    <b><font size=10 color="#0F172A">{empresa_nombre}</font></b><br/>
    <font size=13 color="#0284C7"><b>REPORTE DE SUPERVISIÓN DE LIMPIEZA</b></font><br/>
    <font size=8 color="#64748B">{empresa_subtitulo}</font><br/>
    <font size=7.5 color="#334155">Código de Informe: <b>{cabecera['codigo_informe']}</b> &nbsp;|&nbsp; Formato: {formato_cod} &nbsp;|&nbsp; Versión: {formato_ver}</font>
    """

    # Obtener logotipo corporativo configurado (o override en supervision_data/cabecera)
    logo_path_override = cabecera.get("logo_empresa_path") or supervision_data.get("logo_empresa_path")
    logo_info = None
    if logo_path_override and os.path.exists(logo_path_override):
        try:
            with PILImage.open(logo_path_override) as p_img:
                lw, lh = p_img.size
            logo_info = {"path": logo_path_override, "ancho": lw, "alto": lh}
        except Exception:
            logo_info = None

    if not logo_info:
        logo_info = obtener_logo_empresa()

    logo_flowable = None
    if logo_info and logo_info.get("path") and os.path.exists(logo_info["path"]):
        try:
            with PILImage.open(logo_info["path"]) as p_img:
                lw, lh = p_img.size
                max_w = 1.35 * inch
                max_h = 0.85 * inch
                scale_l = min(max_w / lw, max_h / lh)
                final_lw = max(lw * scale_l, 10)
                final_lh = max(lh * scale_l, 10)
            logo_flowable = Image(logo_info["path"], width=final_lw, height=final_lh)
        except Exception:
            logo_flowable = None

    if logo_flowable is None:
        logo_flowable = Paragraph(
            f"<font size=20 color='#0284C7'>🏢</font><br/><font size=8.5><b>SUPERVISIÓN</b><br/>LIMPIEZA</font>",
            ParagraphStyle('HIcon', parent=body_bold, alignment=1)
        )

    header_table_data = [
        [
            logo_flowable,
            Paragraph(header_text, subtitle_style)
        ]
    ]
    header_table = Table(header_table_data, colWidths=[1.4*inch, 6.0*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0284C7")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # 2. DATOS GENERALES DE LA SUPERVISIÓN Y EL INMUEBLE
    story.append(Paragraph("1. DATOS GENERALES DEL SERVICIO Y EDIFICIO", section_heading))
    
    datos_gral_table_data = [
        [
            Paragraph("<b>Edificio / Sede:</b>", body_bold),
            Paragraph(str(cabecera.get("edificio_nombre", "")), body_style),
            Paragraph("<b>Fecha Inspección:</b>", body_bold),
            Paragraph(f"{cabecera.get('fecha_inspeccion', '')} ({cabecera.get('hora_inicio', '')} - {cabecera.get('hora_fin', '')})", body_style),
        ],
        [
            Paragraph("<b>Dirección:</b>", body_bold),
            Paragraph(str(cabecera.get("edificio_direccion", "")), body_style),
            Paragraph("<b>Turno Operativo:</b>", body_bold),
            Paragraph(str(cabecera.get("turno", "")), body_style),
        ],
        [
            Paragraph("<b>Administrador / Cliente:</b>", body_bold),
            Paragraph(str(cabecera.get("administrador_nombre", "") or "Administración de Edificio"), body_style),
            Paragraph("<b>Tipo Inspección:</b>", body_bold),
            Paragraph(str(cabecera.get("tipo_inspeccion", "")), body_style),
        ],
        [
            Paragraph("<b>Supervisor Responsable:</b>", body_bold),
            Paragraph(f"{cabecera.get('supervisor_nombre', '')} (DNI: {cabecera.get('supervisor_dni', '-')})", body_style),
            Paragraph("<b>Líder de Cuadrilla:</b>", body_bold),
            Paragraph(str(cabecera.get("lider_cuadrilla", "") or "-"), body_style),
        ],
        [
            Paragraph("<b>Dotación de Personal:</b>", body_bold),
            Paragraph(f"Programados: <b>{cabecera.get('personal_programado', 0)}</b> | Presentes: <b>{cabecera.get('personal_presente', 0)}</b> | Faltantes: <b>{cabecera.get('personal_faltante', 0)}</b>", body_style),
            Paragraph("<b>Cumplimiento EPP/Equipos:</b>", body_bold),
            Paragraph(f"EPP: {'✅ Conforme' if cabecera.get('epp_conforme') else '⚠️ Con Observaciones'} | Maquinaria: {'✅ Operativa' if cabecera.get('maquinaria_conforme') else '⚠️ Falla'}", body_style)
        ]
    ]
    
    datos_table = Table(datos_gral_table_data, colWidths=[1.5*inch, 2.7*inch, 1.4*inch, 1.8*inch])
    datos_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#F1F5F9")),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F8FAFC")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(datos_table)
    story.append(Spacer(1, 8))

    # 3. RESULTADO EJECUTIVO Y SEMÁFORO DE CALIDAD (5 NIVELES: ÓPTIMO, ADECUADO, ACEPTABLE, POR MEJORAR, NO CONFORME)
    score = float(cabecera.get("score_global", 0.0))
    calidad_info = clasificar_calidad(score)
    color_hex = calidad_info["color"]

    kpi_table_data = [
        [
            Paragraph(f"<font size=8 color='#64748B'>PUNTAJE GLOBAL DE CALIDAD</font><br/><font size=20 color='{color_hex}'><b>{score:.1f}%</b></font><br/><font size=9 color='{color_hex}'><b>{calidad_info['nivel']}</b></font>", ParagraphStyle('ScoreCard', alignment=1)),
            Paragraph(f"""
            <b>Dictamen de Calidad:</b> <font color='{color_hex}'><b>{calidad_info['estado']}</b></font><br/>
            <font size=7.5 color='#475569'>{calidad_info['descripcion']}</font><br/>
            <font size=7.5>
            <b>Ítems Conformes (C):</b> {cabecera.get('total_conformes', 0)} &nbsp;|&nbsp; 
            <b>Adecuados (AD):</b> {cabecera.get('total_adecuados', 0)} &nbsp;|&nbsp; 
            <b>Regulares (R):</b> {cabecera.get('total_regulares', 0)} &nbsp;|&nbsp; 
            <b>No Conformes (NC):</b> <font color='#EF4444'><b>{cabecera.get('total_no_conformes', 0)}</b></font> &nbsp;|&nbsp; 
            <b>No Aplica (NA):</b> {cabecera.get('total_no_aplica', 0)}
            </font>
            """, body_style)
        ]
    ]
    kpi_table = Table(kpi_table_data, colWidths=[2.5*inch, 4.9*inch])
    kpi_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor(color_hex)),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#FFFFFF")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    # 4. TABLA RESUMEN EJECUTIVO DE DESEMPEÑO POR ZONA / ÁREA
    story.append(Paragraph("2. RESUMEN EJECUTIVO DE DESEMPEÑO POR ZONA / ÁREA", section_heading))
    story.append(Paragraph("Consolidado porcentual y dictamen técnico de calidad por cada zona auditada del inmueble.", body_style))
    story.append(Spacer(1, 4))

    areas_dict = {}
    for d in detalles:
        area_nombre = d["nombre_area"]
        if area_nombre not in areas_dict:
            areas_dict[area_nombre] = []
        areas_dict[area_nombre].append(d)

    resumen_table_rows = [
        [
            Paragraph("<b>Zona / Área Auditada</b>", th_style),
            Paragraph("<b>C</b>", th_center),
            Paragraph("<b>AD</b>", th_center),
            Paragraph("<b>R</b>", th_center),
            Paragraph("<b>NC</b>", th_center),
            Paragraph("<b>NA</b>", th_center),
            Paragraph("<b>Puntaje</b>", th_center),
            Paragraph("<b>Dictamen de Calidad</b>", th_center)
        ]
    ]

    area_scores_calc = {}
    for area_nom, items in areas_dict.items():
        a_c = sum(1 for it in items if it["calificacion"] == "C")
        a_ad = sum(1 for it in items if it["calificacion"] in ["AD", "A"])
        a_r = sum(1 for it in items if it["calificacion"] == "R")
        a_nc = sum(1 for it in items if it["calificacion"] == "NC")
        a_na = sum(1 for it in items if it["calificacion"] == "NA")
        a_pts = sum(it["puntos"] for it in items if it["puntos"] is not None)
        a_pos = (a_c + a_ad + a_r + a_nc) * 100
        
        if a_pos > 0:
            a_sc = (a_pts / a_pos * 100.0)
            a_cal = clasificar_calidad(a_sc)
            area_scores_calc[area_nom] = (a_sc, a_cal, False)
            nc_display = f"<font color='#EF4444'><b>{a_nc}</b></font>" if a_nc > 0 else "0"
            score_display = f"<font color='{a_cal['color']}'><b>{a_sc:.1f}%</b></font>"
            dictamen_display = f"<font color='{a_cal['color']}'><b>{a_cal['nivel']}</b></font> <font size=6.5 color='#475569'>({a_cal['estado']})</font>"
        else:
            # Si todos los ítems fueron marcados como N.A. (no aplica a esta inspección)
            a_cal = {"nivel": "N.A.", "color": "#64748B", "estado": "No Aplica"}
            area_scores_calc[area_nom] = (None, a_cal, True)
            nc_display = "0"
            score_display = "<font color='#64748B'><b>N.A.</b></font>"
            dictamen_display = "<font color='#64748B'><b>N.A.</b></font> <font size=6.5 color='#64748B'>(No Aplica)</font>"

        resumen_table_rows.append([
            Paragraph(f"<b>{area_nom}</b>", body_style),
            Paragraph(str(a_c), ParagraphStyle('C1', parent=body_style, alignment=1)),
            Paragraph(str(a_ad), ParagraphStyle('C_ad', parent=body_style, alignment=1)),
            Paragraph(str(a_r), ParagraphStyle('C2', parent=body_style, alignment=1)),
            Paragraph(nc_display, ParagraphStyle('C3', parent=body_style, alignment=1)),
            Paragraph(str(a_na), ParagraphStyle('C4', parent=body_style, alignment=1)),
            Paragraph(score_display, ParagraphStyle('C5', parent=body_style, alignment=1)),
            Paragraph(dictamen_display, ParagraphStyle('C6', parent=body_style, alignment=1))
        ])

    resumen_table = Table(resumen_table_rows, colWidths=[2.6*inch, 0.4*inch, 0.4*inch, 0.4*inch, 0.4*inch, 0.4*inch, 0.9*inch, 1.9*inch])
    resumen_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(resumen_table)
    story.append(Spacer(1, 10))

    # 5. TABLA DE EVALUACIÓN DETALLADA POR CRITERIOS TÉCNICOS
    story.append(Paragraph("3. EVALUACIÓN DETALLADA POR CRITERIOS TÉCNICOS", section_heading))
    story.append(Paragraph("<b>Criterios Técnicos:</b> Conforme (C: 100 pts) &nbsp;|&nbsp; Adecuado (AD: 80 pts) &nbsp;|&nbsp; Regular (R: 60 pts) &nbsp;|&nbsp; No Conforme (NC: 0 pts) &nbsp;|&nbsp; No Aplica (NA)", body_style))
    story.append(Spacer(1, 3))

    eval_table_rows = [
        [
            Paragraph("<b>Área / Criterio Técnico Evaluado</b>", th_style),
            Paragraph("<b>Calificación</b>", th_center),
            Paragraph("<b>Pts</b>", th_center),
            Paragraph("<b>Observaciones Técnicas / Hallazgo Puntual</b>", th_style)
        ]
    ]

    for area_nom, items in areas_dict.items():
        score_info = area_scores_calc.get(area_nom, (None, {"nivel": "N.A.", "color": "#64748B", "estado": "No Aplica"}, True))
        a_sc, a_cal, is_na = score_info
        if is_na:
            zona_header = f"<b>{area_nom.upper()}</b> &nbsp;&nbsp;&nbsp;&nbsp; <font size=7.5 color='#64748B'><b>[Puntaje Zona: N.A. — No Aplica]</b></font>"
        else:
            zona_header = f"<b>{area_nom.upper()}</b> &nbsp;&nbsp;&nbsp;&nbsp; <font size=7.5 color='{a_cal['color']}'><b>[Puntaje Zona: {a_sc:.1f}% — {a_cal['nivel']}]</b></font>"
        eval_table_rows.append([
            Paragraph(zona_header, ParagraphStyle('AreaH', parent=body_bold, textColor=colors.HexColor("#0284C7"))),
            "", "", ""
        ])
        for it in items:
            calif = it["calificacion"]
            badge_style = badge_c if calif == "C" else (badge_ad if calif in ["AD", "A"] else (badge_r if calif == "R" else (badge_nc if calif == "NC" else badge_na)))
            pts_str = f"{it['puntos']:.0f}" if it['puntos'] is not None else "-"
            obs_str = it.get("observacion", "") or "-"
            
            calif_texto = "Conforme (C)" if calif == "C" else ("Adecuado (AD)" if calif in ["AD", "A"] else ("Regular (R)" if calif == "R" else ("No Conforme (NC)" if calif == "NC" else "N/A")))

            eval_table_rows.append([
                Paragraph(f"<b>{it['item_criterio']}</b>", body_style),
                Paragraph(calif_texto, badge_style),
                Paragraph(pts_str, ParagraphStyle('Pts', parent=body_style, alignment=1)),
                Paragraph(obs_str, body_style)
            ])

    eval_table = Table(eval_table_rows, colWidths=[2.8*inch, 1.2*inch, 0.5*inch, 2.9*inch], repeatRows=1)
    
    table_styles = [
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]

    current_row = 1
    for area_nom, items in areas_dict.items():
        table_styles.append(('SPAN', (0, current_row), (3, current_row)))
        table_styles.append(('BACKGROUND', (0, current_row), (3, current_row), colors.HexColor("#E0F2FE")))
        table_styles.append(('TOPPADDING', (0, current_row), (3, current_row), 3.5))
        table_styles.append(('BOTTOMPADDING', (0, current_row), (3, current_row), 3.5))
        current_row += 1 + len(items)

    eval_table.setStyle(TableStyle(table_styles))
    story.append(eval_table)
    story.append(Spacer(1, 10))

    # 6. MATRIZ DE INCIDENCIAS Y PLAN DE ACCIÓN CORRECTIVO
    if incidencias:
        story.append(KeepTogether([
            Paragraph("4. PLAN DE ACCIÓN Y MATRIZ DE NO CONFORMIDADES (CAPA)", section_heading),
            Paragraph("Detalle de observaciones detectadas que requieren subsanación y seguimiento por la supervisión.", body_style),
            Spacer(1, 4)
        ]))

        inc_rows = [
            [
                Paragraph("<b>Área</b>", th_style),
                Paragraph("<b>Descripción del Hallazgo</b>", th_style),
                Paragraph("<b>Severidad</b>", th_center),
                Paragraph("<b>Acción Correctiva Inmediata</b>", th_style),
                Paragraph("<b>Plazo</b>", th_center),
                Paragraph("<b>Responsable</b>", th_style)
            ]
        ]
        for inc in incidencias:
            sev = inc.get("severidad", "Media")
            sev_color = "#EF4444" if sev in ["Alta", "Inmediata", "Crítica"] else ("#F59E0B" if sev == "Media" else "#10B981")
            
            inc_rows.append([
                Paragraph(str(inc.get("area_nombre", "")), body_style),
                Paragraph(str(inc.get("descripcion_hallazgo", "")), body_style),
                Paragraph(f"<font color='{sev_color}'><b>{sev}</b></font>", ParagraphStyle('Sev', parent=body_style, alignment=1)),
                Paragraph(str(inc.get("accion_correctiva", "")), body_style),
                Paragraph(str(inc.get("plazo_subsanacion", "24 hrs")), ParagraphStyle('Plz', parent=body_style, alignment=1)),
                Paragraph(str(inc.get("responsable", "")), body_style)
            ])

        inc_table = Table(inc_rows, colWidths=[1.3*inch, 2.0*inch, 0.8*inch, 1.8*inch, 0.7*inch, 0.8*inch])
        inc_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(inc_table)
        story.append(Spacer(1, 10))

    # 7. OBSERVACIONES GENERALES Y CONCLUSIONES
    obs_gral = cabecera.get("observaciones_generales")
    if obs_gral:
        story.append(KeepTogether([
            Paragraph("5. OBSERVACIONES GENERALES Y RECOMENDACIONES", section_heading),
            Paragraph(str(obs_gral), body_style),
            Spacer(1, 8)
        ]))

    # 8. REGISTRO FOTOGRÁFICO DE EVIDENCIAS Y CONTROL DE CALIDAD (DISTINCIÓN CAPA VS REGISTRO GENERAL)
    if fotos:
        story.append(PageBreak())
        story.append(Paragraph("6. REGISTRO FOTOGRÁFICO DE EVIDENCIAS Y CONTROL DE CALIDAD", section_heading))
        story.append(Paragraph("Registro visual de auditoría con distinción entre evidencias de no conformidades (CAPA) y control de calidad general.", body_style))
        story.append(Spacer(1, 6))

        # Rutas de fotos de incidencias para identificación segura
        rutas_incidencias = set()
        for inc in incidencias:
            r_inc = inc.get("foto_hallazgo_ruta") or inc.get("foto_ruta")
            if r_inc:
                rutas_incidencias.add(os.path.normpath(r_inc))
            for f_sub in inc.get("fotos", []):
                if f_sub:
                    rutas_incidencias.add(os.path.normpath(f_sub))

        fotos_capa = []
        fotos_calidad = []
        for f in fotos:
            ruta_norm = os.path.normpath(f.get("archivo_ruta", ""))
            origen_f = str(f.get("origen", "")).upper()
            tipo_f = str(f.get("tipo_evidencia", "")).upper()
            if origen_f == "CAPA" or ruta_norm in rutas_incidencias or "CAPA" in tipo_f or "INCIDENCIA" in origen_f:
                fotos_capa.append(f)
            else:
                fotos_calidad.append(f)

            # Incorporar también fotos adicionales / complementarias asociadas a esta evidencia
            for sub_f in f.get("fotos_adicionales", []):
                sub_r_norm = os.path.normpath(sub_f.get("archivo_ruta", ""))
                sub_origen = str(sub_f.get("origen", "")).upper()
                sub_tipo = str(sub_f.get("tipo_evidencia", "")).upper()
                sub_dict = dict(sub_f)
                if not sub_dict.get("area_nombre"):
                    sub_dict["area_nombre"] = f.get("area_nombre", "General")
                sub_dict["es_adicional"] = True
                if sub_origen == "CAPA" or sub_r_norm in rutas_incidencias or "CAPA" in sub_tipo or "INCIDENCIA" in sub_origen or origen_f == "CAPA":
                    fotos_capa.append(sub_dict)
                else:
                    fotos_calidad.append(sub_dict)

        max_foto_w = 3.4 * inch
        max_foto_h = 2.3 * inch

        def _generar_tabla_fotos(lista_f, es_capa=False):
            cells = []
            for f in lista_f:
                ruta_foto = f.get("archivo_ruta", "")
                if os.path.exists(ruta_foto):
                    try:
                        with PILImage.open(ruta_foto) as p_img:
                            # 1. Asegurar orientación EXIF física (vertical u horizontal)
                            p_img_corr = ImageOps.exif_transpose(p_img)
                            orig_w, orig_h = p_img_corr.size

                            es_vertical = orig_h > orig_w
                            if es_vertical:
                                # Proporciones optimizadas para fotos verticales:
                                max_w = 2.6 * inch
                                max_h = 2.85 * inch
                            else:
                                # Proporciones optimizadas para fotos horizontales:
                                max_w = 3.4 * inch
                                max_h = 2.3 * inch

                            scale = min(max_w / orig_w, max_h / orig_h)
                            final_w = orig_w * scale
                            final_h = orig_h * scale

                            # Exportar a BytesIO para garantizar que ReportLab dibuje la imagen
                            # con la orientación ya transpuesta (sin depender de EXIF en ReportLab)
                            img_buf = io.BytesIO()
                            if p_img_corr.mode in ("RGBA", "P"):
                                p_img_corr = p_img_corr.convert("RGB")
                            p_img_corr.save(img_buf, format="JPEG", quality=88)
                            img_buf.seek(0)

                        img_flowable = Image(img_buf, width=final_w, height=final_h)
                        img_flowable.hAlign = 'CENTER'

                        area_f = f.get("area_nombre", "General")
                        desc_f = f.get("descripcion", "")
                        tipo_f = f.get("tipo_evidencia", "Evidencia")
                        es_adic = f.get("es_adicional") or f.get("origen") == "FOTO_ADICIONAL"
                        tag_adic = " (Adicional)" if es_adic else ""

                        if es_capa:
                            caption_text = f"<b><font color='#DC2626'>[INCIDENCIA / CAPA{tag_adic}]</font> {area_f}:</b> <font color='#1E293B'>{desc_f}</font>"
                        else:
                            caption_text = f"<b><font color='#0284C7'>[CONTROL DE CALIDAD{tag_adic}]</font> {tipo_f} — {area_f}:</b> <font color='#475569'>{desc_f}</font>"

                        cell_content = [
                            img_flowable,
                            Spacer(1, 3),
                            Paragraph(caption_text, body_style)
                        ]
                        cells.append(cell_content)
                    except Exception:
                        pass

            if not cells:
                return None

            foto_table_data = []
            for i in range(0, len(cells), 2):
                row = [cells[i]]
                if i + 1 < len(cells):
                    row.append(cells[i+1])
                else:
                    row.append("")
                foto_table_data.append(row)

            foto_table = Table(foto_table_data, colWidths=[3.7*inch, 3.7*inch])
            foto_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            return foto_table

        # 6.1 Incidencias / CAPA
        if fotos_capa:
            story.append(KeepTogether([
                Paragraph("6.1 Evidencias Fotográficas de Incidencias / No Conformidades (CAPA)", sub_heading),
                Paragraph("Fotografías vinculadas al Registro de Incidencias que sustentan hallazgos para acción correctiva:", body_style),
                Spacer(1, 4)
            ]))
            t_capa = _generar_tabla_fotos(fotos_capa, es_capa=True)
            if t_capa:
                story.append(t_capa)
                story.append(Spacer(1, 6))

        # 6.2 Control de Calidad
        if fotos_calidad:
            num_cc = "6.2" if fotos_capa else "6.1"
            story.append(KeepTogether([
                Paragraph(f"{num_cc} Registro Fotográfico de Control de Calidad e Inspección General", sub_heading),
                Paragraph("Fotografías de supervisión rutinaria (Antes / Después / Panorámica General) registradas en campo:", body_style),
                Spacer(1, 4)
            ]))
            t_calidad = _generar_tabla_fotos(fotos_calidad, es_capa=False)
            if t_calidad:
                story.append(t_calidad)
                story.append(Spacer(1, 6))

    # 8. SECCIÓN 6: ACTA DE CONFORMIDAD Y FIRMAS (CONDICIONADA POR OPCIÓN DE HABILITACIÓN)
    incluir_firmas = cabecera.get("incluir_firmas", 1)
    if int(incluir_firmas) == 1:
        firma_supervisor_elem = Paragraph("<br/><br/><br/>_______________________________<br/><b>Firma del Supervisor</b>", ParagraphStyle('F1', parent=body_style, alignment=1))
        firma_cliente_elem = Paragraph("<br/><br/><br/>_______________________________<br/><b>Firma / Sello de Recepción</b>", ParagraphStyle('F2', parent=body_style, alignment=1))

        # Si hay firma en base64 del supervisor (con proporción original)
        if cabecera.get("firma_supervisor_data") and cabecera["firma_supervisor_data"].startswith("data:image"):
            try:
                b64_data = cabecera["firma_supervisor_data"].split(",")[1]
                firma_bytes = base64.b64decode(b64_data)
                with PILImage.open(io.BytesIO(firma_bytes)) as f_img:
                    fw, fh = f_img.size
                    scale_f = min((2.2 * inch) / fw, (0.85 * inch) / fh)
                    fw_f = fw * scale_f
                    fh_f = fh * scale_f
                firma_sup_img = Image(io.BytesIO(firma_bytes), width=fw_f, height=fh_f)
                firma_supervisor_elem = [firma_sup_img, Paragraph("<br/><b>Supervisor Responsable</b>", ParagraphStyle('F1B', parent=body_style, alignment=1))]
            except Exception:
                pass

        # Si hay firma del cliente (con proporción original)
        if cabecera.get("firma_cliente_data") and cabecera["firma_cliente_data"].startswith("data:image"):
            try:
                b64_data = cabecera["firma_cliente_data"].split(",")[1]
                firma_cli_bytes = base64.b64decode(b64_data)
                with PILImage.open(io.BytesIO(firma_cli_bytes)) as f_img:
                    fw, fh = f_img.size
                    scale_f = min((2.2 * inch) / fw, (0.85 * inch) / fh)
                    fw_f = fw * scale_f
                    fh_f = fh * scale_f
                firma_cli_img = Image(io.BytesIO(firma_cli_bytes), width=fw_f, height=fh_f)
                firma_cliente_elem = [firma_cli_img, Paragraph("<br/><b>Recepción / Administración</b>", ParagraphStyle('F2B', parent=body_style, alignment=1))]
            except Exception:
                pass

        firmas_table_data = [
            [
                firma_supervisor_elem,
                firma_cliente_elem
            ],
            [
                Paragraph(f"<b>{cabecera.get('supervisor_nombre', '')}</b><br/>Supervisor de Operaciones & Calidad<br/>DNI: {cabecera.get('supervisor_dni', '-')}", ParagraphStyle('FSup', parent=body_style, alignment=1)),
                Paragraph(f"<b>{cabecera.get('firmante_cliente_nombre', '') or cabecera.get('administrador_nombre', 'Administración')}</b><br/>{cabecera.get('firmante_cliente_cargo', '') or 'Administrador / Representante de Edificio'}<br/>Conformidad de Supervisión", ParagraphStyle('FCli', parent=body_style, alignment=1))
            ]
        ]

        firmas_table = Table(firmas_table_data, colWidths=[3.7*inch, 3.7*inch])
        firmas_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))

        story.append(KeepTogether([
            Paragraph("7. ACTA DE CONFORMIDAD Y FIRMAS", section_heading),
            Spacer(1, 4),
            firmas_table
        ]))

    # Construir el documento con el NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
