/**
 * CleanFacility Pro - Logic & Controller
 * Standalone Offline-First Building Cleaning Supervision System
 */

// Dataset de Áreas y Criterios Técnicos
// Dataset de Áreas y Criterios Técnicos (Estándar ISSA / ISO 9001:2015)
const AREAS_DATA = [
    {
        id: "hall_lobby",
        nombre: "1. Hall de Ingreso / Lobby / Recepción",
        criterios: [
            { id: "lobby_pisos", item: "Pisos y Zócalos", desc: "Pisos (porcelanato, mármol o granito) limpios, abrillantados, sin huellas, polvo ni manchas pegadas." },
            { id: "lobby_vidrios", item: "Mamparas y Cristales de Acceso", desc: "Vidrios, puertas batientes y mamparas transparentes sin marcas dactilares ni polvo en bordes." },
            { id: "lobby_counter", item: "Mobiliario y Mostrador de Recepción", desc: "Mostrador, sillones de espera y mesas de centro despolvados y ordenados." },
            { id: "lobby_tapetes", item: "Tapetes Atrapapolvo y Ceniceros", desc: "Alfombras de ingreso aspiradas y alineadas; papeleras/ceniceros vacíos y limpios." },
            { id: "lobby_aroma", item: "Aromatización y Ambiente", desc: "Sensación de frescura, aroma agradable y libre de polvo en suspensión." }
        ]
    },
    {
        id: "ascensores",
        nombre: "2. Ascensores y Cabinas de Transporte",
        criterios: [
            { id: "asc_botoneras", item: "Botoneras y Pantallas Táctiles", desc: "Botones de cabina e indicadores exteriores desinfectados, limpios y sin marcas de grasa." },
            { id: "asc_acero", item: "Paneles de Acero Inoxidable y Espejos", desc: "Acero pulido con abrillantador (sin rayas de paño sucio); espejos impecables." },
            { id: "asc_rieles", item: "Rieles de Puertas de Piso y Cabina", desc: "Canales y rieles de puertas aspirados, libres de polvo, pelusas o piedras." },
            { id: "asc_piso", item: "Piso de Cabina y Zócalos", desc: "Piso desmanchado, lustrado y libre de residuos en las esquinas." },
            { id: "asc_techo", item: "Techo, Rejillas y Luminarias", desc: "Techo y rejillas de ventilación libres de polvo acumulado y telarañas." }
        ]
    },
    {
        id: "pasadizos",
        nombre: "3. Pasadizos, Corredores y Áreas Comunes",
        criterios: [
            { id: "pas_pisos", item: "Pisos y Mopado Uniforme", desc: "Pisos barridos y mopados de manera uniforme sin marcas de charcos ni vetas de agua sucia." },
            { id: "pas_paredes", item: "Paredes, Zócalos y Guardapolvos", desc: "Paredes y zócalos libres de salpicaduras de mopa, roces de zapatos y manchas." },
            { id: "pas_puertas", item: "Puertas de Oficinas / Deptos y Manijas", desc: "Manijas y chapas desinfectadas; puertas de acceso libres de polvo en marcos." },
            { id: "pas_extintores", item: "Gabinetes, Extintores y Señalética", desc: "Gabinetes contra incendio, extintores y señaléticas de emergencia limpios y visibles." },
            { id: "pas_ventanas", item: "Ventanas y Alféizares de Corredor", desc: "Vidrios interiores y alféizares limpios sin acumulación de polvo exterior." }
        ]
    },
    {
        id: "banos",
        nombre: "4. Servicios Higiénicos (SS.HH. / Baños)",
        criterios: [
            { id: "ssh_aparatos", item: "Inodoros, Urinarios y Asientos", desc: "Aparatos sanitarios desinfectados, desincrustados (sin sarro), limpios y aromatizados." },
            { id: "ssh_lavamanos", item: "Lavatorios, Grifería y Encimeras", desc: "Griferías cromadas brillantes sin manchas de agua/cal; encimeras secas y limpias." },
            { id: "ssh_espejos", item: "Espejos y Repisas", desc: "Espejos nítidos, secos y sin salpicaduras de jabón o gotas." },
            { id: "ssh_insumos", item: "Abastecimiento de Insumos (Papel/Jabón)", desc: "Dispensadores de jabón líquido, papel higiénico y papel toalla al 100% abastecidos." },
            { id: "ssh_tachos", item: "Tachos de Basura y Bolsas", desc: "Tachos con bolsa plástica nueva, limpios por dentro y fuera, con tapa funcional." },
            { id: "ssh_pisos", item: "Pisos, Juntas y Sumideros", desc: "Pisos secos, juntas de azulejos libres de hongos/humedad y rejillas sin cabellos ni olores." }
        ]
    },
    {
        id: "oficinas",
        nombre: "5. Oficinas, Directorios y Zonas de Trabajo",
        criterios: [
            { id: "ofi_escritorios", item: "Escritorios, Mesas y Estantes", desc: "Superficies despolvadas con paño microfibra adecuado sin alterar documentos de trabajo." },
            { id: "ofi_equipos", item: "Equipos Informáticos y Teléfonos", desc: "Teclados, monitores y teléfonos despolvados superficialmente con técnica segura." },
            { id: "ofi_papeleras", item: "Vaciado de Papeleras Individuales", desc: "Papeleras individuales vaciadas oportunamente con recambio de bolsas." },
            { id: "ofi_alfombras", item: "Pisos Flotantes y/o Alfombras", desc: "Pisos mopados / alfombras aspiradas a profundidad sin manchas de café o grasa." },
            { id: "ofi_vidrios_int", item: "Mamparas y Divisiones Internas", desc: "Divisiones de vidrio o policarbonato limpias sin marcas dactilares." }
        ]
    },
    {
        id: "escaleras",
        nombre: "6. Escaleras de Emergencia y Barandas",
        criterios: [
            { id: "esc_pasos", item: "Peldaños, Contrapasos y Descansos", desc: "Peldaños barridos y trapeados sin polvo en esquinas ni colillas/basura." },
            { id: "esc_barandas", item: "Pasamanos y Barandas de Seguridad", desc: "Estructuras metálicas y pasamanos limpios, desinfectados y sin grasa." },
            { id: "esc_puertas", item: "Puertas Cortafuego y Brazos Hidráulicos", desc: "Puertas limpias, barras antipánico desinfectadas y mecanismo sin acumulación de polvo." },
            { id: "esc_despeje", item: "Vía de Evacuación Despejada (SST)", desc: "Vía 100% despejada, sin obstáculos, cajas, tachos o implementos de limpieza abandonados." }
        ]
    },
    {
        id: "cuarto_basura",
        nombre: "7. Cuarto de Basura y Gestión de Residuos",
        criterios: [
            { id: "res_contenedores", item: "Lavado y Desinfección de Contenedores", desc: "Contenedores rodantes limpios, desinfectados y con bolsa plástica de calibre adecuado." },
            { id: "res_segregacion", item: "Segregación y Código de Colores (NTP)", desc: "Clasificación correcta de residuos según código de colores (Verde, Azul, Blanco, Negro, etc.)." },
            { id: "res_pisos", item: "Pisos, Paredes y Sumidero de Lavado", desc: "Piso desengrasado con detergente industrial, sumidero con rejilla limpia." },
            { id: "res_olores", item: "Control de Olores y Vectores", desc: "Uso de desinfectante neutro/clorado y neutralizador de olores; ausencia de moscas/plagas." }
        ]
    },
    {
        id: "estacionamientos",
        nombre: "8. Estacionamientos, Cocheras y Sótanos",
        criterios: [
            { id: "est_rodadura", item: "Calzada de Rodadura y Cajones", desc: "Pisos barridos mecánicamente o con mopa industrial, sin hojas ni detritos." },
            { id: "est_aceite", item: "Desmanchado de Aceite y Combustible", desc: "Tratamiento con absorbente y desengrasante en cajones con goteo vehicular." },
            { id: "est_columnas", item: "Columnas, Tuberías Aéreas y Luminarias", desc: "Remoción periódica de telarañas y polvo en tuberías de agua/luz y números de cajón." },
            { id: "est_tachos", item: "Tachos y Zonas de Depósito Temporal", desc: "Tachos perimétricos limpios y desocupados." }
        ]
    },
    {
        id: "exteriores",
        nombre: "9. Fachada, Cristales Exteriores y Rampas",
        criterios: [
            { id: "ext_veredas", item: "Veredas Perimetrales y Rampas", desc: "Veredas exteriores y rampas vehiculares barridas o baldeadas sin grasa ni chicles." },
            { id: "ext_cristales", item: "Cristales y Letreros de Fachada (Baja Altura)", desc: "Vidrios frontales limpios y marcos exteriores libres de telarañas y polvo." },
            { id: "ext_jardineras", item: "Jardineras y Accesos de Visita", desc: "Zonas de transición libres de basura pequeña, papeles y hojas secas." }
        ]
    },
    {
        id: "office_limpieza",
        nombre: "10. Cuarto de Limpieza (Office) y Equipamiento",
        criterios: [
            { id: "off_quimicos", item: "Rotulado de Químicos y Hojas MSDS/FDS", desc: "Productos químicos en envases rotulados con nombre y dilución; Fichas de Seguridad visibles." },
            { id: "off_herramientas", item: "Mopas, Trapos y Carros Moperos", desc: "Mopas y paños lavados y colgados (código de colores); carros moperos limpios y ordenados." },
            { id: "off_maquinas", item: "Estado de Maquinarias (Lustradoras/Aspiradoras)", desc: "Equipos limpios, cables inspeccionados sin cortes, discos de lavado en buen estado." },
            { id: "off_orden", item: "Orden General y Ausencia de Derrames", desc: "Ambiente ventilado, estantes ordenados y libre de derrames químicos en el suelo." }
        ]
    }
];

// Estado de la Evaluación y Fotografías
let evaluacionState = {};
let pwaFotos = [];

document.addEventListener("DOMContentLoaded", () => {
    // Inicializar Iconos Lucide
    if (window.lucide) {
        lucide.createIcons();
    }

    // Set fecha de hoy
    const fechaInput = document.getElementById("inspeccion-fecha");
    if (fechaInput) {
        fechaInput.value = new Date().toISOString().split("T")[0];
    }

    // Renderizar Checklist
    renderChecklist();

    // Inicializar Canvas de Firmas
    initSignatureCanvas("canvas-sup", "btn-clear-sup");
    initSignatureCanvas("canvas-cli", "btn-clear-cli");

    // Inicializar Eventos de Registro Fotográfico
    setupFotoEvents();

    // Eventos de Navegación
    setupNavigation();

    // Eventos de Botones
    setupActions();

    // Cargar Historial Local
    cargarHistorial();
});

function renderChecklist() {
    const container = document.getElementById("checklist-container");
    if (!container) return;

    container.innerHTML = "";

    AREAS_DATA.forEach(area => {
        const areaGroup = document.createElement("div");
        areaGroup.className = "area-group";

        let criteriaHTML = "";
        area.criterios.forEach(crit => {
            evaluacionState[crit.id] = {
                id_criterio: crit.id,
                item_criterio: crit.item,
                id_area: area.id,
                nombre_area: area.nombre,
                calif: "C",
                calificacion: "C",
                obs: "",
                observacion: ""
            };

            criteriaHTML += `
                <div class="criteria-item">
                    <div class="criteria-info">
                        <strong>${crit.item}</strong>
                        <small>${crit.desc}</small>
                    </div>
                    <div class="criteria-radios" data-cid="${crit.id}">
                        <button type="button" class="radio-btn selected-c" data-val="C">C</button>
                        <button type="button" class="radio-btn" data-val="R">R</button>
                        <button type="button" class="radio-btn" data-val="NC">NC</button>
                        <button type="button" class="radio-btn" data-val="NA">N/A</button>
                    </div>
                    <div class="criteria-obs">
                        <input type="text" placeholder="Observación..." data-cid-obs="${crit.id}">
                    </div>
                </div>
            `;
        });

        areaGroup.innerHTML = `
            <div class="area-group-header">
                <span>${area.nombre}</span>
            </div>
            <div class="area-group-body">
                ${criteriaHTML}
            </div>
        `;

        container.appendChild(areaGroup);
    });

    // Event listeners para los botones de calificación
    container.querySelectorAll(".radio-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const parent = btn.parentElement;
            const cid = parent.getAttribute("data-cid");
            const val = btn.getAttribute("data-val");

            parent.querySelectorAll(".radio-btn").forEach(b => {
                b.className = "radio-btn";
            });

            btn.classList.add(`selected-${val.toLowerCase()}`);
            if (evaluacionState[cid]) {
                evaluacionState[cid].calif = val;
                evaluacionState[cid].calificacion = val;
            }
            actualizarCalculoEnVivo();
        });
    });

    container.querySelectorAll("input[data-cid-obs]").forEach(input => {
        input.addEventListener("input", (e) => {
            const cid = input.getAttribute("data-cid-obs");
            if (evaluacionState[cid]) {
                evaluacionState[cid].obs = input.value;
                evaluacionState[cid].observacion = input.value;
            }
        });
    });

    actualizarCalculoEnVivo();
}

function actualizarCalculoEnVivo() {
    let totalPuntos = 0;
    let puntosPosibles = 0;
    let countC = 0;
    let countR = 0;
    let countNC = 0;
    let countNA = 0;

    Object.values(evaluacionState).forEach(item => {
        if (item.calif === "C") {
            totalPuntos += 100;
            puntosPosibles += 100;
            countC++;
        } else if (item.calif === "R") {
            totalPuntos += 60;
            puntosPosibles += 100;
            countR++;
        } else if (item.calif === "NC") {
            totalPuntos += 0;
            puntosPosibles += 100;
            countNC++;
        } else if (item.calif === "NA") {
            countNA++;
        }
    });

    const score = puntosPosibles > 0 ? (totalPuntos / puntosPosibles) * 100 : 100;

    // Actualizar UI
    const scoreValEl = document.getElementById("live-score-val");
    const scoreLvlEl = document.getElementById("live-score-level");
    const scoreDescEl = document.getElementById("live-score-desc");

    if (scoreValEl) scoreValEl.innerText = `${score.toFixed(1)}%`;

    if (score >= 95) {
        if (scoreLvlEl) scoreLvlEl.innerText = "ÓPTIMO";
        if (scoreDescEl) scoreDescEl.innerText = "El servicio se encuentra en nivel óptimo de calidad y pulcritud.";
    } else if (score >= 90) {
        if (scoreLvlEl) scoreLvlEl.innerText = "ADECUADO";
        if (scoreDescEl) scoreDescEl.innerText = "El servicio cumple adecuadamente con los estándares de limpieza.";
    } else if (score >= 85) {
        if (scoreLvlEl) scoreLvlEl.innerText = "ACEPTABLE";
        if (scoreDescEl) scoreDescEl.innerText = "Cumplimiento aceptable con oportunidades menores de mejora.";
    } else if (score >= 80) {
        if (scoreLvlEl) scoreLvlEl.innerText = "POR MEJORAR";
        if (scoreDescEl) scoreDescEl.innerText = "Requiere plan de acción correctivo y refuerzo de cuadrilla.";
    } else {
        if (scoreLvlEl) scoreLvlEl.innerText = "NO CONFORME";
        if (scoreDescEl) scoreDescEl.innerText = "No cumple con los estándares mínimos requeridos. Requiere intervención inmediata.";
    }

    document.getElementById("chip-c").innerText = `${countC} Conformes`;
    document.getElementById("chip-r").innerText = `${countR} Regulares`;
    document.getElementById("chip-nc").innerText = `${countNC} No Conformes`;
    document.getElementById("chip-na").innerText = `${countNA} N/A`;
}

function setupNavigation() {
    document.querySelectorAll(".nav-item").forEach(item => {
        item.addEventListener("click", () => {
            document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

            item.classList.add("active");
            const tabId = `tab-${item.getAttribute("data-tab")}`;
            const targetPane = document.getElementById(tabId);
            if (targetPane) {
                targetPane.classList.add("active");
            }
        });
    });
}

function setupActions() {
    // Marcar todo Conforme
    document.getElementById("btn-check-all-c")?.addEventListener("click", () => {
        document.querySelectorAll(".criteria-radios").forEach(radios => {
            radios.querySelectorAll(".radio-btn").forEach(b => {
                b.className = "radio-btn";
                if (b.getAttribute("data-val") === "C") {
                    b.classList.add("selected-c");
                }
            });
            const cid = radios.getAttribute("data-cid");
            if (evaluacionState[cid]) {
                evaluacionState[cid].calif = "C";
                evaluacionState[cid].calificacion = "C";
            }
        });
        actualizarCalculoEnVivo();
    });

    // Llenar Datos Demo
    document.getElementById("btn-demo-data")?.addEventListener("click", () => {
        const edifEl = document.getElementById("edificio-nombre");
        const dirEl = document.getElementById("edificio-direccion");
        const adminEl = document.getElementById("cliente-admin");
        const supEl = document.getElementById("supervisor-nombre");
        const dniEl = document.getElementById("supervisor-dni");
        if (edifEl) edifEl.value = "Centro Empresarial Platinum Tower";
        if (dirEl) dirEl.value = "Av. Víctor Andrés Belaúnde 147, San Isidro";
        if (adminEl) adminEl.value = "Ing. Roberto Seminario";
        if (supEl) supEl.value = "Carlos Mendoza Ramos";
        if (dniEl) dniEl.value = "43892156";
        if (pwaFotos.length === 0) {
            generarFotoDemoVertical();
        }
        alert("Datos de demostración y fotografía vertical cargados.");
    });

    // Imprimir / Guardar como PDF
    document.getElementById("btn-print-report")?.addEventListener("click", () => {
        window.print();
    });

    // Guardar Supervisión Form
    document.getElementById("inspection-form")?.addEventListener("submit", (e) => {
        e.preventDefault();
        
        const codigo = `REP-LMP-2026-${Math.floor(1000 + Math.random() * 9000)}`;
        const edificio = document.getElementById("edificio-nombre")?.value || "Centro Empresarial Platinum Tower";
        const supervisor = document.getElementById("supervisor-nombre")?.value || "Carlos Mendoza Ramos";
        const fecha = document.getElementById("inspeccion-fecha")?.value || new Date().toISOString().split("T")[0];
        const turno = document.getElementById("inspeccion-turno")?.value || "Turno Mañana";
        const score = document.getElementById("live-score-val")?.innerText || "100%";
        const nivel = document.getElementById("live-score-level")?.innerText || "ÓPTIMO";

        const nuevoRegistro = {
            codigo, edificio, supervisor, fecha, turno, score, nivel,
            fotosCount: pwaFotos.length,
            fotos: pwaFotos.map(f => ({
                area: f.area,
                tipo: f.tipo,
                descripcion: f.descripcion,
                esVertical: f.esVertical,
                data: f.data
            }))
        };

        const historial = JSON.parse(localStorage.getItem("supervisiones_limpieza_historial") || "[]");
        historial.unshift(nuevoRegistro);
        localStorage.setItem("supervisiones_limpieza_historial", JSON.stringify(historial));

        alert(`¡Supervisión guardada con éxito!\nCódigo generado: ${codigo}\nScore: ${score}\nFotos adjuntas: ${pwaFotos.length}`);
        cargarHistorial();
        
        // Cambiar a pestaña historial
        document.querySelector('[data-tab="historial"]')?.click();
    });

    // Exportar JSON para Sistema Central Streamlit
    document.getElementById("btn-exportar-json")?.addEventListener("click", () => {
        const codigo = `REP-PWA-${Date.now().toString().slice(-4)}`;
        const edificio = document.getElementById("edificio-nombre")?.value || "Centro Empresarial Platinum Tower";
        const direccion = document.getElementById("edificio-direccion")?.value || "Av. Víctor Andrés Belaúnde 147, San Isidro";
        const admin = document.getElementById("cliente-admin")?.value || "Ing. Roberto Seminario";
        const supervisor = document.getElementById("supervisor-nombre")?.value || "Carlos Mendoza Ramos";
        const dni = document.getElementById("supervisor-dni")?.value || "43892156";
        const tipo = document.getElementById("inspeccion-tipo")?.value || "Supervisión Rutinaria Diaria";
        const fecha = document.getElementById("inspeccion-fecha")?.value || new Date().toISOString().split("T")[0];
        const turno = document.getElementById("inspeccion-turno")?.value || "Turno Mañana (07:00 - 15:00)";
        const lider = document.getElementById("lider-cuadrilla")?.value || "Técnico Líder en Turno";
        const pProg = parseInt(document.getElementById("p-programado")?.value || "6");
        const pPres = parseInt(document.getElementById("p-presente")?.value || "6");
        const score = document.getElementById("live-score-val")?.innerText || "100%";
        const nivel = document.getElementById("live-score-level")?.innerText || "ÓPTIMO";
        const obs = document.getElementById("obs-generales")?.value || "Supervisión ejecutada satisfactoriamente en todas las zonas.";

        const checklistList = [];
        Object.entries(evaluacionState).forEach(([cid, val]) => {
            checklistList.push({
                id_criterio: cid,
                item_criterio: val.item_criterio || val.item || cid,
                id_area: val.id_area || "",
                nombre_area: val.nombre_area || "",
                calificacion: val.calif || val.calificacion || "C",
                calif: val.calif || val.calificacion || "C",
                observacion: val.obs || val.observacion || "",
                obs: val.obs || val.observacion || ""
            });
        });

        const payload = {
            origen: "CLEANFACILITY_PRO_PWA",
            codigo_referencia: codigo,
            fecha_inspeccion: fecha,
            hora_inicio: "08:00",
            hora_fin: "09:30",
            edificio_nombre: edificio,
            edificio_direccion: direccion,
            administrador_contacto: admin,
            supervisor_nombre: supervisor,
            supervisor_dni: dni,
            tipo_inspeccion: tipo,
            turno: turno,
            lider_cuadrilla: lider,
            personal_programado: pProg,
            personal_presente: pPres,
            score_pwa: score,
            nivel_pwa: nivel,
            observaciones_generales: obs,
            evaluacion: evaluacionState,
            checklist_evaluacion: checklistList,
            incidencias: [],
            fotos: pwaFotos.map(f => ({
                area_nombre: f.area,
                tipo_evidencia: f.tipo,
                descripcion: f.descripcion,
                archivo_data: f.data,
                data: f.data,
                es_vertical: f.esVertical,
                ancho: f.ancho,
                alto: f.alto,
                fotos_adicionales: (f.fotos_adicionales || []).map(sf => ({
                    tipo_evidencia: sf.tipo || "Después de Limpieza",
                    descripcion: sf.descripcion || "",
                    archivo_data: sf.data,
                    data: sf.data,
                    es_vertical: sf.esVertical,
                    ancho: sf.ancho,
                    alto: sf.alto
                }))
            }))
        };

        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
        const downloadAnchor = document.createElement("a");
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", `Auditoria_PWA_${edificio.replace(/\s+/g, '_')}_${fecha}.json`);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
        alert(`✅ Archivo JSON exportado con éxito (${pwaFotos.length} fotos incluidas con orientación original).\nAhora puede cargarlo en el sistema central en 'Nueva Supervisión > Importar Supervisión desde Archivo JSON'.`);
    });
}

function setupFotoEvents() {
    const btnCam = document.getElementById("btn-pwa-camara");
    const btnGal = document.getElementById("btn-pwa-galeria");
    const inputCam = document.getElementById("pwa-input-camara");
    const inputGal = document.getElementById("pwa-input-galeria");

    btnCam?.addEventListener("click", () => inputCam?.click());
    btnGal?.addEventListener("click", () => inputGal?.click());

    inputCam?.addEventListener("change", (e) => {
        procesarArchivosFotos(e.target.files);
        inputCam.value = "";
    });

    inputGal?.addEventListener("change", (e) => {
        procesarArchivosFotos(e.target.files);
        inputGal.value = "";
    });
}

async function procesarArchivosFotos(archivos) {
    if (!archivos || archivos.length === 0) return;

    for (let i = 0; i < archivos.length; i++) {
        const file = archivos[i];
        if (!file.type.startsWith("image/")) continue;

        try {
            const dataUrl = await leerYCorregirOrientacion(file);
            const img = new Image();
            await new Promise((resolve) => {
                img.onload = resolve;
                img.src = dataUrl;
            });

            const naturalW = img.naturalWidth || img.width;
            const naturalH = img.naturalHeight || img.height;
            const esVertical = naturalH >= naturalW;

            pwaFotos.push({
                id: `foto_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
                nombre: file.name || "evidencia.jpg",
                data: dataUrl,
                area: AREAS_DATA[0]?.nombre || "General / Cuadrilla",
                tipo: "Hallazgo / No Conforme",
                descripcion: "",
                esVertical: esVertical,
                ancho: naturalW,
                alto: naturalH
            });
        } catch (err) {
            console.error("Error al procesar foto:", err);
        }
    }
    renderFotosPWA();
}

async function leerYCorregirOrientacion(archivo) {
    // 1. Usar createImageBitmap con { imageOrientation: 'from-image' } para leer EXIF y corregir posición original
    if (typeof createImageBitmap === "function") {
        try {
            const bitmap = await createImageBitmap(archivo, { imageOrientation: "from-image" });
            const origW = bitmap.width;
            const origH = bitmap.height;
            const maxDim = 1400;
            let targetW = origW;
            let targetH = origH;
            if (Math.max(origW, origH) > maxDim) {
                const ratio = maxDim / Math.max(origW, origH);
                targetW = Math.max(1, Math.round(origW * ratio));
                targetH = Math.max(1, Math.round(origH * ratio));
            }
            const canvas = document.createElement("canvas");
            canvas.width = targetW;
            canvas.height = targetH;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(bitmap, 0, 0, targetW, targetH);
            bitmap.close();
            return canvas.toDataURL("image/jpeg", 0.85);
        } catch (e) {
            console.warn("Fallo createImageBitmap from-image, usando fallback:", e);
        }
    }

    // 2. Fallback estándar con FileReader
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const origW = img.naturalWidth || img.width;
                const origH = img.naturalHeight || img.height;
                const maxDim = 1400;
                let targetW = origW;
                let targetH = origH;
                if (Math.max(targetW, targetH) > maxDim) {
                    const ratio = maxDim / Math.max(targetW, targetH);
                    targetW = Math.max(1, Math.round(origW * ratio));
                    targetH = Math.max(1, Math.round(origH * ratio));
                }
                const canvas = document.createElement("canvas");
                canvas.width = targetW;
                canvas.height = targetH;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, targetW, targetH);
                resolve(canvas.toDataURL("image/jpeg", 0.85));
            };
            img.onerror = reject;
            img.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(archivo);
    });
}

function renderFotosPWA() {
    const vacioEl = document.getElementById("pwa-fotos-vacio");
    const containerEl = document.getElementById("pwa-fotos-container");
    if (!vacioEl || !containerEl) return;

    if (pwaFotos.length === 0) {
        vacioEl.style.display = "block";
        containerEl.style.display = "none";
        containerEl.innerHTML = "";
        return;
    }

    vacioEl.style.display = "none";
    containerEl.style.display = "grid";
    containerEl.innerHTML = "";

    const areasOpciones = [
        ...AREAS_DATA.map(a => a.nombre),
        "General / Cuadrilla"
    ];

    const tiposOpciones = [
        "Hallazgo / No Conforme",
        "Antes de Limpieza",
        "Después de Limpieza",
        "General de Calidad"
    ];

    pwaFotos.forEach((f, idx) => {
        const card = document.createElement("div");
        card.className = "foto-card";

        const optAreasHTML = areasOpciones.map(a => `<option value="${a}" ${a === f.area ? 'selected' : ''}>${a}</option>`).join("");
        const optTiposHTML = tiposOpciones.map(t => `<option value="${t}" ${t === f.tipo ? 'selected' : ''}>${t}</option>`).join("");

        card.innerHTML = `
            <div class="foto-preview-container">
                <img src="${f.data}" alt="Evidencia ${idx + 1}" style="image-orientation: from-image;">
                <span class="foto-orientation-badge ${f.esVertical ? 'badge-vertical' : 'badge-horizontal'}">
                    ${f.esVertical ? '📱 Vertical' : '💻 Horizontal'}
                </span>
                <span class="foto-dim-badge">${f.ancho}x${f.alto}</span>
            </div>
            <div class="foto-card-body">
                <div>
                    <label>Área de Inspección:</label>
                    <select class="pwa-foto-area" data-idx="${idx}" style="width:100%; padding:6px; border:1px solid #CBD5E1; border-radius:6px; font-size:0.85rem;">
                        ${optAreasHTML}
                    </select>
                </div>
                <div>
                    <label>Tipo de Evidencia:</label>
                    <select class="pwa-foto-tipo" data-idx="${idx}" style="width:100%; padding:6px; border:1px solid #CBD5E1; border-radius:6px; font-size:0.85rem;">
                        ${optTiposHTML}
                    </select>
                </div>
                <div>
                    <label>Descripción / Observación:</label>
                    <input type="text" class="pwa-foto-desc" data-idx="${idx}" placeholder="Ej: Mancha tratada en mármol con desengrasante..." value="${f.descripcion || ''}" style="width:100%; padding:6px; border:1px solid #CBD5E1; border-radius:6px; font-size:0.85rem;">
                </div>
                <div class="foto-actions" style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">
                    <button type="button" class="btn btn-sm btn-subfoto" data-idx="${idx}" style="background:#E0F2FE; color:#0369A1; font-weight:600;" title="Agregar foto complementaria (después de limpieza, otro ángulo)">
                        ➕ Foto Adicional
                    </button>
                    <button type="button" class="btn btn-sm btn-rotar-foto" data-idx="${idx}" title="Rotar imagen 90° horario">
                        🔄 Rotar 90°
                    </button>
                    <button type="button" class="btn btn-sm btn-eliminar-foto" data-idx="${idx}" title="Eliminar fotografía">
                        🗑️ Eliminar
                    </button>
                </div>
                ${f.fotos_adicionales && f.fotos_adicionales.length > 0 ? `
                    <div class="subfotos-pwa-box" style="margin-top:10px; border-top:1px dashed #CBD5E1; padding-top:8px;">
                        <span style="font-size:0.75rem; font-weight:700; color:#0284C7; display:block; margin-bottom:4px;">
                            📸 Fotos Adicionales vinculadas (${f.fotos_adicionales.length}):
                        </span>
                        ${f.fotos_adicionales.map((sf, s_i) => `
                            <div style="display:flex; gap:8px; align-items:center; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:6px; margin-bottom:6px;">
                                <img src="${sf.data}" style="width:48px; height:48px; object-fit:cover; border-radius:4px; border:1px solid #CBD5E1;">
                                <div style="flex:1;">
                                    <span style="font-size:0.72rem; font-weight:700; color:#1E293B;">${sf.tipo || 'Evidencia Adicional'}</span>
                                    <input type="text" class="pwa-subfoto-desc" data-parent="${idx}" data-sub="${s_i}" value="${sf.descripcion || ''}" placeholder="Descripción adicional..." style="width:100%; font-size:0.75rem; padding:3px 6px; border:1px solid #CBD5E1; border-radius:4px; margin-top:2px;">
                                </div>
                                <button type="button" class="btn btn-sm btn-rotar-subfoto" data-parent="${idx}" data-sub="${s_i}" title="Rotar 90°" style="padding:4px 7px; font-size:0.75rem;">🔄</button>
                                <button type="button" class="btn btn-sm btn-eliminar-subfoto" data-parent="${idx}" data-sub="${s_i}" title="Eliminar" style="padding:4px 7px; font-size:0.75rem; background:#FEE2E2; color:#DC2626;">🗑️</button>
                            </div>
                        `).join("")}
                    </div>
                ` : ''}
            </div>
        `;
        containerEl.appendChild(card);
    });

    // Event listeners para los controles de cada tarjeta
    containerEl.querySelectorAll(".pwa-foto-area").forEach(sel => {
        sel.addEventListener("change", (e) => {
            const i = parseInt(e.target.getAttribute("data-idx"));
            if (pwaFotos[i]) pwaFotos[i].area = e.target.value;
        });
    });

    containerEl.querySelectorAll(".pwa-foto-tipo").forEach(sel => {
        sel.addEventListener("change", (e) => {
            const i = parseInt(e.target.getAttribute("data-idx"));
            if (pwaFotos[i]) pwaFotos[i].tipo = e.target.value;
        });
    });

    containerEl.querySelectorAll(".pwa-foto-desc").forEach(inp => {
        inp.addEventListener("input", (e) => {
            const i = parseInt(e.target.getAttribute("data-idx"));
            if (pwaFotos[i]) pwaFotos[i].descripcion = e.target.value;
        });
    });

    containerEl.querySelectorAll(".btn-rotar-foto").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const i = parseInt(btn.getAttribute("data-idx"));
            rotarFotoPWA(i);
        });
    });

    containerEl.querySelectorAll(".btn-eliminar-foto").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const i = parseInt(btn.getAttribute("data-idx"));
            eliminarFotoPWA(i);
        });
    });

    containerEl.querySelectorAll(".btn-subfoto").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const parentIdx = parseInt(btn.getAttribute("data-idx"));
            const subInput = document.createElement("input");
            subInput.type = "file";
            subInput.accept = "image/*";
            subInput.onchange = (ev) => {
                const file = ev.target.files && ev.target.files[0];
                if (file) {
                    agregarSubfotoPWA(parentIdx, file);
                }
            };
            subInput.click();
        });
    });

    containerEl.querySelectorAll(".pwa-subfoto-desc").forEach(inp => {
        inp.addEventListener("input", (e) => {
            const pIdx = parseInt(inp.getAttribute("data-parent"));
            const sIdx = parseInt(inp.getAttribute("data-sub"));
            if (pwaFotos[pIdx] && pwaFotos[pIdx].fotos_adicionales && pwaFotos[pIdx].fotos_adicionales[sIdx]) {
                pwaFotos[pIdx].fotos_adicionales[sIdx].descripcion = e.target.value;
            }
        });
    });

    containerEl.querySelectorAll(".btn-rotar-subfoto").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const pIdx = parseInt(btn.getAttribute("data-parent"));
            const sIdx = parseInt(btn.getAttribute("data-sub"));
            rotarSubfotoPWA(pIdx, sIdx);
        });
    });

    containerEl.querySelectorAll(".btn-eliminar-subfoto").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const pIdx = parseInt(btn.getAttribute("data-parent"));
            const sIdx = parseInt(btn.getAttribute("data-sub"));
            if (pwaFotos[pIdx] && pwaFotos[pIdx].fotos_adicionales) {
                pwaFotos[pIdx].fotos_adicionales.splice(sIdx, 1);
                renderFotosPWA();
            }
        });
    });
}

async function agregarSubfotoPWA(parentIdx, file) {
    if (!file || !file.type.startsWith("image/")) return;
    try {
        const dataUrl = await leerYCorregirOrientacion(file);
        const img = new Image();
        await new Promise((resolve) => {
            img.onload = resolve;
            img.src = dataUrl;
        });

        const naturalW = img.naturalWidth || img.width;
        const naturalH = img.naturalHeight || img.height;
        const esVertical = naturalH >= naturalW;

        if (!pwaFotos[parentIdx]) return;
        if (!pwaFotos[parentIdx].fotos_adicionales) {
            pwaFotos[parentIdx].fotos_adicionales = [];
        }

        const parentTipo = pwaFotos[parentIdx].tipo || "";
        const defTipo = (parentTipo.includes("Antes") || parentTipo.includes("Hallazgo")) ? "Después de Limpieza" : "Ángulo Adicional";

        pwaFotos[parentIdx].fotos_adicionales.push({
            id: `sub_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
            nombre: file.name || "sub_evidencia.jpg",
            data: dataUrl,
            tipo: defTipo,
            descripcion: `Foto adicional (${defTipo})`,
            esVertical: esVertical,
            ancho: naturalW,
            alto: naturalH
        });
        renderFotosPWA();
    } catch (err) {
        console.error("Error al procesar foto adicional en PWA:", err);
    }
}

function rotarSubfotoPWA(parentIdx, subIdx) {
    const parent = pwaFotos[parentIdx];
    if (!parent || !parent.fotos_adicionales || !parent.fotos_adicionales[subIdx]) return;
    const sf = parent.fotos_adicionales[subIdx];

    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalHeight || img.height;
        canvas.height = img.naturalWidth || img.width;
        const ctx = canvas.getContext("2d");
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate((90 * Math.PI) / 180);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);

        sf.data = canvas.toDataURL("image/jpeg", 0.88);
        sf.ancho = canvas.width;
        sf.alto = canvas.height;
        sf.esVertical = sf.alto > sf.ancho;
        renderFotosPWA();
    };
    img.src = sf.data;
}

function rotarFotoPWA(index) {
    const f = pwaFotos[index];
    if (!f) return;

    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        // Rotar 90 grados a favor del reloj: se intercambian ancho y alto
        canvas.width = img.naturalHeight || img.height;
        canvas.height = img.naturalWidth || img.width;
        const ctx = canvas.getContext("2d");
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate((90 * Math.PI) / 180);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);

        f.data = canvas.toDataURL("image/jpeg", 0.88);
        f.ancho = canvas.width;
        f.alto = canvas.height;
        f.esVertical = f.alto > f.ancho;
        renderFotosPWA();
    };
    img.src = f.data;
}

function eliminarFotoPWA(index) {
    if (index >= 0 && index < pwaFotos.length) {
        pwaFotos.splice(index, 1);
        renderFotosPWA();
    }
}

function generarFotoDemoVertical() {
    // Genera una imagen demo en orientación vertical (proporción 3:4)
    const canvas = document.createElement("canvas");
    canvas.width = 600;
    canvas.height = 800; // Vertical: altura mayor que ancho
    const ctx = canvas.getContext("2d");

    // Fondo degradado elegante
    const grad = ctx.createLinearGradient(0, 0, 0, 800);
    grad.addColorStop(0, "#0F172A");
    grad.addColorStop(0.5, "#0369A1");
    grad.addColorStop(1, "#0D9488");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 600, 800);

    // Decoración visual
    ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
    ctx.lineWidth = 4;
    ctx.strokeRect(20, 20, 560, 760);

    ctx.fillStyle = "#FFFFFF";
    ctx.font = "bold 32px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("🏢 CLEANFACILITY PRO", 300, 280);

    ctx.font = "24px sans-serif";
    ctx.fillStyle = "#38BDF8";
    ctx.fillText("Evidencia Fotográfica de Campo", 300, 330);

    ctx.font = "bold 36px sans-serif";
    ctx.fillStyle = "#10B981";
    ctx.fillText("📱 FOTO EN VERTICAL (3:4)", 300, 420);

    ctx.font = "18px sans-serif";
    ctx.fillStyle = "#E2E8F0";
    ctx.fillText("Orientación Original Conservada", 300, 470);
    ctx.fillText("Resolución: 600 x 800 px", 300, 510);
    ctx.fillText("Inspección de Servicios Higiénicos y Lobby", 300, 550);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    pwaFotos.push({
        id: `foto_demo_${Date.now()}`,
        nombre: "evidencia_demo_vertical.jpg",
        data: dataUrl,
        area: "3. Servicios Higiénicos (SS.HH.)",
        tipo: "Hallazgo / No Conforme",
        descripcion: "Foto vertical de demostración: griferías y sanitarios inspeccionados.",
        esVertical: true,
        ancho: 600,
        alto: 800
    });
    renderFotosPWA();
}

function cargarHistorial() {
    const tbody = document.querySelector("#tabla-historial tbody");
    if (!tbody) return;

    const historial = JSON.parse(localStorage.getItem("supervisiones_limpieza_historial") || "[]");
    
    if (historial.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#94A3B8;">No hay registros guardados en esta sesión.</td></tr>`;
        return;
    }

    tbody.innerHTML = "";
    // Ordenar por fecha descendente
    historial.sort((a, b) => (b.fecha || "").localeCompare(a.fecha || ""));
    historial.forEach(h => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${h.codigo}</strong></td>
            <td>${h.fecha}</td>
            <td>${h.edificio}</td>
            <td>${h.turno}</td>
            <td>${h.supervisor}</td>
            <td><strong>${h.score}</strong></td>
            <td><span class="status-pill status-success">${h.nivel}</span></td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="window.print()">
                    🖨️ Imprimir
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function initSignatureCanvas(canvasId, clearBtnId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let isDrawing = false;

    ctx.strokeStyle = "#0F172A";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";

    canvas.addEventListener("mousedown", (e) => {
        isDrawing = true;
        ctx.beginPath();
        ctx.moveTo(e.offsetX, e.offsetY);
    });

    canvas.addEventListener("mousemove", (e) => {
        if (!isDrawing) return;
        ctx.lineTo(e.offsetX, e.offsetY);
        ctx.stroke();
    });

    canvas.addEventListener("mouseup", () => isDrawing = false);
    canvas.addEventListener("mouseleave", () => isDrawing = false);

    // Touch events for mobile
    canvas.addEventListener("touchstart", (e) => {
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        isDrawing = true;
        ctx.beginPath();
        ctx.moveTo(touch.clientX - rect.left, touch.clientY - rect.top);
        e.preventDefault();
    });

    canvas.addEventListener("touchmove", (e) => {
        if (!isDrawing) return;
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        ctx.lineTo(touch.clientX - rect.left, touch.clientY - rect.top);
        ctx.stroke();
        e.preventDefault();
    });

    canvas.addEventListener("touchend", () => isDrawing = false);

    document.getElementById(clearBtnId)?.addEventListener("click", () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    });
}
