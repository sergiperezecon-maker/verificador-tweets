import streamlit as st
import anthropic
import requests
import json
import re
import time
from duckduckgo_search import DDGS
from datetime import date

st.set_page_config(
    page_title="Verificador de Tweets",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0d0d0d; color: #e8e8e8; }
    .stTextArea textarea {
        background-color: #1a1a1a !important;
        color: #e8e8e8 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 6px !important;
        font-size: 0.95rem !important;
    }
    .stTextInput input {
        background-color: #1a1a1a !important;
        color: #e8e8e8 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 6px !important;
    }
    .stButton > button {
        background-color: #1a1a1a !important;
        color: #e8e8e8 !important;
        border: 1px solid #3a3a3a !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover { background-color: #252525 !important; border-color: #555 !important; }
    .stExpander { background-color: #111 !important; border: 1px solid #222 !important; border-radius: 6px !important; }
    .verdict-card { padding: 1.2rem 1.5rem; border-radius: 8px; margin-bottom: 1rem; }
    .response-card {
        background-color: #111;
        border: 1px solid #222;
        border-radius: 8px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        height: 100%;
    }
    .tag {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 3px;
        display: inline-block;
        margin-bottom: 0.6rem;
    }
    .divider { border-top: 1px solid #1e1e1e; margin: 1.5rem 0; }
    h1 { font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.5px !important; }
    h3 { font-size: 1rem !important; font-weight: 600 !important; color: #888 !important; text-transform: uppercase !important; letter-spacing: 1px !important; }
    [data-testid="stCodeBlock"] pre { background-color: #111 !important; border: 1px solid #222 !important; }
    .source-link { color: #555; font-size: 0.8rem; word-break: break-all; }
    .model-badge-claude { background:#1a1a2a; border:1px solid #333; color:#888aff; padding:3px 10px; border-radius:4px; font-size:0.75rem; font-weight:700; letter-spacing:1px; }
    .model-badge-gemini { background:#1a2a1a; border:1px solid #333; color:#44ff88; padding:3px 10px; border-radius:4px; font-size:0.75rem; font-weight:700; letter-spacing:1px; }
</style>
""", unsafe_allow_html=True)


def search_web(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5, region="es-es"))
        if not results:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No se encontraron resultados."
        parts = []
        for r in results:
            parts.append(
                f"Título: {r.get('title', '')}\n"
                f"Resumen: {r.get('body', '')}\n"
                f"URL: {r.get('href', '')}"
            )
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"Error en búsqueda: {e}"


def extract_json(text: str) -> dict:
    if not text:
        return _error_json("Respuesta vacía.")
    try:
        return json.loads(text)
    except Exception:
        pass
    code_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return _error_json("No se pudo leer la respuesta. Inténtalo de nuevo.")


def _error_json(msg: str) -> dict:
    return {
        "verificacion": {
            "veredicto": "ERROR",
            "explicacion": msg,
            "dato_correcto": "",
            "fuentes": []
        },
        "respuestas": []
    }


def build_system_prompt(angulo: str) -> str:
    today = date.today().strftime("%d de %B de %Y")
    angulo_line = f"\n\nÁNGULO DEL USUARIO: {angulo.strip()}\nTen muy en cuenta este ángulo al generar las 3 respuestas. Las respuestas deben argumentar desde esta posición, usando los datos verificados como munición." if angulo.strip() else ""

    return f"""Eres un verificador de hechos experto en economía, finanzas y política española y global.
También eres estratega de contenido para el nicho "Aesthetic Financiero / Despertar Económico" en Instagram y TikTok.

FECHA ACTUAL: {today}. Estamos en 2026. Usa SIEMPRE esta fecha como referencia.

CONTEXTO ACTUAL (abril 2026):
- Inflación en España: 3,4% en marzo 2026.
- Vivienda en España: +14,7% interanual. Solo el 36,7% de menores de 35 tiene piso en propiedad.
- Renta mediana de jóvenes (<35 años) cayó un 17%.
- SMI España 2026: 1.221€/mes.
- Aranceles Trump: 34% a China, 20% a la UE.
- Deuda pública mundial: 117% del PIB global (FMI).
- Guerra comercial EE.UU.-China activa.{angulo_line}

VOZ (@contraelrelato): directa, con autoridad, el antagonista es el sistema nunca una persona.
Máximo 4 líneas por respuesta. Negritas para el dato más fuerte.

FORMATO DE SALIDA — devuelve ÚNICAMENTE este JSON, sin texto extra:
{{
  "verificacion": {{
    "veredicto": "VERDADERO | FALSO | PARCIALMENTE VERDADERO",
    "explicacion": "Explicación clara y concisa.",
    "dato_correcto": "El dato exacto si lo hay.",
    "fuentes": ["url1", "url2"]
  }},
  "respuestas": [
    {{"tipo": "Amplificación", "descripcion": "Confirma y añade el dato más impactante.", "texto": "..."}},
    {{"tipo": "Corrección con autoridad", "descripcion": "Corrige o matiza como experto.", "texto": "..."}},
    {{"tipo": "Máximo alcance", "descripcion": "Diseñada para shares y guardados.", "texto": "..."}}
  ]
}}"""


def verify_claude(tweet: str, api_key: str, angulo: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    tools = [{
        "name": "buscar_informacion",
        "description": "Busca en internet para verificar datos y afirmaciones del tweet.",
        "input_schema": {
            "type": "object",
            "properties": {"consulta": {"type": "string", "description": "Consulta de búsqueda."}},
            "required": ["consulta"]
        }
    }]

    angulo_line = f"\n\nÁngulo: {angulo.strip()}" if angulo.strip() else ""
    messages = [{"role": "user", "content": f'Verifica este tweet y genera 3 respuestas:{angulo_line}\n\nTweet:\n\n"{tweet}"'}]

    for _ in range(8):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=build_system_prompt(angulo),
            tools=tools,
            messages=messages
        )
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": search_web(block.input["consulta"])
                    })
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            full_text = "".join(b.text for b in response.content if b.type == "text")
            if full_text:
                return extract_json(full_text)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": "Devuelve ahora el JSON final."})
        else:
            break

    return _error_json("No se pudo obtener respuesta.")


def verify_groq(tweet: str, api_key: str, angulo: str) -> dict:
    context1 = search_web(tweet[:200])
    context2 = search_web(tweet[:100] + " datos España 2026 estadísticas")
    context3 = search_web(tweet[:100] + " fuentes INE Banco de España eurostat")

    angulo_line = f"\n\nÁNGULO DEL USUARIO: {angulo.strip()}\nUsa los datos como munición para este ángulo." if angulo.strip() else ""

    prompt = f"""DATOS DE INTERNET (tres búsquedas):

BÚSQUEDA 1:
{context1}

BÚSQUEDA 2:
{context2}

BÚSQUEDA 3 (fuentes oficiales):
{context3}

NORMAS: Solo usa datos que aparezcan arriba. No inventes cifras. Si no está confirmado, di "dato no verificado".
{angulo_line}

Tweet a verificar: "{tweet}"

Devuelve ÚNICAMENTE el JSON pedido en el system prompt, sin texto extra."""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": [
            {"role": "system", "content": build_system_prompt(angulo)},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.2
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.ok:
            text = resp.json()["choices"][0]["message"]["content"]
            return extract_json(text)
        err = resp.json().get("error", {}).get("message", resp.status_code)
        return _error_json(f"Error Groq: {err}")
    except Exception as e:
        return _error_json(f"Error de conexión con Groq: {e}")


def verify_gemini(tweet: str, api_key: str, angulo: str) -> dict:
    model = get_gemini_model(api_key)
    if not model:
        return _error_json("No se pudo conectar con Gemini. Revisa tu API Key.")

    # 3 búsquedas específicas para máxima precisión
    context = search_web(tweet[:200])
    context2 = search_web(tweet[:100] + " datos España 2026 estadísticas")
    context3 = search_web(tweet[:100] + " fuentes INE Banco de España eurostat")

    angulo_line = f"\n\nÁNGULO DEL USUARIO: {angulo.strip()}\nUsa los datos verificados como munición para este ángulo." if angulo.strip() else ""

    prompt = f"""{build_system_prompt(angulo)}

DATOS DE INTERNET (tres búsquedas independientes — úsalos para verificar con precisión):

BÚSQUEDA 1:
{context}

BÚSQUEDA 2:
{context2}

BÚSQUEDA 3 (fuentes oficiales):
{context3}

NORMAS DE PRECISIÓN — MUY IMPORTANTE:
- Solo afirma datos que aparezcan en los resultados de búsqueda arriba.
- Si un dato no está confirmado, indícalo con "dato no verificado".
- Nunca inventes cifras, fechas ni porcentajes.
- Si los resultados son contradictorios, usa el dato más conservador.
- Las fuentes del JSON deben ser URLs reales de los resultados anteriores.
{angulo_line}

Tweet a verificar: "{tweet}"

Devuelve ÚNICAMENTE el JSON pedido, sin texto extra."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(3):
        resp = requests.post(url, json=payload, timeout=30)
        if resp.ok:
            break
        if resp.status_code == 503 and attempt < 2:
            time.sleep(3)
            continue

    if not resp.ok:
        err = resp.json().get("error", {}).get("message", resp.status_code) if resp.headers.get("content-type","").startswith("application/json") else resp.status_code
        return _error_json(f"Error Gemini: {err}")

    try:
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return extract_json(text)
    except Exception:
        return _error_json("No se pudo leer la respuesta de Gemini.")


# ─── UI ────────────────────────────────────────────────────────────────────────

st.markdown("# ⚡ Verificador de Tweets")
st.markdown("<p style='color:#555; margin-top:-0.5rem;'>Aesthetic Financiero · Verifica datos · Genera respuestas</p>", unsafe_allow_html=True)
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Model selector + API key
st.markdown("### Motor de IA")
modelo = st.radio("", ["Groq — Llama 3.1 (gratis)", "Claude (de pago, más preciso)"], horizontal=True, label_visibility="collapsed")

placeholders = {
    "Groq — Llama 3.1 (gratis)": ("console.groq.com → Create API Key (gratis)", "gsk_..."),
    "Claude (de pago, más preciso)": ("console.anthropic.com → API Keys", "sk-ant-api03-..."),
}
hint, placeholder = placeholders[modelo]

with st.expander("🔑 API Key", expanded=not st.session_state.get("api_key", "")):
    st.markdown(f"<p style='color:#666; font-size:0.82rem;'>{hint}</p>", unsafe_allow_html=True)
    key_input = st.text_input("", type="password", value=st.session_state.get("api_key", ""), placeholder=placeholder, label_visibility="collapsed")
    if key_input:
        st.session_state["api_key"] = key_input
        st.success("API Key guardada ✓")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Tweet input
st.markdown("### Tweet a verificar")
tweet_input = st.text_area("", height=160, placeholder="Pega aquí el tweet...", label_visibility="collapsed")

st.markdown("### ¿Qué quieres argumentar?")
st.markdown("<p style='color:#444; font-size:0.82rem; margin-top:-0.8rem; margin-bottom:0.6rem;'>Opcional — dile a la IA tu posición. Ej: \"Quiero demostrar que subir el SMI no reduce la inflación\"</p>", unsafe_allow_html=True)
angulo_input = st.text_area("", height=80, placeholder="Quiero demostrar que... / Quiero ir contra... / Mi argumento es que...", label_visibility="collapsed", key="angulo")

run = st.button("⚡  Verificar y generar respuestas", use_container_width=True)
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Process
if run:
    if not st.session_state.get("api_key"):
        st.error("Añade tu API Key arriba.")
    elif not tweet_input.strip():
        st.error("Pega un tweet para verificar.")
    else:
        with st.spinner("Buscando datos y analizando..."):
            if "Claude" in modelo:
                result = verify_claude(tweet_input.strip(), st.session_state["api_key"], angulo_input.strip())
            else:
                result = verify_groq(tweet_input.strip(), st.session_state["api_key"], angulo_input.strip())

        verif = result.get("verificacion", {})
        veredicto = verif.get("veredicto", "ERROR")

        palette = {
            "VERDADERO":               ("#00e676", "#0a1f14", "#0d3022"),
            "FALSO":                   ("#ff5252", "#1f0a0a", "#300d0d"),
            "PARCIALMENTE VERDADERO":  ("#ffab40", "#1f1500", "#30200a"),
            "ERROR":                   ("#888888", "#111111", "#1a1a1a"),
        }
        text_color, bg_color, border_color = palette.get(veredicto, palette["ERROR"])

        st.markdown("### Verificación")
        st.markdown(f"""
        <div class="verdict-card" style="background:{bg_color}; border:1px solid {border_color};">
            <span style="color:{text_color}; font-weight:700; font-size:0.8rem; letter-spacing:1.5px; text-transform:uppercase;">{veredicto}</span>
            <p style="margin:0.6rem 0 0 0; color:#ccc; font-size:0.95rem; line-height:1.6;">{verif.get('explicacion', '')}</p>
            {"<p style='margin:0.8rem 0 0 0; color:#aaa; font-size:0.9rem;'>💡 <strong>Dato clave:</strong> " + verif.get('dato_correcto','') + "</p>" if verif.get('dato_correcto') else ""}
        </div>
        """, unsafe_allow_html=True)

        fuentes = [f for f in verif.get("fuentes", []) if f]
        if fuentes:
            with st.expander("🔗 Fuentes consultadas"):
                for url in fuentes:
                    st.markdown(f"<span class='source-link'>→ {url}</span>", unsafe_allow_html=True)

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.markdown("### Respuestas listas para publicar")
        respuestas = result.get("respuestas", [])

        if respuestas:
            cols = st.columns(len(respuestas), gap="medium")
            tag_colors = ["#1a3a2a", "#2a1a1a", "#1a1a3a"]
            tag_text   = ["#00e676", "#ff5252", "#448aff"]
            for i, (resp, col) in enumerate(zip(respuestas, cols)):
                with col:
                    tc = tag_text[i % len(tag_text)]
                    bc = tag_colors[i % len(tag_colors)]
                    st.markdown(f"""
                    <div class="response-card">
                        <span class="tag" style="background:{bc}; color:{tc};">{resp.get('tipo','')}</span>
                        <p style="color:#555; font-size:0.75rem; margin:0 0 0.8rem 0;">{resp.get('descripcion','')}</p>
                        <p style="color:#ddd; font-size:0.92rem; line-height:1.65; margin:0;">{resp.get('texto','').replace(chr(10),'<br>')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.code(resp.get("texto", ""), language=None)
        else:
            st.warning("No se generaron respuestas. Inténtalo de nuevo.")
