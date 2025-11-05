import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx'; // Importa el hook de Auth
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';

// Importa las clases de CSS que ya definimos
import { btnPrimary, inputClass } from '../styles/appStyles.js';

function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();
  const { login } = useAuth(); // Obtén la función 'login' del contexto

  const handleSubmit = async (e) => {
    e.preventDefault(); // Evita que el formulario recargue la página
    setError('');
    setIsLoading(true);

    try {
      // Llama a la función 'login' del contexto
      // Esta función (que definiremos) se encargará de llamar a la API
      await login(email, password);
      
      // Si 'login' fue exitoso, redirige a la página principal
      navigate('/'); 

    } catch (err) {
      // Si 'login' falla (ej. 401 Unauthorized), muestra un error
      setError('Correo o contraseña incorrecta.');
      console.error("Error de login:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    // Centra el formulario en la pantalla
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="p-8 bg-white shadow-md rounded-lg w-full max-w-sm">
        
        {/* Encabezado (como en tu Reflex) */}
        <h1 className="text-4xl font-bold text-center bg-gradient-to-r from-indigo-600 to-green-500 bg-clip-text text-transparent pb-4">
          NETPAG-INTRA
        </h1>
        <h2 className="text-2xl font-semibold text-center text-gray-700 mb-6">
          Iniciar Sesión
        </h2>
        
        {/* Formulario */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label 
              htmlFor="email" 
              className="block text-sm font-medium text-gray-600 mb-1"
            >
              Correo Electrónico
            </label>
            <InputText 
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass} // Reutiliza tu clase de CSS
              placeholder="usuario@dominio.com"
              required
              disabled={isLoading}
            />
          </div>
          
          <div>
            <label 
              htmlFor="password" 
              className="block text-sm font-medium text-gray-600 mb-1"
            >
              Contraseña
            </label>
            <InputText 
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass} // Reutiliza tu clase de CSS
              placeholder="••••••••"
              required
              disabled={isLoading}
            />
          </div>
          
          {/* Muestra errores de login */}
          {error && (
            <div className="text-red-600 text-sm text-center">
              {error}
            </div>
          )}

          {/* Botón de Ingresar */}
          <Button 
            label={isLoading ? "Ingresando..." : "Ingresar"}
            type="submit" 
            className={`${btnPrimary} w-full`} // Usa la clase de CSS y la hace ancha
            disabled={isLoading}
          />
        </form>
      </div>
    </div>
  );
}

export default LoginPage;