import React, { useState, useEffect, useCallback, useRef } from 'react'; // 1. IMPORTAR useRef

import axios from 'axios';
import { useAuth } from '../context/AuthContext.jsx'; 

// --- TUS COMPONENTES ---
import FiltroPanel from './FiltroPanel'; 

// --- IMPORTACIONES DE PRIMEREACT ---
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { MultiSelect } from 'primereact/multiselect';
import { Paginator } from 'primereact/paginator'; 
// 2. IMPORTAR COMPONENTES Y ESTILOS
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';
import { Dialog } from 'primereact/dialog';
import { 
  selectClass, 
  btnPrimary, 
  btnSecondary, 
  btnDanger 
    } from '../styles/appStyles';

// --- Iconos (Estilo Visor) ---
const IconExcel = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M5.18 4.616a.5.5 0 0 1 .704.064L8 7.219l2.116-2.54a.5.5 0 1 1 .768.641L8.651 8l2.233 2.68a.5.5 0 0 1-.768.64L8 8.781l-2.116 2.54a.5.5 0 0 1-.768-.641L7.349 8 5.116 5.32a.5.5 0 0 1 .064-.704z"/><path d="M4 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2H4zm0 1h8a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1z"/></svg>;
const IconCsv = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M1 1h2.5L1 3.5V1zM3 0a1 1 0 0 1 1 1v2.5a.5.5 0 0 1-1 0V1H1a1 1 0 0 1-1-1a1 1 0 0 1 1-1h2z"/><path d="M8.5 6.427a.5.5 0 0 1 .134.001l.277.068a.5.5 0 0 1 .311.445v2.339a.5.5 0 0 1-.311.445l-.277.068a.5.5 0 0 1-.134.001h-2.5a.5.5 0 0 1-.5-.5v-2.408a.5.5 0 0 1 .5-.5h2.5zM6.5 7v2h2v-2h-2z"/><path d="M12 6.427a.5.5 0 0 1 .134.001l.277.068a.5.5 0 0 1 .311.445v2.339a.5.5 0 0 1-.311.445l-.277.068a.5.5 0 0 1-.134.001h-2.5a.5.5 0 0 1-.5-.5v-2.408a.5.5 0 0 1 .5-.5h2.5zM10 7v2h2v-2h-2z"/><path d="M4 14.5a.5.5 0 0 1-.5-.5v-2.408a.5.5 0 0 1 .5-.5h2.5a.5.5 0 0 1 .134.001l.277.068a.5.5 0 0 1 .311.445v2.339a.5.5 0 0 1-.311.445l-.277.068a.5.5 0 0 1-.134.001h-2.5a.5.5 0 0 1-.5-.5zm1-2.5v2h2v-2h-2z"/><path d="M4 0h8a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM3 1a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H3z"/></svg>;

// --- URL DESARROLLO: http://localhost:8001/api/listanegra ---
const API_URL = '/api/listanegra';

function ListaNegra() {
    
    const { token } = useAuth(); 

    // --- ESTADOS DE LA PÁGINA ---
    const [isLoading, setIsLoading] = useState(false);
    const [rows, setRows] = useState([]);
    const [totalRows, setTotalRows] = useState(0);
    const [sortConfig, setSortConfig] = useState({ field: null, order: 1 });
    const [filtrosActivos, setFiltrosActivos] = useState({});
    const [first, setFirst] = useState(0); 
    const [itemsPerPage, setItemsPerPage] = useState(15); 
    const [allColumnNames, setAllColumnNames] = useState([]); 
    const [visibleColumns, setVisibleColumns] = useState([]); 
    const [filtroPanelKey, setFiltroPanelKey] = useState(0); 

    // --- LÓGICA DE DATOS ---

    // --- 3. AÑADIR ESTADOS DE CONSULTAS (copiado de Visor.jsx) ---
    const [consultasGuardadas, setConsultasGuardadas] = useState([]);
    const [mostrarDialogoGuardar, setMostrarDialogoGuardar] = useState(false);
    const [showOverwriteDialog, setShowOverwriteDialog] = useState(false);
    const [nuevoNombreConsulta, setNuevoNombreConsulta] = useState("");
    const [selectedConsultaId, setSelectedConsultaId] = useState("");

    // --- Flag para controlar cuándo se carga una consulta ---
    const [loadingConsulta, setLoadingConsulta] = useState(false);    

        // --- 2. Añadir estados para el dropdown (como en Visor.jsx) ---
    const [listaNegraOptions, setListaNegraOptions] = useState([]);
    const [selectedLista, setSelectedLista] = useState("");

    // ---  Cargar la lista de tablas disponibles al inicio ---
    useEffect(() => {
        const fetchListaNegras = async () => {
            if (!token) return;
            try {
                const config = { headers: { Authorization: `Bearer ${token}` } };
                const response = await axios.get(`${API_URL}/listanegras`, config);
                setListaNegraOptions(response.data);
            } catch (error) {
                console.error("Error al cargar lista de tablas:", error);
            }
        };
        fetchListaNegras();
    }, [token]);

    // --- 4. AÑADIR FUNCIÓN PARA CARGAR CONSULTAS GUARDADAS ---
    const fetchConsultas = useCallback(async () => {
        if (!selectedLista) return;
        try {
            const config = { headers: { Authorization: `Bearer ${token}` } };
            const response = await axios.get(`${API_URL}/consultas/${selectedLista}`, config);
            setConsultasGuardadas(response.data);
        } catch (error) { 
            console.error("Error al cargar consultas guardadas:", error); 
            setConsultasGuardadas([]); // Limpia en caso de error
        }  
    }, [selectedLista, token]);    

    const fetchData = useCallback(async () => {
        if (!token || !selectedLista) return; // <-- No hacer fetch si no hay lista seleccionada
        setIsLoading(true); 
        const currentPage = Math.floor(first / itemsPerPage) + 1; 
        try {
            const body = {
                filtros: filtrosActivos, 
                page: currentPage, 
                items_per_page: itemsPerPage, 
                sort_field: sortConfig.field, 
                sort_order: sortConfig.order 
            };
            const config = {
                headers: { Authorization: `Bearer ${token}` } 
            };
            
            const response = await axios.post(`${API_URL}/data/${selectedLista}`, body, config); // <-- 5. Usar selectedLista 
            const data = response.data; 
            
            setRows(data.rows); 
            setTotalRows(data.total_rows); 
            setAllColumnNames(data.all_columns); 
            
        } catch (error) {
            console.error("Error en fetchData (ListaNegra):", error); 
        } finally {
            setIsLoading(false); 
        }
    }, [first, itemsPerPage, filtrosActivos, sortConfig, token, selectedLista]); // <-- 6. Añadir dependencia 

    useEffect(() => {
        if (allColumnNames.length > 0 && visibleColumns.length === 0) { 
            setVisibleColumns(
                allColumnNames.map(name => ({ field: name, header: name.toUpperCase() })) 
            );
        }
    }, [allColumnNames]); 

    useEffect(() => {
        if (selectedLista) { // Solo corre si hay una lista seleccionada
            if (!loadingConsulta) { // <-- 5. AÑADIR CHECK
                fetchData();
            }
            fetchConsultas(); // <-- 6. Cargar consultas guardadas al cambiar de lista
         }
    }, [fetchData, selectedLista, loadingConsulta, fetchConsultas]); // <-- 7. AÑADIR DEPENDENCIAS // 'selectedLista' reemplaza a 'fetchData' como disparador principal
 
    // --- 8. Añadir manejador para el cambio del dropdown (como en Visor.jsx) ---
    const handleListaChange = (e) => {
        const newLista = e.target.value;
        setSelectedLista(newLista);
        // Resetear todo al cambiar de lista
        setRows([]); setTotalRows(0); setAllColumnNames([]); setVisibleColumns([]);
        setFiltrosActivos({}); setFirst(0); setSortConfig({ field: null, order: 1 });
        setConsultasGuardadas([]); // <-- Limpiar consultas
        setSelectedConsultaId(""); // <-- Limpiar consulta seleccionada
        setFiltroPanelKey(prev => prev  +1);
    };
    // --- MANEJADORES DE DATATABLE ---
    const onPage = (e) => {
        setFirst(e.first); 
        setItemsPerPage(e.rows); 
    };

    const onSort = (e) => {
        setSortConfig({ 
            field: e.sortField, 
            order: e.sortOrder 
        });
        setSelectedConsultaId(""); // <-- Resetear
    };

    // --- 👈 1. AÑADIR HANDLER PARA REORDENAR (Igual que Visor.jsx) ---
    const handleColReorder = (e) => {
        if (e.columns && Array.isArray(e.columns)) {
            // Re-mapear las columnas de PrimeReact al formato de nuestro estado ({field, header})
            const newOrderedVisibleColumns = e.columns
                .map(primeCol => {
                    // (Asumimos que columnOptions está definido abajo)
                    const option = columnOptions.find(opt => opt.field === primeCol.props.field);
                    return option ? { field: option.field, header: option.header } : null;
                })
                .filter(col => col !== null);
            
            setVisibleColumns(newOrderedVisibleColumns);
            setSelectedConsultaId(""); // <-- Resetear
        }
    };
    
    // --- MANEJADORES DE FILTRO Y EXPORTACIÓN ---
    const handleAplicarFiltros = (nuevosFiltros) => {
        setFiltrosActivos(nuevosFiltros); 
        setFirst(0); 
        setSelectedConsultaId(""); // <-- Resetear
    };

    const handleLimpiarFiltros = () => {
        setFiltrosActivos({}); 
        setFirst(0); 
        setSelectedConsultaId(""); // <-- Resetear
        setFiltroPanelKey(prev => prev + 1); 
    };
    
    const handleExport = async (formato) => {
        if (!token || !selectedLista) return; // <-- 9. Bloquear si no hay lista 
        setIsLoading(true); 
        try {
            const body = {
                filtros: filtrosActivos, 
                formato: formato, 
                visible_columns: visibleColumns.map(col => col.field), 
                sort_field: sortConfig.field, 
                sort_order: sortConfig.order 
            };
            const config = {
                headers: { Authorization: `Bearer ${token}` }, 
                responseType: 'blob'  
            };
            const response = await axios.post(`${API_URL}/export/${selectedLista}`, body, config); // <-- 10. Usar selectedLista 
            // ... (lógica de descarga sin cambios) ...
            const blob = new Blob([response.data], { type: response.headers['content-type'] }); 
            const url = window.URL.createObjectURL(blob); 
            const a = document.createElement('a'); 
            a.href = url; 
            const contentDisposition = response.headers['content-disposition']; 
            let filename = `exportacion_listanegra.${formato === 'excel' ? 'xlsx' : 'csv'}`; 
            if (contentDisposition) { 
                const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/); 
                if (filenameMatch && filenameMatch[1]) { 
                    filename = filenameMatch[1]; 
                }
            }
            a.download = filename; 
            document.body.appendChild(a); 
            a.click(); 
            a.remove(); 
            window.URL.revokeObjectURL(url); 
        } catch (error) {
            console.error(`Error en exportación ${formato}:`, error); 
        } finally {
            setIsLoading(false); 
        }
    };
    
    const onColumnToggle = (e) => {
        setVisibleColumns(e.value); 
        setSelectedConsultaId(""); // <-- Resetear
    };

    // --- 9. AÑADIR LÓGICA DE GUARDAR/CARGAR (copiado de Visor.jsx) ---

    const getGridState = () => {
        return {
            columnas_visibles: JSON.stringify(visibleColumns),
            filtros_aplicados: JSON.stringify(filtrosActivos),
            orden_estado: JSON.stringify(sortConfig)
        };
    };

    const handleSaveConsulta = async () => {
        if (!nuevoNombreConsulta.trim()) { alert("Introduce un nombre."); return; }
        const { columnas_visibles, filtros_aplicados, orden_estado } = getGridState();
        const requestBody = {
            nombre_estrategia: nuevoNombreConsulta, // El modelo Pydantic espera este nombre
            columnas_visibles,
            filtro_columnas: "", // Este campo no se usa pero el modelo lo tiene
            filtros_aplicados,
            orden_estado
        };
        try {
            const config = { headers: { Authorization: `Bearer ${token}` } };
            await axios.post(`${API_URL}/consultas/${selectedLista}`, requestBody, config);
            alert("Consulta guardada."); 
            setMostrarDialogoGuardar(false); 
            setNuevoNombreConsulta("");
            fetchConsultas(); // Recargar la lista
        } catch (error) {
            if (error.response?.status === 409) {
                alert(error.response.data.detail || "Ya existe una consulta con ese nombre.");
                setMostrarDialogoGuardar(false); 
                // setShowOverwriteDialog(true); 
            } else { 
                console.error("Error al guardar:", error); 
                alert("Error al guardar la consulta."); 
            }
        }
    };

    const handleOverwriteConsulta = async () => {
        const { columnas_visibles, filtros_aplicados, orden_estado } = getGridState();
        const requestBody = {
            nombre_estrategia: nuevoNombreConsulta,
            columnas_visibles,
            filtro_columnas: "",
            filtros_aplicados,
            orden_estado
        };
        try {
            const config = { headers: { Authorization: `Bearer ${token}` } };
            await axios.put(`${API_URL}/consultas/${selectedLista}`, requestBody, config);
            alert("Consulta actualizada."); 
            setShowOverwriteDialog(false); 
            setNuevoNombreConsulta("");
            fetchConsultas(); // Recargar la lista
        } catch (error) { 
            console.error("Error al sobrescribir:", error); 
            alert("Error al actualizar la consulta."); 
        }
    };

    const handleLoadConsulta = async (event) => {
        const consultaId = event.target.value;
        if (!consultaId) return;
        
        setSelectedConsultaId(consultaId);
        console.log(`Cargando consulta con ID: ${consultaId}`);
        
        setLoadingConsulta(true);
        setIsLoading(true); // Activa el spinner principal

        let loadedVisibleColumns = [];
        let loadedFilters = {};
        let loadedSortState = { field: null, order: 1 }; // Default

        try {
            const config = { headers: { Authorization: `Bearer ${token}` } };
            // 1. Obtiene la configuración de la consulta
            const response = await axios.get(`${API_URL}/consultas/load/${consultaId}`, config);
            const consultaData = response.data;

            // Parsear JSON (igual que en Visor)
            try { loadedVisibleColumns = JSON.parse(consultaData.columnas_visibles || "[]"); } catch (e) { console.error("Error parseando columnas"); }
            try { loadedFilters = JSON.parse(consultaData.filtros_aplicados || "{}"); } catch (e) { console.error("Error parseando filtros"); }
            try { if (consultaData.orden_estado) { loadedSortState = JSON.parse(consultaData.orden_estado); } } catch (e) { console.error("Error parseando orden"); }

            // 2. Llama a fetchData MANUALMENTE con los NUEVOS filtros y orden
            const body = {
                filtros: loadedFilters,
                page: 1, // Siempre resetea a página 1
                items_per_page: itemsPerPage,
                sort_field: loadedSortState.field,
                sort_order: loadedSortState.order
            };

            const dataResponse = await axios.post(`${API_URL}/data/${selectedLista}`, body, config);
            const { all_columns, rows: dataRows, total_rows } = dataResponse.data;

            // 3. Actualiza TODO el estado
            setAllColumnNames(all_columns);
            setRows(dataRows);
            setTotalRows(total_rows);
            setVisibleColumns(loadedVisibleColumns.filter(col => all_columns.includes(col.field)));
            setFiltrosActivos(loadedFilters);
            setSortConfig(loadedSortState);
            setFirst(0); // Resetea paginador
            setFiltroPanelKey(prev => prev + 1); // Forzar re-render del panel

        } catch (error) {
            console.error("Error al cargar la consulta:", error);
            alert("Error: No se pudo cargar la configuración de la consulta.");
            setSelectedConsultaId("");
        } finally {
            setIsLoading(false);
            setTimeout(() => setLoadingConsulta(false), 0);
        }
    };    

    const columnOptions = allColumnNames.map(name => ({ 
        field: name, 
        header: name.toUpperCase() 
    }));

    const dynamicColumns = visibleColumns.map(col => ( 
        <Column 
            key={col.field} 
            field={col.field} 
            header={col.header} 
            sortable 
            reorderable // 👈 2. Habilitar reorden en la columna
        />
    ));

    // --- RENDERIZADO ---
    return (
        <>
            {/* --- Barra de Acciones (Estilo Visor) --- */}
            <div className="bg-white shadow rounded-lg p-4 mb-4 flex flex-col md:flex-row justify-between items-center gap-4"> 
                {/* <h2 className="text-2xl font-semibold text-gray-900 m-0"> */}
                    {/* Consulta de Lista Negra */}
                {/* </h2>  */}
                <div className="flex flex-shrink-0 flex-wrap items-center gap-5"> 
                    {/* --- 11. Añadir el dropdown (como en Visor.jsx) --- */}
                    <select onChange={handleListaChange} value={selectedLista} className={selectClass}>
                        <option value="">Selecciona una lista...</option>
                        {listaNegraOptions.map(lista => (<option key={lista} value={lista}>{lista}</option>))}
                    </select>

                        {/* --- 10. AÑADIR DROPDOWN DE CONSULTAS (copiado de Visor.jsx) --- */}
                        <select
                            className={selectClass}
                            disabled={!selectedLista || consultasGuardadas.length === 0}
                            onChange={handleLoadConsulta}
                            value={selectedConsultaId}
                        >
                            <option value="">Cargar consulta...</option>
                            {consultasGuardadas.map(c => (<option key={c.id} value={c.id}>{c.nombre}</option>))}
                        </select>
                        <Button 
                            label="Guardar Consulta" 
                            icon="pi pi-save" 
                            disabled={!selectedLista || isLoading} 
                            onClick={() => setMostrarDialogoGuardar(true)} 
                            size="small" 
                        />
                    
                    <button
                        onClick={() => handleExport('excel')} 
                        disabled={isLoading || !selectedLista} // <-- 12. Deshabilitar
                        className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                    >
                        <IconExcel />
                        {isLoading ? 'Exportando...' : 'Exportar Excel'}
                    </button> 
                    <button
                        onClick={() => handleExport('csv')} 
                        disabled={isLoading || !selectedLista} // <-- 12. Deshabilitar 
                        className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                    >
                        <IconCsv />
                        {isLoading ? 'Exportando...' : 'Exportar CSV'}
                    </button> 
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
                        disabled={allColumnNames.length === 0 || !selectedLista} // <-- 12. Deshabilitar
                        filter 
                    />
                    </div>
                </div>
            </div>

            {/* --- PANEL DE FILTROS --- */}
            <FiltroPanel
                allColumns={visibleColumns.map(col => col.field)} 
                initialFilters={filtrosActivos} 
                onAplicarFiltros={handleAplicarFiltros} 
                onLimpiarFiltros={handleLimpiarFiltros} 
                key={`filtropanel-ln-${filtroPanelKey}`} 
            />

            {/* --- GRILLA DATATABLE DE PRIMEREACT --- */}
            <div className="bg-white shadow-md rounded-lg overflow-hidden mt-4">
                <DataTable
                    value={rows} 
                    loading={isLoading} 
                    emptyMessage="No se encontraron registros." 
                    lazy 
                    rows={itemsPerPage} 
                    sortField={sortConfig.field} 
                    sortOrder={sortConfig.order} 
                    onSort={onSort} 
                    removableSort 
                    responsiveLayout="scroll" 
                    size="small" 
                    className="p-datatable-gridlines"
                    
                    // --- 👈 3. Añadir props a la tabla (Igual que Visor.jsx) ---
                    reorderableColumns
                    onColReorder={handleColReorder}
                >
                    {dynamicColumns}
                </DataTable>
            </div>

            {/* --- Paginador EXTERNO --- */}
            {totalRows > 0 && (
                <Paginator
                    first={first} 
                    rows={itemsPerPage} 
                    totalRecords={totalRows} 
                    rowsPerPageOptions={[15, 25, 50]} 
                    onPageChange={onPage} 
                    template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport" 
                    currentPageReportTemplate={`Mostrando {first} a {last} de ${totalRows.toLocaleString('es-ES')} registros`} 
                    className="mt-4" 
                />
            )}
            
            {/* --- 11. AÑADIR DIÁLOGOS (copiado de Visor.jsx) --- */}
            <Dialog 
                header="Guardar Consulta" 
                visible={mostrarDialogoGuardar} 
                className="w-11/12 md:w-1/3"
                onHide={() => setMostrarDialogoGuardar(false)} 
                footer={
                    <div className="flex justify-end gap-2">
                        <Button label="Cancelar" icon="pi pi-times" onClick={() => setMostrarDialogoGuardar(false)} className={btnSecondary} />
                        <Button label="Guardar" icon="pi pi-check" onClick={handleSaveConsulta} className={btnPrimary} autoFocus />
                    </div>
                }>
                <InputText value={nuevoNombreConsulta} onChange={(e) => setNuevoNombreConsulta(e.target.value)} placeholder="Nombre de la consulta..." className="w-full mt-2" />
            </Dialog>
            <Dialog 
                header="Confirmar Sobrescritura" 
                visible={showOverwriteDialog} 
                className="w-11/12 md:w-1/3"
                onHide={() => setShowOverwriteDialog(false)} 
                footer={
                    <div className="flex justify-end gap-2">
                        <Button label="Cancelar" icon="pi pi-times" onClick={() => setShowOverwriteDialog(false)} className={btnSecondary} />
                        <Button label="Sobrescribir" icon="pi pi-check" onClick={handleOverwriteConsulta} className={btnDanger} autoFocus />
                    </div>
                }>
                <p className="m-0 text-sm text-gray-600">Ya existe una consulta llamada "<strong>{nuevoNombreConsulta}</strong>". ¿Deseas sobrescribirla?</p>
            </Dialog>
        </>
    );
}

export default ListaNegra;