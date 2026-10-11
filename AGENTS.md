# AGENTS.md — Rumbo (fork de FSolutionsPG)

> Fichero único de instrucciones del repo. `CLAUDE.md` y `GEMINI.md` contienen solo `@AGENTS.md`.
> Las reglas comunes están en `C:\Dev\` (`AGENTS.md`, `MEMORIA.md`); este fichero añade lo propio y manda en lo suyo.

## Qué es

Panel local de patrimonio neto (fondos, ETF, acciones, cripto, cuentas…) de **Dani Dominguez Quant**
(`danidm98/rumbo`, MIT). Este es un fork para uso propio de Fran: arregla fallos y añade lo que pide
en las incidencias del autor. El autor prepara una 2.0: **los cambios se mantienen pequeños y en
ramas separadas**, para poder traer su versión con `git fetch upstream` y proponerle los arreglos generales.

No pasó por `/nuevo-proyecto`: no nace de la plantilla, es código ajeno ya en marcha (decisión del 11/10/2026).

## Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Runtime | Python | 3.12 en `.python-version` (`requires-python >=3.10`) |
| Servidor | Flask, solo en `127.0.0.1` | `>=3.0` |
| Excel | openpyxl | `>=3.1` |
| Front | HTML, CSS y JS sin librerías; gráficos SVG propios (`app/web/graficos.js`) | — |
| Tests | `unittest` de la biblioteca estándar (sin dependencias nuevas) | — |

## Comandos

```bash
uv run python -m app                                  # arranca y abre el navegador (puerto 8765, o el siguiente libre)
uv run python -m unittest discover -s tests -v        # tests
node --check app/web/app.js                           # sintaxis JS (uno por fichero)
```

Variables para pruebas (no tocan `mis_datos/`):
`PATRIMONIO_DATOS=<carpeta>` (otra carpeta de datos), `PATRIMONIO_PUERTO=<n>`, `PATRIMONIO_NO_ABRIR=1` (no abre el navegador).

Traer la versión del autor: `git fetch upstream` y fusionar `upstream/main` en una rama `chore/…`.

## Estructura

```
app/servidor.py   rutas Flask; guarda de peticiones ajenas
app/motor.py      cálculos: series diarias, FIFO, TIR, rendimiento, comparador (construir())
app/almacen.py    validación y guardado de la cartera, con copias automáticas
app/importar.py   importadores: MyInvestor, plantilla, texto de la IA
app/exportar.py   el panel como HTML estático (incrusta app.js y graficos.js; editor.js no)
app/web/          index.html, app.js (panel), graficos.js, editor.js (Mis datos)
demo/cartera.json cartera de ejemplo (la real del autor)
tests/            unittest
mis_datos/        DATOS REALES del usuario: ignorado por git
```

## Trampas conocidas

- `motor.construir()` depende de `motor.hoy()` y de la caché de precios en `<datos>/cache`: en tests, fija `hoy` y usa `descargar=False` con una caché temporal.
- `motor.num_es` interpreta `1.234` como mil (formato español): cualquier cambio se prueba con las dos formas.
- `exportar.py` recorta `index.html` con expresiones regulares (`#tab-datos`, `#tab-ayuda`, el cargador de scripts): si cambias esas zonas, exporta y abre el HTML.
- Todo campo nuevo con euros va en `exportar.CAMPOS_DINERO`; si no, se filtra en «Ocultar importes».
- El filtro «Solo largo plazo» (`estado.ocultos`) recalcula TIR y KPIs en el navegador: no lo uses para esconder cosas que deban seguir contando.

## Reglas para los agentes

- **Nunca** se toca ni se lee `mis_datos/` (datos financieros reales). Para probar: `PATRIMONIO_DATOS` en el scratchpad.
- `demo/cartera.json` no se modifica: es del autor.
- Al remoto `upstream` no se empuja nunca; `git push` y los PR los hace Fran.
- Ramas `fix/…` o `feat/…` desde `integracion`; a `main` solo llega lo que fusiona Fran.
- Cada cambio con su test (`tests/test_<tema>.py`). Antes de darlo por bueno, sabotéalo: quita el arreglo y el test tiene que fallar.
- Cambios en `app/web/`: mirar la app en un navegador real (390 y 1440 px), no basta con `node --check`.
- Los tests que fallen se reportan tal cual.

## Verificación (terminado =)

1. `python -m unittest discover -s tests -v` → código 0.
2. `node --check` de cada `app/web/*.js` → código 0.
3. Si toca `motor.py`: los totales de la cartera de ejemplo (valor, aportado, plusvalía, TIR) no cambian frente a `integracion`, salvo los campos nuevos.
4. Si toca `app/web/`: captura en navegador revisada y export estático abierto (con y sin importes).

## Contexto y decisiones

- **Traspaso** entre fondos o planes: hereda el coste y la fecha de cada lote (régimen español), no realiza plusvalía y no es flujo de dinero para la TIR de cartera (Fran, 11/10/2026).
- **Productos cerrados**: se ocultan solos con 0 unidades y valor 0, o con «Archivado»; siguen contando en el histórico, la TIR y Rendimiento (Fran, 11/10/2026).
- `app/VERSION` lleva sufijo `-fs.N`: `/api/version` lo compara por sus números con la del autor y avisa cuando él publica una nueva.
