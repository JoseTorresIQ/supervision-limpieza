"""
Módulo de Configuración y Constantes: Sistema de Supervisión de Limpieza de Edificios.
Estándares Internacionales ISSA / OSHA / ISO 9001:2015 / Ley N° 29783 (SST).
"""
import os
from pathlib import Path

# Rutas Base del Proyecto
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"

# Asegurar directorios esenciales
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Metadatos del Sistema
SYSTEM_TITLE = "CLEANFACILITY PRO"
SYSTEM_SUBTITLE = "Sistema de Gestión y Reporte de Supervisión de Limpieza de Edificios"
FORMAT_CODE = "FOR-SGI-LMP-04"
FORMAT_VERSION = "2.4 - 2026"
COMPANY_NAME = "SERVICIOS INTEGRALES DE LIMPIEZA Y FACILITY MANAGEMENT S.A.C."
NORMATIVE_REFERENCES = [
    "ISSA - Cleaning Industry Management Standard (CIMS)",
    "Ley N° 29783 - Seguridad y Salud en el Trabajo",
    "D.S. N° 005-2012-TR - Reglamento de Seguridad y Salud en el Trabajo",
    "NTP 900.058:2019 - Gestión de Residuos Sólidos (Código de Colores)",
    "ISO 9001:2015 - Sistema de Gestión de Calidad (Control de Servicios)"
]

# Tipos de Inspección
TIPOS_INSPECCION = [
    "Supervisión Rutinaria Diaria",
    "Supervisión Periódica Semanal",
    "Auditoría Mensual de Calidad",
    "Supervisión Inopinada / Nocturna",
    "Entrega / Recepción de Turno",
    "Inspección por Reclamo / Requerimiento Especial",
    "Recepción de Limpieza Post-Obra / Profunda"
]

# Turnos Operativos
TURNOS_TRABAJO = [
    "Turno Mañana (07:00 - 15:00)",
    "Turno Tarde (15:00 - 23:00)",
    "Turno Noche (23:00 - 07:00)",
    "Jornada Completa / Horario Central"
]

# Calificaciones y Escalas
PUNTAJES = {
    "C": {"nombre": "Conforme / Impecable", "puntos": 100, "color": "#10B981", "badge": "🟢 C"},
    "AD": {"nombre": "Adecuado", "puntos": 80, "color": "#0284C7", "badge": "🔵 AD"},
    "R": {"nombre": "Regular / Obs. Menor", "puntos": 60, "color": "#F59E0B", "badge": "🟡 R"},
    "NC": {"nombre": "No Conforme / Crítico", "puntos": 0, "color": "#EF4444", "badge": "🔴 NC"},
    "NA": {"nombre": "No Aplica en Sede", "puntos": None, "color": "#94A3B8", "badge": "⚪ N/A"}
}
PUNTAJES["A"] = PUNTAJES["AD"]

# Niveles de Calidad Global
def clasificar_calidad(score: float):
    if score >= 97.0:
        return {
            "nivel": "ÓPTIMO",
            "estado": "APROBADO CON DISTINCIÓN",
            "color": "#10B981",
            "descripcion": "El servicio se encuentra en nivel óptimo de calidad y pulcritud."
        }
    elif score >= 92.0:
        return {
            "nivel": "ADECUADO",
            "estado": "APROBADO SATISFACTORIO",
            "color": "#0284C7",
            "descripcion": "El servicio cumple adecuadamente con los estándares de limpieza."
        }
    elif score >= 87.0:
        return {
            "nivel": "ACEPTABLE",
            "estado": "APROBADO CON OBSERVACIONES",
            "color": "#0D9488",
            "descripcion": "Cumplimiento aceptable con oportunidades menores de mejora."
        }
    elif score >= 80.0:
        return {
            "nivel": "POR MEJORAR",
            "estado": "CONDICIONADO A MEJORA",
            "color": "#F59E0B",
            "descripcion": "Requiere plan de acción correctivo y refuerzo de cuadrilla."
        }
    else:
        return {
            "nivel": "NO CONFORME",
            "estado": "RECHAZADO / NO CONFORME",
            "color": "#EF4444",
            "descripcion": "No cumple con los estándares mínimos requeridos. Requiere intervención inmediata."
        }

# Áreas y Criterios Técnicos de Inspección en Limpieza de Edificios
CHECKLIST_AREAS = [
    {
        "id_area": "hall_lobby",
        "nombre": "1. Hall de Ingreso / Lobby / Recepción",
        "icono": "🏢",
        "criterios": [
            {
                "id": "lobby_pisos",
                "item": "Pisos y Zócalos",
                "descripcion": "Pisos (porcelanato, mármol o granito) limpios, abrillantados, sin huellas, polvo ni manchas pegadas."
            },
            {
                "id": "lobby_vidrios",
                "item": "Mamparas y Cristales de Acceso",
                "descripcion": "Vidrios, puertas batientes y mamparas transparentes sin marcas dactilares ni polvo en bordes."
            },
            {
                "id": "lobby_counter",
                "item": "Mobiliario y Mostrador de Recepción",
                "descripcion": "Mostrador, sillones de espera y mesas de centro despolvados y ordenados."
            },
            {
                "id": "lobby_tapetes",
                "item": "Tapetes Atrapapolvo y Ceniceros",
                "descripcion": "Alfombras de ingreso aspiradas y alineadas; papeleras/ceniceros vacíos y limpios."
            },
            {
                "id": "lobby_aroma",
                "item": "Aromatización y Ambiente",
                "descripcion": "Sensación de frescura, aroma agradable y libre de polvo en suspensión."
            }
        ]
    },
    {
        "id_area": "ascensores",
        "nombre": "2. Ascensores y Cabinas de Transporte",
        "icono": "🛗",
        "criterios": [
            {
                "id": "asc_botoneras",
                "item": "Botoneras y Pantallas Táctiles",
                "descripcion": "Botones de cabina e indicadores exteriores desinfectados, limpios y sin marcas de grasa."
            },
            {
                "id": "asc_acero",
                "item": "Paneles de Acero Inoxidable y Espejos",
                "descripcion": "Acero pulido con abrillantador (sin rayas de paño sucio); espejos impecables."
            },
            {
                "id": "asc_rieles",
                "item": "Rieles de Puertas de Piso y Cabina",
                "descripcion": "Canales y rieles de puertas aspirados, libres de polvo, pelusas o piedras."
            },
            {
                "id": "asc_piso",
                "item": "Piso de Cabina y Zócalos",
                "descripcion": "Piso desmanchado, lustrado y libre de residuos en las esquinas."
            },
            {
                "id": "asc_techo",
                "item": "Techo, Rejillas y Luminarias",
                "descripcion": "Techo y rejillas de ventilación libres de polvo acumulado y telarañas."
            }
        ]
    },
    {
        "id_area": "pasadizos",
        "nombre": "3. Pasadizos, Corredores y Áreas Comunes",
        "icono": "🚶‍♂️",
        "criterios": [
            {
                "id": "pas_pisos",
                "item": "Pisos y Mopado Uniforme",
                "descripcion": "Pisos barridos y mopados de manera uniforme sin marcas de charcos ni vetas de agua sucia."
            },
            {
                "id": "pas_paredes",
                "item": "Paredes, Zócalos y Guardapolvos",
                "descripcion": "Paredes y zócalos libres de salpicaduras de mopa, roces de zapatos y manchas."
            },
            {
                "id": "pas_puertas",
                "item": "Puertas de Oficinas / Deptos y Manijas",
                "descripcion": "Manijas y chapas desinfectadas; puertas de acceso libres de polvo en marcos."
            },
            {
                "id": "pas_extintores",
                "item": "Gabinetes, Extintores y Señalética",
                "descripcion": "Gabinetes contra incendio, extintores y señaléticas de emergencia limpios y visibles."
            },
            {
                "id": "pas_ventanas",
                "item": "Ventanas y Alféizares de Corredor",
                "descripcion": "Vidrios interiores y alféizares limpios sin acumulación de polvo exterior."
            }
        ]
    },
    {
        "id_area": "banos",
        "nombre": "4. Servicios Higiénicos (SS.HH. / Baños)",
        "icono": "🚻",
        "criterios": [
            {
                "id": "ssh_aparatos",
                "item": "Inodoros, Urinarios y Asientos",
                "descripcion": "Aparatos sanitarios desinfectados, desincrustados (sin sarro), limpios y aromatizados."
            },
            {
                "id": "ssh_lavamanos",
                "item": "Lavatorios, Grifería y Encimeras",
                "descripcion": "Griferías cromadas brillantes sin manchas de agua/cal; encimeras secas y limpias."
            },
            {
                "id": "ssh_espejos",
                "item": "Espejos y Repisas",
                "descripcion": "Espejos nítidos, secos y sin salpicaduras de jabón o gotas."
            },
            {
                "id": "ssh_insumos",
                "item": "Abastecimiento de Insumos (Papel/Jabón)",
                "descripcion": "Dispensadores de jabón líquido, papel higiénico y papel toalla al 100% abastecidos."
            },
            {
                "id": "ssh_tachos",
                "item": "Tachos de Basura y Bolsas",
                "descripcion": "Tachos con bolsa plástica nueva, limpios por dentro y fuera, con tapa funcional."
            },
            {
                "id": "ssh_pisos",
                "item": "Pisos, Juntas y Sumideros",
                "descripcion": "Pisos secos, juntas de azulejos libres de hongos/humedad y rejillas sin cabellos ni olores."
            }
        ]
    },
    {
        "id_area": "oficinas",
        "nombre": "5. Oficinas, Directorios y Zonas de Trabajo",
        "icono": "💼",
        "criterios": [
            {
                "id": "ofi_escritorios",
                "item": "Escritorios, Mesas y Estantes",
                "descripcion": "Superficies despolvadas con paño microfibra adecuado sin alterar documentos de trabajo."
            },
            {
                "id": "ofi_equipos",
                "item": "Equipos Informáticos y Teléfonos",
                "descripcion": "Teclados, monitores y teléfonos despolvados superficialmente con técnica segura."
            },
            {
                "id": "ofi_papeleras",
                "item": "Vaciado de Papeleras Individuales",
                "descripcion": "Papeleras individuales vaciadas oportunamente con recambio de bolsas."
            },
            {
                "id": "ofi_alfombras",
                "item": "Pisos Flotantes y/o Alfombras",
                "descripcion": "Pisos mopados / alfombras aspiradas a profundidad sin manchas de café o grasa."
            },
            {
                "id": "ofi_vidrios_int",
                "item": "Mamparas y Divisiones Internas",
                "descripcion": "Divisiones de vidrio o policarbonato limpias sin marcas dactilares."
            }
        ]
    },
    {
        "id_area": "escaleras",
        "nombre": "6. Escaleras de Emergencia y Barandas",
        "icono": "🪜",
        "criterios": [
            {
                "id": "esc_pasos",
                "item": "Peldaños, Contrapasos y Descansos",
                "descripcion": "Peldaños barridos y trapeados sin polvo en esquinas ni colillas/basura."
            },
            {
                "id": "esc_barandas",
                "item": "Pasamanos y Barandas de Seguridad",
                "descripcion": "Estructuras metálicas y pasamanos limpios, desinfectados y sin grasa."
            },
            {
                "id": "esc_puertas",
                "item": "Puertas Cortafuego y Brazos Hidráulicos",
                "descripcion": "Puertas limpias, barras antipánico desinfectadas y mecanismo sin acumulación de polvo."
            },
            {
                "id": "esc_despeje",
                "item": "Vía de Evacuación Despejada (SST)",
                "descripcion": "Vía 100% despejada, sin obstáculos, cajas, tachos o implementos de limpieza abandonados."
            }
        ]
    },
    {
        "id_area": "cuarto_basura",
        "nombre": "7. Cuarto de Basura y Gestión de Residuos",
        "icono": "🗑️",
        "criterios": [
            {
                "id": "res_contenedores",
                "item": "Lavado y Desinfección de Contenedores",
                "descripcion": "Contenedores rodantes limpios, desinfectados y con bolsa plástica de calibre adecuado."
            },
            {
                "id": "res_segregacion",
                "item": "Segregación y Código de Colores (NTP)",
                "descripcion": "Clasificación correcta de residuos según código de colores (Verde, Azul, Blanco, Negro, etc.)."
            },
            {
                "id": "res_pisos",
                "item": "Pisos, Paredes y Sumidero de Lavado",
                "descripcion": "Piso desengrasado con detergente industrial, sumidero con rejilla limpia."
            },
            {
                "id": "res_olores",
                "item": "Control de Olores y Vectores",
                "descripcion": "Uso de desinfectante neutro/clorado y neutralizador de olores; ausencia de moscas/plagas."
            }
        ]
    },
    {
        "id_area": "estacionamientos",
        "nombre": "8. Estacionamientos, Cocheras y Sótanos",
        "icono": "🚗",
        "criterios": [
            {
                "id": "est_rodadura",
                "item": "Calzada de Rodadura y Cajones",
                "descripcion": "Pisos barridos mecánicamente o con mopa industrial, sin hojas ni detritos."
            },
            {
                "id": "est_aceite",
                "item": "Desmanchado de Aceite y Combustible",
                "descripcion": "Tratamiento con absorbente y desengrasante en cajones con goteo vehicular."
            },
            {
                "id": "est_columnas",
                "item": "Columnas, Tuberías Aéreas y Luminarias",
                "descripcion": "Remoción periódica de telarañas y polvo en tuberías de agua/luz y números de cajón."
            },
            {
                "id": "est_tachos",
                "item": "Tachos y Zonas de Depósito Temporal",
                "descripcion": "Tachos perimétricos limpios y desocupados."
            }
        ]
    },
    {
        "id_area": "exteriores",
        "nombre": "9. Fachada, Cristales Exteriores y Rampas",
        "icono": "🌳",
        "criterios": [
            {
                "id": "ext_veredas",
                "item": "Veredas Perimetrales y Rampas",
                "descripcion": "Veredas exteriores y rampas vehiculares barridas o baldeadas sin grasa ni chicles."
            },
            {
                "id": "ext_cristales",
                "item": "Cristales y Letreros de Fachada (Baja Altura)",
                "descripcion": "Vidrios frontales limpios y marcos exteriores libres de telarañas y polvo."
            },
            {
                "id": "ext_jardineras",
                "item": "Jardineras y Accesos de Visita",
                "descripcion": "Zonas de transición libres de basura pequeña, papeles y hojas secas."
            }
        ]
    },
    {
        "id_area": "office_limpieza",
        "nombre": "10. Cuarto de Limpieza (Office) y Equipamiento",
        "icono": "🧹",
        "criterios": [
            {
                "id": "off_quimicos",
                "item": "Rotulado de Químicos y Hojas MSDS/FDS",
                "descripcion": "Productos químicos en envases rotulados con nombre y dilución; Fichas de Seguridad visibles."
            },
            {
                "id": "off_herramientas",
                "item": "Mopas, Trapos y Carros Moperos",
                "descripcion": "Mopas y paños lavados y colgados (código de colores); carros moperos limpios y ordenados."
            },
            {
                "id": "off_maquinas",
                "item": "Estado de Maquinarias (Lustradoras/Aspiradoras)",
                "descripcion": "Equipos limpios, cables inspeccionados sin cortes, discos de lavado en buen estado."
            },
            {
                "id": "off_orden",
                "item": "Orden General y Ausencia de Derrames",
                "descripcion": "Ambiente ventilado, estantes ordenados y libre de derrames químicos en el suelo."
            }
        ]
    }
]

# Control de EPPs Obligatorios
ITEMS_EPP = [
    {"id": "epp_uniforme", "item": "Uniforme Completo y Limpio (con Fotocheck visible)"},
    {"id": "epp_calzado", "item": "Zapatos / Botas de Seguridad con Suela Antideslizante"},
    {"id": "epp_guantes", "item": "Guantes de Nitrilo / Jebe de Caña Larga"},
    {"id": "epp_lentes", "item": "Lentes de Seguridad para Dosificación de Químicos"},
    {"id": "epp_mascarilla", "item": "Mascarilla / Respirador contra Vapores y Polvo"},
    {"id": "epp_senaletica", "item": "Uso Obligatorio de Señalética 'Piso Mojado'"}
]
