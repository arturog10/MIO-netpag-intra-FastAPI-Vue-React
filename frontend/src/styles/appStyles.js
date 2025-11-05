// Este archivo centraliza tus clases de Tailwind para reutilizarlas.

// --- Clases de Botones ---
// Base para botones (los que usas en Visor.jsx)
const btnBaseVisor = "px-4 py-2 rounded-md font-medium text-sm transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed";
export const btnPrimary = `${btnBaseVisor} bg-blue-600 text-white hover:bg-blue-700`;
export const btnSecondary = `${btnBaseVisor} bg-gray-100 text-gray-800 hover:bg-gray-200 border border-gray-300`;
export const btnDanger = `${btnBaseVisor} bg-red-600 text-white hover:bg-red-700`;

// Base para botones de FiltroPanel (son un poco diferentes)
const btnBasePanel = "px-4 py-2 rounded-md font-medium text-sm transition-colors";
export const btnPanelPrimary = `${btnBasePanel} bg-blue-600 text-white hover:bg-blue-700`;
export const btnPanelSecondary = `${btnBasePanel} text-blue-600 border border-blue-600 hover:bg-blue-50`;


// --- Clases de Formularios ---
export const selectClass = "border border-gray-300 rounded-md px-2 py-2 text-sm";
export const inputClass = "w-full border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:ring-blue-500 focus:border-blue-500";
export const disabledInputClass = `${inputClass} bg-gray-100 cursor-not-allowed`;
export const calendarInputClass = "w-full text-sm p-1.5 border border-gray-300 rounded-md";