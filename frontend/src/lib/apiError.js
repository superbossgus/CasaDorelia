/**
 * El mensaje que el usuario alcanza a leer cuando el API dice no.
 *
 * Importa para el 403 por sucursal (BOS-152): el backend manda un `detail`
 * escrito para una persona ("Solo puedes consultar los datos de tu sucursal"),
 * y varias pantallas lo tiraban a la basura para mostrar un "Error al cargar X"
 * que no dice que paso ni que hacer. Peor: las que ademas esconden la pantalla
 * hasta tener datos quedaban girando el spinner para siempre (BOS-154).
 *
 * El 403 ya no deberia aparecer por el combo — la lista de sucursales viene
 * acotada — pero sigue alcanzable con un enlace guardado, un token que cambio
 * de sucursal, o cualquier llamada que mande `cafeteria_id` a mano. Que se lea.
 *
 * Solo se usa `detail`. El `message` de axios ("Request failed with status code
 * 500") no le dice nada a quien esta en la caja; para eso esta el `fallback`,
 * que cada pantalla escribe en su propio idioma.
 */
export const apiErrorMessage = (error, fallback) =>
  error?.response?.data?.detail || fallback;

/**
 * Lo mismo, para una peticion que pidio `responseType: "blob"`.
 *
 * Los reportes se descargan como blob, asi que el cuerpo del error **tambien**
 * llega como blob: `data.detail` es `undefined` y el 403 por sucursal se veia
 * como "Error al descargar reporte". Hay que abrir el blob para leerlo, y eso
 * es asincrono — de ahi que este separado en vez de dentro del de arriba.
 */
export const apiErrorMessageFromBlob = async (error, fallback) => {
  const body = error?.response?.data;
  if (!(body instanceof Blob)) return apiErrorMessage(error, fallback);
  try {
    return JSON.parse(await body.text())?.detail || fallback;
  } catch {
    // Un blob que no es el JSON de FastAPI (un PDF a medias, un 502 de HTML).
    return fallback;
  }
};
