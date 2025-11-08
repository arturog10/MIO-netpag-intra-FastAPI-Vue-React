import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
// --- Importaciones de PrimeReact ---
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Paginator } from 'primereact/paginator';
import { MultiSelect } from 'primereact/multiselect';
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';
import { Dialog } from 'primereact/dialog';
// ------------------------------------------

// --- IMPORTA EL FILTRO PANEL DE NUEVO ---
import FiltroPanel from './FiltroPanel';
import { useAuth } from '../context/AuthContext.jsx';
import { useNavigate } from 'react-router-dom';

const API_URL = 'http://localhost:8001/api/visor';

// --- Clases de Tailwind y consts ---
import { 
  selectClass, 
  btnPrimary, 
  btnSecondary, 
  btnDanger 
} from '../styles/appStyles';

function Visor() {
  const dt = useRef(null);
  const { token } = useAuth();
  // (Opcional: puedes necesitar 'navigate' si quieres redirigir si no hay token)
  const navigate = useNavigate();

  const getAuthHeaders = () => {
      if (!token) {
        console.error("No hay token para la petición");
        navigate('/login'); // Opcional: forzar redirección
        return {};
      }
      return { Authorization: `Bearer ${token}` };
    };  

  // --- Estados ---
  const [isLoading, setIsLoading] = useState(false);
  const [selectedClient, setSelectedClient] = useState("");
  const [clientList, setClientList] = useState([]);
  const [rowData, setRowData] = useState([]);
  const [allColumnNames, setAllColumnNames] = useState([]);
  const [visibleColumns, setVisibleColumns] = useState([]); // Objetos {field, header} con ORDEN
  const [totalRows, setTotalRows] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [filtrosActivos, setFiltrosActivos] = useState({});

  // --- ESTADO PARA ORDENAMIENTO ---
  const [sortState, setSortState] = useState({
    sortField: null,
    sortOrder: null
  });

  // --- Estados de Estrategias ---
  const [estrategiasGuardadas, setEstrategiasGuardadas] = useState([]);
  const [mostrarDialogoGuardar, setMostrarDialogoGuardar] = useState(false);
  const [showOverwriteDialog, setShowOverwriteDialog] = useState(false);
  const [nuevoNombreEstrategia, setNuevoNombreEstrategia] = useState("");
  const [selectedStrategyId, setSelectedStrategyId] = useState("");

  // --- NUEVO: Flag para controlar cuándo se carga una estrategia ---
  const [loadingStrategy, setLoadingStrategy] = useState(false);

  // --- NUEVO: Contador para forzar re-render del FiltroPanel ---
  const [filtroPanelKey, setFiltroPanelKey] = useState(0);

  // --- Carga Inicial ---
  const fetchEstrategias = useCallback(async () => {
     if (!selectedClient) return;
     try {
       const response = await axios.get(`${API_URL}/strategies/${selectedClient}`,{headers: getAuthHeaders()});
       setEstrategiasGuardadas(response.data);
     } catch (error) { console.error("Error al cargar estrategias:", error); }  
   }, [selectedClient, token]);

  useEffect(() => {
    const fetchClients = async () => {
      try {
        const response = await axios.get(`${API_URL}/clients`,{headers: getAuthHeaders()});
        setClientList(response.data);
      } catch (error) { console.error("Error al cargar lista de clientes:", error); }
    };
    if (token) {
          fetchClients();
        }
      }, [token]);

  // --- FUNCIÓN fetchData SIN DEPENDENCIAS CIRCULARES ---
  const fetchData = useCallback(async (page, filters, sort, perPage) => {
    if (!selectedClient) return;
    setIsLoading(true);

    const requestBody = {
      filtros: filters,
      page: page,
      items_per_page: perPage,
      sort_field: sort.sortField,
      sort_order: sort.sortOrder
    };

    try {
      const response = await axios.post(`${API_URL}/data/${selectedClient}`, requestBody,{headers: getAuthHeaders()});
      const { all_columns, rows, total_rows } = response.data;

      setAllColumnNames(prevNames => {
        if (JSON.stringify(prevNames) !== JSON.stringify(all_columns)) {
          return all_columns;
        }
        return prevNames;
      });
      
      setRowData(rows);
      setTotalRows(total_rows);
      setCurrentPage(page);
    } catch (error) {
      console.error("Error al cargar datos:", error);
    } finally {
      setIsLoading(false);
    }
  }, [selectedClient, token]);


  // --- Manejadores de Eventos ---
  const handleClientChange = (e) => {
    const clientCode = e.target.value;
    setSelectedClient(clientCode);
    setRowData([]); setAllColumnNames([]); setVisibleColumns([]);
    setTotalRows(0); setFiltrosActivos({}); setCurrentPage(1);
    setEstrategiasGuardadas([]);
    setSortState({ sortField: null, sortOrder: null });
    setSelectedStrategyId("");
  };

  // useEffect para cargar datos cuando cambian filtros, orden o cliente
  // PERO NO cuando estamos cargando una estrategia
  useEffect(() => {
    if (selectedClient && !loadingStrategy) {
      console.log("Disparando fetchData(1) porque selectedClient, filtrosActivos o sortState cambió.");
      fetchData(1, filtrosActivos, sortState, rowsPerPage);
    }
  }, [selectedClient, filtrosActivos, sortState, rowsPerPage, fetchData, loadingStrategy]);

  // useEffect para cargar la lista de estrategias (SOLO al cambiar de cliente)
  useEffect(() => {
    if (selectedClient) {
      console.log("Disparando fetchEstrategias porque selectedClient cambió.");
      fetchEstrategias();
    }
  }, [selectedClient, fetchEstrategias]);

  // useEffect para columnas por defecto
  useEffect(() => {
    if (allColumnNames.length > 0 && visibleColumns.length === 0 && !loadingStrategy) {
      console.log("Estableciendo visibleColumns por defecto porque allColumnNames cambió y visibles está vacío.");
      setVisibleColumns(allColumnNames.map(name => ({ field: name, header: name.toUpperCase() })));
    }
  }, [allColumnNames]);


  // --- Manejador de Paginación ---
  const onPageChange = (event) => {
    const newPage = event.page + 1;
    const newRowsPerPage = event.rows;
    setRowsPerPage(newRowsPerPage);
    fetchData(newPage, filtrosActivos, sortState, newRowsPerPage);
  };

  // --- Manejador de Ordenamiento ---
  const handleSortChange = (event) => {
    const { sortField, sortOrder } = event;
    console.log(`Ordenamiento cambiado: Campo=${sortField}, Orden=${sortOrder}`);
    setSortState({ sortField, sortOrder });
    setSelectedStrategyId("");
  };

  // --- Lógica de Filtros ---
  const handleAplicarFiltros = (nuevosFiltros) => {
    const filtrosLimpios = {};
    for (const col in nuevosFiltros) {
      const filtro = nuevosFiltros[col];
       if (filtro && filtro.operador) {
          if (filtro.operador === 'esta_entre') {
            if (filtro.desde || filtro.hasta) filtrosLimpios[col] = filtro;
          } else if (filtro.operador === 'es_nulo' || filtro.operador === 'no_es_nulo') {
            filtrosLimpios[col] = filtro;
          } else if (filtro.valor !== undefined && filtro.valor !== '') {
            filtrosLimpios[col] = filtro;
          }
       }
    }
    setFiltrosActivos(filtrosLimpios);
    setCurrentPage(1);
    setSelectedStrategyId("");
    // NO incrementar filtroPanelKey aquí
  };

  const handleLimpiarFiltros = () => {
    setFiltrosActivos({});
    setCurrentPage(1);
    setSelectedStrategyId("");
    // Incrementar key para forzar remontaje con filtros vacíos
    setFiltroPanelKey(prev => prev + 1);
  };

  // --- Lógica de Columnas ---
  const onColumnToggle = (event) => {
    setVisibleColumns(event.value);
    setSelectedStrategyId("");
  };

  // Manejador de Reordenamiento de Columnas
  const handleColReorder = (event) => {
      console.log("Columnas reordenadas:", event.columns);
      if (event.columns && Array.isArray(event.columns)) {
          const newOrderedVisibleColumns = event.columns
            .map(primeCol => {
                const option = columnOptions.find(opt => opt.field === primeCol.props.field);
                return option ? { field: option.field, header: option.header } : null;
            })
            .filter(col => col !== null);
          setVisibleColumns(newOrderedVisibleColumns);
          setSelectedStrategyId("");
      }
  };


  const dynamicColumns = visibleColumns.map(col => (
    <Column
      key={col.field}
      field={col.field}
      header={col.header}
      sortable
      
      reorderable
    />
  ));

  const columnOptions = allColumnNames.map(name => ({ field: name, header: name.toUpperCase() }));

  // --- Lógica de Estrategias ---
   const getGridState = () => {
    return {
      columnas_visibles: JSON.stringify(visibleColumns),
      filtros_aplicados: JSON.stringify(filtrosActivos),
      orden_estado: JSON.stringify(sortState)
    };
  };

  const handleSaveStrategy = async () => {
    if (!nuevoNombreEstrategia.trim()) { alert("Introduce un nombre."); return; }
    const { columnas_visibles, filtros_aplicados, orden_estado } = getGridState();
    const requestBody = {
        nombre_estrategia: nuevoNombreEstrategia,
        columnas_visibles,
        filtro_columnas: "",
        filtros_aplicados,
        orden_estado
    };
    try {
      await axios.post(`${API_URL}/strategies/${selectedClient}`, requestBody,{headers: getAuthHeaders()});
      alert("Estrategia guardada."); 
      setMostrarDialogoGuardar(false); 
      setNuevoNombreEstrategia("");
      fetchEstrategias();
    } catch (error) {
      if (error.response?.status === 409) { setMostrarDialogoGuardar(false); setShowOverwriteDialog(true); }
      else { console.error("Error al guardar:", error); alert("Error al guardar."); }
    }
  };

  const handleOverwriteStrategy = async () => {
     const { columnas_visibles, filtros_aplicados, orden_estado } = getGridState();
     const requestBody = {
         nombre_estrategia: nuevoNombreEstrategia,
         columnas_visibles,
         filtro_columnas: "",
         filtros_aplicados,
         orden_estado
     };
     try {
       await axios.put(`${API_URL}/strategies/${selectedClient}`, requestBody,{headers: getAuthHeaders()});
       alert("Estrategia actualizada."); 
       setShowOverwriteDialog(false); 
       setNuevoNombreEstrategia("");
       fetchEstrategias();
     } catch (error) { console.error("Error al sobrescribir:", error); alert("Error al actualizar."); }
   };

   const handleLoadStrategy = async (event) => {
    const strategyId = event.target.value;
    if (!strategyId) return;
    
    setSelectedStrategyId(strategyId);
    console.log(`Cargando estrategia con ID: ${strategyId}`);
    
    // ¡CRÍTICO! Activar flag para evitar que el useEffect dispare fetchData
    setLoadingStrategy(true);
    setIsLoading(true);

    let loadedVisibleColumns = [];
    let loadedFilters = {};
    let loadedSortState = { sortField: null, sortOrder: null };

    try {
      // 1. Obtiene la configuración de la estrategia
      const response = await axios.get(`${API_URL}/strategies/load/${strategyId}`,{headers: getAuthHeaders()});
      const strategyData = response.data;
      console.log("Datos de estrategia recibidos:", strategyData);

      try {
        loadedVisibleColumns = JSON.parse(strategyData.columnas_visibles || "[]");
      } catch (e) { console.error("Error parseando columnas visibles:", e); loadedVisibleColumns = []; }

      try {
        loadedFilters = JSON.parse(strategyData.filtros_aplicados || "{}");
        console.log("Filtros parseados de la estrategia:", loadedFilters);
      } catch (e) { console.error("Error parseando filtros aplicados:", e); loadedFilters = {}; }
      
      try {
        if (strategyData.orden_estado) { 
             loadedSortState = JSON.parse(strategyData.orden_estado);
        }
      } catch (e) { console.error("Error parseando estado de orden:", e); }

      // 2. Llama a fetchData MANUALMENTE con los NUEVOS filtros y orden
      const requestBody = {
        filtros: loadedFilters,
        page: 1, 
        items_per_page: rowsPerPage,
        sort_field: loadedSortState.sortField,
        sort_order: loadedSortState.sortOrder
      };
      
      const dataResponse = await axios.post(`${API_URL}/data/${selectedClient}`, requestBody,{headers: getAuthHeaders()});
      const { all_columns, rows, total_rows } = dataResponse.data;

      // 3. Actualiza las columnas disponibles
      setAllColumnNames(all_columns);
      setRowData(rows);
      setTotalRows(total_rows);

      // 4. Filtra las columnas guardadas contra las que SÍ existen
      const newVisibleColumns = loadedVisibleColumns
          .filter(colObj => all_columns.includes(colObj.field));

      if (newVisibleColumns.length === 0 && all_columns.length > 0) {
           console.warn("La estrategia cargada no tenía columnas válidas. Mostrando todas.");
           setVisibleColumns(all_columns.map(name => ({ field: name, header: name.toUpperCase() })));
       } else {
           // ¡PRIMERO! Establece las columnas visibles
           setVisibleColumns(newVisibleColumns);
       }
      
      // 5. DESPUÉS establece los filtros y el orden
      // React procesará estos cambios en batch
      setFiltrosActivos(loadedFilters);
      setSortState(loadedSortState);
      setCurrentPage(1);
      
      // 6. Forzar re-render del FiltroPanel incrementando su key
      setFiltroPanelKey(prev => prev + 1);

      console.log("Estrategia cargada y estado actualizado.");

    } catch (error) {
      console.error("Error al cargar la estrategia:", error);
      alert("Error: No se pudo cargar la configuración de la estrategia.");
      setSelectedStrategyId("");
    } finally {
      setIsLoading(false);
      // Esperar un tick para que React procese todos los cambios de estado
      setTimeout(() => setLoadingStrategy(false), 0);
    }
  };

  const handleExport = async (formato) => {
    if (!selectedClient) {
      alert("Por favor, selecciona un cliente primero.");
      return;
    }
    if (visibleColumns.length === 0) {
      alert("Por favor, selecciona al menos una columna para exportar.");
      return;
    }

    console.log(`Iniciando exportación a ${formato}...`);
    setIsLoading(true);

    const exportRequestBody = {
      filtros: filtrosActivos,
      visible_columns: visibleColumns.map(col => col.field), 
      formato: formato
    };

    try {
      const response = await axios.post(
        `${API_URL}/export/${selectedClient}`,
        exportRequestBody,
        { responseType: 'blob' ,headers: getAuthHeaders()}
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      const contentDisposition = response.headers['content-disposition'];
      let filename = `exportacion.${formato === 'excel' ? 'xlsx' : 'csv'}`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
        if (filenameMatch && filenameMatch.length === 2) {
          filename = filenameMatch[1];
        }
      }

      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error("Error al exportar:", error);
      alert("Error: No se pudo generar el archivo de exportación.");
    } finally {
      setIsLoading(false);
    }
  };


  // --- RENDERIZADO DEL COMPONENTE ---
  return (
    <div className="w-full card">
      {/* --- Barra de Acciones Superior --- */}
      <div className="mb-4 flex flex-wrap gap-2.5 items-center">
         <select onChange={handleClientChange} value={selectedClient} className={selectClass}>
            <option value="">Selecciona un cliente</option>
            {clientList.map(client => (<option key={client} value={client}>{client}</option>))}
         </select>
         <select
             className={selectClass}
             disabled={!selectedClient || estrategiasGuardadas.length === 0}
             onChange={handleLoadStrategy}
             value={selectedStrategyId}
         >
             <option value="">Cargar estrategia...</option>
             {estrategiasGuardadas.map(strategy => (<option key={strategy.id} value={strategy.id}>{strategy.nombre}</option>))}
         </select>
         
         <Button 
            label="Guardar Estrategia" 
            icon="pi pi-save" 
            disabled={!selectedClient || isLoading} 
            onClick={() => setMostrarDialogoGuardar(true)} 
            size="small" 
         />
         <Button 
            label="Exportar Excel" 
            icon="pi pi-file-excel" 
            disabled={!selectedClient || isLoading} 
            onClick={() => handleExport('excel')}
            severity="secondary" 
            size="small" 
         />
         <Button 
            label="Exportar CSV" 
            icon="pi pi-file" 
            disabled={!selectedClient || isLoading} 
            onClick={() => handleExport('csv')}
            severity="secondary" 
            size="small" 
         />

         {/* --- Selector de Columnas --- */}
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
                
                disabled={allColumnNames.length === 0}
                filter
            />
         </div>
      </div>

      {/* --- Panel de Filtros - SOLO COLUMNAS VISIBLES --- */}
      {selectedClient && visibleColumns.length > 0 && (
        <FiltroPanel
          allColumns={visibleColumns.map(col => col.field)}
          initialFilters={filtrosActivos}
          onAplicarFiltros={handleAplicarFiltros}
          onLimpiarFiltros={handleLimpiarFiltros}
          // La key fuerza el DESMONTAJE y REMONTAJE completo del componente
          // Esto evita problemas de sincronización
          key={`filtropanel-${selectedClient}-${filtroPanelKey}`} 
        />
      )}

      {/* --- Grilla PrimeReact DataTable --- */}
      <DataTable
          ref={dt}
          value={rowData}
          lazy
          paginator={false}
          rows={rowsPerPage}
          totalRecords={totalRows}
          loading={isLoading}
          stripedRows
          size="small"
          scrollable
          scrollHeight="600px"
          emptyMessage="No hay filas para mostrar"
          
          resizableColumns
          columnResizeMode="fit"

          reorderableColumns
          onColReorder={handleColReorder}

          removableSort
          sortMode="single"
          onSort={handleSortChange}
          sortField={sortState.sortField}
          sortOrder={sortState.sortOrder}

          key={`table-${selectedClient}`}
      >
          {dynamicColumns}
      </DataTable>

      {/* --- Paginador Externo --- */}
      {totalRows > 0 && (
          <Paginator
              first={currentPage * rowsPerPage - rowsPerPage}
              rows={rowsPerPage} totalRecords={totalRows}
              rowsPerPageOptions={[15, 30, 50, 100]} onPageChange={onPageChange}
              template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport"
              currentPageReportTemplate={`Mostrando {first} a {last} de ${totalRows.toLocaleString('es-ES')} registros`}
              className="mt-4"
          />
      )}

      {/* --- Diálogos (Pop-ups) --- */}
       <Dialog 
          header="Guardar Estrategia" 
          visible={mostrarDialogoGuardar} 
          className="w-11/12 md:w-1/3" // Ancho responsivo
          onHide={() => setMostrarDialogoGuardar(false)} 
          footer={
             <div className="flex justify-end gap-2">
                 <Button label="Cancelar" icon="pi pi-times" onClick={() => setMostrarDialogoGuardar(false)} className={btnSecondary} />
                 <Button label="Guardar" icon="pi pi-check" onClick={handleSaveStrategy} className={btnPrimary} autoFocus />
             </div>
          }
       >
           <p className="m-0 mb-4 text-sm text-gray-600">Dale un nombre a tu configuración actual de columnas y filtros.</p>
           <InputText value={nuevoNombreEstrategia} onChange={(e) => setNuevoNombreEstrategia(e.target.value)} placeholder="Ej: Análisis de Deuda" className="w-full" />
       </Dialog>
       
       <Dialog 
          header="Confirmar Sobrescritura" 
          visible={showOverwriteDialog} 
          className="w-11/12 md:w-1/3" // Ancho responsivo
          onHide={() => setShowOverwriteDialog(false)} 
          footer={
             <div className="flex justify-end gap-2">
                 <Button label="Cancelar" icon="pi pi-times" onClick={() => setShowOverwriteDialog(false)} className={btnSecondary} />
                 <Button label="Sobrescribir" icon="pi pi-check" onClick={handleOverwriteStrategy} className={btnDanger} autoFocus />
             </div>
          }
       >
           <p className="m-0 text-sm text-gray-600">Ya existe una estrategia llamada "<strong>{nuevoNombreEstrategia}</strong>". ¿Deseas sobrescribirla?</p>
       </Dialog>

    </div>
  );
}

export default Visor;