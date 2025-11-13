import React, { useState, useEffect } from "react";
import axios from "axios";
import { useAuth } from "../context/AuthContext.jsx";

// Componentes de Gráficos (Recharts)
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line, ResponsiveContainer, Legend } from "recharts";

// Componentes de UI (PrimeReact)
import { Card } from 'primereact/card';
import { Dropdown } from 'primereact/dropdown';
import { ProgressSpinner } from 'primereact/progressspinner';

// Estilos
const API_REPORTES_URL = '/api/reportes'; // Usando el proxy

export default function ReportesPage() {
  const { token } = useAuth();
  const [cartera, setCartera] = useState("Todas");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  // Cargar datos desde FastAPI
  useEffect(() => {
    if (!token) return;

    const fetchData = async () => {
      setLoading(true);
      try {
        const response = await axios.get(`${API_REPORTES_URL}/funnel`, {
          headers: { Authorization: `Bearer ${token}` },
          params: {
            fecha_inicio: "20251103", // Estos podrían ser dinámicos con un calendario
            periodo: "202511",
          },
        });
        setData(response.data);
      } catch (error) {
        console.error("Error al obtener datos del backend:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [token]);

  if (loading) {
    return (
        <div className="flex justify-center items-center h-64">
            <ProgressSpinner />
        </div>
    );
  }

  if (!data.length) {
    return <div className="p-6 text-lg text-gray-600">No hay datos disponibles para el periodo seleccionado.</div>;
  }

  // --- LÓGICA DE PROCESAMIENTO DE DATOS (Adaptada de tu archivo) ---

  // Filtrar datos si se selecciona una cartera específica
  const filteredData = cartera === "Todas" ? data : data.filter(d => d.CARTERA === cartera);

  // Cálculos agregados
  const resumen = filteredData.reduce(
    (acc, curr) => {
      acc.gestiones += curr["Q.Gestiones"] || 0;
      acc.deudores += curr["Q.Deudores"] || 0;
      acc.cd += curr["Q.CD"] || 0;
      acc.compromisos += curr["Q.Compromisos"] || 0;
      return acc;
    },
    { gestiones: 0, deudores: 0, cd: 0, compromisos: 0 }
  );

  // Datos de embudo
  const funnelData = [
    { etapa: "Gestiones", valor: resumen.gestiones, fill: "#3b82f6" },
    { etapa: "Deudores", valor: resumen.deudores, fill: "#6366f1" },
    { etapa: "Contactos Directos", valor: resumen.cd, fill: "#10b981" },
    { etapa: "Compromisos", valor: resumen.compromisos, fill: "#f59e0b" },
  ];

  // Datos por fecha (Agrupados si hay múltiples carteras)
  const tendenciaMap = {};
  filteredData.forEach(d => {
      if (!tendenciaMap[d.FECHA]) {
          tendenciaMap[d.FECHA] = { fecha: d.FECHA, gestiones: 0, cd: 0, compromisos: 0 };
      }
      tendenciaMap[d.FECHA].gestiones += d["Q.Gestiones"];
      tendenciaMap[d.FECHA].cd += d["Q.CD"];
      tendenciaMap[d.FECHA].compromisos += d["Q.Compromisos"];
  });
  // Ordenar por fecha
  const tendencia = Object.values(tendenciaMap).sort((a, b) => new Date(a.fecha) - new Date(b.fecha));

  // Agrupación por cartera (para el gráfico comparativo)
  const carterasMap = {};
  data.forEach((d) => {
    const c = d.CARTERA;
    if (!carterasMap[c]) carterasMap[c] = { cartera: c, gestiones: 0, cd: 0, compromisos: 0 };
    carterasMap[c].gestiones += d["Q.Gestiones"];
    carterasMap[c].cd += d["Q.CD"];
    carterasMap[c].compromisos += d["Q.Compromisos"];
  });
  const carterasData = Object.values(carterasMap);
  
  // Opciones para el dropdown
  const carteraOptions = [{label: "Todas", value: "Todas"}, ...carterasData.map(c => ({label: c.cartera, value: c.cartera}))];

  return (
    <div className="w-full animate-fade-in">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Funnel de Cobranza - Bot</h1>
        
        <div className="flex items-center gap-2">
            <label className="font-semibold text-gray-700">Cartera:</label>
            <Dropdown value={cartera} options={carteraOptions} onChange={(e) => setCartera(e.value)} className="w-[200px]" />
        </div>
      </div>

      {/* KPIs principales */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {[
          { title: "Gestiones", value: resumen.gestiones, color: "text-blue-600", icon: "pi pi-send" },
          { title: "Deudores", value: resumen.deudores, color: "text-indigo-600", icon: "pi pi-users" },
          { title: "Contactos Directos", value: resumen.cd, color: "text-green-600", icon: "pi pi-phone" },
          { title: "Compromisos", value: resumen.compromisos, color: "text-yellow-600", icon: "pi pi-check-circle" },
        ].map((kpi) => (
          <Card key={kpi.title} className="shadow-sm border border-gray-100">
            <div className="flex justify-between items-center">
                <div>
                    <div className="text-gray-500 font-medium text-sm uppercase">{kpi.title}</div>
                    <div className={`text-3xl font-bold ${kpi.color}`}>{kpi.value.toLocaleString()}</div>
                </div>
                <i className={`${kpi.icon} text-2xl opacity-20`}></i>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Funnel */}
          <Card title="Embudo de Conversión" className="shadow-sm h-full">
            <ResponsiveContainer width="100%" height={300}>
                <BarChart data={funnelData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" />
                <YAxis type="category" dataKey="etapa" width={120} />
                <Tooltip formatter={(value) => value.toLocaleString()} />
                <Bar dataKey="valor" fill="#8884d8" radius={[0, 4, 4, 0]} barSize={40}>
                    {/* Colores personalizados por barra */}
                </Bar>
                </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Tendencia temporal */}
          <Card title="Evolución Diaria" className="shadow-sm h-full">
            <ResponsiveContainer width="100%" height={300}>
                <LineChart data={tendencia} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="fecha" tickFormatter={(t) => t.substring(5)} /> {/* Muestra solo MM-DD */}
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="gestiones" name="Gestiones" stroke="#3b82f6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="cd" name="Cont. Directos" stroke="#10b981" strokeWidth={2} />
                <Line type="monotone" dataKey="compromisos" name="Compromisos" stroke="#f59e0b" strokeWidth={2} />
                </LineChart>
            </ResponsiveContainer>
          </Card>
      </div>

      {/* Comparación por cartera */}
      <Card title="Desempeño por Cartera" className="shadow-sm">
        <ResponsiveContainer width="100%" height={350}>
            <BarChart data={carterasData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="cartera" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="gestiones" name="Gestiones" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            <Bar dataKey="cd" name="Cont. Directos" fill="#10b981" radius={[4, 4, 0, 0]} />
            <Bar dataKey="compromisos" name="Compromisos" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}