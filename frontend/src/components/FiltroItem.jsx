import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Calendar } from 'primereact/calendar';

// --- Helper para convertir 'DD/MM/YYYY' O 'DD-MM-YYYY' a un objeto Date ---
const parseDateString = (dateString) => {
  if (!dateString || typeof dateString !== 'string') return null;
  
  // Acepta tanto slashes como guiones
  const normalizedString = dateString.replace(/-/g, '/');
  
  const parts = normalizedString.split('/');
  if (parts.length === 3) {
    const [day, month, year] = parts.map(Number);
    if (day > 0 && month > 0 && year > 1900) {
      const dt = new Date(year, month - 1, day);
      if (dt.getDate() === day && dt.getMonth() === month - 1 && dt.getFullYear() === year) {
         return dt;
      }
    }
  }
  return null;
};

// --- Helper para convertir un objeto Date (del calendario) a 'DD-MM-YYYY' (para la API) ---
const formatDateString = (dateObj) => {
  if (!dateObj || !(dateObj instanceof Date)) return "";
  
  const day = String(dateObj.getDate()).padStart(2, '0');
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const year = dateObj.getFullYear();
  
  // Retorna con guiones para consistencia
  return `${day}-${month}-${year}`;
};


function FiltroItem({ columnName, initialValue, onChange }) {
  const esFecha = columnName.toUpperCase().includes("FECHA");

  const opcionesOperador = esFecha
    ? ["esta_entre", "es_nulo", "no_es_nulo"]
    : ["esta_entre", "contiene", "es_igual", "distinto_de", "mayor_que", "menor_que", "in", "not_in", "es_nulo", "no_es_nulo"];

  const defaultOperator = esFecha ? "esta_entre" : "contiene";
  
  // --- Ref para evitar reportar durante la inicialización ---
  const isInitialMount = useRef(true);
  
  // --- FUNCIÓN PARA VALIDAR EL OPERADOR ---
  const getValidOperator = (op) => {
    if (!op) return defaultOperator;
    if (opcionesOperador.includes(op)) return op;
    return defaultOperator;
  };
  
  // --- Estados Internos - SE INICIALIZAN UNA SOLA VEZ ---
  const [operador, setOperador] = useState(() => getValidOperator(initialValue?.operador));
  const [valor, setValor] = useState(() => initialValue?.valor || "");
  
  // --- Inicialización de fechas ---
  const [desde, setDesde] = useState(() => {
    if (!initialValue) return esFecha ? null : "";
    if (!esFecha) return initialValue.desde || "";
    return parseDateString(initialValue.desde);
  });
  
  const [hasta, setHasta] = useState(() => {
    if (!initialValue) return esFecha ? null : "";
    if (!esFecha) return initialValue.hasta || "";
    return parseDateString(initialValue.hasta);
  });
  
  const memoizedOnChange = useCallback(onChange, [onChange]);

  // --- useEffect que reporta cambios al padre (FiltroPanel) ---
  useEffect(() => {
    // NO reportar en el primer render (montaje inicial)
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const filtro = { operador };
    if (operador === 'esta_entre') {
      if (esFecha) {
        filtro.desde = formatDateString(desde);
        filtro.hasta = formatDateString(hasta);
      } else {
        filtro.desde = desde;
        filtro.hasta = hasta;
      }
    } else if (operador !== 'es_nulo' && operador !== 'no_es_nulo') {
      filtro.valor = valor;
    }
    
    memoizedOnChange(columnName, filtro);
  }, [operador, valor, desde, hasta, columnName, esFecha, memoizedOnChange]);

  // --- Clases de CSS ---
  const inputClass = "w-full border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:ring-blue-500 focus:border-blue-500";
  const disabledInputClass = `${inputClass} bg-gray-100 cursor-not-allowed`;
  const calendarInputClass = "w-full text-sm p-1.5 border border-gray-300 rounded-md";

  const renderInputs = () => {
    if (operador === 'esta_entre') {
      if (esFecha) {
        // --- CALENDARIOS ---
        return (
          <>
            <Calendar
              value={desde}
              onChange={(e) => setDesde(e.value)}
              dateFormat="dd/mm/yy"
              placeholder="Desde (DD/MM/AAAA)"
              className="w-full"
              inputClassName={calendarInputClass}
              showIcon
            />
            <Calendar
              value={hasta}
              onChange={(e) => setHasta(e.value)}
              dateFormat="dd/mm/yy"
              placeholder="Hasta (DD/MM/AAAA)"
              className="w-full"
              inputClassName={calendarInputClass}
              showIcon
            />
          </>
        );
      }
      // --- TEXTO ---
      return (
        <>
          <input
            type="text"
            placeholder="Mínimo (Desde)"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className={inputClass}
          />
          <input
            type="text"
            placeholder="Máximo (Hasta)"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className={inputClass}
          />
        </>
      );
    }
    
    // --- Render para 'es_nulo' y otros ---
    if (operador === 'es_nulo' || operador === 'no_es_nulo') {
      return <input type="text" placeholder="No se requiere valor" disabled className={disabledInputClass} />;
    }
    return (
      <input
        type="text"
        placeholder={operador === 'in' || operador === 'not_in' ? "Valores separados por coma..." : "Valor..."}
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        className={inputClass}
      />
    );
  };

  return (
    <div className={`border border-gray-300 p-2.5 rounded-lg flex flex-col gap-2 flex-grow ${esFecha ? 'min-w-[400px]' : 'min-w-[300px]'}`}>
      <strong className="text-sm font-medium select-none">{columnName.toUpperCase()}</strong>
      <div className="flex gap-2">
        <select value={operador} onChange={(e) => setOperador(e.target.value)} className={inputClass}>
          {opcionesOperador.map(op => (
            <option key={op} value={op}>{op.replace(/_/g, ' ')}</option>
          ))}
        </select>
        {renderInputs()}
      </div>
    </div>
  );
}

export default React.memo(FiltroItem);