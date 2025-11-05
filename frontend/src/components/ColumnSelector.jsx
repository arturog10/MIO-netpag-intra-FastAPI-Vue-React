import React, { useState } from 'react';

// --- Clases de Tailwind para botones ---
const btn = "px-3 py-1.5 rounded-md font-medium text-xs transition-colors";
const btnPrimary = `${btn} bg-blue-600 text-white hover:bg-blue-700`;
const btnSecondary = `${btn} bg-gray-100 text-gray-800 hover:bg-gray-200 border border-gray-300`;

function ColumnSelector({ 
  allColumns, 
  visibleColumns, 
  onToggleColumn,
  onSelectAll,
  onDeselectAll
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  const filteredColumns = allColumns.filter(col =>
    col.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <details 
      open={isOpen} 
      onToggle={(e) => setIsOpen(e.currentTarget.open)} 
      className="w-full border border-gray-300 rounded-lg mb-4"
    >
      <summary className="p-4 cursor-pointer font-bold">
        Columnas Disponibles
      </summary>
      
      <div className="p-4 border-t border-gray-300">
        <div className="flex justify-between items-center mb-4">
          <input
            type="text"
            placeholder="Buscar columna..."
            className="w-full max-w-xs border border-gray-300 rounded-md px-2 py-1.5 text-sm"
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          {/* --- Botones de Seleccionar Todo --- */}
          <div className="flex gap-2">
            <button onClick={onSelectAll} className={btnPrimary}>
              Seleccionar Todo
            </button>
            <button onClick={onDeselectAll} className={btnSecondary}>
              Deseleccionar Todo
            </button>
          </div>
        </div>
        
        {/* Contenedor de las etiquetas */}
        <div className="flex flex-wrap gap-2 max-h-[200px] overflow-y-auto">
          {filteredColumns.map(colName => {
            const isVisible = visibleColumns.includes(colName);
            return (
              <span
                key={colName}
                onClick={() => onToggleColumn(colName)}
                className={`
                  px-3 py-1 rounded-full text-sm font-medium cursor-pointer 
                  transition-colors select-none
                  ${isVisible
                    ? 'bg-blue-600 text-white hover:bg-blue-700'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }
                `}
              >
                {colName}
              </span>
            );
          })}
        </div>
      </div>
    </details>
  );
}

export default ColumnSelector;