# Panel Llamadas_Turnos — versión online

Dashboard público (con contraseña) del discador. **No contiene datos sensibles**:
el consolidado `data/publico.parquet` viene con el teléfono hasheado y sin
nombres ni datos de clientes. Lo genera `publicar.py` en la máquina donde están
los `.rsl`.

## Puesta en marcha (una sola vez)

1. Creá un repo **público** en GitHub, p. ej. `BBDD-2026/llamadas-turnos-web`, y
   dejá que esta carpeta sea ese repo:
   ```bash
   cd web
   git init -b main
   git remote add origin https://github.com/BBDD-2026/llamadas-turnos-web.git
   git add -A && git commit -m "panel online inicial"
   git push -u origin main
   ```
2. Entrá a <https://share.streamlit.io> → **New app** → elegí el repo, rama
   `main`, archivo `streamlit_app.py`.
3. En **Advanced settings → Secrets** pegá:
   ```toml
   password = "una-clave-para-el-equipo"
   ```
4. Deploy. La URL queda tipo `https://llamadas-turnos-web.streamlit.app`.

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
