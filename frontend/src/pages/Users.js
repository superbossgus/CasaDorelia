import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import { Users as UsersIcon, Plus, Pencil, Trash2, Loader2, Shield } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Users = () => {
  const [users, setUsers] = useState([]);
  const [cafeterias, setCafeterias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    name: "", email: "", password: "", role: "cajero", cafeteria_id: "", is_active: true
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [usersRes, cafeteriasRes] = await Promise.all([
        axios.get(`${API}/users`),
        axios.get(`${API}/cafeterias`),
      ]);
      setUsers(usersRes.data);
      setCafeterias(cafeteriasRes.data);
    } catch (error) {
      toast.error("Error al cargar usuarios");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.email || (!editingUser && !formData.password)) {
      toast.error("Completa los campos requeridos");
      return;
    }
    setIsSubmitting(true);
    try {
      if (editingUser) {
        await axios.put(`${API}/users/${editingUser.id}`, {
          name: formData.name,
          email: formData.email,
          role: formData.role,
          cafeteria_id: formData.cafeteria_id || null,
          is_active: formData.is_active
        });
        toast.success("Usuario actualizado");
      } else {
        await axios.post(`${API}/users`, formData);
        toast.success("Usuario creado");
      }
      setIsDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar usuario");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar este usuario?")) return;
    try {
      await axios.delete(`${API}/users/${id}`);
      toast.success("Usuario eliminado");
      fetchData();
    } catch (error) {
      toast.error("Error al eliminar usuario");
    }
  };

  const openEditDialog = (user) => {
    setEditingUser(user);
    setFormData({
      name: user.name,
      email: user.email,
      password: "",
      role: user.role,
      cafeteria_id: user.cafeteria_id || "",
      is_active: user.is_active
    });
    setIsDialogOpen(true);
  };

  const resetForm = () => {
    setEditingUser(null);
    setFormData({ name: "", email: "", password: "", role: "cajero", cafeteria_id: "", is_active: true });
  };

  const getRoleBadgeClass = (role) => {
    switch (role) {
      case "admin": return "bg-[#708238]/20 text-[#708238]";
      case "gerente": return "bg-blue-500/20 text-blue-400";
      default: return "bg-[#27272A] text-[#A1A1AA]";
    }
  };

  const roleLabels = {
    admin: "Administrador",
    gerente: "Gerente",
    cajero: "Cajero"
  };

  const getCafeteriaName = (id) => cafeterias.find(c => c.id === id)?.name || "—";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="users-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Usuarios</h1>
          <p className="text-[#A1A1AA] mt-1">Gestiona el acceso al sistema</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-user-button">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Usuario
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white font-manrope">
                {editingUser ? "Editar Usuario" : "Nuevo Usuario"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Nombre *</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Nombre completo"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Email *</Label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="correo@ejemplo.com"
                />
              </div>
              {!editingUser && (
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Contraseña *</Label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="••••••••"
                  />
                </div>
              )}
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Rol *</Label>
                <Select value={formData.role} onValueChange={(v) => setFormData({...formData, role: v})}>
                  <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                    <SelectValue placeholder="Seleccionar rol" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#161616] border-[#27272A]">
                    <SelectItem value="admin" className="text-white hover:bg-[#27272A]">Administrador</SelectItem>
                    <SelectItem value="gerente" className="text-white hover:bg-[#27272A]">Gerente</SelectItem>
                    <SelectItem value="cajero" className="text-white hover:bg-[#27272A]">Cajero</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {(formData.role === "gerente" || formData.role === "cajero") && (
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Cafetería Asignada</Label>
                  <Select value={formData.cafeteria_id} onValueChange={(v) => setFormData({...formData, cafeteria_id: v})}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                      <SelectValue placeholder="Seleccionar cafetería" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      <SelectItem value="" className="text-white hover:bg-[#27272A]">Sin asignar</SelectItem>
                      {cafeterias.map((cafe) => (
                        <SelectItem key={cafe.id} value={cafe.id} className="text-white hover:bg-[#27272A]">{cafe.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {editingUser ? "Actualizar" : "Crear"} Usuario
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Users Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <UsersIcon className="h-5 w-5 text-[#708238]" />
            Lista de Usuarios ({users.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {users.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <UsersIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay usuarios registrados</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Nombre</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Email</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Rol</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Cafetería</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell className="text-white font-medium">{user.name}</TableCell>
                      <TableCell className="text-[#A1A1AA]">{user.email}</TableCell>
                      <TableCell>
                        <Badge className={`flex items-center gap-1 w-fit ${getRoleBadgeClass(user.role)}`}>
                          <Shield className="h-3 w-3" />
                          {roleLabels[user.role]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-[#A1A1AA]">{getCafeteriaName(user.cafeteria_id)}</TableCell>
                      <TableCell>
                        <Badge className={user.is_active ? 'status-active' : 'status-inactive'}>
                          {user.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(user)}
                            className="text-[#A1A1AA] hover:text-white hover:bg-[#27272A]"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(user.id)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-400/10"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Users;
