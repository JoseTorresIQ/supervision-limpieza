/**
 * CleanFacility Pro - Logic & Controller
 * Standalone Offline-First Building Cleaning Supervision System
 */

// Dataset de Áreas y Criterios Técnicos
const AREAS_DATA = [
    {
        id: "lobby",
        nombre: "1. Hall de Ingreso / Lobby / Recepción",
        criterios: [
            { id: "c1", item: "Pisos y Zócalos", desc: "Pisos de mármol/porcelanato pulidos, sin huellas ni polvo." },
            { id: "c2", item: "Mamparas y Cristales", desc: "Vidrios sin marcas dactilares ni polvo en marcos." },
            { id: "c3", item: "Mobiliario y Mostrador", desc: "Muebles despolvados y tapetes atrapapolvo aspirados." }
        ]
    },
    {
        id: "ascensores",
        nombre: "2. Ascensores y Cabinas",
        criterios: [
            { id: "c4", item: "Botoneras y Pantallas", desc: "Botones desinfectados y sin manchas de grasa." },
            { id: "c5", item: "Acero Inoxidable y Espejos", desc: "Acero abrillantado sin rayas; espejos limpios." },
            { id: "c6", item: "Rieles y Pisos de Cabina", desc: "Rieles de puertas aspirados sin residuos." }
        ]
    },
    {
        id: "banos",
        nombre: "3. Servicios Higiénicos (SS.HH.)",
        criterios: [
            { id: "c7", item: "Inodoros y Urinarios", desc: "Sanitarios lavados, desinfectados y sin sarro." },
            { id: "c8", item: "Griferías y Lavamanos", desc: "Griferías cromadas brillantes y secas." },
            { id: "c9", item: "Abastecimiento de Insumos", desc: "Dispensadores de jabón y papel 100% llenos." }
        ]
    },
    {
        id: "pasadizos",
        nombre: "4. Pasadizos y Áreas Comunes",
        criterios: [
            { id: "c10", item: "Pisos y Mopado", desc: "Pisos mopados de manera uniforme sin vetas." },
            { id: "c11", item: "Extintores y Gabinetes", desc: "Equipos contra incendios limpios y visibles." }
        ]
    },
    {
        id: "escaleras",
        nombre: "5. Escaleras de Emergencia",
        criterios: [
            { id: "c12", item: "Pasos y Descansos", desc: "Peldaños barridos y trapeados." },
            { id: "c13", item: "Vía Despejada (SST)", desc: "Libre de cajas, obstáculos o basura." }
        ]
    },
    {
        id: "basura",
        nombre: "6. Cuarto de Basura y Residuos",
        criterios: [
            { id: "c14", item: "Lavado de Contenedores", desc: "Contenedores desinfectados con bolsa." },
            { id: "c15", item: "Control de Olores", desc: "Piso desengrasado y libre de vectores." }
        ]
    }
];

// Estado de la Evaluación
let evaluacionState = {};

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
            evaluacionState[crit.id] = { calif: "C", obs: "" };

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
            evaluacionState[cid].calif = val;
            actualizarCalculoEnVivo();
        });
    });

    container.querySelectorAll("input[data-cid-obs]").forEach(input => {
        input.addEventListener("input", (e) => {
            const cid = input.getAttribute("data-cid-obs");
            evaluacionState[cid].obs = input.value;
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
            evaluacionState[cid].calif = "C";
        });
        actualizarCalculoEnVivo();
    });

    // Llenar Datos Demo
    document.getElementById("btn-demo-data")?.addEventListener("click", () => {
        document.getElementById("edificio-nombre").value = "Torre Empresarial Javier Prado";
        document.getElementById("edificio-direccion").value = "Av. Javier Prado Este 4200, Surco";
        document.getElementById("cliente-admin").value = "Arq. Melissa Fernández";
        document.getElementById("supervisor-nombre").value = "Carlos Mendoza Ramos";
        alert("Datos de demostración cargados.");
    });

    // Imprimir / Guardar como PDF
    document.getElementById("btn-print-report")?.addEventListener("click", () => {
        window.print();
    });

    // Guardar Supervisión Form
    document.getElementById("inspection-form")?.addEventListener("submit", (e) => {
        e.preventDefault();
        
        const codigo = `REP-LMP-2026-${Math.floor(1000 + Math.random() * 9000)}`;
        const edificio = document.getElementById("edificio-nombre").value;
        const supervisor = document.getElementById("supervisor-nombre").value;
        const fecha = document.getElementById("inspeccion-fecha").value;
        const turno = document.getElementById("inspeccion-turno").value;
        const score = document.getElementById("live-score-val").innerText;
        const nivel = document.getElementById("live-score-level").innerText;

        const nuevoRegistro = {
            codigo, edificio, supervisor, fecha, turno, score, nivel
        };

        const historial = JSON.parse(localStorage.getItem("supervisiones_limpieza_historial") || "[]");
        historial.unshift(nuevoRegistro);
        localStorage.setItem("supervisiones_limpieza_historial", JSON.stringify(historial));

        alert(`¡Supervisión guardada con éxito!\nCódigo generado: ${codigo}\nScore: ${score}`);
        cargarHistorial();
        
        // Cambiar a pestaña historial
        document.querySelector('[data-tab="historial"]')?.click();
    });

    // Exportar JSON para Sistema Central Streamlit
    document.getElementById("btn-exportar-json")?.addEventListener("click", () => {
        const codigo = `REP-PWA-${Date.now().toString().slice(-4)}`;
        const edificio = document.getElementById("edificio-nombre")?.value || "Edificio";
        const direccion = document.getElementById("edificio-direccion")?.value || "";
        const supervisor = document.getElementById("supervisor-nombre")?.value || "Supervisor";
        const fecha = document.getElementById("inspeccion-fecha")?.value || new Date().toISOString().split("T")[0];
        const turno = document.getElementById("inspeccion-turno")?.value || "Turno Mañana";
        const score = document.getElementById("live-score-val")?.innerText || "100%";
        const nivel = document.getElementById("live-score-level")?.innerText || "ÓPTIMO";
        const obs = document.getElementById("obs-generales")?.value || "";

        const payload = {
            origen: "CLEANFACILITY_PRO_PWA",
            codigo_referencia: codigo,
            fecha_inspeccion: fecha,
            edificio_nombre: edificio,
            edificio_direccion: direccion,
            supervisor_nombre: supervisor,
            turno: turno,
            score_pwa: score,
            nivel_pwa: nivel,
            observaciones_generales: obs,
            evaluacion: evaluacionState,
            incidencias: []
        };

        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
        const downloadAnchor = document.createElement("a");
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", `Auditoria_PWA_${edificio.replace(/\s+/g, '_')}_${fecha}.json`);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
        alert("✅ Archivo JSON exportado con éxito. Ahora puede cargarlo en el sistema central en 'Nueva Supervisión > Importar Inspección Offline'.");
    });
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
