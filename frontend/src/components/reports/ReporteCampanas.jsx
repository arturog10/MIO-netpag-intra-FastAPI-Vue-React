import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext.jsx';
import { TabView, TabPanel } from 'primereact/tabview';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Button } from 'primereact/button';
import { Calendar } from 'primereact/calendar';
import { Dropdown } from 'primereact/dropdown';

const API_VISOR_URL = '/api/visor';
const API_REPORTES_URL = '/api/reportes';

export default function ReporteCampanas() {
    const { token } = useAuth();
    
    // Control de Pestaña Activa (0: Rechazos, 1: Gestión)
    const [activeIndex, setActiveIndex] = useState(0);

    // Estados de Filtro
    const [fechaDesde, setFechaDesde] = useState(new Date());
    const [fechaHasta, setFechaHasta] = useState(new Date());
    const [clientes, setClientes] = useState([]);
    const [selectedCliente, setSelectedCliente] = useState(null);
    
    // Estados de Datos
    const [dataRechazos, setDataRechazos] = useState([]);
    const [dataGestion, setDataGestion] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (token) {
            axios.get(`${API_VISOR_URL}/clients`, { headers: { Authorization: `Bearer ${token}` } })
                .then(res => setClientes(res.data.map(c => ({ label: c, value: c }))))
                .catch(err => console.error(err));
        }
    }, [token]);

    const buscarDatos = async () => {
        setLoading(true);
        try {
            const f1 = fechaDesde.toISOString().split('T')[0];
            const f2 = fechaHasta.toISOString().split('T')[0];
            const cliParam = selectedCliente ? `&cliente=${selectedCliente}` : '';

            const resRech = await axios.get(`${API_REPORTES_URL}/rechazos?fecha_desde=${f1}&fecha_hasta=${f2}${cliParam}`, { headers: { Authorization: `Bearer ${token}` } });
            setDataRechazos(resRech.data);

            const resGest = await axios.get(`${API_REPORTES_URL}/gestion?fecha_desde=${f1}&fecha_hasta=${f2}${cliParam}`, { headers: { Authorization: `Bearer ${token}` } });
            setDataGestion(resGest.data);
            
        } catch (error) {
            console.error("Error cargando reportes:", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="animate-fade-in">
            
            {/* --- BARRA DE FILTROS --- */}
            <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 mb-4">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div className="md:col-span-3">
                        <label className="block text-xs font-bold text-gray-500 mb-1">Fecha Desde</label>
                        <Calendar value={fechaDesde} onChange={(e) => setFechaDesde(e.value)} showIcon dateFormat="yy-mm-dd" className="w-full p-inputtext-sm" />
                    </div>
                    <div className="md:col-span-3">
                        <label className="block text-xs font-bold text-gray-500 mb-1">Fecha Hasta</label>
                        <Calendar value={fechaHasta} onChange={(e) => setFechaHasta(e.value)} showIcon dateFormat="yy-mm-dd" className="w-full p-inputtext-sm" />
                    </div>
                    <div className="md:col-span-4">
                        <label className="block text-xs font-bold text-gray-500 mb-1">Cliente (Opcional)</label>
                        <Dropdown value={selectedCliente} options={clientes} onChange={(e) => setSelectedCliente(e.value)} placeholder="Todos los clientes" showClear className="w-full p-inputtext-sm" filter />
                    </div>
                    <div className="md:col-span-2">
                        <Button label="Consultar" icon="pi pi-search" onClick={buscarDatos} loading={loading} className="w-full p-button-sm" />
                    </div>
                </div>
            </div>

            {/* --- INDICADOR VISUAL DE VISTA ACTIVA (NUEVO) --- */}
            <div className="mb-3 flex items-center gap-2 px-1">
                <span className="text-sm text-gray-500 font-medium">Viendo actualmente:</span>
                <div className={`px-3 py-1 rounded-md text-sm font-bold border flex items-center gap-2 ${
                    activeIndex === 0 
                    ? 'bg-red-50 text-red-700 border-red-200' 
                    : 'bg-blue-50 text-blue-700 border-blue-200'
                }`}>
                    <i className={`pi ${activeIndex === 0 ? 'pi-ban' : 'pi-check-circle'}`}></i>
                    {activeIndex === 0 ? "RECHAZOS HISTÓRICOS" : "GESTIÓN EXITOSA"}
                </div>
            </div>

            {/* --- CONTENIDO --- */}
            <div className="card">
                <TabView activeIndex={activeIndex} onTabChange={(e) => setActiveIndex(e.index)}>
                    <TabPanel header="Rechazos Históricos">
                        <DataTable 
                            value={dataRechazos} 
                            paginator rows={10} size="small" stripedRows 
                            emptyMessage="No se encontraron registros rechazados." 
                            className="text-sm" rowsPerPageOptions={[10, 20, 50]}
                        >
                            <Column field="fecha" header="Fecha" sortable style={{minWidth:'140px'}} />
                            <Column field="cliente" header="Cliente" sortable style={{width:'100px'}} />
                            <Column field="rut" header="RUT" sortable style={{width:'120px'}} />
                            <Column field="telefono" header="Fono" style={{width:'120px'}} />
                            <Column field="mail" header="Mail" style={{maxWidth:'200px', overflow:'hidden', textOverflow:'ellipsis'}} />
                            <Column field="motivo_rechazo" header="Motivo de Rechazo" sortable body={(r) => <span className="font-bold text-red-600">{r.motivo_rechazo}</span>} />
                            <Column field="archivo_origen" header="Archivo Origen" sortable className="text-xs text-gray-500" />
                        </DataTable>
                    </TabPanel>
                    
                    <TabPanel header="Gestión Exitosa (Cargada)">
                        <DataTable 
                            value={dataGestion} 
                            paginator rows={10} size="small" stripedRows 
                            emptyMessage="No hay gestión cargada en este periodo." 
                            className="text-sm" rowsPerPageOptions={[10, 20, 50]}
                        >
                            <Column field="fecha" header="Fecha" sortable style={{minWidth:'140px'}} />
                            <Column field="cliente" header="Cliente" sortable style={{width:'100px'}} />
                            <Column field="rut" header="RUT" sortable style={{width:'120px'}} />
                            <Column field="telefono" header="Fono" style={{width:'120px'}} />
                            <Column field="mail" header="Mail" style={{maxWidth:'200px', overflow:'hidden', textOverflow:'ellipsis'}} />
                            <Column field="gestion" header="Tipo Gestión" sortable body={(r) => <span className="font-medium text-blue-700">{r.gestion}</span>} />
                        </DataTable>
                    </TabPanel>
                </TabView>
            </div>
        </div>
    );
}