import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext.jsx'; 

// --- TUS COMPONENTES ---
import FiltroPanel from './FiltroPanel'; 

// --- IMPORTACIONES DE PRIMEREACT ---
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { MultiSelect } from 'primereact/multiselect';
import { Paginator } from 'primereact/paginator'; 

// --- Iconos (Estilo Visor) ---
const IconExcel = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M5.18 4.616a.5.5 0 0 1 .704.064L8 7.219l2.116-2.54a.5.5 0 1 1 .768.641L8.651 8l2.233 2.68a.5.5 0 0 1-.768.64L8 8.781l-2.116 2.54a.5.5 0 0 1-.768-.641L7.349 8 5.116 5.32a.5.5 0 0 1 .064-.704z"/><path d="M4 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2H4zm0 1h8a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1z"/></svg>;
const IconCsv = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M1 1h2.5L1 3.5V1zM3 0a1 1 0 0 1 1 1v2.5a.5.5 0 0 1-1 0V1H1a1 1 0 0 1-1-1a1 1 0 0 1 1-1h2z"/><path d="M8.5 6.427a.5.5 0 0 1 .134.001l.277.068a.5.5 0 0 1 .311.445v2.339a.5.5 0 0 1-.311.445l-.277.068a.5.5 0 0 1-.134.001h-2.5a.5.5 0 0 1-.5-.5v-2.408a.5.5 0 0 1 .5-.5h2.5zM6.5 7v2h2v-2h-2z"/><path d="M12 6.427a.5.5 0 0 1 .134.001l.277.068a.5.5 0 0 1 .311.445v2.339a.5.5 0 0 1-.311.445l-.277.068a.5.5 0 0 1-.134.001h-2.5a.5.5 0 0 1-.5-.5v-2.408a.5.5 0 0 1 .5-.5h2.5zM10 7v2h2v-2h-2z"/><path d="M4 14.5a.5.5 0 0 1-.5-.5v-2.408a.5.5 0 0 1 .5-.5h2.5a.5.5 0 0 1 .134.001l.277.068a.5.5 0 0 1 .311.445v2.339a.5.5 0 0 1-.311.445l-.277.068a.5.5 0 0 1-.134.001h-2.5a.5.5 0 0 1-.5-.5zm1-2.5v2h2v-2h-2z"/><path d="M4 0h8a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM3 1a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H3z"/></svg>;

const API_URL = 'http://localhost:8000/api/listanegra';

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
    const fetchData = useCallback(async () => {
        if (!token) return; 
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
            
            const response = await axios.post(`${API_URL}/data`, body, config); 
            const data = response.data; 
            
            setRows(data.rows); 
            setTotalRows(data.total_rows); 
            setAllColumnNames(data.all_columns); 
            
        } catch (error) {
            console.error("Error en fetchData (ListaNegra):", error); 
        } finally {
            setIsLoading(false); 
        }
    }, [first, itemsPerPage, filtrosActivos, sortConfig, token]); 

    useEffect(() => {
        if (allColumnNames.length > 0 && visibleColumns.length === 0) { 
            setVisibleColumns(
                allColumnNames.map(name => ({ field: name, header: name.toUpperCase() })) 
            );
        }
    }, [allColumnNames]); 

    useEffect(() => {
        fetchData(); 
    }, [fetchData]); 

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
        }
    };
    
    // --- MANEJADORES DE FILTRO Y EXPORTACIÓN ---
    const handleAplicarFiltros = (nuevosFiltros) => {
        setFiltrosActivos(nuevosFiltros); 
        setFirst(0); 
    };

    const handleLimpiarFiltros = () => {
        setFiltrosActivos({}); 
        setFirst(0); 
        setFiltroPanelKey(prev => prev + 1); 
    };
    
    const handleExport = async (formato) => {
        if (!token) return; 
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
            const response = await axios.post(`${API_URL}/export`, body, config); 
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
                <h2 className="text-2xl font-semibold text-gray-900 m-0">
                    {/* Consulta de Lista Negra */}
                </h2> 
                <div className="flex flex-shrink-0 flex-wrap items-center gap-5"> 
                    <button
                        onClick={() => handleExport('excel')} 
                        disabled={isLoading} 
                        className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                    >
                        <IconExcel />
                        {isLoading ? 'Exportando...' : 'Exportar Excel'}
                    </button> 
                    <button
                        onClick={() => handleExport('csv')} 
                        disabled={isLoading} 
                        className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                    >
                        <IconCsv />
                        {isLoading ? 'Exportando...' : 'Exportar CSV'}
                    </button> 
                    
                    <MultiSelect
                        value={visibleColumns} 
                        options={columnOptions} 
                        onChange={onColumnToggle} 
                        optionLabel="header" 
                        placeholder="Seleccionar Columnas" 
                        maxSelectedLabels={0} 
                        selectedItemsLabel={`${visibleColumns.length} columnas`} 
                        className="w-full md:w-20rem text-sm" 
                        disabled={allColumnNames.length === 0} 
                        filter 
                    />
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
        </>
    );
}

export default ListaNegra;