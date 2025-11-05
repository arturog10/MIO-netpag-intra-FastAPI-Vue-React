import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from 'primereact/button'; // Re-usamos el botón de PrimeReact

function HomePage() {
  return (
    // Centra el contenido verticalmente (menos la altura aprox. del navbar)
    <div className="flex items-center justify-center min-h-[calc(100vh-80px)] p-4">
      <div className="flex flex-col items-center text-center space-y-4">
        
        <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-indigo-600 to-green-500 bg-clip-text text-transparent pb-2">
          Bienvenidos a NETPAG-INTRA
        </h1>

        <p className="text-xl md:text-2xl text-gray-600">
          Herramientas internas para la gestión de datos.
        </p>

        <div className="pt-6">
          {/* Usamos el componente Button de PrimeReact, pero podríamos reemplazarlo por un <Link> con clases de Tailwind */}
          <Link to="/visor_page">
            <Button label="Crear Estrategia" size="large" />
          </Link>
        </div>

      </div>
    </div>
  );
}

export default HomePage;