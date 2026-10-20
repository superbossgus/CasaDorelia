/**
 * El selector de sucursal: dibuja combo solo cuando hay algo que elegir.
 *
 * El defecto que origina este modulo (BOS-154): las seis pantallas con filtro
 * de sucursal listaban **las dos** marcas a cualquier rol, y elegir la ajena
 * terminaba en el 403 que las 14 rutas con `cafeteria_id` empezaron a contestar
 * en BOS-152. Un combo que ofrece un camino muerto.
 *
 * La lista ya llega acotada: `GET /api/cafeterias` devuelve una sola sucursal a
 * `gerente`/`cajero` (`server.py`, misma regla que revalida el parametro). Lo
 * que falta es no dibujar un combo de una opcion, y eso se decide por **lo que
 * trae la lista**, no por el rol: el gate anterior era `isAdmin()`, que esconde
 * el combo a un `superadmin` que si puede pedir las dos.
 *
 * Son dos componentes porque el valor "ninguna sucursal en particular" significa
 * cosas distintas en cada sitio:
 *
 * - `BranchFilter` (encabezado de pantalla): `"all"` es un valor legitimo — es
 *   el que **no manda** el parametro y deja que el API acote solo. Con una sola
 *   sucursal no se dibuja nada y `"all"` ya es exactamente esa sucursal.
 * - `BranchField` (formulario): el valor tiene que ser una sucursal concreta,
 *   porque viaja en el POST. Con una sola, se fija sola y se muestra como
 *   rotulo: esconder el combo sin fijar el valor dejaria el formulario sin
 *   sucursal y el guardado contestaria "Completa todos los campos".
 */
import { useEffect } from "react";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export const ALL_BRANCHES = "all";

const TRIGGER_FILTER = "w-[180px] bg-[#161616] border-[#27272A] text-white";
const TRIGGER_FIELD = "bg-[#0D0D0D] border-[#27272A] text-white";
const ITEM = "text-white hover:bg-[#27272A]";

export const BranchFilter = ({
  branches,
  value,
  onChange,
  allLabel = "Todas",
  placeholder = "Filtrar por cafetería",
  className = TRIGGER_FILTER,
  testId,
}) => {
  if ((branches?.length || 0) <= 1) return null;

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={className} data-testid={testId}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="bg-[#161616] border-[#27272A]">
        <SelectItem value={ALL_BRANCHES} className={ITEM}>{allLabel}</SelectItem>
        {branches.map((branch) => (
          <SelectItem key={branch.id} value={branch.id} className={ITEM}>
            {branch.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export const BranchField = ({
  branches,
  value,
  onChange,
  label = "Cafetería",
  placeholder = "Seleccionar cafetería",
  className = TRIGGER_FIELD,
  testId,
}) => {
  const only = (branches?.length || 0) === 1 ? branches[0] : null;

  // Fijar el valor es parte de esconder el combo, no un extra: el formulario
  // manda `cafeteria_id` en el POST. Se vuelve a disparar cuando el formulario
  // se limpia tras guardar, que es justo cuando hace falta otra vez.
  useEffect(() => {
    if (only && value !== only.id) onChange(only.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [only?.id, value]);

  // Con una sola sucursal se muestra el nombre, no un combo. Hereda las clases
  // del trigger a proposito: asi ocupa el mismo lugar que ocupaba el combo y no
  // mueve la fila donde vive (en `CashCut` comparte renglon con la fecha).
  const control = only ? (
    <div
      className={`${className} flex items-center rounded-md px-3 py-2 text-sm`}
      data-testid={testId}
    >
      {only.name}
    </div>
  ) : (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={className} data-testid={testId}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="bg-[#161616] border-[#27272A]">
        {(branches || []).map((branch) => (
          <SelectItem key={branch.id} value={branch.id} className={ITEM}>
            {branch.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );

  // `label={null}` para los sitios donde el combo vive solo en una fila de
  // encabezado y no llevaba rotulo (`CashCut`).
  if (!label) return control;

  return (
    <div className="space-y-2">
      <Label className="text-[#EDEDED]">{label}</Label>
      {control}
    </div>
  );
};
