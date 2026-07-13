# Despliegue — Agentes de Eventos (Backstage/Mitümi)

Carpeta autocontenida con lo estrictamente necesario para desplegar el sistema
de agentes. Generada desde el repo `Agentes_Eventos` (2026-07-13): sin guías,
tests, docs ni salidas de demo. La documentación completa vive en el repo
(`docs/endpoints_v5.md`).

## Puesta en marcha

1. **Python 3.10+** (probado con 3.12) y dependencias de cada servicio:
   ```bash
   for req in $(find . -name "requirements*.txt"); do pip install -r "$req"; done
   ```
2. **Credenciales**: copia `.env.example` a `.env` en esta carpeta y rellena
   `DATABASE_URL` (rol readonly de Neon), `GROQ_API_KEY` y, si aplican,
   `TELEGRAM_BOT_TOKEN` (Hermes) y `COMPOSIO_API_KEY` (Garum).
   Los `.env.example` de cada agente son solo referencia: **el `.env` de la
   raíz manda** (el script de arranque lo exporta para todos).
3. **Arrancar todo**:
   ```bash
   ./arrancar_todo.sh              # + --con-hermes para el bot de Telegram
   ./comprobar_salud.sh            # smoke test
   ```

## Mapa

| Puerto | Servicio |
|---|---|
| **5003** | **Gateway — única URL para el front** (`/agentes/...`, `/salud`, `/docs`) |
| 5001 | Lumen (chat) · 5002 Operis (briefings) · 8000 Vigil (concursos) · 8001 Jano (transporte) |
| 5004 | Backend de datos para agentes (Neon readonly) |
| — | Hermes (bot Telegram, `--con-hermes`) · Garum (por ciclos: `POST :5003/agentes/garum/ciclos`) |
