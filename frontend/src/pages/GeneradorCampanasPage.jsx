import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext.jsx';

// --- PrimeReact Components ---
import { TabView, TabPanel } from 'primereact/tabview';
import { Dropdown } from 'primereact/dropdown';
import { MultiSelect } from 'primereact/multiselect';
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';
import { Toast } from 'primereact/toast';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { ProgressSpinner } from 'primereact/progressspinner';

// --- Estilos ---
import { selectClass, inputClass, btnPrimary, btnSecondary, btnDanger } from '../styles/appStyles';

// --- Configuración API ---
const API_VISOR_URL = '/api/visor';
const API_CAMPANAS_URL = '/api/campanas';

const tiposCampanaOptions = [
    { label: 'Mail Cobranza', value: 'MAIL' },
    { label: 'Mail Comercial', value: 'MAIL_INF' },
    { label: 'SMS', value: 'SMS' }
];

function GeneradorCampanasPage() {
    const { token, user } = useAuth(); // Obtener usuario para permisos
    const toast = useRef(null);

    // --- ESTADOS DE UI ---
    const [activeIndex, setActiveIndex] = useState(0); // 0: Lista, 1: Editor
    const [loading, setLoading] = useState(false);     // Carga general
    
    // --- ESTADOS DE EJECUCIÓN (Polling) ---
    const [executingTaskId, setExecutingTaskId] = useState(null);
    const [executionStatus, setExecutionStatus] = useState(null); // 'running', 'complete', 'error'
    const [executionResults, setExecutionResults] = useState([]); 
    const [executionStats, setExecutionStats] = useState(null); // Estadísticas
    const pollerRef = useRef(null);

    // --- ESTADOS DEL FORMULARIO ---
    const [isEditing, setIsEditing] = useState(false);
    const [editingId, setEditingId] = useState(null);

    const [nombrePlantilla, setNombrePlantilla] = useState("");
    
    // 1. Fuente de Datos
    const [clientesDisponibles, setClientesDisponibles] = useState([]); 
    const [selectedCliente, setSelectedCliente] = useState(null);
    
    const [estrategiasDisponibles, setEstrategiasDisponibles] = useState([]); 
    const [selectedEstrategia, setSelectedEstrategia] = useState(null);

    // 2. Configuración (Tipo)
    const [tipoCampana, setTipoCampana] = useState(null); 

    // 3. División y Procesamiento
    const [columnasDisponibles, setColumnasDisponibles] = useState([]); 
    const [columnasDivision, setColumnasDivision] = useState([]); 
    const [modoSalida, setModoSalida] = useState("archivo"); 

    // --- ESTADOS DE LISTA ---
    const [plantillasGuardadas, setPlantillasGuardadas] = useState([]);
    
    // Determinar si es admin
    const isAdmin = user?.rol === 'admin';

    // ========================================================================
    // 1. CARGA INICIAL Y LISTAS
    // ========================================================================

    useEffect(() => {
        if (!token) return;
        fetchPlantillas();
        fetchClientes();
        return () => stopPolling();
    }, [token]);

    const fetchPlantillas = async () => {
        try {
            const res = await axios.get(`${API_CAMPANAS_URL}/plantillas`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setPlantillasGuardadas(res.data);
        } catch (e) { console.error("Error cargando plantillas", e); }
    };

    const fetchClientes = async () => {
        try {
            const res = await axios.get(`${API_VISOR_URL}/clients`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setClientesDisponibles(res.data.map(c => ({ label: c, value: c })));
        } catch (e) { console.error(e); }
    };

    // Cargar Estrategias cuando cambia Cliente
    useEffect(() => {
        if (!selectedCliente || !token) {
            setEstrategiasDisponibles([]);
            return;
        }
        if (isEditing && estrategiasDisponibles.length > 0) return;

        const fetchEstrategias = async () => {
            try {
                const res = await axios.get(`${API_VISOR_URL}/strategies/${selectedCliente}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setEstrategiasDisponibles(res.data.map(e => ({ label: e.nombre, value: e.id })));
            } catch (e) { console.error(e); }
        };
        fetchEstrategias();
    }, [selectedCliente, token, isEditing]);

    // Cargar Columnas cuando cambia Estrategia
    useEffect(() => {
        if (!selectedEstrategia || !token) {
            setColumnasDisponibles([]);
            return;
        }
        const fetchDetalles = async () => {
            try {
                const res = await axios.get(`${API_VISOR_URL}/strategies/load/${selectedEstrategia}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                const cols = JSON.parse(res.data.columnas_visibles || "[]");
                setColumnasDisponibles(cols.map(c => ({ label: c.header, value: c.field })));
            } catch (e) { console.error(e); }
        };
        fetchDetalles();
    }, [selectedEstrategia, token]);


    // ========================================================================
    // 2. LÓGICA DEL FORMULARIO
    // ========================================================================

    const resetForm = () => {
        setIsEditing(false);
        setEditingId(null);
        setNombrePlantilla("");
        setSelectedCliente(null); 
        setSelectedEstrategia(null);
        setTipoCampana(null);
        setColumnasDivision([]);
        setModoSalida("archivo");
        setEstrategiasDisponibles([]);
    };

    const handleEditPlantilla = async (rowData) => {
        setLoading(true);
        try {
            // 1. Obtener la plantilla completa
            const resPlantilla = await axios.get(`${API_CAMPANAS_URL}/plantillas/${rowData.id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            const plantilla = resPlantilla.data;

            // 2. Obtener la estrategia base para saber el cliente
            const resEstrategia = await axios.get(`${API_VISOR_URL}/strategies/load/${plantilla.id_estrategia_base}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            const estrategiaData = resEstrategia.data;
            const clienteCode = estrategiaData.codigo_cliente;

            // 3. Setear datos básicos
            setIsEditing(true);
            setEditingId(plantilla.id);
            setNombrePlantilla(plantilla.nombre_plantilla);
            
            // 4. Setear Cliente y Cargar sus Estrategias MANUALMENTE
            setSelectedCliente(clienteCode); 
            if (clienteCode) {
                const resEstrategiasList = await axios.get(`${API_VISOR_URL}/strategies/${clienteCode}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                const listaEstrategias = resEstrategiasList.data.map(e => ({ label: e.nombre, value: e.id }));
                setEstrategiasDisponibles(listaEstrategias);
            }

            // 5. Setear la estrategia seleccionada
            setSelectedEstrategia(plantilla.id_estrategia_base);

            // 6. Cargar Configuración (Tipo de Campaña)
            try {
                const val = JSON.parse(plantilla.reglas_validacion_json || "{}");
                if (val.tipo_campana) {
                    setTipoCampana(val.tipo_campana); 
                }
            } catch (e) { console.error("Error parsing validacion json", e); }

            // 7. Cargar División
            try {
                const proc = JSON.parse(plantilla.reglas_procesamiento_json || "{}");
                setColumnasDivision(proc.columnas_division || []); 
            } catch (e) { console.error("Error parsing procesamiento json", e); }

            setModoSalida(plantilla.modo_salida);
            setActiveIndex(1);

        } catch (error) {
            console.error("Error al cargar para editar:", error);
            toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo cargar la plantilla.' });
        } finally {
            setLoading(false);
        }
    };

    const handleGuardar = async () => {
        if (!nombrePlantilla || !selectedEstrategia || !tipoCampana) {
            toast.current.show({ severity: 'warn', summary: 'Faltan datos', detail: 'Complete al menos Nombre, Estrategia y Tipo de Campaña.' });
            return;
        }

        const payload = {
            nombre_plantilla: nombrePlantilla,
            id_estrategia_base: selectedEstrategia,
            // Guardamos solo el tipo. El backend deduce las reglas automáticas.
            reglas_validacion_json: JSON.stringify({ tipo_campana: tipoCampana }),
            reglas_procesamiento_json: JSON.stringify({
                columnas_division: columnasDivision, // Puede estar vacío
                reglas_por_grupo: {} 
            }),
            modo_salida: modoSalida
        };

        try {
            const url = isEditing ? `${API_CAMPANAS_URL}/plantillas/${editingId}` : `${API_CAMPANAS_URL}/plantillas`;
            const method = isEditing ? 'put' : 'post';
            
            await axios[method](url, payload, { headers: { Authorization: `Bearer ${token}` } });
            
            toast.current.show({ severity: 'success', summary: 'Éxito', detail: 'Plantilla guardada.' });
            resetForm();
            fetchPlantillas();
            setActiveIndex(0);
        } catch (error) {
            console.error(error);
            const errorMsg = error.response?.data?.detail || 'No se pudo guardar.';
            toast.current.show({ severity: 'error', summary: 'Error', detail: errorMsg });
        }
    };

    // ========================================================================
    // 3. LÓGICA DE EJECUCIÓN
    // ========================================================================

    const handleEjecutar = async (rowData) => {
        setExecutionStatus("running");
        setExecutionResults([]);
        setExecutionStats(null);
        setExecutingTaskId(null);
        
        toast.current.show({ severity: 'info', summary: 'Iniciando...', detail: 'Procesando campaña...' });

        try {
            const res = await axios.post(`${API_CAMPANAS_URL}/ejecutar/${rowData.id}`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            const taskId = res.data.task_id;
            setExecutingTaskId(taskId);
            pollerRef.current = setInterval(() => checkStatus(taskId), 3000); 
        } catch (error) {
            setExecutionStatus("error");
            toast.current.show({ severity: 'error', summary: 'Error', detail: 'Fallo al iniciar.' });
        }
    };

    const checkStatus = async (taskId) => {
        try {
            const res = await axios.get(`${API_CAMPANAS_URL}/status/${taskId}`, { headers: { Authorization: `Bearer ${token}` } });
            const { status, error } = res.data;

            if (status === 'complete') {
                stopPolling();
                fetchResultados(taskId);
                setExecutionStatus("complete");
                toast.current.show({ severity: 'success', summary: 'Completado', detail: 'Proceso finalizado.' });
            } else if (status === 'error') {
                stopPolling();
                setExecutionStatus("error");
                toast.current.show({ severity: 'error', summary: 'Fallo', detail: error });
            }
        } catch (error) { stopPolling(); }
    };

    const fetchResultados = async (taskId) => {
        try {
            const res = await axios.get(`${API_CAMPANAS_URL}/resultados/${taskId}`, { headers: { Authorization: `Bearer ${token}` } });
            const data = res.data.resultados;
            
            if (data.archivos) {
                setExecutionResults(data.archivos);
                setExecutionStats(data.resumen);
            } else {
                setExecutionResults(data);
            }
        } catch (error) { console.error(error); }
    };

    const stopPolling = () => {
        if (pollerRef.current) { clearInterval(pollerRef.current); pollerRef.current = null; }
    };

    const handleCancel = async () => {
        if (!executingTaskId) return;
        stopPolling(); 
        setExecutionStatus("cancelled"); 
        toast.current.show({ severity: 'warn', summary: 'Cancelando...', detail: 'Enviando solicitud...' });

        try {
            await axios.post(`${API_CAMPANAS_URL}/cancel/${executingTaskId}`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            toast.current.show({ severity: 'info', summary: 'Tarea Cancelada', detail: 'El proceso se detuvo.' });
        } catch (error) {
            console.error("Error al cancelar:", error);
            toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo cancelar la tarea.' });
        } finally {
            setExecutingTaskId(null);
            setExecutionStatus(null); 
        }
    };

    // --- HELPERS DE RENDER ---
    const formatDate = (dateString) => {
        if (!dateString) return "-";
        const date = new Date(dateString);
        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const year = date.getFullYear();
        return `${day}-${month}-${year}`;
    };

    const renderValidationInfo = () => {
        if (!tipoCampana) return null;
        return (
            <div className="mt-3 p-3 bg-blue-50 border border-blue-100 rounded text-sm text-blue-800">
                <strong className="block mb-1"><i className="pi pi-info-circle mr-2"></i>Validaciones Automáticas:</strong>
                <ul className="list-disc pl-5 space-y-1">
                    <li>Eliminación de duplicados (RUT, Email, Teléfono) si las columnas existen.</li>
                    <li>Cruce con reglas de negocio (Inhibición SQL) para <strong>{tipoCampana}</strong>.</li>
                    <li>Rechazo de registros gestionados el mismo día.</li>
                    {tipoCampana === 'SMS' && <li>Validación estricta de formato teléfono y largo de mensaje (160).</li>}
                    {tipoCampana !== 'SMS' && <li>Consolidación de correos (mail1-6) y normalización de teléfonos (agrega '56').</li>}
                </ul>
            </div>
        );
    };

    return (
        <div className="w-full card">
            <Toast ref={toast} />
            <h1 className="text-2xl font-bold mb-4 text-gray-800">Generador de Campañas</h1>

            {/* SECCIÓN DE EJECUCIÓN ACTIVA */}
            {(executionStatus === 'running' || executionStatus === 'complete' || executionStatus === 'error') && (
                <div className={`mb-6 p-4 border rounded-lg shadow-sm ${executionStatus === 'running' ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-200'}`}>
                    <h3 className="font-bold text-lg mb-3 text-gray-900">Estado de Ejecución</h3>
                    
                    {executionStatus === 'running' && (
                        <div className="flex flex-col md:flex-row items-center justify-between gap-4 p-4">
                            <div className="flex items-center gap-3">
                                <ProgressSpinner style={{width: '40px', height: '40px'}} strokeWidth="4" />
                                <span className="text-lg">Procesando validaciones y cruces...</span>
                            </div>
                            <Button 
                                label="Cancelar Proceso" 
                                icon="pi pi-stop-circle" 
                                className={btnSecondary} // Cambiado a secundario
                                onClick={handleCancel} 
                            />
                        </div>
                    )}

                    {executionStatus === 'complete' && (
                        <div className="animate-fade-in">
                            <div className="flex items-center gap-2 text-green-700 font-bold mb-4 text-xl">
                                <i className="pi pi-check-circle" style={{fontSize: '1.5rem'}}></i>
                                ¡Proceso Finalizado!
                            </div>

                            {/* TARJETA DE ESTADÍSTICAS */}
                            {executionStats && (
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                    <div className="bg-white p-4 rounded border border-gray-200 text-center">
                                        <div className="text-gray-500 text-sm font-bold uppercase">Total Registros</div>
                                        <div className="text-2xl font-bold text-blue-600">{executionStats.total_registros?.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-white p-4 rounded border border-gray-200 text-center border-l-4 border-l-green-500">
                                        <div className="text-gray-500 text-sm font-bold uppercase">Válidos</div>
                                        <div className="text-2xl font-bold text-green-600">{executionStats.total_validos?.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-white p-4 rounded border border-gray-200 text-center border-l-4 border-l-red-500">
                                        <div className="text-gray-500 text-sm font-bold uppercase">Rechazados</div>
                                        <div className="text-2xl font-bold text-red-600">{executionStats.total_rechazados?.toLocaleString()}</div>
                                    </div>
                                </div>
                            )}

                            {/* DETALLE RECHAZOS */}
                            {executionStats && executionStats.total_rechazados > 0 && executionStats.detalle_rechazo && (
                                <div className="mb-4 bg-red-50 p-3 rounded border border-red-100 text-sm">
                                    <strong className="text-red-800 block mb-1">Motivos de Rechazo:</strong>
                                    <ul className="list-disc pl-5 text-red-700">
                                        {Object.entries(executionStats.detalle_rechazo).map(([motivo, cant]) => (
                                            <li key={motivo}>
                                                <strong>{motivo}:</strong> {cant.toLocaleString()} registros
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            <div className="font-bold mb-2 text-gray-700">Archivos Generados:</div>
                            <ul className="list-none pl-0 space-y-2">
                                {executionResults.map((file, idx) => (
                                    <li key={idx} className="flex items-center gap-2 bg-white p-2 rounded border border-gray-200">
                                        <i className={`pi ${file.includes('RECHAZADOS') ? 'pi-times-circle text-red-500' : 'pi-file-excel text-green-500'}`}></i>
                                        <span className="text-sm font-mono">{file}</span>
                                    </li>
                                ))}
                            </ul>
                            
                            <div className="mt-4 flex justify-end">
                                <Button label="Cerrar" onClick={() => { setExecutionStatus(null); setExecutionStats(null); }} className="p-button-secondary" />
                            </div>
                        </div>
                    )}

                    {executionStatus === 'error' && (
                         <div className="flex justify-between items-center">
                            <div className="text-red-600 font-bold">La tarea falló. Revisa los logs.</div>
                            <Button label="Cerrar" onClick={() => setExecutionStatus(null)} className="p-button-secondary" />
                        </div>
                    )}
                </div>
            )}

            <TabView activeIndex={activeIndex} onTabChange={(e) => { setActiveIndex(e.index); if(e.index === 0 && !isEditing) resetForm(); }}>
                <TabPanel header="Mis Plantillas">
                    <div className="mb-4 flex justify-between">
                        <Button label="Refrescar" icon="pi pi-refresh" onClick={fetchPlantillas} size="small" className={btnSecondary} />
                        {isAdmin && (
                            <Button label="Nueva Plantilla" icon="pi pi-plus" onClick={() => { resetForm(); setActiveIndex(1); }} size="small" className={btnPrimary} />
                        )}
                    </div>
                    <DataTable value={plantillasGuardadas} stripedRows size="small" emptyMessage="No hay plantillas.">
                        <Column field="id" header="ID" sortable style={{width: '60px'}} />
                        <Column field="nombre_plantilla" header="Nombre" sortable />
                        <Column field="usuario_creador" header="Creador" sortable />
                        <Column 
                            field="fecha_creacion" 
                            header="Fecha" 
                            sortable 
                            body={(rowData) => formatDate(rowData.fecha_creacion)}
                            style={{ minWidth: '120px' }}
                        />
                        <Column header="Acciones" body={(rowData) => (
                            <div className="flex gap-2">
                                <Button icon="pi pi-play" className="p-button-rounded p-button-success p-button-text" tooltip="Ejecutar" onClick={() => handleEjecutar(rowData)} />
                                {isAdmin && (
                                    <Button icon="pi pi-pencil" className="p-button-rounded p-button-info p-button-text" tooltip="Editar" onClick={() => handleEditPlantilla(rowData)} />
                                )}
                            </div>
                        )} />
                    </DataTable>
                </TabPanel>

                {isAdmin && (
                    <TabPanel header={isEditing ? "Editar Plantilla" : "Nueva Plantilla"}>
                        <div className="flex flex-col gap-6 max-w-5xl mx-auto">
                            <div className="flex flex-col gap-2">
                                <label className="font-bold">Nombre de la Plantilla</label>
                                <InputText value={nombrePlantilla} onChange={(e) => setNombrePlantilla(e.target.value)} className={inputClass} />
                            </div>

                            {/* 1. FUENTE */}
                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">1. Fuente de Datos</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div>
                                        <label className="text-sm font-semibold block mb-1">Cliente</label>
                                        <Dropdown value={selectedCliente} options={clientesDisponibles} onChange={(e) => setSelectedCliente(e.value)} placeholder="Seleccione..." className="w-full" filter />
                                    </div>
                                    <div>
                                        <label className="text-sm font-semibold block mb-1">Estrategia Base</label>
                                        <Dropdown value={selectedEstrategia} options={estrategiasDisponibles} onChange={(e) => setSelectedEstrategia(e.value)} placeholder="Seleccione..." className="w-full" disabled={!selectedCliente} filter />
                                    </div>
                                </div>
                            </div>

                            {/* 2. CONFIGURACIÓN */}
                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">2. Configuración de Campaña</h3>
                                <div className="mb-2">
                                    <label className="text-sm font-semibold block mb-2">Tipo de Campaña</label>
                                    <Dropdown 
                                        value={tipoCampana} 
                                        options={tiposCampanaOptions} 
                                        onChange={(e) => setTipoCampana(e.value)} 
                                        placeholder="Seleccione el tipo..." 
                                        className="w-full md:w-1/2"
                                    />
                                </div>
                                {renderValidationInfo()}
                            </div>

                            {/* 3. DIVISIÓN */}
                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">3. División de Archivos</h3>
                                <div className="flex flex-col gap-2">
                                    <label className="text-sm font-semibold">Columnas para dividir (Máx 3)</label>
                                    <MultiSelect 
                                        value={columnasDivision} 
                                        options={columnasDisponibles} 
                                        onChange={(e) => setColumnasDivision(e.value)} 
                                        placeholder="Seleccione columnas (opcional)..." 
                                        maxSelectedLabels={3} selectionLimit={3}
                                        className="w-full" disabled={!selectedEstrategia} display="chip" filter
                                    />
                                    <small className="text-gray-500">Si se deja vacío, se generará un solo archivo.</small>
                                </div>
                            </div>

                            {/* 4. SALIDA */}
                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">4. Modo de Salida</h3>
                                <div className="flex gap-6">
                                    <div className="flex align-items-center"><input type="radio" id="out1" name="salida" value="archivo" checked={modoSalida === 'archivo'} onChange={(e) => setModoSalida(e.target.value)} className="w-4 h-4" /><label htmlFor="out1" className="ml-2">Generar Archivos Excel</label></div>
                                    <div className="flex align-items-center"><input type="radio" id="out2" name="salida" value="api" checked={modoSalida === 'api'} onChange={(e) => setModoSalida(e.target.value)} className="w-4 h-4" /><label htmlFor="out2" className="ml-2">Enviar a API</label></div>
                                </div>
                            </div>

                            <div className="flex justify-end mt-6 gap-3 pt-4 border-t">
                                <Button label="Cancelar" onClick={() => { resetForm(); setActiveIndex(0); }} className={btnSecondary} />
                                <Button label={isEditing ? "Actualizar" : "Guardar"} icon="pi pi-save" onClick={handleGuardar} className={btnPrimary} disabled={loading} />
                            </div>
                        </div>
                    </TabPanel>
                )}
            </TabView>
        </div>
    );
}

export default GeneradorCampanasPage;