"""
Módulo de Informes Consolidados Mensuales en PDF:
Genera un informe gerencial consolidado para Juntas de Propietarios y Administradores de Edificios,
agrupando todas las auditorías del mes con gráficos evolutivos, cumplimiento de cuadrilla e incidencias.
"""
import io
import os
import streamlit as st
import pandas as pd
from datetime import datetime, date

from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

from config import COMPANY_NAME, FORMAT_CODE, FORMAT_VERSION, clasificar_calidad
from database import (
    obtener_supervisiones_mes, obtener_lista_edificios, obtener_parametro,
    obtener_todas_incidencias, obtener_logo_empresa
)
from modules.reportes_pdf import NumberedCanvas


def generar_pdf_consolidado_mensual(edificio_nombre: str, anio: int, mes: int, supervisiones: list) -> bytes:
    """Genera el documento PDF formal consolidado mensual con ReportLab."""
    empresa_nombre = obtener_parametro("empresa_nombre", COMPANY_NAME)
    empresa_subtitulo = obtener_parametro("empresa_subtitulo", "Control de Calidad, Estándares de Higiene y Cumplimiento de Servicio")
    formato_cod = obtener_parametro("formato_codigo", FORMAT_CODE)
    formato_ver = obtener_parametro("formato_version", FORMAT_VERSION)

    meses_nombres = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    periodo_str = f"{meses_nombres[mes]} {anio}"

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
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1E293B")
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    th_style = ParagraphStyle(
        'TableHeader',
        parent=body_bold,
        textColor=colors.white
    )
    section_heading = ParagraphStyle(
        'SecHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#0369A1"),
        spaceBefore=8,
        spaceAfter=4
    )

    story = []

    # 1. ENCABEZADO FORMAL
    logo_info = obtener_logo_empresa()
    logo_flowable = None
    if logo_info and logo_info.get("path") and os.path.exists(logo_info["path"]):
        try:
            with PILImage.open(logo_info["path"]) as p_img:
                lw, lh = p_img.size
                scale_l = min((2.0 * inch) / lw, (0.45 * inch) / lh)
                final_lw = max(lw * scale_l, 10)
                final_lh = max(lh * scale_l, 10)
            logo_flowable = Image(logo_info["path"], width=final_lw, height=final_lh)
        except Exception:
            logo_flowable = None

    if logo_flowable:
        col0_content = [
            logo_flowable,
            Spacer(1, 2),
            Paragraph(f"<b><font size=7 color='#0284C7'>{empresa_nombre.upper()}</font></b>", ParagraphStyle('H1_Sub', parent=body_bold, alignment=1))
        ]
    else:
        col0_content = Paragraph(f"<b>🏢 {empresa_nombre.upper()}</b>", ParagraphStyle('H1', parent=body_bold, fontSize=9.5, textColor=colors.HexColor("#0284C7")))

    header_data = [
        [
            col0_content,
            Paragraph("<b>INFORME CONSOLIDADO MENSUAL DE CALIDAD</b><br/><font size=7 color='#64748B'>SERVICIOS DE LIMPIEZA Y FACILITY MANAGEMENT</font>", title_style),
            Paragraph(f"<b>CÓDIGO:</b> {formato_cod}-MES<br/><b>VERSIÓN:</b> {formato_ver}<br/><b>PERIODO:</b> {periodo_str}", ParagraphStyle('H3', parent=body_style, fontSize=7.5, alignment=2))
        ]
    ]
    t_header = Table(header_data, colWidths=[2.2*inch, 3.2*inch, 2.1*inch])
    t_header.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0284C7")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    # 2. DATOS DEL INMUEBLE Y PERIODO
    info_data = [
        [
            Paragraph("<b>Edificio / Cliente:</b>", body_bold),
            Paragraph(f"<b>{edificio_nombre}</b>", body_style),
            Paragraph("<b>Periodo Evaluado:</b>", body_bold),
            Paragraph(periodo_str, body_style)
        ],
        [
            Paragraph("<b>Fecha de Emisión:</b>", body_bold),
            Paragraph(datetime.now().strftime("%d/%m/%Y"), body_style),
            Paragraph("<b>Total Auditorías:</b>", body_bold),
            Paragraph(str(len(supervisiones)), body_style)
        ]
    ]
    t_info = Table(info_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 2.0*inch])
    t_info.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F1F5F9")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F1F5F9")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 10))

    # Métricas consolidadas
    prom_score = sum(s["score_global"] for s in supervisiones) / len(supervisiones) if supervisiones else 0
    clasif = clasificar_calidad(prom_score)
    tot_nc = sum(s.get("total_no_conformes", 0) for s in supervisiones)
    prog_tot = sum(s.get("personal_programado", 0) for s in supervisiones)
    pres_tot = sum(s.get("personal_presente", 0) for s in supervisiones)
    tasa_dot = (pres_tot / prog_tot * 100.0) if prog_tot > 0 else 100.0

    # 3. RESUMEN EJECUTIVO
    story.append(Paragraph("1. RESUMEN EJECUTIVO Y DESEMPEÑO DEL PERIODO", section_heading))
    kpi_table_data = [
        [
            Paragraph("<b>Índice Calidad Promedio</b>", body_bold),
            Paragraph("<b>Nivel Alcanzado</b>", body_bold),
            Paragraph("<b>Cumplimiento Cuadrilla</b>", body_bold),
            Paragraph("<b>Total No Conformidades</b>", body_bold)
        ],
        [
            Paragraph(f"<font size=12 color='{clasif['color']}'><b>{prom_score:.1f}%</b></font>", ParagraphStyle('K1', parent=body_style, alignment=1)),
            Paragraph(f"<b>{clasif['nivel']}</b><br/><font size=7 color='#64748B'>{clasif['estado']}</font>", ParagraphStyle('K2', parent=body_style, alignment=1)),
            Paragraph(f"<b>{tasa_dot:.1f}%</b><br/><font size=7 color='#64748B'>{pres_tot} de {prog_tot} operarios</font>", ParagraphStyle('K3', parent=body_style, alignment=1)),
            Paragraph(f"<font size=12 color='#EF4444'><b>{int(tot_nc)}</b></font>", ParagraphStyle('K4', parent=body_style, alignment=1))
        ]
    ]
    t_kpi = Table(kpi_table_data, colWidths=[1.87*inch, 1.87*inch, 1.87*inch, 1.87*inch])
    t_kpi.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0284C7")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 10))

    # 4. TABLA DETALLADA DE AUDITORÍAS REALIZADAS EN EL MES
    story.append(Paragraph("2. REGISTRO CRONOLÓGICO DE AUDITORÍAS REALIZADAS", section_heading))
    aud_rows = [
        [
            Paragraph("<b>Código</b>", th_style),
            Paragraph("<b>Fecha</b>", th_style),
            Paragraph("<b>Tipo de Inspección</b>", th_style),
            Paragraph("<b>Turno</b>", th_style),
            Paragraph("<b>Supervisor</b>", th_style),
            Paragraph("<b>Calificación</b>", th_style),
            Paragraph("<b>Estado</b>", th_style)
        ]
    ]
    for s in supervisiones:
        sc = s["score_global"]
        col_sc = "#10B981" if sc >= 90 else ("#0284C7" if sc >= 80 else "#EF4444")
        aud_rows.append([
            Paragraph(s["codigo_informe"], body_style),
            Paragraph(s["fecha_inspeccion"], body_style),
            Paragraph(s["tipo_inspeccion"], body_style),
            Paragraph(s.get("turno", ""), body_style),
            Paragraph(s.get("supervisor_nombre", ""), body_style),
            Paragraph(f"<font color='{col_sc}'><b>{sc:.1f}%</b></font>", ParagraphStyle('ScoreCol', parent=body_style, alignment=1)),
            Paragraph(s.get("nivel_calidad", ""), body_style)
        ])

    t_aud = Table(aud_rows, colWidths=[1.1*inch, 0.8*inch, 1.8*inch, 1.2*inch, 1.2*inch, 0.7*inch, 0.7*inch])
    t_aud.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_aud)
    story.append(Spacer(1, 15))

    # 5. FIRMAS DE CONFORMIDAD
    story.append(KeepTogether([
        Paragraph("3. CONFORMIDAD Y VALIDACIÓN TÉCNICA", section_heading),
        Spacer(1, 10),
        Table([
            [
                Paragraph("____________________________________________<br/><b>SUPERVISIÓN / OPERACIONES</b><br/>" + empresa_nombre, ParagraphStyle('F1', parent=body_style, alignment=1)),
                Paragraph("____________________________________________<br/><b>ADMINISTRACIÓN DEL EDIFICIO</b><br/>" + edificio_nombre, ParagraphStyle('F2', parent=body_style, alignment=1))
            ]
        ], colWidths=[3.7*inch, 3.7*inch], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')])
    ]))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


def render_modulo_consolidados():
    """Renderiza la interfaz para generar el informe mensual consolidado."""
    st.markdown("""
        <div class="header-hero">
            <h1>📑 Informe Consolidado Mensual de Calidad</h1>
            <p>Generación de reportes ejecutivos mensuales en PDF para Juntas de Propietarios y Gerencias de Inmuebles.</p>
            <div class="header-badges">
                <span class="badge-tag">📊 Informe Mensual</span>
                <span class="badge-tag">🏢 Resumen para Clientes</span>
                <span class="badge-tag">📄 PDF Ejecutivo</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    edificios = obtener_lista_edificios(solo_activos=False)
    if not edificios:
        st.info("No hay edificios registrados.")
        return

    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        edif_sel = st.selectbox("Seleccionar Edificio:", [e["nombre"] for e in edificios], key="cons_edif")
    with col_c2:
        mes_sel = st.selectbox("Mes:", list(range(1, 13)), index=datetime.now().month - 1, format_func=lambda m: ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"][m-1], key="cons_mes")
    with col_c3:
        anio_sel = st.number_input("Año:", min_value=2020, max_value=2035, value=datetime.now().year, key="cons_anio")

    supervisiones = obtener_supervisiones_mes(edif_sel, int(anio_sel), int(mes_sel))

    if not supervisiones:
        st.warning(f"⚠️ No se encontraron supervisiones para '{edif_sel}' en el periodo seleccionado ({mes_sel:02d}/{anio_sel}).")
        st.info("💡 Asegúrese de haber registrado al menos una supervisión en este mes para generar el consolidado.")
        return

    st.success(f"✅ Se encontraron **{len(supervisiones)} supervisiones** para '{edif_sel}' en este periodo.")

    # Resumen en pantalla
    df_prev = pd.DataFrame(supervisiones)[[
        "codigo_informe", "fecha_inspeccion", "tipo_inspeccion", "supervisor_nombre",
        "score_global", "nivel_calidad", "personal_programado", "personal_presente"
    ]]
    df_prev.columns = ["Código", "Fecha", "Tipo Inspección", "Supervisor", "Score (%)", "Nivel", "Prog.", "Pres."]
    st.dataframe(df_prev, use_container_width=True, hide_index=True)

    # Botón para generar y descargar el PDF
    pdf_bytes = generar_pdf_consolidado_mensual(edif_sel, int(anio_sel), int(mes_sel), supervisiones)

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn2:
        st.download_button(
            label="📄 Descargar Informe Mensual PDF",
            data=pdf_bytes,
            file_name=f"Informe_Consolidado_{edif_sel.replace(' ', '_')}_{anio_sel}_{mes_sel:02d}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
