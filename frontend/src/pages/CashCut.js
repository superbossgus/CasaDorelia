/**
 * Corte de caja (BOS-119).
 *
 * El efectivo no viaja por la API de Clip, asi que esta pantalla es la unica
 * fuente de ese dinero. Tres reglas que estan en el codigo, no en un aviso:
 *
 * 1. La venta en efectivo NO se captura: se deriva de lo que se cuenta
 *    (contado + retiros - fondo). El preview usa la misma formula que el
 *    servidor, y el servidor es el que manda.
 * 2. No se dibuja un total de las dos marcas. Casa Dorelia y Le Pain Dore
 *    tienen repartos distintos; el total del dia es por sucursal.
 * 3. Un dia sin corte dice que su cifra es piso. Un corte en cero es un cero
 *    medido, y eso vuelve citable el bruto con tarjeta de ese dia.
 */
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { toast } from "sonner";
import axios from "axios";
import { useAuth } from "../context/AuthContext";
import { Banknote, Loader2, Calculator, Pencil, AlertTriangle, CreditCard } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const money = (value) =>
  new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(Number(value || 0));

/** Un campo vacio es "no capturado", no cero: `Number("")` da 0 y eso mentiria. */
const toNumber = (value) => (value === "" || value === null ? null : Number(value));

const EMPTY_FORM = {
  turno: "completo",
  fondo_inicial: "",
  efectivo_contado: "",
  retiros: "",
  tickets_efectivo: "",
  notas: "",
};

const CashCut = () => {
  const { user, isAdmin, canManage } = useAuth();
  const [cafeterias, setCafeterias] = useState([]);
  const [cafeteriaId, setCafeteriaId] = useState(user?.cafeteria_id || "");
  const [businessDate, setBusinessDate] = useState("");
  const [prefill, setPrefill] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [history, setHistory] = useState({ cuts: [], summary: null });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editReason, setEditReason] = useState("");

  useEffect(() => {
    const fetchCafeterias = async () => {
      try {
        const response = await axios.get(`${API}/cafeterias`);
        setCafeterias(response.data || []);
        if (!cafeteriaId && response.data?.length) {
          setCafeteriaId(user?.cafeteria_id || response.data[0].id);
        }
      } catch (error) {
        toast.error("No se pudieron cargar las sucursales");
      }
    };
    fetchCafeterias();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadPrefill = useCallback(async () => {
    if (!cafeteriaId) return;
    setLoading(true);
    try {
      const params = { cafeteria_id: cafeteriaId };
      if (businessDate) params.business_date = businessDate;
      const { data } = await axios.get(`${API}/cash-cuts/prefill`, { params });
      setPrefill(data);
      // El dia lo fija el servidor en hora del negocio (UTC-6): a las 20:30 de
      // CDMX el dia UTC ya es el siguiente, y el corte es del dia que cerro.
      if (!businessDate) setBusinessDate(data.business_date);
      setForm((current) => ({
        ...current,
        // Solo el fondo se propone, y viene del corte anterior. Proponer lo
        // contado seria sugerir un numero que nadie conto.
        fondo_inicial:
          current.fondo_inicial !== ""
            ? current.fondo_inicial
            : data.prefill?.fondo_inicial ?? "",
      }));
    } catch (error) {
      toast.error(error.response?.data?.detail || "No se pudo preparar el corte");
      setPrefill(null);
    } finally {
      setLoading(false);
    }
  }, [cafeteriaId, businessDate]);

  const loadHistory = useCallback(async () => {
    if (!cafeteriaId) return;
    try {
      const { data } = await axios.get(`${API}/cash-cuts`, {
        params: { cafeteria_id: cafeteriaId },
      });
      setHistory(data);
    } catch (error) {
      toast.error("No se pudo cargar el historial de cortes");
    }
  }, [cafeteriaId]);

  useEffect(() => {
    loadPrefill();
    loadHistory();
  }, [loadPrefill, loadHistory]);

  // La misma resta que hace el servidor. Esta aqui para que la cajera vea el
  // numero antes de guardar, no para decidirlo: lo que se guarda es lo que
  // devuelve el API.
  const fondo = toNumber(form.fondo_inicial);
  const contado = toNumber(form.efectivo_contado);
  const retiros = toNumber(form.retiros) ?? 0;
  const countedComplete = fondo !== null && contado !== null;
  const derived = countedComplete ? Number((contado + retiros - fondo).toFixed(2)) : null;
  const negative = derived !== null && derived < 0;

  const existing = prefill?.existing;
  const cardGross = prefill?.tarjeta?.gross ?? 0;
  const cardCharges = prefill?.tarjeta?.charges ?? 0;

  const handleSubmit = async () => {
    if (!countedComplete) {
      toast.error("Captura el fondo inicial y el efectivo contado");
      return;
    }
    setSaving(true);
    try {
      const { data } = await axios.post(`${API}/cash-cuts`, {
        cafeteria_id: cafeteriaId,
        business_date: businessDate || undefined,
        turno: form.turno,
        fondo_inicial: fondo,
        efectivo_contado: contado,
        retiros,
        tickets_efectivo: toNumber(form.tickets_efectivo),
        notas: form.notas || null,
      });
      toast.success(`Corte guardado: ${money(data.ventas_efectivo)} en efectivo`);
      setForm(EMPTY_FORM);
      loadPrefill();
      loadHistory();
    } catch (error) {
      // El backend contesta con el numero que esta mal y por que (efectivo
      // negativo, dedazo de ceros, turno ya capturado). Se enseña tal cual.
      toast.error(error.response?.data?.detail || "No se pudo guardar el corte");
    } finally {
      setSaving(false);
    }
  };

  const handleRevise = async () => {
    if (!editReason.trim()) {
      toast.error("Escribe por que se corrige: queda en el historial del corte");
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/cash-cuts/${editing.id}`, {
        reason: editReason,
        fondo_inicial: toNumber(editing.fondo_inicial),
        efectivo_contado: toNumber(editing.efectivo_contado),
        retiros: toNumber(editing.retiros) ?? 0,
        tickets_efectivo: toNumber(editing.tickets_efectivo),
      });
      toast.success("Corte corregido, con el monto anterior guardado");
      setEditing(null);
      setEditReason("");
      loadPrefill();
      loadHistory();
    } catch (error) {
      toast.error(error.response?.data?.detail || "No se pudo corregir el corte");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="cash-cut-container">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Corte de Caja</h1>
          <p className="text-[#A1A1AA] mt-1">
            El efectivo no llega por la API de Clip: sin este corte, la venta del día es un piso
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <Select value={cafeteriaId} onValueChange={setCafeteriaId} disabled={!isAdmin}>
            <SelectTrigger
              className="w-full sm:w-[220px] bg-[#161616] border-[#27272A] text-white"
              data-testid="cash-cut-branch-select"
            >
              <SelectValue placeholder="Sucursal" />
            </SelectTrigger>
            <SelectContent className="bg-[#161616] border-[#27272A]">
              {cafeterias.map((cafe) => (
                <SelectItem key={cafe.id} value={cafe.id} className="text-white hover:bg-[#27272A]">
                  {cafe.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="date"
            value={businessDate}
            onChange={(e) => setBusinessDate(e.target.value)}
            className="w-full sm:w-[170px] bg-[#161616] border-[#27272A] text-white"
            data-testid="cash-cut-date"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-[40vh]">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Captura */}
          <Card className="bg-[#161616] border-[#27272A] lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-white font-manrope flex items-center gap-2">
                <Banknote className="h-5 w-5 text-[#708238]" />
                {existing ? "Ya hay corte de este día" : "Contar el cajón"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {existing ? (
                <div className="space-y-3" data-testid="cash-cut-existing">
                  <p className="text-[#A1A1AA] text-sm">
                    Turno <strong className="text-white">{existing.turno}</strong>, capturado por{" "}
                    {existing.created_by_name || "—"}. Dos cortes del mismo turno duplicarían la
                    venta del día, así que este se corrige, no se vuelve a capturar.
                  </p>
                  <div className="text-4xl font-bold text-[#708238]" data-testid="cash-cut-existing-amount">
                    {money(existing.ventas_efectivo)}
                  </div>
                  <div className="text-sm text-[#A1A1AA]">
                    Contado {money(existing.efectivo_contado)} + retiros {money(existing.retiros)} −
                    fondo {money(existing.fondo_inicial)}
                  </div>
                  {canManage && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        setEditing({ ...existing });
                        setEditReason("");
                      }}
                      className="bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white"
                      data-testid="cash-cut-edit-button"
                    >
                      <Pencil className="h-4 w-4 mr-2" />
                      Corregir con motivo
                    </Button>
                  )}
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Turno</Label>
                      <Select
                        value={form.turno}
                        onValueChange={(value) => setForm({ ...form, turno: value })}
                      >
                        <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#161616] border-[#27272A]">
                          {(prefill?.turnos || ["completo"]).map((turno) => (
                            <SelectItem key={turno} value={turno} className="text-white hover:bg-[#27272A]">
                              {turno}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Fondo inicial *</Label>
                      <Input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        value={form.fondo_inicial}
                        onChange={(e) => setForm({ ...form, fondo_inicial: e.target.value })}
                        className="bg-[#0D0D0D] border-[#27272A] text-white"
                        data-testid="cash-cut-fondo"
                      />
                      <p className="text-xs text-[#71717A]">
                        {prefill?.prefill?.fondo_inicial_origen}
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Efectivo contado al cerrar *</Label>
                      <Input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        value={form.efectivo_contado}
                        onChange={(e) => setForm({ ...form, efectivo_contado: e.target.value })}
                        className="bg-[#0D0D0D] border-[#27272A] text-white"
                        data-testid="cash-cut-contado"
                      />
                      <p className="text-xs text-[#71717A]">Todo lo que hay en el cajón, con el fondo</p>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Retiros del día</Label>
                      <Input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        value={form.retiros}
                        onChange={(e) => setForm({ ...form, retiros: e.target.value })}
                        className="bg-[#0D0D0D] border-[#27272A] text-white"
                        data-testid="cash-cut-retiros"
                      />
                      <p className="text-xs text-[#71717A]">
                        Depósitos, pagos o traslados que salieron del cajón
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Cobros en efectivo (opcional)</Label>
                      <Input
                        type="number"
                        inputMode="numeric"
                        step="1"
                        value={form.tickets_efectivo}
                        onChange={(e) => setForm({ ...form, tickets_efectivo: e.target.value })}
                        className="bg-[#0D0D0D] border-[#27272A] text-white"
                        data-testid="cash-cut-tickets"
                      />
                      <p className="text-xs text-[#71717A]">Cuántos tickets se pagaron en efectivo</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Notas</Label>
                    <Textarea
                      value={form.notas}
                      onChange={(e) => setForm({ ...form, notas: e.target.value })}
                      className="bg-[#0D0D0D] border-[#27272A] text-white"
                      placeholder="Quién cerró, algo fuera de lo normal…"
                    />
                  </div>

                  {/* El numero derivado, grande. No es un campo: es una resta. */}
                  <div
                    className={`rounded-lg p-4 border ${
                      negative ? "border-[#7F1D1D] bg-[#7F1D1D]/10" : "border-[#27272A] bg-[#0D0D0D]"
                    }`}
                    data-testid="cash-cut-derived"
                  >
                    <div className="flex items-center gap-2 text-sm text-[#A1A1AA]">
                      <Calculator className="h-4 w-4" />
                      Venta en efectivo del turno (contado + retiros − fondo)
                    </div>
                    <div
                      className={`text-4xl font-bold mt-2 ${
                        negative ? "text-red-400" : "text-[#708238]"
                      }`}
                    >
                      {derived === null ? "—" : money(derived)}
                    </div>
                    {negative && (
                      <p className="text-sm text-red-400 mt-2 flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        Da negativo: falta registrar un retiro, o el fondo inicial no es el que se
                        dejó. Así no se guarda, porque restaría venta de un día que sí vendió.
                      </p>
                    )}
                  </div>

                  <Button
                    onClick={handleSubmit}
                    disabled={saving || !countedComplete || negative}
                    className="w-full bg-[#708238] hover:bg-[#5a692d] text-white"
                    data-testid="cash-cut-submit"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Guardar corte del {businessDate || "día"}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          {/* El dia, con las dos piezas separadas */}
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <CardTitle className="text-white font-manrope text-lg">El día en esta sucursal</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex items-center gap-2 text-sm text-[#A1A1AA]">
                  <CreditCard className="h-4 w-4" />
                  Tarjeta y vales (de Clip)
                </div>
                <div className="text-2xl font-bold text-white" data-testid="cash-cut-card-gross">
                  {money(cardGross)}
                </div>
                <div className="text-xs text-[#71717A]">{cardCharges} cobro(s) cargados</div>
              </div>

              <div>
                <div className="flex items-center gap-2 text-sm text-[#A1A1AA]">
                  <Banknote className="h-4 w-4" />
                  Efectivo del corte
                </div>
                <div className="text-2xl font-bold text-white" data-testid="cash-cut-cash-gross">
                  {existing ? money(existing.ventas_efectivo) : derived === null ? "sin corte" : money(derived)}
                </div>
              </div>

              <div className="pt-3 border-t border-[#27272A]">
                <div className="text-sm text-[#A1A1AA]">Total del día en esta sucursal</div>
                <div className="text-3xl font-bold text-[#708238]" data-testid="cash-cut-day-total">
                  {existing || derived !== null
                    ? money(cardGross + (existing ? existing.ventas_efectivo : derived))
                    : "—"}
                </div>
                {/* Por sucursal y nunca cruzado: Casa Dorelia y Le Pain Dore son
                    dos marcas con repartos distintos (BOS-101). */}
                <p className="text-xs text-[#71717A] mt-2">
                  {existing || derived !== null
                    ? "Ya incluye efectivo: es la venta del día de esta sucursal, no un piso."
                    : "Mientras no se guarde el corte, la cifra de tarjeta es un piso, no la venta."}
                </p>
              </div>

              {existing?.comparable === false && existing?.diferencia_motivo && (
                <p className="text-xs text-[#71717A]">
                  Sin diferencia contra el sistema: {existing.diferencia_motivo}.
                </p>
              )}
              {existing?.comparable && (
                <div className="text-sm">
                  <span className="text-[#A1A1AA]">Diferencia contra lo capturado en el app: </span>
                  <strong className={existing.diferencia < 0 ? "text-red-400" : "text-[#708238]"}>
                    {money(existing.diferencia)}
                  </strong>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Historial */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope text-lg">
            Cortes de esta sucursal
            {history.summary?.cuts ? (
              <Badge className="ml-3 bg-[#708238]/20 text-[#708238]">
                {history.summary.cuts} corte(s)
              </Badge>
            ) : null}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {history.cuts?.length ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-[#27272A]">
                    <TableHead className="text-[#A1A1AA]">Día</TableHead>
                    <TableHead className="text-[#A1A1AA]">Turno</TableHead>
                    <TableHead className="text-[#A1A1AA] text-right">Efectivo</TableHead>
                    <TableHead className="text-[#A1A1AA] text-right">Cobros</TableHead>
                    <TableHead className="text-[#A1A1AA]">Notas</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.cuts.map((cut) => (
                    <TableRow key={cut.id} className="border-[#27272A]">
                      <TableCell className="text-white">
                        {cut.business_date}
                        {cut.captured_late && (
                          <Badge className="ml-2 bg-[#27272A] text-[#A1A1AA] text-xs">
                            capturado tarde
                          </Badge>
                        )}
                        {cut.revisions?.length ? (
                          <Badge className="ml-2 bg-[#27272A] text-[#A1A1AA] text-xs">
                            corregido {cut.revisions.length}x
                          </Badge>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-[#A1A1AA]">{cut.turno}</TableCell>
                      <TableCell className="text-right text-white font-medium">
                        {money(cut.ventas_efectivo)}
                      </TableCell>
                      <TableCell className="text-right text-[#A1A1AA]">
                        {cut.tickets_efectivo ?? "—"}
                      </TableCell>
                      <TableCell className="text-[#71717A] text-sm">{cut.notas || "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-[#71717A] text-center py-8">
              No hay cortes capturados en esta sucursal. Cada día sin corte queda como piso.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Correccion con motivo obligatorio */}
      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="bg-[#161616] border-[#27272A]">
          <DialogHeader>
            <DialogTitle className="text-white font-manrope">Corregir el corte</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-4 mt-2">
              <p className="text-sm text-[#A1A1AA]">
                El monto anterior, quién corrige y el motivo quedan guardados en el corte. El día,
                la sucursal y el turno no se pueden cambiar: para eso se captura otro corte.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Fondo inicial</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editing.fondo_inicial}
                    onChange={(e) => setEditing({ ...editing, fondo_inicial: e.target.value })}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Efectivo contado</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editing.efectivo_contado}
                    onChange={(e) => setEditing({ ...editing, efectivo_contado: e.target.value })}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Retiros</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editing.retiros}
                    onChange={(e) => setEditing({ ...editing, retiros: e.target.value })}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Cobros en efectivo</Label>
                  <Input
                    type="number"
                    step="1"
                    value={editing.tickets_efectivo ?? ""}
                    onChange={(e) => setEditing({ ...editing, tickets_efectivo: e.target.value })}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Motivo de la corrección *</Label>
                <Textarea
                  value={editReason}
                  onChange={(e) => setEditReason(e.target.value)}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Ej: faltaba contar el sobre del depósito"
                  data-testid="cash-cut-edit-reason"
                />
              </div>
              <Button
                onClick={handleRevise}
                disabled={saving}
                className="w-full bg-[#708238] hover:bg-[#5a692d] text-white"
                data-testid="cash-cut-edit-submit"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Guardar corrección
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CashCut;
