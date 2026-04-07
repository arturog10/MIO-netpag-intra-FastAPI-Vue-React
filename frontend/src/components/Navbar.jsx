import React from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom'; // --- CAMBIO: Importa useNavigate
import { useAuth } from '../context/AuthContext.jsx';
import { Button } from 'primereact/button';

// (Tus clases de estilo están perfectas)
const btnBase = "py-2 px-3 rounded-md text-sm font-medium transition-colors";
const btnOutline = `${btnBase} bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50`;
// const btnRed = `${btnBase} bg-red-600 text-white hover:bg-red-700`;

function Navbar() {
  // --- CAMBIO: Obtén 'isAuthenticated' y 'user' por separado ---
  // 'isAuthenticated' es el booleano (true/false)
  // 'user' es el objeto ({email, rol}) o null
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate(); // Hook para redirigir

  // Clase para NavLink activo
  const activeClass = "text-blue-600 font-semibold";
  const inactiveClass = "text-gray-600 hover:text-blue-600";

  // --- CAMBIO: Mejor manejo del logout ---
  const handleLogout = () => {
    logout();
    navigate('/login'); // Redirige a login después de cerrar sesión
  };

  return (
    <nav className="flex w-full flex-col md:flex-row items-center justify-between gap-4 px-6 py-4 shadow-md bg-white">

      {/* Lado Izquierdo: Título y Links */}
      <div className="flex w-full md:w-auto items-center justify-between">
        <Link to="/" className="text-xl font-bold text-gray-800">
          INTRANET
        </Link>
      </div>

      {/* --- CAMBIO: Oculta los links si no está autenticado --- */}
      {/* Esto evita mostrar links a rutas protegidas */}
      {isAuthenticated && (
        <div className="flex flex-col md:flex-row items-center gap-4 md:gap-6">
          <NavLink to="/visor_page" className={({ isActive }) => isActive ? activeClass : inactiveClass}>
            Estrategias
          </NavLink>
          {/* <NavLink to="/trazabilidad_page" className={({ isActive }) => isActive ? activeClass : inactiveClass}>
            Trazabilidad
          </NavLink>
          <NavLink to="/ListaNegra_Page" className={({ isActive }) => isActive ? activeClass : inactiveClass}>
            Lista Negra
          </NavLink>

          <NavLink to="/campanas" className={({ isActive }) => isActive ? activeClass : inactiveClass}>
            Campañas
          </NavLink> */}

          <NavLink to="/reportes" className={({ isActive }) => isActive ? activeClass : inactiveClass}>
            Reportes
          </NavLink>
          {/* --- CAMBIO: Verificación segura del rol --- */}
          {/* 'user' aquí nunca será 'null' gracias al 'isAuthenticated' de arriba */}
          {user.rol === 'admin' && (
            <NavLink to="/admin" className="font-bold text-red-600 hover:text-red-700">
              Admin
            </NavLink>
          )}
        </div>
      )}

      {/* Lado Derecho: Info de Usuario y Logout */}
      <div className="flex items-center gap-4">
        {/* --- CAMBIO: Usa 'isAuthenticated' como condición --- */}
        {isAuthenticated ? (
          <>
            <span className="text-sm font-medium text-gray-700 hidden md:block">
              {/* --- CAMBIO: El token solo tiene 'email', no 'nombre_completo' --- */}
              Usuario: {user.email}
            </span>
            <Button
              label="Cerrar Sesión"
              onClick={handleLogout} // Usa el nuevo handler
              className={btnOutline}
              size="small"
            />
          </>
        ) : (
          // --- CAMBIO: El botón "Iniciar Sesión" ahora funciona ---
          <Button
            label="Iniciar Sesión"
            size="small"
            onClick={() => navigate('/login')} // Añade el onClick
            className={btnOutline} // Le da el mismo estilo
          />
        )}
      </div>
    </nav>
  );
}

export default Navbar;