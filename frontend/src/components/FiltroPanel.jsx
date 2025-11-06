import React, { useState, useCallback, useMemo } from 'react';
import FiltroItem from './FiltroItem';

// Clases de Tailwind para los botones

import { btnPanelPrimary, btnPanelSecondary } from '../styles/appStyles';

function FiltroPanel({ allColumns, initialFilters, onAplicarFiltros, onLimpiarFiltros, isLoading }) {
  
  // Mantenemos un "borrador" de los filtros aquí - SOLO se inicializa una vez
  const [filtrosBorrador, setFiltrosBorrador] = useState(initialFilters || {});
  
  // Abre el panel por defecto si hay filtros iniciales
  const [isOpen, setIsOpen] = useState(Object.keys(initialFilters || {}).length > 0);

  // NO usamos useEffect para sincronizar - el componente se remonta completamente
  // cuando cambia la key en Visor.jsx

  const handleFiltroChange = useCallback((columnName, filtro) => {
    // Actualiza el estado del "borrador" interno mientras el usuario escribe
    setFiltrosBorrador(prevFiltros => ({
      ...prevFiltros,
      [columnName]: filtro,
    }));
  }, []);

  const handleAplicar = () => {
    onAplicarFiltros(filtrosBorrador);
  };

  const handleLimpiar = () => {
    setFiltrosBorrador({}); // Limpia el borrador interno
    onLimpiarFiltros(); // Llama a la función del padre (Visor)
  };

  // --- Determinar qué columnas mostrar ---
  const columnasParaMostrar = useMemo(() => {
    return allColumns;
  }, [allColumns]);

  // Contar filtros que realmente tienen valores
  const numFiltrosActivos = useMemo(() => {
    return Object.keys(filtrosBorrador).filter(key => {
      const filtro = filtrosBorrador[key];
      if (!filtro || !filtro.operador) return false;
      
      // Operadores que no requieren valor
      if (filtro.operador === 'es_nulo' || filtro.operador === 'no_es_nulo') return true;
      
      // Operador "esta_entre" requiere desde o hasta
      if (filtro.operador === 'esta_entre') {
        return !!(filtro.desde || filtro.hasta);
      }
      
      // Otros operadores requieren valor
      return !!(filtro.valor);
    }).length;
  }, [filtrosBorrador]);

  return (
    <details
      open={isOpen}
      onToggle={(e) => setIsOpen(e.currentTarget.open)}
      className="w-full border border-gray-300 rounded-lg mb-4"
    >
      <summary 
          className={`p-4 cursor-pointer font-bold ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          // 2. Previene que se abra/cierre el panel si está cargando
          onClick={(e) => {
            if (isLoading) {
              e.preventDefault();
            }
          }}
        >
        Filtros Avanzados
        {numFiltrosActivos > 0 && (
          <span className="ml-2 text-sm font-normal text-blue-600">
            ({numFiltrosActivos} filtro{numFiltrosActivos !== 1 ? 's' : ''} aplicado{numFiltrosActivos !== 1 ? 's' : ''})
          </span>
        )}
      </summary>
      <fieldset disabled={isLoading}>
      <div className="p-4 border-t border-gray-300">
        <div className="flex flex-wrap gap-4 max-h-[300px] overflow-y-auto pb-4">
          {columnasParaMostrar.map(colName => {
            const filtroInicial = filtrosBorrador[colName] || {};
            return (
              <FiltroItem
                key={colName}
                columnName={colName}
                initialValue={filtroInicial}
                onChange={handleFiltroChange}
              />
            );
          })}
        </div>

        {/* Botones de acción */}
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={handleLimpiar} className={btnPanelSecondary}>
            Limpiar Filtros
          </button>
          <button onClick={handleAplicar} className={btnPanelPrimary}>
            Aplicar Filtros
          </button>
        </div>
      </div>       
       </fieldset>
    </details>
  );
}

export default FiltroPanel;