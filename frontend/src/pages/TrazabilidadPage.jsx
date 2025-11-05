// Ruta: src/pages/TrazabilidadPage.jsx
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext.jsx';
import { useNavigate } from 'react-router-dom';

// --- Importaciones de Componentes Reutilizados ---
import FiltroPanel from '../components/FiltroPanel'; //
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Paginator } from 'primereact/paginator';
import { Button } from 'primereact/button';
import { Dropdown } from 'primereact/dropdown';
import { Calendar } from 'primereact/calendar';
import { Toast } from 'primereact/toast';
import { ProgressSpinner } from 'primereact/progressspinner';
import { MultiSelect } from 'primereact/multiselect'; // Para el selector de columnas

// --- Estilos Globales (Asume que este archivo existe) ---
import { btnPrimary, btnSecondary, btnDanger, selectClass, calendarInputClass } from '../styles/appStyles';

const API_URL = 'http://localhost:8000/api/trazabilidad';

const sufijoOptions = [
    { label: 'Masividades', value: 'MASI' },
    { label: 'Discador', value: 'DISC' },
];

function TrazabilidadPage() {
    const toast = useRef(null);
    const navigate = useNavigate();
    const { token } = useAuth();
    
    // --- Estado de la Tarea ---
    const [isLoading, setIsLoading] = useState(false); // Spinner principal de consulta
    const [isColLoading, setIsColLoading] = useState(false); // Spinner de carga de columnas
    const [currentTaskId, setCurrentTaskId] = useState(null);
    const pollerRef = useRef(null); // Ref para guardar el ID del intervalo de sondeo

    // --- Estado de Datos de la Grilla ---
    const [resultados, setResultados] = useState([]);
    const [totalRows, setTotalRows] = useState(0);

    // --- Estado de Filtros Principales (UI) ---
    const [sufijo, setSufijo] = useState("");
    const [fechaDesde, setFechaDesde] = useState(null);
    const [fechaHasta, setFechaHasta] = useState(null);
    
    // --- Estado de Columnas ---
    const [allColumns, setAllColumns] = useState([]); // Todas las columnas disponibles
    const [visibleColumns, setVisibleColumns] = useState([]); // Columnas que se muestran en la grilla (objetos {field, header})
    
    // --- Estado de Filtros Avanzados (para FiltroPanel) ---
    const [filtrosActivos, setFiltrosActivos] = useState({});
    const [filtroPanelKey, setFiltroPanelKey] = useState(0); // Para forzar re-render de FiltroPanel

    // --- Estado de Paginación ---
    const [first, setFirst] = useState(0); // Índice del primer elemento
    const [rows, setRows] = useState(15);   // Cantidad de filas por página

    // --- Headers de Autenticación ---
    const getAuthHeaders = useCallback(() => {
        if (!token) {
            console.error("No hay token para la petición");
            navigate('/login');
            return {};
        }
        return { Authorization: `Bearer ${token}` };
    }, [token, navigate]);

    // --- Lógica de Limpieza de Sondeo ---
    const stopPolling = useCallback(() => {
        if (pollerRef.current) {
            clearInterval(pollerRef.current);
            pollerRef.current = null;
        }
    }, []);

    // Limpia el sondeo si el usuario se va de la página
    useEffect(() => {
        return () => {
            stopPolling();
        };
    }, [stopPolling]);

    // --- LÓGICA DE MANEJADORES DE EVENTOS ---

    // 1. Al cambiar el Tipo (Masividades/Discador)
    const handleSufijoChange = async (suf) => {
        setSufijo(suf);
        setIsColLoading(true);
        setAllColumns([]);
        setVisibleColumns([]);
        setFiltrosActivos({});
        setResultados([]);
        setTotalRows(0);
        setFiltroPanelKey(prev => prev + 1); // Forzar re-render
        setFirst(0); // Resetear paginación
        setRows(15); // Resetear paginación
        
        if (!suf) {
            setIsColLoading(false);
            return;
        }

        try {
            const response = await axios.get(`${API_URL}/columns/${suf}`, { headers: getAuthHeaders() });
            const columnNames = response.data;
            setAllColumns(columnNames);
            // Por defecto, todas visibles, en el formato {field, header}
            setVisibleColumns(columnNames.map(name => ({ field: name, header: name.toUpperCase() })));
        } catch (error) {
            console.error("Error al cargar columnas:", error);
            toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar las columnas.' });
        } finally {
            setIsColLoading(false);
        }
    };

    // 2. Al cambiar Columnas Visibles (desde MultiSelect)
    // (Lógica de Visor.jsx)
    const onColumnToggle = (event) => {
        setVisibleColumns(event.value);
    };
    
    // Opciones para el MultiSelect
    // (Lógica de Visor.jsx)
    const columnOptions = useMemo(() => 
        allColumns.map(name => ({ field: name, header: name.toUpperCase() }))
    , [allColumns]);


    // 3. Al cambiar Filtros Avanzados (desde FiltroPanel)
    const handleAplicarFiltros = useCallback((nuevosFiltros) => {
        setFiltrosActivos(nuevosFiltros);
        // No consultamos, solo guardamos el estado
    }, []);

    const handleLimpiarFiltros = useCallback(() => {
        setFiltrosActivos({});
        setFiltroPanelKey(prev => prev + 1); // Resetear FiltroPanel
        setResultados([]); // Limpiar resultados
        setTotalRows(0);
        setFirst(0); // Resetear paginación
        setRows(15); // Resetear paginación
        toast.current.show({ severity: 'info', summary: 'Filtros Limpiados', detail: 'Se han limpiado los filtros y resultados.' });
    }, []);

    // --- LÓGICA DE CONSULTA ASÍNCRONA (El núcleo) ---

    // 4. Al presionar "Consultar"
    const handleConsultar = async () => {
        if (!sufijo || !fechaDesde || !fechaHasta) {
            toast.current.show({ severity: 'warn', summary: 'Campos requeridos', detail: 'Seleccione Tipo, Fecha Desde y Fecha Hasta.' });
            return;
        }
        if (visibleColumns.length === 0) {
            toast.current.show({ severity: 'warn', summary: 'Columnas requeridas', detail: 'Seleccione al menos una columna visible.' });
            return;
        }
        
        stopPolling(); // Detiene cualquier sondeo anterior
        setIsLoading(true);
        setResultados([]);
        setTotalRows(0);
        setFirst(0); // Resetear paginación
        setRows(15); // Resetear paginación
        toast.current.show({ 
            severity: 'info', summary: 'Consulta Iniciada', 
            detail: 'Tu consulta se está procesando en segundo plano. Esto puede tardar varios minutos...', 
            life: 5000 
        });

        // Formatea las fechas para la API (Esto produce DD/MM/YYYY)
        const formatApiDate = (date) => date.toLocaleDateString('es-CL', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/-/g, '/');
        const requestBody = {
            sufijo: sufijo,
            fecha_desde: formatApiDate(fechaDesde),
            fecha_hasta: formatApiDate(fechaHasta),
            filtros: filtrosActivos,
            visible_columns: allColumns // Enviamos TODAS las columnas
        };

        try {
            // 4a. Inicia la tarea
            const response = await axios.post(`${API_URL}/start`, requestBody, { headers: getAuthHeaders() });
            const { task_id } = response.data;
            setCurrentTaskId(task_id);
            
            // 4b. Inicia el sondeo (polling)
            pollerRef.current = setInterval(() => {
                checkTaskStatus(task_id);
            }, 10000); // Sondea cada 10 segundos

        } catch (error) {
            console.error("Error al iniciar la consulta:", error);
            const detail = error.response?.data?.detail || error.message;
            toast.current.show({ severity: 'error', summary: 'Error', detail: `No se pudo iniciar la consulta: ${detail}` });
            setIsLoading(false);
        }
    };

    // 5. El Sondeo (llamado por el intervalo)
    const checkTaskStatus = async (taskId) => {
        try {
            const response = await axios.get(`${API_URL}/status/${taskId}`, { headers: getAuthHeaders() });
            const { status, error } = response.data;

            if (status === 'complete') {
                stopPolling();
                toast.current.show({ severity: 'success', summary: 'Consulta Completa', detail: 'Cargando resultados en la grilla...' });
                handleFetchResults(taskId); // Tarea completada, trae los datos
            } else if (status === 'error') {
                stopPolling();
                setIsLoading(false);
                toast.current.show({ severity: 'error', summary: 'Error en Consulta', detail: error || 'La tarea falló en el servidor.' });
                setCurrentTaskId(null); // Limpiar ID de tarea
            } else if (status === 'cancelled') {
                stopPolling();
                setIsLoading(false);
                toast.current.show({ severity: 'warn', summary: 'Tarea Cancelada', detail: 'La consulta ha sido cancelada.' });
                setCurrentTaskId(null); // Limpiar ID de tarea
            } else if (status === 'not_found') {
                stopPolling();
                setIsLoading(false);
                toast.current.show({ severity: 'error', summary: 'Tarea no encontrada', detail: 'La tarea no existe o ya ha sido procesada.' });
                setCurrentTaskId(null); // Limpiar ID de tarea
            }
            // Si el estado es 'running', no hace nada y sigue sondeando...

        } catch (error) {
            console.error("Error en el sondeo:", error);
            stopPolling();
            setIsLoading(false);
            toast.current.show({ severity: 'error', summary: 'Error de Conexión', detail: 'Se perdió la conexión con el servidor mientras se sondeaba la tarea.' });
            setCurrentTaskId(null); // Limpiar ID de tarea
        }
    };

    // 6. Obtener Resultados (al finalizar)
    const handleFetchResults = async (taskId) => {
        try {
            const response = await axios.get(`${API_URL}/results/${taskId}`, { headers: getAuthHeaders() });
            setResultados(response.data);
            setTotalRows(response.data.length);
        } catch (error) {
            console.error("Error al obtener resultados:", error);
            toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar los resultados.' });
        } finally {
            setIsLoading(false);
            // NOTA: Dejamos el currentTaskId para permitir la exportación de estos resultados
            // Lo limpiaremos en la próxima consulta o al limpiar filtros.
        }
    };

    // 7. Al presionar "Cancelar"
    const handleCancelar = async () => {
        if (!currentTaskId) return;
        
        toast.current.show({ severity: 'warn', summary: 'Cancelando...', detail: 'Enviando solicitud de cancelación...' });
        stopPolling(); // Detiene el sondeo
        
        try {
            await axios.post(`${API_URL}/cancel/${currentTaskId}`, {}, { headers: getAuthHeaders() });
            toast.current.show({ severity: 'info', summary: 'Cancelación Solicitada', detail: 'La consulta se detendrá en breve.' });
        } catch (error) {
            console.error("Error al cancelar:", error);
            const detail = error.response?.data?.detail || error.message;
            toast.current.show({ severity: 'error', summary: 'Error', detail: `No se pudo enviar la solicitud de cancelación: ${detail}` });
        } finally {
            setIsLoading(false);
            setCurrentTaskId(null); // Ya no hay tarea activa
        }
    };

    // 8. Exportar
    const handleExport = async (formato) => {
        if (resultados.length === 0) {
            toast.current.show({ severity: 'warn', summary: 'Sin datos', detail: 'No hay resultados en la grilla para exportar.' });
            return;
        }

        // Usamos el ID de la última tarea exitosa (guardado en currentTaskId)
        if (!currentTaskId) {
            toast.current.show({ severity: 'warn', summary: 'Error de Exportación', detail: 'No se encontró el ID de la consulta. Realice una nueva consulta.' });
            return;
        }

        toast.current.show({ severity: 'info', summary: 'Exportando...', detail: 'Preparando archivo para descargar...' });
        
        const exportBody = {
            formato: formato,
            // Exporta solo las columnas que el usuario está viendo
            visible_columns: visibleColumns.map(col => col.field)
        };

        try {
            // Llama al endpoint de exportación que usa la data cacheada en el backend
            const response = await axios.post(
                `${API_URL}/export/${currentTaskId}`,
                exportBody,
                { responseType: 'blob', headers: getAuthHeaders() }
            );

            // (Lógica de descarga copiada de Visor.jsx)
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            const contentDisposition = response.headers['content-disposition'];
            let filename = `exportacion_${sufijo}_${new Date().toISOString().slice(0,10)}.${formato === 'excel' ? 'xlsx' : 'csv'}`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch && filenameMatch.length === 2) filename = filenameMatch[1];
            }
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.parentNode.removeChild(link);
            window.URL.revokeObjectURL(url);
            toast.current.show({ severity: 'success', summary: 'Exportación Exitosa', detail: 'Archivo descargado.' });

        } catch (error) {
            console.error("Error al exportar:", error);
            const detail = error.response?.data?.detail || error.message;
            toast.current.show({ severity: 'error', summary: 'Error', detail: `No se pudo generar el archivo: ${detail}` });
        }
    };
    
    // --- Paginación ---
    const onPageChange = (event) => {
        setFirst(event.first);
        setRows(event.rows);
    };

    // Columnas de la grilla (solo las visibles)
    // (Lógica de Visor.jsx)
    const dynamicColumns = useMemo(() => visibleColumns.map(col => (
        <Column 
            key={col.field} 
            field={col.field} 
            header={col.header} 
            sortable 
            filter // Habilita filtro en cliente
            filterMatchMode="contains" 
        />
    )), [visibleColumns]);

    // Datos paginados en el frontend
    const paginatedResults = useMemo(() => {
        if (!resultados || resultados.length === 0) return [];
        return resultados.slice(first, first + rows);
    }, [resultados, first, rows]);


    return (
        // Quitamos el 'card' y 'mx-auto' para que tome el padding del MainLayout en App.jsx
        <div className="w-full"> 
            <Toast ref={toast} />
            {/* <h1 className="text-3xl font-bold mb-4 text-gray-800">Consulta de Trazabilidad</h1> */}

            {/* --- 1. Panel Principal de Filtros y Acciones --- */}
            <div className="p-4 border border-gray-200 rounded-lg shadow-sm bg-white mb-4">
                <div className="flex flex-wrap gap-4 items-center">
                    {/* Fecha Desde */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="fechaDesde" className="font-semibold text-sm text-gray-700">Fecha Desde</label>
                        <Calendar id="fechaDesde" value={fechaDesde} onChange={(e) => setFechaDesde(e.value)} dateFormat="dd/mm/yy" placeholder="DD/MM/AAAA" inputClassName={calendarInputClass} showIcon />
                    </div>
                    {/* Fecha Hasta */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="fechaHasta" className="font-semibold text-sm text-gray-700">Fecha Hasta</label>
                        <Calendar id="fechaHasta" value={fechaHasta} onChange={(e) => setFechaHasta(e.value)} dateFormat="dd/mm/yy" placeholder="DD/MM/AAAA" inputClassName={calendarInputClass} showIcon />
                    </div>
                    {/* Tipo de Consulta */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="sufijo" className="font-semibold text-sm text-gray-700">Tipo de Consulta</label>
                        <Dropdown id="sufijo" value={sufijo} options={sufijoOptions} onChange={(e) => handleSufijoChange(e.value)} placeholder="Selecciona un tipo..." className={selectClass} />
                    </div>
                    {/* Spinner de carga de columnas */}
                    {isColLoading && <ProgressSpinner style={{width: '30px', height: '30px'}} strokeWidth="6" />}

                    {/* Selector de Columnas (estilo Visor.jsx) */}
                    <div className="ml-auto">
                        <MultiSelect
                            value={visibleColumns}
                            options={columnOptions}
                            onChange={onColumnToggle}
                            optionLabel="header"
                            placeholder="Seleccionar Columnas"
                            maxSelectedLabels={0}
                            selectedItemsLabel={`${visibleColumns.length} columnas`}
                            className="w-full md:w-20rem text-sm"
                            disabled={allColumns.length === 0}
                            filter
                        />
                    </div>
                </div>
            </div>

            {/* --- 2. Acordeón ÚNICO para Filtros Avanzados (como en Visor.jsx) --- */}
            {allColumns.length > 0 && !isColLoading && (
                <FiltroPanel
                    allColumns={visibleColumns.map(col => col.field)} // Filtra sobre las columnas visibles
                    initialFilters={filtrosActivos}
                    onAplicarFiltros={handleAplicarFiltros}
                    onLimpiarFiltros={handleLimpiarFiltros}
                    key={`filtropanel-${sufijo}-${filtroPanelKey}`}
                />
            )}
            
            {/* --- 3. Botones de Acción (Movidos debajo del FiltroPanel) --- */}
            <div className="flex justify-end gap-2 mb-4 mt-4">
                {!isLoading ? (
                    <>
                        <Button 
                            label="Limpiar Filtros y Grilla" 
                            onClick={handleLimpiarFiltros} 
                            className={btnSecondary} 
                            icon="pi pi-times" 
                            disabled={allColumns.length === 0}
                        />
                        <Button 
                            label="Consultar" 
                            onClick={handleConsultar} 
                            className={btnPrimary} 
                            icon="pi pi-search" 
                            disabled={allColumns.length === 0 || !fechaDesde || !fechaHasta || visibleColumns.length === 0}
                        />
                    </>
                ) : (
                    <Button 
                        label="Cancelar Consulta" 
                        onClick={handleCancelar} 
                        className={btnDanger} 
                        icon="pi pi-stop-circle"
                    />
                )}
            </div>

            {/* --- 4. Grilla de Resultados --- */}
            <div className="relative p-4 border border-gray-200 rounded-lg shadow-sm bg-white">
                {isLoading && (
                    <div className="absolute inset-0 bg-white bg-opacity-70 flex flex-col justify-center items-center z-20 rounded-lg">
                        <ProgressSpinner />
                        <span className="mt-4 font-semibold text-lg text-gray-700">Consultando... Esto puede tardar varios minutos.</span>
                        <span className="text-sm text-gray-500">Mantén esta ventana abierta o presiona "Cancelar".</span>
                    </div>
                )}
                
                <div className="flex justify-between items-center mb-4">
                    {/* <h2 className="text-xl font-semibold text-gray-800">Resultados de la Consulta</h2> */}
                    <div className="flex gap-2">
                        <Button 
                            label="Exportar Excel" 
                            icon="pi pi-file-excel" 
                            disabled={isLoading || resultados.length === 0} 
                            onClick={() => handleExport('excel')} 
                            severity="success" 
                            size="small"
                        />
                        <Button 
                            label="Exportar CSV" 
                            icon="pi pi-file" 
                            disabled={isLoading || resultados.length === 0} 
                            onClick={() => handleExport('csv')} 
                            severity="info" 
                            size="small"
                        />
                    </div>
                </div>

                <DataTable
                    value={paginatedResults}
                    lazy={false} // Paginación y filtro son en cliente
                    rows={rows}
                    first={first}
                    totalRecords={totalRows}
                    loading={isLoading}
                    stripedRows
                    size="small"
                    scrollable
                    scrollHeight="calc(100vh - 600px)" // Ajusta la altura
                    emptyMessage={isLoading ? "Cargando datos..." : "No hay filas para mostrar. Realice una consulta."}
                    resizableColumns
                    sortMode="multiple" // Habilita orden en cliente
                    paginator={false} // Usamos el paginador externo
                >
                    {dynamicColumns}
                </DataTable>

                {totalRows > 0 && (
                    <Paginator
                        first={first}
                        rows={rows}
                        totalRecords={totalRows}
                        rowsPerPageOptions={[15, 30, 50, 100, 500]}
                        onPageChange={onPageChange}
                        template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport"
                        currentPageReportTemplate={`Mostrando {first} a {last} de ${totalRows.toLocaleString('es-ES')} registros`}
                        className="mt-4 border-t border-gray-200 pt-2"
                    />
                )}
            </div>
        </div>
    );
}

export default TrazabilidadPage;