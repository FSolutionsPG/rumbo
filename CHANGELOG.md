# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado según [SemVer](https://semver.org/lang/es/). Las versiones `-fs.N` son de este fork;
la base es la del autor (`danidm98/rumbo`).

## [Sin publicar]

## [1.1.1-fs.1] - 2026-10-11

### Añadido
- **Traspaso entre fondos o planes** (#7): hereda el coste y la fecha de cada lote, no realiza plusvalía y no cuenta como dinero tuyo en la TIR de la cartera.
- **Productos cerrados** (#7): con 0 unidades y valor 0, o marcados «Archivado», salen del panel; «Ver cerrados» los enseña. Siguen contando en el histórico, la TIR y Rendimiento.
- **Intereses de cuentas remuneradas** (#1): movimiento «Interés» en cuentas; total y por año en Patrimonio, en la ficha de la cuenta y en El mes. No cambia el saldo (ya va dentro del banco).
- **Zoom temporal** (#3): 1M, 3M, 6M, YTD, 1A y Todo también en Productos y Rendimiento, compartido y recordado; el comparador vuelve a base 100 al inicio del rango.
- Enlace «Todas (x,xxxxxx)» en ventas y traspasos, con la precisión completa.
- Instrucciones para agentes (`AGENTS.md`), permisos que niegan leer `.env` y 70 tests con `unittest`.

### Corregido
- **Fuga de datos** (#8): cualquier web abierta podía leer la cartera en `/datos.js` o mandar formularios a la app. Ahora se rechazan las peticiones de otras webs y de hosts ajenos (403).
- `0.123` o `0.005` unidades se leían como 123 o 5; al importar sin comas, `1.250` era 1250. Ahora el punto es decimal cuando el fichero no lleva comas, con aviso en la vista previa.
- No se podía vender el total de unidades con más de 4 decimales.

### Cambiado
- `.gitattributes`: LF por defecto en todo el repo; los `.bat` siguen en CRLF.

---

## [1.1.1] - 2026-09-30

Versión del autor de la que parte el fork (`a024a09`).
