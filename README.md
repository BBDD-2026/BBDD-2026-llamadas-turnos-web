# Panel Llamadas_Turnos — versión online

Dashboard del discador, con login. **No guarda datos.** Cada quien sube los
`.rsl` del día desde la barra lateral: se parsean y **anonimizan en memoria**
(el teléfono se reemplaza por un hash de sesión) y se muestra el panel. Al
recargar la página o reiniciarse la app, los datos se van y hay que volver a
subirlos. Nada se escribe en disco ni se manda a ningún servidor.

## Puesta en marcha

Repo: **`BBDD-2026/BBDD-2026-llamadas-turnos-web`** (público). Esta carpeta es
ese repo git (rama `main`).

1. <https://share.streamlit.io> → **New app** → repo
   `BBDD-2026/BBDD-2026-llamadas-turnos-web`, rama `main`, archivo
   `streamlit_app.py`.
2. **Advanced settings → Secrets**:
   ```toml
   [passwords]
   enzo = "..."
   tmk  = "..."
   ```
   (o `password = "clave-unica"` para una sola clave).
3. Deploy. URL tipo `https://bbdd-2026-llamadas-turnos-web.streamlit.app`.

## Uso

Barra lateral → **Cargar .rsl** → subís los `.rsl` (o un `.zip` con varios) →
**Procesar**. El panel se arma con eso. "Sumar a lo ya cargado" acumula varias
subidas en la misma sesión; "Vaciar datos" limpia.

## Actualizar el CÓDIGO del panel

Sólo cuando cambia la lógica (no hay datos que actualizar). En la máquina del
proyecto:

```bash
python publicar.py --push
```

Sincroniza `streamlit_app.py`, `paneles.py`, `core.py`, `requirements.txt` y
`.streamlit/config.toml` a esta carpeta y hace commit + push. Community Cloud
redeploya solo.

## Archivos

| Archivo | Rol |
|---|---|
| `streamlit_app.py` | entrypoint de Community Cloud (login + carga en sesión + tableros) |
| `paneles.py` | render de KPIs y pestañas (copiado del proyecto, no editar acá) |
| `core.py` | parseo `.rsl` + `sanitizar()` (copiado del proyecto) |
| `requirements.txt` / `.streamlit/config.toml` | los genera `publicar.py` |

> Este repo **no contiene datos**. El `.gitignore` bloquea `*.rsl`, `*.db`,
> `*.parquet`, `.salt` y los `secrets.toml`.
