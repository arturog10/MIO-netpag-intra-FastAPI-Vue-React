import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' // Tu CSS de Tailwind

// 1. Importa el Router y el AuthProvider
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext.jsx'; // Ajusta la ruta si es necesario

// 2. Importa los estilos de PrimeReact (¡asegúrate de que estén aquí!)
import "primereact/resources/themes/lara-light-indigo/theme.css"; 
import "primereact/resources/primereact.min.css";                
import "primeicons/primeicons.css";                              

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* 3. Envuelve tu App con el Router y el Provider */}
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)