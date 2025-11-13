import React from 'react';
import { Routes, Route, Outlet, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext.jsx';

// Importa tus componentes
import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';
import VisorPage from './pages/VisorPage';
import PlaceholderPage from './pages/PlaceholderPage';
import LoginPage from './pages/LoginPage';
import AdminPage from './pages/AdminPage.jsx';
import TrazabilidadPage from './pages/TrazabilidadPage.jsx';
import ListaNegraPage from './pages/ListaNegraPage.jsx';
import GeneradorCampanasPage from './pages/GeneradorCampanasPage.jsx';
import ReportesPage from './pages/reportesPage.jsx';


// Componente de Layout (Sin cambios)
function MainLayout() {
  return (
    <div>
      <Navbar />
      <main className="p-4 md:p-6">
        <Outlet /> 
      </main>
    </div>
  );
}

function ProtectedRoute() {
  // --- CAMBIO ---
  // Usamos 'isAuthenticated' que es un booleano más claro que 'user'
  const { isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    // Si no está autenticado, redirige a la página de login
    return <Navigate to="/login" replace />;
  }
  
  // Si está autenticado, muestra el layout principal (con Navbar y la página hija)
  return <MainLayout />;
}

function App() {
  // --- CAMBIO ---
  // Obtenemos 'isAuthenticated' (en lugar de 'user') y el nuevo 'isLoading'
  const { isAuthenticated, isLoading } = useAuth();

  // --- CAMBIO ---
  // 1. Manejar el estado de carga
  // Mientras el AuthContext verifica el token, mostramos un loader.
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        {/* Puedes poner un spinner o logo aquí */}
        <div>Cargando...</div>
      </div>
    );
  }

  // 2. Una vez que 'isLoading' es false, renderizamos las rutas
  return (
    <Routes>
      {/* --- RUTAS PÚBLICAS --- */}
      {/* Si el usuario ya está logueado y visita /login, redirige al inicio */}
      <Route 
        path="/login" 
        // Usamos 'isAuthenticated' para la redirección
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />

      {/* --- RUTAS PROTEGIDAS --- */}
      {/* Todas las rutas dentro de 'ProtectedRoute' requieren autenticación */}
      <Route path="/" element={<ProtectedRoute />}>
        {/* Ruta raíz (index) */}
        <Route index element={<HomePage />} />
        
        {/* Ruta del Visor */}
        <Route path="visor_page" element={<VisorPage />} />

        {/* Rutas de Trazabilidad */}
        <Route path="trazabilidad_page"  element={<TrazabilidadPage/>} />
        
        {/* Rutas de Lista Negra */}        
        <Route path="ListaNegra_Page"  element={<ListaNegraPage/>} />

        {/* Rutas de placeholder */}       
        <Route 
          path="PlaceholderPage" 
          element={<PlaceholderPage title="Pagina en construccion" />} 
        />
        <Route 
          path="campanas" 
          element={<GeneradorCampanasPage />} 
        />
        <Route 
          path="reportes" 
          element={<ReportesPage />} 
        />
        <Route 
          path="admin" 
          // Quitamos 'title' porque el AdminPage.jsx que hicimos no lo usa
          element={<AdminPage />}
        />

        {/* Ruta para cualquier otra cosa (404) */}
        <Route path="*" element={<PlaceholderPage title="404 - Página No Encontrada" />} />
      </Route>
    </Routes>
  );
}
export default App;