import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { jwtDecode } from 'jwt-decode';

// URL base
const API_URL = ''; 
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [user, setUser] = useState(() => {
        try { return JSON.parse(localStorage.getItem('user')); } catch { return null; }
    });
    const [isLoading, setIsLoading] = useState(true);
    
    // Estado para mensajes de sesión (para que la App los muestre)
    const [sessionAlert, setSessionAlert] = useState(null); // { type: 'warning'|'error', msg: '' }

    // Referencias para los timers
    const logoutTimerRef = useRef(null);
    const warningTimer5Ref = useRef(null);
    const warningTimer1Ref = useRef(null);

    // Función de limpieza de timers
    const clearTimers = () => {
        if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
        if (warningTimer5Ref.current) clearTimeout(warningTimer5Ref.current);
        if (warningTimer1Ref.current) clearTimeout(warningTimer1Ref.current);
    };

    // Función de Logout (Llama al backend para cancelar procesos)
    const logout = useCallback(async (expired = false) => {
        clearTimers();
        
        if (token) {
            try {
                // Avisar al backend para matar procesos (Fire and forget)
                await axios.post(`${API_URL}/api/auth/logout`, {}, {
                    headers: { Authorization: `Bearer ${token}` }
                });
            } catch (e) {
                console.warn("No se pudo notificar logout al backend", e);
            }
        }

        setToken(null);
        setUser(null);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        
        if (expired) {
            setSessionAlert({ type: 'error', msg: 'Tu sesión ha expirado. Por favor ingresa nuevamente.' });
        } else {
            setSessionAlert(null); // Limpiar alertas si fue logout manual
        }
    }, [token]);

    // Función para iniciar los timers basados en el token
    const startSessionTimers = useCallback((accessToken) => {
        clearTimers();
        if (!accessToken) return;

        try {
            const decoded = jwtDecode(accessToken);
            const expTime = decoded.exp * 1000; // a milisegundos
            const currentTime = Date.now();
            const timeLeft = expTime - currentTime;

            if (timeLeft <= 0) {
                logout(true);
                return;
            }

            console.log(`Sesión expira en ${(timeLeft / 60000).toFixed(1)} minutos.`);

            // 1. Timer de Logout exacto
            logoutTimerRef.current = setTimeout(() => {
                logout(true);
            }, timeLeft);

            // 2. Advertencia 5 minutos antes
            const timeToWarn5 = timeLeft - (5 * 60 * 1000);
            if (timeToWarn5 > 0) {
                warningTimer5Ref.current = setTimeout(() => {
                    setSessionAlert({ type: 'warning', msg: 'Tu sesión expirará en 5 minutos.' });
                }, timeToWarn5);
            }

            // 3. Advertencia 1 minuto antes
            const timeToWarn1 = timeLeft - (1 * 60 * 1000);
            if (timeToWarn1 > 0) {
                warningTimer1Ref.current = setTimeout(() => {
                    setSessionAlert({ type: 'error', msg: '¡Atención! Tu sesión expirará en 1 minuto.' });
                }, timeToWarn1);
            }

        } catch (error) {
            console.error("Error decodificando token para timers:", error);
            logout();
        }
    }, [logout]);

    // Efecto de inicialización
    useEffect(() => {
        const initAuth = async () => {
            const storedToken = localStorage.getItem('token');
            if (storedToken) {
                try {
                    const decoded = jwtDecode(storedToken);
                    if (decoded.exp * 1000 < Date.now()) {
                        logout(true);
                    } else {
                        setToken(storedToken);
                        // Reiniciar timers al recargar página
                        startSessionTimers(storedToken);
                    }
                } catch {
                    logout();
                }
            }
            setIsLoading(false);
        };
        initAuth();
        
        return () => clearTimers();
    }, [startSessionTimers, logout]);

    // Login
    const login = useCallback(async (email, password) => {
        try {
            const params = new URLSearchParams();
            params.append('username', email);
            params.append('password', password);

            const response = await axios.post(`${API_URL}/api/auth/token`, params);
            const { access_token } = response.data;
            
            const decodedUser = jwtDecode(access_token);
            const userData = { email: decodedUser.sub, rol: decodedUser.rol };

            localStorage.setItem('token', access_token);
            localStorage.setItem('user', JSON.stringify(userData));
            
            setToken(access_token);
            setUser(userData);
            setSessionAlert(null); // Limpiar alertas viejas
            
            // Iniciar timers
            startSessionTimers(access_token);
            
            return true;
        } catch (error) {
            throw error;
        }
    }, [startSessionTimers]);

    // Interceptor de Axios para atrapar 401 globalmente
    useEffect(() => {
        const interceptor = axios.interceptors.response.use(
            (response) => response,
            (error) => {
                if (error.response && error.response.status === 401) {
                    // Si el backend dice 401, forzamos logout
                    console.warn("401 detectado, cerrando sesión...");
                    logout(true);
                }
                return Promise.reject(error);
            }
        );
        return () => axios.interceptors.response.eject(interceptor);
    }, [logout]);

    const value = {
        token,
        user,
        isAuthenticated: !!token,
        isLoading,
        sessionAlert, // Exponemos la alerta para que App.jsx la use
        setSessionAlert, // Para poder cerrarla manualmente
        login,
        logout
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);