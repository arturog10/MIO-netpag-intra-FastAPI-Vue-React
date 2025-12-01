import React, { useState, useMemo } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { Card } from 'primereact/card';
import { Dropdown } from 'primereact/dropdown'; // Mantenemos por si acaso, aunque usamos sidebar

// Importamos los reportes
import FunnelCobranza from '../components/reports/FunnelCobranza.jsx';
import ReporteCampanas from '../components/reports/ReporteCampanas.jsx';

export default function ReportesPage() {
    const { user } = useAuth();
    const [activeReportId, setActiveReportId] = useState('funnel');

    // Configuración de los reportes disponibles
    const availableReports = useMemo(() => {
        const reports = [
            { 
                id: 'funnel', 
                label: 'Funnel de Cobranza', 
                icon: 'pi pi-filter', 
                description: 'Rendimiento del bot y conversiones',
                component: <FunnelCobranza /> 
            },
        ];

        // Reportes exclusivos de ADMIN
        if (user && user.rol === 'admin') {
            reports.push({ 
                id: 'campanas', 
                label: 'Auditoría de Campañas', 
                icon: 'pi pi-list', 
                description: 'Historial de rechazos y gestión masiva',
                component: <ReporteCampanas /> 
            });
        }

        return reports;
    }, [user]);

    // Obtener el componente activo
    const activeComponent = availableReports.find(r => r.id === activeReportId)?.component;
    const activeTitle = availableReports.find(r => r.id === activeReportId)?.label;

    return (
        <div className="flex flex-col md:flex-row w-full min-h-[calc(100vh-100px)] gap-4 p-2 animate-fade-in">
            
            {/* --- SIDEBAR DE NAVEGACIÓN (IZQUIERDA) --- */}
            <div className="w-full md:w-64 flex-shrink-0">
                <Card className="h-full shadow-sm border border-gray-200 sticky top-4">
                    <div className="mb-4 px-2">
                        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                            <i className="pi pi-chart-bar text-blue-600"></i>
                            Reportes
                        </h2>
                        <p className="text-xs text-gray-500">Seleccione una opción</p>
                    </div>
                    
                    <div className="flex flex-col gap-2">
                        {availableReports.map((report) => {
                            const isActive = activeReportId === report.id;
                            return (
                                <button
                                    key={report.id}
                                    onClick={() => setActiveReportId(report.id)}
                                    className={`
                                        w-full text-left px-4 py-3 rounded-lg transition-all duration-200 flex items-center gap-3 group
                                        ${isActive 
                                            ? 'bg-blue-100 text-blue-800 border-l-4 border-blue-600 shadow-sm font-bold' 
                                            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                                        }
                                    `}
                                >
                                    <i className={`${report.icon} text-lg ${isActive ? 'text-blue-700' : 'text-gray-400 group-hover:text-gray-600'}`}></i>
                                    <div>
                                        <div className="text-sm">{report.label}</div>
                                        {/* Descripción pequeña opcional */}
                                        {isActive && (
                                            <div className="text-[10px] font-normal text-blue-600 mt-1">
                                                {report.description}
                                            </div>
                                        )}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </Card>
            </div>

            {/* --- AREA DE CONTENIDO (DERECHA) --- */}
            <div className="flex-1 min-w-0">
                {/* Header del Reporte Actual */}
                <div className="mb-4 pb-2 border-b border-gray-200 flex justify-between items-center">
                    <h1 className="text-2xl font-bold text-gray-800">{activeTitle}</h1>
                </div>

                {/* Renderizado del Componente */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-1">
                    {activeComponent}
                </div>
            </div>
        </div>
    );
}