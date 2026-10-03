# Lead Management Automation

English: [README.md](README.md)

![CI](https://github.com/gabrielvalle-491/lead-management-automation/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Captura, clasifica y organiza leads (contactos comerciales) de forma automática.

Los leads llegan desde exportaciones CSV de plataformas de anuncios, el formulario de
contacto del sitio web y la casilla `sales@`. Esta herramienta los unifica en un solo
pipeline, elimina duplicados, detecta qué busca cada persona (con IA o reglas de palabras
clave), les asigna un puntaje de 0 a 100 con **motivos explicados**, asigna un
responsable, programa el seguimiento y genera un reporte de pipeline en Excel además de
un CSV listo para importar en un CRM.

## El problema de negocio

Una empresa pequeña invierte en anuncios de Facebook/LinkedIn y recibe leads en tres
lugares distintos. Nadie sabe a qué lead llamar primero, se contacta dos veces a la
misma persona, el spam y las postulaciones laborales se mezclan con clientes reales, y
los leads calientes se enfrían porque nadie hizo el seguimiento a tiempo.

## Cómo funciona

```
 CSV exports ─┐
 Web form  ───┼─► normalize ─► dedupe ─► intent (AI / rules) ─► score + reasons ─► route ─► SQLite
 Emails .eml ─┘                                                                       │
                                                       Excel pipeline report ◄────────┤
                                                       CRM import CSV        ◄────────┘
```

| Función | Detalle |
|---------|--------|
| **Captura** | CSV de Lead Ads, payloads JSON del sitio web, correos `.eml` (extrae empresa, teléfono y presupuesto del texto) y un **webhook en tiempo real** (`POST /lead`) para Zapier / Make / n8n o un formulario web |
| **Deduplicación** | Mismo email/teléfono en distintas fuentes = un solo lead (contador `times_seen` en lugar de filas duplicadas) |
| **Intención** | `sales`, `support`, `partnership`, `job_application`, `spam`. Usa Claude o Gemini cuando hay una API key configurada; de lo contrario, reglas de palabras clave (siempre funciona sin conexión) |
| **Puntaje** | Reglas transparentes: fuente, presupuesto, tamaño de la empresa, urgencia, pedido de precios/demo, email personal sin empresa, falta de teléfono. Cada punto queda registrado en `reasons` |
| **Asignación** | Hot / Warm / Cold con próxima acción + hora de seguimiento; soporte → `support@`, CV → `hr@`, spam → archivo; reparto rotativo (round-robin) entre vendedores |
| **Reporte** | Excel con **Summary**, **Pipeline** con colores por categoría y **Follow-ups due**; `crm_import.csv` (columnas al estilo HubSpot/Pipedrive) |

## Inicio rápido

```bash
pip install -r requirements.txt

python -m lead_automation.generate_samples samples   # demo leads in the 3 formats
python -m lead_automation samples --out output --no-llm
```

```
Leads received: 16 | new: 14 | duplicates merged: 2
Tiers: Hot: 6 | Warm: 4 | Cold: 1 | Disqualified: 3
Follow-ups due: 6
Report: output/lead_pipeline.xlsx
CRM import: output/crm_import.csv
```

Para usar la clasificación de intención con IA, configure una clave (opcional):

```bash
export ANTHROPIC_API_KEY=...   # Claude
# or
export GEMINI_API_KEY=...      # Google Gemini (free tier)
python -m lead_automation samples --out output
```

Captura en tiempo real:

```bash
python -m lead_automation.webhook --db output/leads.db --port 8000
curl -X POST localhost:8000/lead -H "Content-Type: application/json" \
     -d '{"name": "Ana Gil", "email": "ana@acme.com", "message": "Need a quote ASAP", "budget": 8000}'
# {"status": "created", "tier": "Hot", "score": 90, "owner": "Sales Rep A", "next_action": "Call within 1 hour"}
```

## Ejemplo de resultado (salida real de la demo)

| Puntaje | Categoría | Intención | Nombre | Empresa | Fuente | Responsable | Próxima acción | Motivo |
|---:|---|---|---|---|---|---|---|---|
| 100 | Hot | sales | Sofía Navarro | AgroAndes | ads_csv | Sales Rep A | Call within 1 hour | Budget ≥ 5,000 +25 · Company size 260 +15 · Urgent +15 · Asked for pricing +10 |
| 93 | Hot | sales | Lucas Ferreyra | Tienda Ferreyra | website | Sales Rep B | Call within 1 hour | Website +15 · Budget ≥ 1,000 +15 · Urgent +15 · Pricing +10 |
| 53 | Warm | sales | Valentina Paz | Inmobiliaria Paz | website | Sales Rep A | Send case study + book a call | Website +15 · Company size 18 +8 |
| 33 | Cold | partnership | Carla Vega | Estudio Vega | ads_csv | Sales Rep A | Add to nurture sequence | Partnership −10 |
| 0 | Disqualified | spam | Seo Master | – | email | archive | – | Spam |
| 0 | Disqualified | job_application | Pablo Candidato | – | email | hr@ | – | Routed to HR |

## Estructura del proyecto

```
lead_automation/
├── models.py            # Lead dataclass + normalization
├── sources.py           # CSV / JSON web form / .eml parsers
├── classify.py          # intent (LLM or keywords) + explainable scoring
├── pipeline.py          # dedupe, routing, follow-ups, SQLite storage
├── report.py            # Excel report + CRM CSV
├── webhook.py           # real-time capture endpoint (stdlib only)
└── generate_samples.py
tests/                   # 12 pytest tests incl. a live webhook test
```

## Pruebas

```bash
pytest -q
```

## Notas

- Todos los leads son datos de demostración sintéticos. No corresponden a personas ni empresas reales.
- Los pesos del puntaje están en `classify.py` y están pensados para ajustarse junto con el equipo de ventas.
- Desarrollado con Python y [Claude Code](https://claude.com/claude-code) como asistente de programación con IA.

## Cómo se lo entregaría a un cliente

Si me contrata para esto, yo haría lo siguiente:

- **Acordar primero los datos de entrada:** sus exportaciones CSV de Lead Ads (con cualquiera de los nombres de columna de `sources.py`, por ejemplo `full_name` / `nombre`), los envíos del formulario web en JSON (o enviados en vivo al webhook) y los correos a `sales@` guardados como archivos `.eml`.
- **Dejar una carpeta y un solo comando:** se colocan los archivos de la semana en la carpeta de entrada (`*.csv`, `web_forms/`, `emails/`) y se ejecuta `python -m lead_automation <folder> --out output`, o bien lo programo como tarea del Programador de tareas de Windows / cron todos los lunes por la mañana.
- **Ajustar las reglas con su equipo de ventas:** los pesos del puntaje, las palabras clave, los nombres de los vendedores y los tiempos de seguimiento están en `classify.py` y `pipeline.py`, por lo que se pueden modificar sin tocar el resto.
- **Entregar los resultados que realmente se usan:** `lead_pipeline.xlsx` (Summary, Pipeline, Follow-ups due) para el equipo y `crm_import.csv` para HubSpot / Pipedrive.
- **Hacer visibles los problemas:** cada ejecución muestra un resumen (leads recibidos, duplicados unificados, categorías, seguimientos pendientes); el comando termina con un código de salida distinto de cero (y un traceback de Python) ante argumentos incorrectos o un archivo que no puede procesar, como un JSON dañado, de modo que la tarea programada figure como fallida; una carpeta vacía o equivocada se detecta como `Leads received: 0`; el webhook responde `400` ante un JSON inválido y `422` cuando un lead no tiene email ni teléfono.
- **Mantenerlo funcionando sin conexión:** sin una API key (o si falla la llamada a la IA) la intención se determina con las reglas de palabras clave, así que la ejecución semanal nunca depende de un servicio externo.
- **Documentarlo y probarlo:** una guía breve de uso para su equipo más las pruebas automatizadas (`pytest -q`), para verificar los cambios en las reglas antes de ponerlos en uso.

## Autor

**Gabriel Valle** — Automatización de datos e IA (Excel, PDF, flujos de trabajo) · Villa Mercedes, Argentina · Remoto
