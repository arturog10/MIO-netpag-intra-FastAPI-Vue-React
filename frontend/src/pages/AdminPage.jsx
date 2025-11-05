// En src/pages/AdminPage.jsx
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

// --- CAMBIO ---
// Asumimos que tu contexto de autenticación está en esta ruta
// y provee un hook 'useAuth'
import { useAuth } from '../context/AuthContext'; 
// --- FIN CAMBIO ---

// --- Importaciones de PrimeReact ---
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Button } from 'primereact/button';
import { Dialog } from 'primereact/dialog';
import { InputText } from 'primereact/inputtext';
import { Dropdown } from 'primereact/dropdown';
import { InputSwitch } from 'primereact/inputswitch';
import { TabView, TabPanel } from 'primereact/tabview';
import { Toast } from 'primereact/toast';

// URL de la API de Admin
const API_URL = 'http://localhost:8000/api/admin';

// Opciones de Roles
const rolesOptions = [
    { label: 'Usuario', value: 'usuario' },
    { label: 'Admin', value: 'admin' }
];

function AdminPage() {
    const toast = useRef(null);
    const navigate = useNavigate();
    
    // --- CAMBIO ---
    // Obtenemos el token y los datos del usuario desde tu AuthContext
    // Asumo que 'user' es un objeto como: { email: '...', rol: 'admin' }
    const { token, user } = useAuth(); 
    // --- FIN CAMBIO ---
    
    // --- Estados ---
    const [isLoading, setIsLoading] = useState(false);
    const [users, setUsers] = useState([]);
    const [activeTab, setActiveTab] = useState(0); 
    
    const [newUserForm, setNewUserForm] = useState({
        nombre_completo: '',
        email: '',
        password: '',
        rol: 'usuario'
    });
    
    const [showResetDialog, setShowResetDialog] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);
    const [newPassword, setNewPassword] = useState('');

    // --- CAMBIO: Configuración de Axios (¡IMPORTANTE!) ---
    // Esta función ahora usa el 'token' real del AuthContext.
    const getAuthHeaders = () => {
        if (!token) {
            console.error("No hay token de autenticación.");
            // Si no hay token, redirigimos a login
            // (Aunque el useEffect de abajo ya debería haberlo hecho)
            navigate('/login');
            return {};
        }
        return { Authorization: `Bearer ${token}` };
    };
    // --- FIN CAMBIO ---

    // --- CAMBIO: Protección de Página y Carga de Datos ---
    useEffect(() => {
        // Este efecto se ejecuta cuando el componente carga
        // o cuando 'token' o 'user' cambian.
        
        if (token && user) {
            // Caso 1: El usuario está logueado y tenemos sus datos
            if (user.rol !== 'admin') {
                // No es admin. Mostrar error y redirigir.
                toast.current.show({ 
                    severity: 'error', 
                    summary: 'Acceso Denegado', 
                    detail: 'No tienes permisos de administrador.' 
                });
                setTimeout(() => navigate('/'), 2000); // Redirige al Home
            } else {
                // ¡Es admin! Cargar la lista de usuarios.
                fetchUsers();
            }
        } else if (!token) {
            // Caso 2: No hay token (usuario no logueado)
            // Redirigir a la página de login
            toast.current.show({ 
                severity: 'warn', 
                summary: 'No autenticado', 
                detail: 'Por favor, inicia sesión.' 
            });
            navigate('/login');
        }
        // Caso 3 (implícito): Hay token pero 'user' aún está cargando.
        // El efecto no hace nada y espera al siguiente render cuando 'user' esté listo.

    }, [token, user, navigate]); // Dependencias clave
    // --- FIN CAMBIO ---


    // --- Funciones de API ---
    // (No es necesario cambiar esta función, ya que depende de 'getAuthHeaders')
    const fetchUsers = async () => {
        setIsLoading(true);
        try {
            const response = await axios.get(`${API_URL}/users`, { headers: getAuthHeaders() });
            setUsers(response.data);
        } catch (error) {
            console.error("Error al cargar usuarios:", error);
            if (error.response?.status !== 401) { // Evita doble toast si es por no estar logueado
                 toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar los usuarios.' });
            }
        } finally {
            setIsLoading(false);
        }
    };

    // --- Manejadores Pestaña "Crear Usuario" ---
    // (Sin cambios, ya usa 'getAuthHeaders')
    const handleCreateUserChange = (e) => {
        const { name, value } = e.target;
        setNewUserForm(prev => ({ ...prev, [name]: value }));
    };

    const handleCreateUserSubmit = async (e) => {
        e.preventDefault();
        if (!newUserForm.email || !newUserForm.password || !newUserForm.nombre_completo) {
             toast.current.show({ severity: 'warn', summary: 'Campos requeridos', detail: 'Completa todos los campos.' });
             return;
        }
        
        try {
            await axios.post(`${API_URL}/users`, newUserForm, { headers: getAuthHeaders() });
            toast.current.show({ severity: 'success', summary: 'Éxito', detail: 'Usuario creado.' });
            setNewUserForm({ nombre_completo: '', email: '', password: '', rol: 'usuario' });
            setActiveTab(0);
            fetchUsers();
        } catch (error) {
            console.error("Error al crear usuario:", error);
            toast.current.show({ severity: 'error', summary: 'Error', detail: error.response?.data?.detail || 'No se pudo crear el usuario.' });
        }
    };

    // --- Manejadores Pestaña "Gestionar Usuarios" (Inline) ---
    // (Sin cambios, ya usa 'getAuthHeaders')
    const handleRoleChange = async (user, newRole) => {
        try {
            await axios.put(`${API_URL}/users/${user.id_usuario}/role`, { rol: newRole }, { headers: getAuthHeaders() });
            
            setUsers(prevUsers => 
                prevUsers.map(u => 
                    u.id_usuario === user.id_usuario ? { ...u, rol: newRole } : u
                )
            );
            toast.current.show({ severity: 'success', summary: 'Actualizado', detail: 'Rol cambiado.' });
        } catch (error) {
             console.error("Error al cambiar rol:", error);
             toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo cambiar el rol.' });
             fetchUsers();
        }
    };

    const handleStatusToggle = async (user, newStatus) => {
         try {
            await axios.put(`${API_URL}/users/${user.id_usuario}/status`, { activo: newStatus }, { headers: getAuthHeaders() });
            
            setUsers(prevUsers => 
                prevUsers.map(u => 
                    u.id_usuario === user.id_usuario ? { ...u, activo: newStatus } : u
                )
            );
            toast.current.show({ severity: 'success', summary: 'Actualizado', detail: 'Estado cambiado.' });
        } catch (error) {
             console.error("Error al cambiar estado:", error);
             toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo cambiar el estado.' });
             fetchUsers();
        }
    };

    // --- Manejadores "Resetear Contraseña" (Dialog) ---
    // (Sin cambios, ya usa 'getAuthHeaders')
    const openResetDialog = (user) => {
        setSelectedUser(user);
        setNewPassword('');
        setShowResetDialog(true);
    };

    const handleResetPassword = async () => {
        if (!newPassword) {
            toast.current.show({ severity: 'warn', summary: 'Inválido', detail: 'Ingresa una contraseña.' });
            return;
        }
        
        try {
            await axios.put(`${API_URL}/users/${selectedUser.id_usuario}/reset-password`, { new_password: newPassword }, { headers: getAuthHeaders() });
            setShowResetDialog(false);
            setSelectedUser(null);
            toast.current.show({ severity: 'success', summary: 'Éxito', detail: 'Contraseña reseteada.' });
        } catch (error) {
             console.error("Error al resetear contraseña:", error);
             toast.current.show({ severity: 'error', summary: 'Error', detail: 'No se pudo resetear.' });
        }
    };

    // --- Templates para Celdas de la Tabla ---
    // (Sin cambios)
    const rolBodyTemplate = (rowData) => {
        return (
            <Dropdown 
                value={rowData.rol} 
                options={rolesOptions} 
                onChange={(e) => handleRoleChange(rowData, e.value)} 
                placeholder="Selecciona Rol"
                className="w-full"
            />
        );
    };

    const statusBodyTemplate = (rowData) => {
        return (
            <div className="flex justify-center">
                <InputSwitch 
                    checked={Boolean(rowData.activo)} 
                    onChange={(e) => handleStatusToggle(rowData, e.value)} 
                />
            </div>
        );
    };

    const actionsBodyTemplate = (rowData) => {
        return (
            <Button 
                label="Resetear Contraseña" 
                icon="pi pi-key" 
                className="p-button-sm p-button-secondary" 
                onClick={() => openResetDialog(rowData)}
            />
        );
    };
    
    // --- Renderizado ---
    // (Sin cambios)
    return (
        <div className="w-full card p-4">
            <Toast ref={toast} />
            
            {/* <h1 className="text-3xl font-bold mb-4">Panel de Administración</h1> */}

            <TabView activeIndex={activeTab} onTabChange={(e) => setActiveTab(e.index)}>
                
                {/* Pestaña 1: Gestionar Usuarios */}
                <TabPanel header="Gestionar Usuarios">
                    <DataTable 
                        value={users} 
                        loading={isLoading}
                        emptyMessage="No se encontraron usuarios."
                        stripedRows size="small"
                        responsiveLayout="scroll"
                    >
                        <Column field="id_usuario" header="ID" sortable />
                        <Column field="email" header="Email (Login)" sortable />
                        <Column field="nombre_completo" header="Nombre Completo" sortable />
                        <Column field="rol" header="Rol" body={rolBodyTemplate} />
                        <Column field="activo" header="Activo" body={statusBodyTemplate} style={{ width: '8rem' }} />
                        <Column header="Acciones" body={actionsBodyTemplate} />
                    </DataTable>
                </TabPanel>

                {/* Pestaña 2: Crear Nuevo Usuario */}
                <TabPanel header="Crear Nuevo Usuario">
                    <div className="p-4 max-w-lg mx-auto">
                        <form onSubmit={handleCreateUserSubmit} className="flex flex-col gap-4">
                            <h2 className="text-xl font-semibold">Crear Nuevo Usuario</h2>
                            <div className="flex flex-col gap-2">
                                <label htmlFor="nombre_completo">Nombre Completo</label>
                                <InputText id="nombre_completo" name="nombre_completo" value={newUserForm.nombre_completo} onChange={handleCreateUserChange} required />
                            </div>
                            <div className="flex flex-col gap-2">
                                <label htmlFor="email">Correo Electrónico (Login)</label>
                                <InputText id="email" name="email" type="email" value={newUserForm.email} onChange={handleCreateUserChange} required />
                            </div>
                            <div className="flex flex-col gap-2">
                                <label htmlFor="password">Contraseña Temporal</label>
                                <InputText id="password" name="password" type="password" value={newUserForm.password} onChange={handleCreateUserChange} required />
                            </div>
                            <div className="flex flex-col gap-2">
                                <label htmlFor="rol">Rol</label>
                                <Dropdown id="rol" name="rol" value={newUserForm.rol} options={rolesOptions} onChange={handleCreateUserChange} />
                            </div>
                            <Button label="Crear Usuario" type="submit" icon="pi pi-plus" className="mt-2" />
                        </form>
                    </div>
                </TabPanel>

            </TabView>

            {/* --- Diálogo para Resetear Contraseña --- */}
            <Dialog 
                header={`Resetear Contraseña para ${selectedUser?.email || ''}`}
                visible={showResetDialog} 
                className="w-11/12 md:w-1/3"
                onHide={() => setShowResetDialog(false)} 
                footer={
                    <div className="flex justify-end gap-2">
                        <Button label="Cancelar" icon="pi pi-times" onClick={() => setShowResetDialog(false)} className="p-button-text" />
                        <Button label="Guardar Contraseña" icon="pi pi-check" onClick={handleResetPassword} autoFocus />
                    </div>
                }
            >
                <div className="flex flex-col gap-2 mt-4">
                    <label htmlFor="new_password">Nueva Contraseña</label>
                    <InputText id="new_password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Nueva Contraseña Temporal" />
                </div>
            </Dialog>

        </div>
    );
}

export default AdminPage;