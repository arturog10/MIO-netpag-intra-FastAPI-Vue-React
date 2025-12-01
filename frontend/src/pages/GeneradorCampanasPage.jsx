import React, { useState, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext.jsx';

// --- PrimeReact Components ---
import { TabView, TabPanel } from 'primereact/tabview';
import { Dropdown } from 'primereact/dropdown';
import { MultiSelect } from 'primereact/multiselect';
import { InputText } from 'primereact/inputtext';
import { InputTextarea } from 'primereact/inputtextarea';
import { Button } from 'primereact/button';
import { Toast } from 'primereact/toast';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { ProgressSpinner } from 'primereact/progressspinner';
import { InputNumber } from 'primereact/inputnumber';
import { Divider } from 'primereact/divider';
import { Badge } from 'primereact/badge';
import { Accordion, AccordionTab } from 'primereact/accordion';
import { Dialog } from 'primereact/dialog';
import { InputSwitch } from 'primereact/inputswitch';
import { Card } from 'primereact/card';

import { selectClass, inputClass, btnPrimary, btnSecondary, btnDanger } from '../styles/appStyles';

const API_VISOR_URL = '/api/visor';
const API_CAMPANAS_URL = '/api/campanas';

const tiposCampanaOptions = [
    { label: 'Mail Cobranza', value: 'MAIL' },
    { label: 'Mail Comercial', value: 'MAIL_INF' },
    { label: 'SMS', value: 'SMS' }
];

const tiposDatoOptions = [
    { label: 'Entero', value: 'int' },
    { label: 'Decimal', value: 'float' },
    { label: 'Texto', value: 'str' }
];

const operadoresOptions = [
    { label: 'Contiene', value: 'contiene' },
    { label: 'Igual (==)', value: '==' },
    { label: 'Distinto (!=)', value: '!=' },
    { label: 'Mayor (>)', value: '>' },
    { label: 'Menor (<)', value: '<' },
    { label: 'Mayor o Igual (>=)', value: '>=' },
    { label: 'Menor o Igual (<=)', value: '<=' },
    { label: 'Es Nulo / Vacío', value: 'es_nulo' },
    { label: 'No es Nulo / Vacío', value: 'no_es_nulo' }
];

function GeneradorCampanasPage() {
    const { token, user } = useAuth();
    const toast = useRef(null);
    const smsTextAreaRef = useRef(null); 

    // --- ESTADOS UI ---
    const [activeIndex, setActiveIndex] = useState(0);
    const [loading, setLoading] = useState(false);
    const [executingTaskId, setExecutingTaskId] = useState(null);
    const [executionStatus, setExecutionStatus] = useState(null);
    const [executionResults, setExecutionResults] = useState([]); 
    const [executionStats, setExecutionStats] = useState(null); 
    
    // NUEVO: Estado para mostrar el paso actual
    const [executionStep, setExecutionStep] = useState(""); 

    const pollerRef = useRef(null);

    // Preview & Check Files
    const [previewVisible, setPreviewVisible] = useState(false);
    const [previewData, setPreviewData] = useState([]);
    const [previewTitle, setPreviewTitle] = useState("");
    const [previewLoading, setPreviewLoading] = useState(false);
    const [existingFilesDialogVisible, setExistingFilesDialogVisible] = useState(false);
    const [existingFilesList, setExistingFilesList] = useState([]);
    const [pendingRunRowData, setPendingRunRowData] = useState(null);

    // --- ESTADOS FORMULARIO ---
    const [isEditing, setIsEditing] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [nombrePlantilla, setNombrePlantilla] = useState("");
    
    const [clientesDisponibles, setClientesDisponibles] = useState([]); 
    const [selectedCliente, setSelectedCliente] = useState(null);
    const [estrategiasDisponibles, setEstrategiasDisponibles] = useState([]); 
    const [selectedEstrategia, setSelectedEstrategia] = useState(null);
    
    const [tipoCampana, setTipoCampana] = useState(null); 
    const [selectedProveedor, setSelectedProveedor] = useState(null); 
    const [emailStrategy, setEmailStrategy] = useState("jerarquia");
    const [selectedEmailCol, setSelectedEmailCol] = useState(null);
    const [fonoStrategy, setFonoStrategy] = useState("jerarquia");
    const [selectedFonoCol, setSelectedFonoCol] = useState(null);
    const [mensajeSMS, setMensajeSMS] = useState("");
    const [colToInsertSMS, setColToInsertSMS] = useState(null);
    
    const [columnasDisponibles, setColumnasDisponibles] = useState([]); 
    const [columnasDivision, setColumnasDivision] = useState([]); 
    const [modoSalida, setModoSalida] = useState("archivo"); 
    const [plantillasGuardadas, setPlantillasGuardadas] = useState([]);
    const isAdmin = user?.rol === 'admin';
    const [strategyData, setStrategyData] = useState(null); 

    // --- REGLAS DE NEGOCIO ---
    const [segmentation, setSegmentation] = useState([
        { id: 'base', sufijo: 'BASE (Todos)', condiciones: [], formulas: [], columnas_estaticas: [] }
    ]);
    const [activeSegmentIndex, setActiveSegmentIndex] = useState(0);

    // Temporales
    const [tempTargetCol, setTempTargetCol] = useState("");
    const [tempFormula, setTempFormula] = useState("");
    const [tempCondicion, setTempCondicion] = useState(""); 
    const [tempTipoDato, setTempTipoDato] = useState("int");
    const [tempConstante, setTempConstante] = useState(null);
    const [colToInsert, setColToInsert] = useState(null);
    const [tempCondCol, setTempCondCol] = useState(null);
    const [tempCondOp, setTempCondOp] = useState(null);
    const [tempCondVal, setTempCondVal] = useState("");
    const [tempSegSufijo, setTempSegSufijo] = useState("");
    const [tempSegCol, setTempSegCol] = useState(null);
    const [tempSegOp, setTempSegOp] = useState("contiene");
    const [tempSegVal, setTempSegVal] = useState("");
    const [tempStaticCol, setTempStaticCol] = useState("");
    const [tempStaticVal, setTempStaticVal] = useState("");

    const proveedoresConfig = useMemo(() => ({
        'MAIL': [{ label: 'Punto Net', value: 'PUNTO_NET' }, { label: 'Fidelizador', value: 'FIDELIZADOR' }],
        'MAIL_INF': [{ label: 'Punto Net', value: 'PUNTO_NET' }, { label: 'Fidelizador', value: 'FIDELIZADOR' }],
        'SMS': [{ label: 'Masivian', value: 'MASIVIAN' }, { label: 'Siptel', value: 'SIPTEL' }]
    }), []);

    useEffect(() => { if (!isEditing) setSelectedProveedor(null); }, [tipoCampana]);
    const isOpNulo = (op) => op === 'es_nulo' || op === 'no_es_nulo';

    const availableColumns = useMemo(() => {
        const base = [...columnasDisponibles];
        if (!segmentation || activeSegmentIndex < 0 || activeSegmentIndex >= segmentation.length) return base;
        const currentSegment = segmentation[activeSegmentIndex];
        if (currentSegment) {
            if (currentSegment.formulas) { currentSegment.formulas.forEach(f => { if (f.columna && !base.find(b => b.value === f.columna.toLowerCase())) base.push({ label: `${f.columna} (Calc)`, value: f.columna.toLowerCase() }); }); }
            if (currentSegment.columnas_estaticas) { currentSegment.columnas_estaticas.forEach(c => { if (c.columna && !base.find(b => b.value === c.columna.toLowerCase())) base.push({ label: `${c.columna} (Fija)`, value: c.columna.toLowerCase() }); }); }
        }
        return base;
    }, [columnasDisponibles, segmentation, activeSegmentIndex]);

    const emailColumnsAvailable = useMemo(() => columnasDisponibles.filter(c => c.value.toLowerCase().includes('mail') || c.value.toLowerCase().includes('correo') || c.value.toLowerCase().includes('email')), [columnasDisponibles]);
    const fonoColumnsAvailable = useMemo(() => columnasDisponibles.filter(c => c.value.toLowerCase().includes('fono') || c.value.toLowerCase().includes('tel') || c.value.toLowerCase().includes('movil') || c.value.toLowerCase().includes('cel')), [columnasDisponibles]);

    useEffect(() => { if (activeSegmentIndex >= segmentation.length && segmentation.length > 0) setActiveSegmentIndex(segmentation.length - 1); }, [segmentation.length]);
    useEffect(() => { if (token) { fetchPlantillas(); fetchClientes(); } return () => stopPolling(); }, [token]);
    const fetchPlantillas = async () => { try { const res = await axios.get(`${API_CAMPANAS_URL}/plantillas`, { headers: { Authorization: `Bearer ${token}` } }); setPlantillasGuardadas(res.data); } catch (e) {} };
    const fetchClientes = async () => { try { const res = await axios.get(`${API_VISOR_URL}/clients`, { headers: { Authorization: `Bearer ${token}` } }); setClientesDisponibles(res.data.map(c => ({ label: c, value: c }))); } catch (e) {} };
    useEffect(() => { if (!selectedCliente || !token) { setEstrategiasDisponibles([]); return; } if (isEditing && estrategiasDisponibles.length > 0) return; const fetch = async () => { try { const res = await axios.get(`${API_VISOR_URL}/strategies/${selectedCliente}`, { headers: { Authorization: `Bearer ${token}` } }); setEstrategiasDisponibles(res.data.map(e => ({ label: e.nombre, value: e.id }))); } catch (e) {} }; fetch(); }, [selectedCliente, token, isEditing]);
    useEffect(() => { if (!selectedEstrategia || !token) { setColumnasDisponibles([]); setStrategyData(null); return; } const fetch = async () => { try { const res = await axios.get(`${API_VISOR_URL}/strategies/load/${selectedEstrategia}`, { headers: { Authorization: `Bearer ${token}` } }); const cols = JSON.parse(res.data.columnas_visibles || "[]"); setColumnasDisponibles(cols.map(c => ({ label: c.header, value: c.field }))); setStrategyData(res.data); } catch (e) {} }; fetch(); }, [selectedEstrategia, token]);

    // --- HANDLERS ---
    const resetForm = () => {
        setIsEditing(false); setEditingId(null); setNombrePlantilla(""); setSelectedCliente(null); setSelectedEstrategia(null); setTipoCampana(null); setColumnasDivision([]); setModoSalida("archivo");
        setSegmentation([{ id: 'base', sufijo: 'BASE (Todos)', condiciones: [], formulas: [], columnas_estaticas: [] }]);
        setActiveSegmentIndex(0);
        setTempTargetCol(""); setTempFormula(""); setTempSegSufijo(""); setTempCondCol(null); setTempCondOp(null); setTempCondVal(""); setTempSegCol(null); setTempSegOp("contiene"); setTempSegVal(""); setTempStaticCol(""); setTempStaticVal("");
        setSelectedProveedor(null); setEmailStrategy("jerarquia"); setSelectedEmailCol(null); setFonoStrategy("jerarquia"); setSelectedFonoCol(null); setMensajeSMS("");
        setStrategyData(null); setEstrategiasDisponibles([]);
    };

    const addSegmento = () => { if (!tempSegSufijo) { toast.current.show({ severity: 'warn', summary: 'Falta Sufijo', detail: 'Indique el nombre.' }); return; } const newSeg = { id: Date.now(), sufijo: tempSegSufijo, condiciones: [], formulas: [], columnas_estaticas: [] }; setSegmentation([...segmentation, newSeg]); setTempSegSufijo(""); setActiveSegmentIndex(segmentation.length); };
    const addSegmentoElse = () => setSegmentation([...segmentation, { id: 'else', sufijo: "RESTO", condicion: "else", condiciones: [], formulas: [], columnas_estaticas: [] }]);
    const removeSegment = (idx) => { if (segmentation.length === 1) return; setSegmentation(segmentation.filter((_, i) => i !== idx)); };
    const addConditionToSegment = () => { if (!tempSegCol) return; if (!isOpNulo(tempSegOp) && !tempSegVal) return; const newSegs = [...segmentation]; if (!newSegs[activeSegmentIndex].condiciones) newSegs[activeSegmentIndex].condiciones = []; newSegs[activeSegmentIndex].condiciones.push({ columna: tempSegCol, operador: tempSegOp, valor: isOpNulo(tempSegOp) ? '' : tempSegVal }); setSegmentation(newSegs); setTempSegVal(""); };
    const removeConditionFromSegment = (idxCond) => { const newSegs = [...segmentation]; newSegs[activeSegmentIndex].condiciones.splice(idxCond, 1); setSegmentation(newSegs); };
    const addStaticColToSegment = () => { if (!tempStaticCol || !tempStaticVal) return; const newSegs = [...segmentation]; if (!newSegs[activeSegmentIndex].columnas_estaticas) newSegs[activeSegmentIndex].columnas_estaticas = []; newSegs[activeSegmentIndex].columnas_estaticas.push({ columna: tempStaticCol, valor: tempStaticVal }); setSegmentation(newSegs); setTempStaticCol(""); setTempStaticVal(""); };
    const removeStaticColFromSegment = (i) => { const n = [...segmentation]; n[activeSegmentIndex].columnas_estaticas.splice(i, 1); setSegmentation(n); };
    const appendToFormula = (text) => setTempFormula(prev => prev + " " + text + " ");
    const clearFormula = () => setTempFormula("");
    const addFormulaToSegment = () => { if (!tempTargetCol || !tempFormula) { toast.current.show({ severity: 'warn', summary: 'Falta info', detail: 'Defina columna y fórmula.' }); return; } const newSegs = [...segmentation]; if (!newSegs[activeSegmentIndex].formulas) newSegs[activeSegmentIndex].formulas = []; if (tempCondCol && (!tempCondOp || (!isOpNulo(tempCondOp) && !tempCondVal))) { toast.current.show({ severity: 'warn', summary: 'Condición incompleta', detail: 'Complete operador y valor.' }); return; } newSegs[activeSegmentIndex].formulas.push({ columna: tempTargetCol, formula: tempFormula.trim(), cond_col: tempCondCol, cond_op: tempCondOp, cond_val: tempCondVal, tipo: tempTipoDato, rellenar_nulos: 0 }); setSegmentation(newSegs); setTempTargetCol(""); setTempFormula(""); setTempConstante(null); setTempCondCol(null); setTempCondOp(null); setTempCondVal(""); };
    const removeFormulaFromSegment = (i) => { const n = [...segmentation]; n[activeSegmentIndex].formulas.splice(i, 1); setSegmentation(n); };
    const insertColumnToSMS = (col) => { setMensajeSMS(prev => prev + " {" + col + "} "); setColToInsertSMS(null); };

    const handleEditPlantilla = async (rowData) => {
        setLoading(true);
        try {
            const resP = await axios.get(`${API_CAMPANAS_URL}/plantillas/${rowData.id}`, { headers: { Authorization: `Bearer ${token}` } });
            const plantilla = resP.data;
            let clienteCode = null;
            try {
                const resE = await axios.get(`${API_VISOR_URL}/strategies/load/${plantilla.id_estrategia_base}`, { headers: { Authorization: `Bearer ${token}` } });
                if (resE.data) { if (resE.data.codigo_cliente) clienteCode = resE.data.codigo_cliente; setStrategyData(resE.data); }
            } catch (err) {}

            setIsEditing(true); setEditingId(plantilla.id); setNombrePlantilla(plantilla.nombre_plantilla);
            if (clienteCode) { setSelectedCliente(clienteCode); try { const resList = await axios.get(`${API_VISOR_URL}/strategies/${clienteCode}`, { headers: { Authorization: `Bearer ${token}` } }); setEstrategiasDisponibles(resList.data.map(e => ({ label: e.nombre, value: e.id }))); } catch(e) {} }
            setSelectedEstrategia(plantilla.id_estrategia_base);

            try {
                const val = JSON.parse(plantilla.reglas_validacion_json || "{}");
                if (val.tipo_campana) setTipoCampana(val.tipo_campana);
                const proc = JSON.parse(plantilla.reglas_procesamiento_json || "{}");
                setColumnasDivision(proc.columnas_division || []);
                if (proc.proveedor) setSelectedProveedor(proc.proveedor);
                if (proc.estrategia_email) setEmailStrategy(proc.estrategia_email);
                if (proc.columna_email_elegida) setSelectedEmailCol(proc.columna_email_elegida);
                if (proc.estrategia_fono) setFonoStrategy(proc.estrategia_fono);
                if (proc.columna_fono_elegida) setSelectedFonoCol(proc.columna_fono_elegida);
                if (proc.mensaje_sms_template) setMensajeSMS(proc.mensaje_sms_template);
                if (proc.segmentacion && Array.isArray(proc.segmentacion)) { const segsSanitized = proc.segmentacion.map(s => ({ ...s, id: s.id || Date.now() + Math.random(), condiciones: Array.isArray(s.condiciones) ? s.condiciones : [], formulas: Array.isArray(s.formulas) ? s.formulas : [], columnas_estaticas: Array.isArray(s.columnas_estaticas) ? s.columnas_estaticas : [] })); setSegmentation(segsSanitized); } else { setSegmentation([{ id: 'base', sufijo: 'BASE (Todos)', condiciones: [], formulas: [], columnas_estaticas: [] }]); }
            } catch (e) {}
            setModoSalida(plantilla.modo_salida); setActiveIndex(1); setActiveSegmentIndex(0);
        } catch (error) { toast.current.show({ severity: 'error', summary: 'Error', detail: 'Error carga.' }); } finally { setLoading(false); }
    };

    const handleToggleEstado = async (rowData, nuevoValor) => {
        const originalList = [...plantillasGuardadas];
        setPlantillasGuardadas(prevList => prevList.map(p => p.id === rowData.id ? { ...p, estado: nuevoValor ? 1 : 0 } : p));
        try {
            await axios.patch(`${API_CAMPANAS_URL}/plantillas/${rowData.id}/estado`, { estado: nuevoValor ? 1 : 0 }, { headers: { Authorization: `Bearer ${token}` } });
            toast.current.show({ severity: 'success', summary: 'Estado', detail: `Plantilla ${nuevoValor ? 'Activada' : 'Desactivada'}` });
        } catch (error) {
            setPlantillasGuardadas(originalList);
            toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo cambiar el estado.' });
        }
    };

    const handleGuardar = async () => {
        if (!nombrePlantilla || !selectedEstrategia || !tipoCampana) { toast.current.show({ severity: 'warn', summary: 'Faltan datos', detail: 'Complete campos.' }); return; }
        if ((tipoCampana === 'MAIL' || tipoCampana === 'MAIL_INF') && emailStrategy === 'unica' && !selectedEmailCol) { toast.current.show({ severity: 'warn', summary: 'Falta Columna Email', detail: 'Seleccione columna.' }); return; }
        if ((tipoCampana === 'SMS') && fonoStrategy === 'unica' && !selectedFonoCol) { toast.current.show({ severity: 'warn', summary: 'Falta Columna Fono', detail: 'Seleccione columna.' }); return; }
        if (tipoCampana === 'SMS' && (selectedProveedor === 'MASIVIAN' || selectedProveedor === 'SIPTEL') && !mensajeSMS) { toast.current.show({ severity: 'warn', summary: 'Falta Mensaje', detail: 'Escriba el mensaje SMS.' }); return; }

        const payload = {
            nombre_plantilla: nombrePlantilla, id_estrategia_base: selectedEstrategia,
            reglas_validacion_json: JSON.stringify({ tipo_campana: tipoCampana }),
            reglas_procesamiento_json: JSON.stringify({ columnas_division: columnasDivision, segmentacion: segmentation, proveedor: selectedProveedor, estrategia_email: emailStrategy, columna_email_elegida: selectedEmailCol, estrategia_fono: fonoStrategy, columna_fono_elegida: selectedFonoCol, mensaje_sms_template: mensajeSMS }),
            modo_salida: modoSalida
        };
        try {
            const url = isEditing ? `${API_CAMPANAS_URL}/plantillas/${editingId}` : `${API_CAMPANAS_URL}/plantillas`;
            await axios[isEditing ? 'put' : 'post'](url, payload, { headers: { Authorization: `Bearer ${token}` } });
            toast.current.show({ severity: 'success', summary: 'Guardado', detail: 'Éxito.' });
            resetForm(); fetchPlantillas(); setActiveIndex(0);
        } catch (error) { toast.current.show({ severity: 'error', summary: 'Error', detail: 'Fallo al guardar.' }); }
    };

    // --- EJECUCIÓN ---
    const handleCheckAndRun = async (rowData) => {
        setPendingRunRowData(rowData);
        try {
            const res = await axios.get(`${API_CAMPANAS_URL}/check-existing/${rowData.id}`, { headers: { Authorization: `Bearer ${token}` } });
            if (res.data.files && res.data.files.length > 0) { setExistingFilesList(res.data.files); setExistingFilesDialogVisible(true); } 
            else { runCampaign(rowData); }
        } catch (error) { runCampaign(rowData); }
    };
    const runCampaign = async (rowData) => {
        setExistingFilesDialogVisible(false); 
        setExecutionStatus("running"); 
        setExecutionResults([]); 
        setExecutionStats(null); 
        setExecutionStep("Iniciando..."); // Reset paso
        setExecutingTaskId(null);
        try {
            const res = await axios.post(`${API_CAMPANAS_URL}/ejecutar/${rowData.id}`, {}, { headers: { Authorization: `Bearer ${token}` } });
            const taskId = res.data.task_id; 
            setExecutingTaskId(taskId);
            pollerRef.current = setInterval(() => checkStatus(taskId), 3000);
        } catch (error) { setExecutionStatus("error"); }
    };
    const checkStatus = async (taskId) => {
        try {
            const res = await axios.get(`${API_CAMPANAS_URL}/status/${taskId}`, { headers: { Authorization: `Bearer ${token}` } });
            
            // Actualizar paso visual (NUEVO)
            if (res.data.step) setExecutionStep(res.data.step);

            if (res.data.status === 'complete') { stopPolling(); fetchResultados(taskId); setExecutionStatus("complete"); }
            else if (res.data.status === 'error') { stopPolling(); setExecutionStatus("error"); }
            else if (res.data.status === 'cancelled') { stopPolling(); setExecutionStatus("cancelled"); }
        } catch (error) { stopPolling(); }
    };
    const fetchResultados = async (taskId) => { try { const res = await axios.get(`${API_CAMPANAS_URL}/resultados/${taskId}`, { headers: { Authorization: `Bearer ${token}` } }); if (res.data.resultados.archivos) { setExecutionResults(res.data.resultados.archivos); setExecutionStats(res.data.resultados.resumen); } } catch (e) {} };
    const stopPolling = () => { if (pollerRef.current) { clearInterval(pollerRef.current); pollerRef.current = null; } };
    const handleCancel = async () => { if (!executingTaskId) return; stopPolling(); setExecutionStatus("cancelled"); try { await axios.post(`${API_CAMPANAS_URL}/cancel/${executingTaskId}`, {}, { headers: { Authorization: `Bearer ${token}` } }); } catch (e) {} };
    const handlePreviewFile = async (filePath) => { setPreviewTitle(filePath.split('/').pop()); setPreviewVisible(true); setPreviewLoading(true); setPreviewData([]); try { const encodedPath = encodeURIComponent(filePath); const res = await axios.get(`${API_CAMPANAS_URL}/preview?file_path=${encodedPath}`, { headers: { Authorization: `Bearer ${token}` } }); setPreviewData(res.data); } catch (error) { toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo leer.' }); setPreviewVisible(false); } finally { setPreviewLoading(false); } };
    const handleDownloadZip = async (filesList) => { if (!filesList || filesList.length === 0) return; toast.current.show({ severity: 'info', summary: 'Generando ZIP...', detail: 'Descarga en breve.' }); try { const res = await axios.post(`${API_CAMPANAS_URL}/download-zip`, { files: filesList }, { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' }); const url = window.URL.createObjectURL(new Blob([res.data])); const link = document.createElement('a'); link.href = url; link.setAttribute('download', `campana_pack_${new Date().getTime()}.zip`); document.body.appendChild(link); link.click(); link.remove(); } catch (e) { toast.current.show({ severity: 'error', summary: 'Error', detail: 'Error descarga ZIP.' }); } };
    const handleDownloadFile = async (e, filePath) => { e.stopPropagation(); try { const res = await axios.get(`${API_CAMPANAS_URL}/download-file?file_path=${encodeURIComponent(filePath)}`, { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' }); const url = window.URL.createObjectURL(new Blob([res.data])); const link = document.createElement('a'); link.href = url; link.setAttribute('download', filePath.split('/').pop()); document.body.appendChild(link); link.click(); link.remove(); } catch (e) { toast.current.show({ severity: 'error', summary: 'Error', detail: 'Error descarga.' }); } };
    const formatDate = (dateString) => { if (!dateString) return "-"; const date = new Date(dateString); return `${date.getDate().toString().padStart(2,'0')}-${(date.getMonth()+1).toString().padStart(2,'0')}-${date.getFullYear()}`; };
    
    const renderValidationInfo = () => {
        if (!tipoCampana) return null;
        return (
            <div className="mt-3 p-3 bg-blue-50 border border-blue-100 rounded text-sm text-blue-800">
                <strong className="block mb-1"><i className="pi pi-info-circle mr-2"></i>Validaciones Automáticas:</strong>
                <ul className="list-disc pl-5 space-y-1">
                    <li>Filtro de registros ya gestionados hoy (masiv_dia).</li>
                    <li>Validación de Inhibiciones y Lista Negra (SP).</li>
                    <li>Validación por Ley Cobranza (Segmento).</li>
                    <li>Eliminación de Duplicados (RUT, IC).</li>
                    {tipoCampana === 'SMS' && ( <> <li>Validación de formato teléfono y prefijo 56.</li> <li>Eliminación de duplicados por Teléfono.</li> </> )}
                    {(tipoCampana === 'MAIL' || tipoCampana === 'MAIL_INF') && ( <> <li>Consolidación de correos ({emailStrategy === 'unica' ? 'Columna Única' : 'Jerarquía'}).</li> <li>Validación de formato email.</li> <li>Eliminación de duplicados por Email.</li> </> )}
                    {selectedCliente === '0360CQTA' && <li><strong>Reglas Especiales 0360CQTA:</strong> Duplicados por ID y Dirección.</li>}
                </ul>
            </div>
        );
    };

    return (
        <div className="w-full card">
            <Toast ref={toast} />
            {/* Dialogs Existentes y Preview */}
            <Dialog header="Archivos Existentes" visible={existingFilesDialogVisible} style={{ width: '50vw' }} onHide={() => setExistingFilesDialogVisible(false)} footer={<div className="flex justify-between w-full"><Button label="Descargar Todo (ZIP)" icon="pi pi-download" severity="success" onClick={() => handleDownloadZip(existingFilesList)} /><div className="flex gap-2"><Button label="Cancelar" icon="pi pi-times" onClick={() => setExistingFilesDialogVisible(false)} className="p-button-text" /><Button label="Ejecutar Igual" icon="pi pi-check" onClick={() => runCampaign(pendingRunRowData)} autoFocus /></div></div>} >
                <div className="mb-4 text-yellow-600 font-bold"><i className="pi pi-exclamation-triangle mr-2"></i>Ya existen archivos hoy.</div>
                <ul className="bg-gray-50 rounded border p-2 max-h-60 overflow-y-auto divide-y">{existingFilesList.map((f, i) => (<li key={i} className="p-2 hover:bg-blue-100 cursor-pointer flex items-center justify-between text-sm text-blue-700" onClick={() => handlePreviewFile(f)}><span className="underline truncate flex-1">{f.split('/').pop()}</span><div className="flex gap-2"><Button icon="pi pi-eye" rounded text size="small" tooltip="Ver" /><Button icon="pi pi-download" rounded text severity="success" size="small" tooltip="Descargar" onClick={(e) => handleDownloadFile(e, f)} /></div></li>))}</ul>
            </Dialog>
            <Dialog header={`Vista Previa: ${previewTitle}`} visible={previewVisible} style={{ width: '90vw' }} onHide={() => setPreviewVisible(false)} maximizable>
                {previewLoading ? <div className="flex justify-center p-4"><ProgressSpinner /></div> : (previewData.length > 0 ? <DataTable value={previewData} size="small" stripedRows scrollable scrollHeight="400px" className="text-xs">{Object.keys(previewData[0]).map((col) => <Column key={col} field={col} header={col} sortable style={{ minWidth: '150px' }} />)}</DataTable> : <div className="text-center p-4 text-gray-500">Vacío.</div>)}
            </Dialog>

            <h1 className="text-2xl font-bold mb-4 text-gray-800">Generador de Campañas</h1>

            {/* SECCIÓN EJECUCIÓN (CON PASO ACTUAL) */}
            {(executionStatus) && (
                <div className={`mb-6 p-4 border rounded-lg shadow-sm ${executionStatus === 'running' ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-200'}`}>
                    <h3 className="font-bold text-lg mb-3 text-gray-900">Estado de Ejecución</h3>
                    
                    {executionStatus === 'running' && (
                        <div className="flex flex-col p-4">
                            <div className="flex items-center gap-3 mb-2">
                                <ProgressSpinner style={{width:'30px', height:'30px'}}/>
                                <span className="font-bold text-blue-700">Procesando...</span>
                            </div>
                            {/* Muestra el paso actual aquí */}
                            <div className="text-sm text-gray-600 ml-10 italic">{executionStep || "Iniciando..."}</div>
                            
                            <div className="flex justify-end mt-2">
                                <Button label="Cancelar" className={btnSecondary} onClick={handleCancel} size="small"/>
                            </div>
                        </div>
                    )}

                    {executionStatus === 'complete' && (
                        <div>
                            <div className="flex justify-between items-center mb-4"><div className="text-green-600 font-bold text-xl">¡Finalizado!</div><Button label="Descargar Todo (ZIP)" icon="pi pi-download" severity="success" onClick={() => handleDownloadZip(executionResults)} /></div>
                            {executionStats && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                    <div className="p-3 bg-white border rounded">
                                        <h4 className="text-sm font-bold text-gray-500 uppercase mb-2">Resumen</h4>
                                        <div className="flex justify-between text-sm mb-1"><span>Total:</span><b>{executionStats.total_registros?.toLocaleString()}</b></div>
                                        <div className="flex justify-between text-sm mb-1 text-green-600"><span>Válidos:</span><b>{executionStats.total_validos?.toLocaleString()}</b></div>
                                        <div className="flex justify-between text-sm mb-1 text-red-600"><span>Rechazados:</span><b>{executionStats.total_rechazados?.toLocaleString()}</b></div>
                                    </div>
                                    <div className="p-3 bg-red-50 border border-red-100 rounded max-h-40 overflow-y-auto">
                                        <h4 className="text-sm font-bold text-red-800 uppercase mb-2">Motivos de Rechazo</h4>
                                        <ul className="text-xs list-disc pl-4 text-red-700">{executionStats.detalle_rechazo && Object.entries(executionStats.detalle_rechazo).map(([motivo, cant]) => (<li key={motivo}><b>{motivo}:</b> {cant.toLocaleString()}</li>))}</ul>
                                    </div>
                                </div>
                            )}
                             <h4 className="font-bold mb-2 text-gray-700">Archivos Generados:</h4>
                             <ul className="bg-white rounded border divide-y">{executionResults.map((file, idx) => (<li key={idx} className="p-3 hover:bg-blue-50 cursor-pointer flex items-center gap-3 transition-colors group" onClick={() => handlePreviewFile(file)}><i className={`pi ${file.includes('RECHAZADOS') ? 'pi-times-circle text-red-500' : 'pi-file-excel text-green-500'} text-xl`}></i><span className="text-sm font-mono flex-1 text-gray-700 group-hover:text-blue-600 group-hover:underline break-all">{file.split('/').pop()}</span><div className="flex gap-2 opacity-50 group-hover:opacity-100 transition-opacity"><Button icon="pi pi-eye" rounded text severity="info" tooltip="Ver" /><Button icon="pi pi-download" rounded text severity="success" tooltip="Descargar" onClick={(e) => handleDownloadFile(e, file)} /></div></li>))}</ul>
                            <div className="mt-4 flex justify-end"><Button label="Cerrar Panel" onClick={() => setExecutionStatus(null)} className="p-button-secondary" /></div>
                        </div>
                    )}
                    {executionStatus === 'error' && <div className="text-red-600 p-4">Error: {executionStats?.error_message || "Error desconocido"}</div>}
                    {executionStatus === 'cancelled' && <div className="text-orange-600 p-4">Cancelado por el usuario.</div>}
                </div>
            )}

            {/* Resto de Tabs (Mis Plantillas, Editar) IGUAL */}
            <TabView activeIndex={activeIndex} onTabChange={(e) => { setActiveIndex(e.index); if(e.index === 0 && !isEditing) resetForm(); }}>
                {/* ... (Contenido de los Tabs se mantiene igual que antes) ... */}
                <TabPanel header="Mis Plantillas">
                    <div className="mb-4 flex justify-between">
                        <Button label="Refrescar" icon="pi pi-refresh" onClick={fetchPlantillas} size="small" className={btnSecondary} />
                        {isAdmin && <Button label="Nueva Plantilla" icon="pi pi-plus" onClick={() => { resetForm(); setActiveIndex(1); }} size="small" className={btnPrimary} />}
                    </div>
                    <DataTable value={plantillasGuardadas} stripedRows size="small" emptyMessage="No hay plantillas disponibles.">
                        <Column field="id" header="ID" sortable style={{width:'60px'}}/>
                        <Column field="nombre_plantilla" header="Nombre" sortable />
                        {isAdmin && (<Column field="estado" header="Estado" body={(r) => (<InputSwitch checked={r.estado === 1} onChange={(e) => handleToggleEstado(r, e.value)} />)} sortable style={{width:'100px'}}/>)}
                        <Column header="Creado" sortable field="fecha_creacion" body={(r) => (<div className="flex flex-col"><span className="font-medium text-sm">{r.fecha_creacion}</span><span className="text-xs text-gray-500 truncate" title={r.usuario_creador}>{r.usuario_creador}</span></div>)} style={{ minWidth: '150px' }} />
                        <Column header="Modificado" sortable field="fecha_modificacion" body={(r) => { const sinModificacion = r.fecha_modificacion === '-' || !r.fecha_modificacion; return (<div className="flex flex-col"><span className={`font-medium text-sm ${sinModificacion ? 'text-gray-400' : ''}`}>{r.fecha_modificacion}</span>{!sinModificacion && r.usuario_modificacion && (<span className="text-xs text-gray-500 truncate" title={r.usuario_modificacion}>{r.usuario_modificacion}</span>)}</div>); }} style={{ minWidth: '150px' }} />
                        <Column header="Acciones" body={(rowData) => (<div className="flex gap-2">{rowData.estado !== 0 && (<Button icon="pi pi-play" className="p-button-rounded p-button-success p-button-text" onClick={() => handleCheckAndRun(rowData)} tooltip="Ejecutar" />)}{isAdmin && rowData.estado !== 0 && (<Button icon="pi pi-pencil" className="p-button-rounded p-button-info p-button-text" onClick={() => handleEditPlantilla(rowData)} tooltip="Editar" />)}</div>)} />
                    </DataTable>
                </TabPanel>

                {isAdmin && (
                    <TabPanel header={isEditing ? "Editar Plantilla" : "Nueva Plantilla"}>
                         {/* ... (Contenido del formulario igual que antes) ... */}
                        <div className="flex flex-col gap-6 max-w-5xl mx-auto">
                            <div className="flex flex-col gap-2">
                                <label className="font-bold">Nombre de la Plantilla</label>
                                <InputText value={nombrePlantilla} onChange={(e) => setNombrePlantilla(e.target.value)} className={inputClass} />
                            </div>
                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">1. Fuente de Datos</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div><label className="block mb-1 text-sm font-semibold">Cliente</label><Dropdown value={selectedCliente} options={clientesDisponibles} onChange={(e) => setSelectedCliente(e.value)} className="w-full" filter /></div>
                                    <div><label className="block mb-1 text-sm font-semibold">Estrategia Base</label><Dropdown value={selectedEstrategia} options={estrategiasDisponibles} onChange={(e) => setSelectedEstrategia(e.value)} className="w-full" disabled={!selectedCliente} filter /></div>
                                </div>
                                {strategyData && (
                                    <div className="mt-3">
                                        <Card title={strategyData.nombre_estrategia} subTitle="Estrategia Base Seleccionada" className="shadow-none bg-gray-50 border">
                                            <div className="text-xs text-gray-600">
                                                <p><strong>Filtros:</strong> {strategyData.filtros_aplicados || "Ninguno"}</p>
                                                <p><strong>Columnas:</strong> {JSON.parse(strategyData.columnas_visibles || "[]").map(c=>c.header).join(", ")}</p>
                                            </div>
                                        </Card>
                                    </div>
                                )}
                            </div>
                            
                            {/* ... Resto del formulario (Config, División, Reglas, Salida) IGUAL ... */}
                            {/* (Ya lo tienes en el mensaje anterior, solo asegúrate de que esté aquí) */}
                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">2. Configuración</h3>
                                <div className="grid grid-cols-2 gap-6 mb-4">
                                    <div><label className="block mb-2 text-sm font-semibold">Tipo de Campaña</label><Dropdown value={tipoCampana} options={tiposCampanaOptions} onChange={(e) => setTipoCampana(e.value)} placeholder="Seleccione..." className="w-full" /></div>
                                    <div><label className="block mb-2 text-sm font-semibold">Proveedor de Envío</label><Dropdown value={selectedProveedor} options={tipoCampana ? proveedoresConfig[tipoCampana] : []} onChange={(e) => setSelectedProveedor(e.value)} placeholder="Seleccione..." className="w-full" disabled={!tipoCampana} /></div>
                                </div>

                                {(tipoCampana === 'MAIL' || tipoCampana === 'MAIL_INF') && (
                                    <div className="bg-blue-50 p-3 rounded border border-blue-100 mb-3">
                                        <label className="block mb-2 text-sm font-bold text-blue-800">Estrategia de Contacto (Mail)</label>
                                        <div className="flex flex-col gap-3">
                                            <div className="flex align-items-center"><input type="radio" name="emailStrat" value="jerarquia" checked={emailStrategy === 'jerarquia'} onChange={(e) => setEmailStrategy(e.target.value)} className="w-4 h-4 text-blue-600"/><label className="ml-2 text-sm text-gray-700"><strong>Jerarquía Automática:</strong> Buscar el primer correo válido (Mail1 → Mail2...).</label></div>
                                            <div className="flex align-items-center"><input type="radio" name="emailStrat" value="unica" checked={emailStrategy === 'unica'} onChange={(e) => setEmailStrategy(e.target.value)} className="w-4 h-4 text-blue-600"/><label className="ml-2 text-sm text-gray-700"><strong>Columna Específica:</strong> Usar solo una columna. Si falla, se rechaza.</label></div>
                                            {emailStrategy === 'unica' && (<div className="ml-6 mt-1"><Dropdown value={selectedEmailCol} options={emailColumnsAvailable} onChange={(e) => setSelectedEmailCol(e.value)} placeholder="Seleccione columna..." className="w-full md:w-1/2 p-inputtext-sm" filter /></div>)}
                                        </div>
                                    </div>
                                )}

                                {tipoCampana === 'SMS' && (
                                    <div className="bg-blue-50 p-3 rounded border border-blue-100 mb-3">
                                        <label className="block mb-2 text-sm font-bold text-blue-800">Estrategia de Contacto (SMS)</label>
                                        <div className="flex flex-col gap-3">
                                            <div className="flex align-items-center"><input type="radio" name="fonoStrat" value="jerarquia" checked={fonoStrategy === 'jerarquia'} onChange={(e) => setFonoStrategy(e.target.value)} className="w-4 h-4 text-blue-600"/><label className="ml-2 text-sm text-gray-700"><strong>Jerarquía Automática:</strong> Buscar el primer teléfono válido (Fono1 → Fono2...).</label></div>
                                            <div className="flex align-items-center"><input type="radio" name="fonoStrat" value="unica" checked={fonoStrategy === 'unica'} onChange={(e) => setFonoStrategy(e.target.value)} className="w-4 h-4 text-blue-600"/><label className="ml-2 text-sm text-gray-700"><strong>Columna Específica:</strong> Usar solo una columna.</label></div>
                                            {fonoStrategy === 'unica' && (<div className="ml-6 mt-1"><Dropdown value={selectedFonoCol} options={fonoColumnsAvailable} onChange={(e) => setSelectedFonoCol(e.value)} placeholder="Seleccione columna..." className="w-full md:w-1/2 p-inputtext-sm" filter /></div>)}
                                            
                                            {/* Mensaje SMS */}
                                            <div className="mt-4 p-3 bg-white rounded border border-gray-300">
                                                <label className="block mb-1 text-sm font-bold text-gray-700">Mensaje SMS (Máx 160 chars)</label>
                                                <InputTextarea ref={smsTextAreaRef} value={mensajeSMS} onChange={(e) => setMensajeSMS(e.target.value)} rows={3} maxLength={160} className="w-full font-mono text-sm" placeholder="Hola {nombre}, recuerda pagar tu deuda de {deuda}..." />
                                                <div className="flex justify-between items-center mt-2">
                                                    <small className={`text-xs font-bold ${mensajeSMS.length > 150 ? 'text-red-500' : 'text-gray-500'}`}>{mensajeSMS.length}/160 caracteres</small>
                                                    <div className="flex gap-2 items-center">
                                                        <span className="text-xs text-gray-500">Insertar variable:</span>
                                                        <Dropdown value={colToInsertSMS} options={availableColumns} onChange={(e) => insertColumnToSMS(e.value)} placeholder="Columna..." className="p-inputtext-sm w-40" filter />
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                                {renderValidationInfo()}
                            </div>

                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">3. División</h3>
                                <label className="text-sm font-semibold">Columnas para dividir</label>
                                <MultiSelect value={columnasDivision} options={columnasDisponibles} onChange={(e) => setColumnasDivision(e.value)} className="w-full" display="chip" filter />
                            </div>

                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">4. Reglas de Segmentación y Cálculo</h3>
                                <div className="mb-4 flex flex-col gap-2 bg-gray-50 p-3 rounded border">
                                    <div className="flex gap-2 items-center mb-2">
                                        <span className="font-bold text-sm text-gray-700">Nuevo Segmento:</span>
                                        <InputText value={tempSegSufijo} onChange={(e) => setTempSegSufijo(e.target.value)} placeholder="Sufijo (_VIP)" className="p-inputtext-sm w-40" />
                                        <Button icon="pi pi-plus" label="Crear" size="small" onClick={addSegmento} />
                                        <Button icon="pi pi-filter" label="Else" size="small" severity="warning" outlined onClick={addSegmentoElse} />
                                    </div>
                                    <small className="text-gray-400">Crea un segmento y luego agrégale condiciones y cálculos.</small>
                                </div>

                                <Accordion activeIndex={activeSegmentIndex} onTabChange={(e) => setActiveSegmentIndex(e.index)}>
                                    {segmentation.map((seg, idx) => (
                                        <AccordionTab key={seg.id} header={<div className="flex align-items-center justify-content-between w-full"><div className="flex items-center gap-2"><span className="font-bold text-blue-800">{seg.sufijo}</span><Badge value={seg.condiciones?.length > 0 ? `${seg.condiciones.length} Filtros` : (seg.condicion === 'else' ? 'ELSE' : 'Sin Filtros')} severity={idx === 0 ? "info" : "warning"}></Badge></div>{idx > 0 && <Button icon="pi pi-trash" rounded text severity="danger" className="ml-auto p-1" onClick={(e) => { e.stopPropagation(); removeSegment(idx); }} />}</div>}>
                                            {/* ... (Contenido del Acordeón IGUAL QUE ANTES) ... */}
                                            <div className="flex flex-col gap-4">
                                                {seg.condicion !== 'else' && (
                                                    <div className="bg-yellow-50 p-3 rounded border border-yellow-200">
                                                        <h4 className="text-xs font-bold mb-2 text-yellow-700 uppercase">1. Condiciones de Filtro (AND)</h4>
                                                        <div className="grid grid-cols-12 gap-2 items-end mb-2">
                                                            <div className="col-span-4"><Dropdown value={tempSegCol} options={availableColumns} onChange={(e) => setTempSegCol(e.value)} placeholder="Columna" className="w-full p-inputtext-sm" filter /></div>
                                                            <div className="col-span-3"><Dropdown value={tempSegOp} options={operadoresOptions} onChange={(e) => setTempSegOp(e.value)} className="w-full p-inputtext-sm" /></div>
                                                            <div className="col-span-4"><InputText value={tempSegVal} onChange={(e) => setTempSegVal(e.target.value)} placeholder="Valor" className="w-full p-inputtext-sm" disabled={isOpNulo(tempSegOp)} /></div>
                                                            <div className="col-span-1"><Button icon="pi pi-plus" size="small" onClick={addConditionToSegment} className="w-full" /></div>
                                                        </div>
                                                        <ul className="text-xs list-disc pl-4">{seg.condiciones?.map((c, i) => (<li key={i} className="flex justify-between items-center mb-1"><span className="font-mono font-bold text-gray-700">{c.columna} <span className="text-blue-600">{c.operador}</span> {c.valor}</span><i className="pi pi-times text-red-500 cursor-pointer" onClick={()=>removeConditionFromSegment(i)}></i></li>))}</ul>
                                                    </div>
                                                )}
                                                <div className="border p-3 rounded">
                                                    <h4 className="text-xs font-bold mb-2 text-gray-500 uppercase">2. Columnas Fijas</h4>
                                                    <div className="grid grid-cols-12 gap-2 mb-2 items-end">
                                                        <div className="col-span-5"><InputText placeholder="Nombre Columna" value={tempStaticCol} onChange={(e)=>setTempStaticCol(e.target.value)} className="w-full p-inputtext-sm"/></div>
                                                        <div className="col-span-6"><InputText placeholder="Valor" value={tempStaticVal} onChange={(e)=>setTempStaticVal(e.target.value)} className="w-full p-inputtext-sm"/></div>
                                                        <div className="col-span-1"><Button icon="pi pi-plus" size="small" text className="w-full" onClick={addStaticColToSegment}/></div>
                                                    </div>
                                                    <ul className="text-xs pl-4 list-disc">{seg.columnas_estaticas?.map((c, i) => (<li key={i} className="flex justify-between"><span>{c.columna}={c.valor}</span><i className="pi pi-times text-red-500 cursor-pointer" onClick={()=>removeStaticColFromSegment(i)}></i></li>))}</ul>
                                                </div>
                                                <div className="border p-3 rounded bg-gray-50">
                                                    <h4 className="text-xs font-bold mb-2 text-gray-500 uppercase">3. Fórmulas</h4>
                                                    <div className="grid grid-cols-12 gap-2 mb-3 items-end">
                                                        <div className="col-span-6"><label className="text-xs text-gray-500">Nueva Columna</label><InputText value={tempTargetCol} onChange={(e) => setTempTargetCol(e.target.value)} placeholder="Ej: total" className="w-full p-inputtext-sm" /></div>
                                                        <div className="col-span-6"><label className="text-xs text-gray-500">Tipo</label><Dropdown value={tempTipoDato} options={tiposDatoOptions} onChange={(e) => setTempTipoDato(e.value)} className="w-full p-inputtext-sm" /></div>
                                                    </div>
                                                    <div className="grid grid-cols-12 gap-2 mb-2 items-center bg-white p-2 border rounded">
                                                        <div className="col-span-1 text-xs font-bold text-gray-400">Si:</div>
                                                        <div className="col-span-4"><Dropdown value={tempCondCol} options={availableColumns} onChange={(e)=>setTempCondCol(e.value)} placeholder="Columna" className="w-full p-inputtext-sm" filter /></div>
                                                        <div className="col-span-3"><Dropdown value={tempCondOp} options={operadoresOptions} onChange={(e)=>setTempCondOp(e.value)} placeholder="Op" className="w-full p-inputtext-sm" /></div>
                                                        <div className="col-span-4"><InputText value={tempCondVal} onChange={(e)=>setTempCondVal(e.target.value)} placeholder="Valor" className="w-full p-inputtext-sm" disabled={isOpNulo(tempCondOp)} /></div>
                                                    </div>
                                                    <div className="bg-white p-2 border rounded mb-4">
                                                        <div className="flex gap-2 mb-2 items-center">
                                                            <div className="p-inputgroup flex-1"><InputText value={tempFormula} readOnly className="w-full font-mono bg-gray-100 p-inputtext-sm border-none" placeholder="Usa botones ->" /><Button icon="pi pi-times" className="p-button-danger" onClick={clearFormula} tooltip="Limpiar" /></div>
                                                            <Button icon="pi pi-check" className="p-button-success" onClick={addFormulaToSegment} tooltip="Guardar Cálculo" />
                                                        </div>
                                                        <div className="flex flex-wrap gap-1 justify-between items-center">
                                                            <div className="flex gap-1">
                                                                <Dropdown value={colToInsert} options={availableColumns} onChange={(e)=>{appendToFormula(e.value); setColToInsert(null);}} placeholder="Insertar Col..." className="w-40 p-inputtext-sm" filter />
                                                                {['+', '-', '*', '/', '(', ')'].map(op => <Button key={op} label={op} size="small" outlined className="p-1 w-8 text-center" onClick={() => appendToFormula(op)} />)}
                                                            </div>
                                                            <div className="flex items-center border rounded px-1"><InputNumber value={tempConstante} onValueChange={(e)=>setTempConstante(e.value)} placeholder="#" inputClassName="w-16 p-1 text-sm text-center border-none" /><Button icon="pi pi-plus" text size="small" onClick={()=>{if(tempConstante!==null)appendToFormula(tempConstante.toString());setTempConstante(null)}}/></div>
                                                        </div>
                                                    </div>
                                                    <div className="mt-4 border rounded overflow-hidden">
                                                        <table className="w-full text-sm text-left bg-white">
                                                            <thead className="bg-gray-100 text-gray-600 border-b"><tr><th className="p-2">Columna</th><th className="p-2">Fórmula</th><th className="p-2">Condición</th><th className="p-2 w-10"></th></tr></thead>
                                                            <tbody>{seg.formulas?.map((f, i) => (<tr key={i} className="border-b last:border-0 hover:bg-gray-50"><td className="p-2 font-bold text-blue-600">{f.columna}</td><td className="p-2 font-mono break-all">{f.formula}</td><td className="p-2 text-xs text-gray-500">{f.cond_col ? `${f.cond_col} ${f.cond_op} ${f.cond_val}` : '-'}</td><td className="p-2 text-center"><Button icon="pi pi-trash" rounded text severity="danger" size="small" onClick={() => removeFormulaFromSegment(i)} /></td></tr>))}</tbody>
                                                        </table>
                                                    </div>
                                                </div>
                                            </div>
                                        </AccordionTab>
                                    ))}
                                </Accordion>
                            </div>

                            <div className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                                <h3 className="font-bold mb-4 text-blue-800 border-b pb-2">5. Modo de Salida</h3>
                                <div className="flex gap-6"><div className="flex align-items-center"><input type="radio" id="out1" name="salida" value="archivo" checked={modoSalida === 'archivo'} onChange={(e) => setModoSalida(e.target.value)} className="w-4 h-4" /><label htmlFor="out1" className="ml-2">Generar Archivos Excel</label></div><div className="flex align-items-center"><input type="radio" id="out2" name="salida" value="api" checked={modoSalida === 'api'} onChange={(e) => setModoSalida(e.target.value)} className="w-4 h-4" /><label htmlFor="out2" className="ml-2">Enviar a API</label></div></div>
                            </div>
                            <div className="flex justify-end mt-6 gap-3 pt-4 border-t"><Button label="Cancelar" onClick={() => { resetForm(); setActiveIndex(0); }} className={btnSecondary} /><Button label={isEditing ? "Actualizar" : "Guardar"} icon="pi pi-save" onClick={handleGuardar} className={btnPrimary} disabled={loading} /></div>
                        </div>
                    </TabPanel>
                )}
            </TabView>
        </div>
    );
}

export default GeneradorCampanasPage;