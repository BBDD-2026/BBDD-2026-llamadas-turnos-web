# Panel Llamadas_Turnos — versión online

Dashboard público (con contraseña) del discador. **No contiene datos sensibles**:
el consolidado `data/publico.parquet` viene con el teléfono hasheado y sin
nombres ni datos de clientes. Lo genera `publicar.py` en la máquina donde están
los `.rsl`.

## Puesta en marcha

Repo: **`BBDD-2026/BBDD-2026-llamadas-turnos-web`** (público). Esta carpeta ya es
ese repo git (rama `main`, primer push hecho).

Falta conectar el deploy:

1. Entrá a <https://share.streamlit.io> → **New app** → repo
   `BBDD-2026/BBDD-2026-llamadas-turnos-web`, rama `main`, archivo
   `streamlit_app.py`.
2. En **Advanced settings → Secrets** pegá:
   ```toml
   password = "una-clave-para-el-equipo"
   ```
3. Deploy. La URL queda tipo `https://bbdd-2026-llamadas-turnos-web.streamlit.app`.

## Actualizar los datos

En la máquina de los `.rsl`, después de cargar la jornada del día:

```bash
python publicar.py --push
```

Regenera `web/data/publico.parquet` (sanitizado), hace commit y push. Streamlit
Community Cloud redeploya solo en ~1 minuto.

- `python publicar.py --dias 60` → publica sólo las últimas 60 jornadas (para
  que el parquet no crezca de más).
- Sin `--push` sólo regenera el archivo local (`web/data/publico.parquet`), que
  también podés subir a mano desde la barra lateral del panel (dura hasta el
  próximo reinicio de la instancia).

## Archivos

| Archivo | Rol |
|---|---|
| `streamlit_app.py` | entrypoint de Community Cloud (login + filtros + tableros) |
| `paneles.py` | render de KPIs y pestañas (copiado del proyecto, no editar acá) |
| `data/publico.parquet` | consolidado sanitizado (lo pisa `publicar.py`) |
| `requirements.txt` / `.streamlit/config.toml` | los genera `publicar.py` |

> Nunca pongas `.rsl`, `llamadas.db` ni `data/.salt` en este repo. El
> `.gitignore` ya los bloquea.
