// Ruta: src/context/AuthContext.jsx

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { jwtDecode } from 'jwt-decode'; // Asegúrate de tenerlo instalado (npm install jwt-decode)

// URL DE DESARROLLO http://localhost:8001

const API_URL = ''; // URL base de tu API
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [user, setUser] = useState(JSON.parse(localStorage.getItem('user')));
    const [isLoading, setIsLoading] = useState(true); // Para la carga inicial

    useEffect(() => {
        try {
            const storedToken = localStorage.getItem('token');
            const storedUser = localStorage.getItem('user');

            if (storedToken && storedUser) {
                // ESTA ES LA LÓGICA CLAVE QUE FALTABA:
                const decodedToken = jwtDecode(storedToken);
                const isExpired = decodedToken.exp * 1000 < Date.now();

                if (isExpired) {
                    console.log("Token expirado, cerrando sesión.");
                    logout(); // Llama a logout para limpiar localStorage
                } else {
                    setToken(storedToken);
                    setUser(JSON.parse(storedUser));
                }
            }
        } catch (error) {
            console.error("Error al verificar token guardado:", error);
            logout(); // Limpia datos corruptos
        } finally {
            setIsLoading(false); // Terminamos la carga inicial
        }
    }, []); // El array vacío asegura que solo se ejecute al montar

    const login = useCallback(async (email, password) => {
        try {
            const params = new URLSearchParams();
            params.append('username', email); // FastAPI espera 'username'
            params.append('password', password);

            const response = await axios.post(`${API_URL}/api/auth/token`, params, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            });

            const { access_token } = response.data;
            const decodedUser = jwtDecode(access_token);
            
            const userData = {
                email: decodedUser.sub,
                rol: decodedUser.rol
            };

            localStorage.setItem('token', access_token);
            localStorage.setItem('user', JSON.stringify(userData));
            setToken(access_token);
            setUser(userData);
            
            return true;
        } catch (error) {
            console.error("Error en el login:", error.response?.data?.detail || error.message);
            logout(); 
            throw error; // Lanza el error para que LoginPage.jsx lo atrape
        }
    }, []);

    const logout = useCallback(() => {
        setToken(null);
        setUser(null);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }, []);

    const isAuthenticated = !!token; 

    const value = {
        token,
        user,
        isAuthenticated, // App.jsx usa esto
        isLoading,     // App.jsx usa esto
        login,
        logout,
    };

    return (
        <AuthContext.Provider value={value}>
            {!isLoading && children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth debe ser usado dentro de un AuthProvider');
    }
    return context;
};