import streamlit as st
import requests
import json
import re
import time
from duckduckgo_search import DDGS
from datetime import date
import os

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
    .stButton > button:hover {
        background-color: #252525 !important;
        border-color: #555 !important;
    }
    .stExpander {
        background-color: #111 !important;
        border: 1px solid #222 !important;
        border-radius: 6px !important;
    }
    .verdict-card {
        padding: 1.2rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
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
    .stCode { background-color: #111 !important; }
    [data-testid="stCodeBlock"] { background-color: #111 !important; }
    [data-testid="stCodeBlock"] pre { background-color: #111 !important; border: 1px solid #222 !important; }
    .source-link { color: #555; font-size: 0.8rem; word-break: break-all; }
    .counter-free    { color: #888; font-size: 0.8rem; }
    .counter-warning { color: #ffaa00; font-size: 0.8rem; }
    .counter-empty   { color: #ff5252; font-size: 0.8rem; }
    .premium-badge {
        background: linear-gradient(90deg, #1a1400, #2a2000);
        border: 1px solid #5a4500;
        color: #ffcc44;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)

FREE_LIMIT = 3


def init_session():
    if "query_count" not in st.session_state:
        st.session_state.query_count = 0
        st.session_state.query_date = date.today()
        st.session_state.is_premium = False
    if st.session_state.query_date != date.today():
        st.session_state.query_count = 0
        st.session_state.query_date = date.today()


def get_api_key() -> str:
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")


def get_premium_codes() -> list:
    try:
        raw = st.secrets.get("PREMIUM_CODES", "")
        return [c.strip().upper() for c in raw.split(",") if c.strip()]
    except Exception:
        return []


def queries_remaining() -> int:
    if st.session_state.is_premium:
        return 9999
    return max(0, FREE_LIMIT - st.session_state.query_count)


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


@st.cache_data(ttl=3600)
def get_working_model(api_key: str) -> str:
    list_url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    try:
        r = requests.get(list_url, timeout=10)
        if r.ok:
            models = r.json().get("models", [])
            for m in models:
                supported = m.get("supportedGenerationMethods", [])
                name = m.get("name", "")
                if "generateContent" in supported and "flash" in name.lower():
                    return name.replace("models/", "")
            for m in models:
                supported = m.get("supportedGenerationMethods", [])
                name = m.get("name", "")
                if "generateContent" in supported:
                    return name.replace("models/", "")
    except Exception:
        pass
    return None


def verify_tweet(tweet: str, api_key: str, angulo: str = "") -> dict:
    model = get_working_model(api_key)
    if not model:
        return _error_json("No se pudo conectar con la IA. Inténtalo de nuevo.")

    today = date.today().strftime("%d de %B de %Y")

    angulo_line = ""
    if angulo.strip():
        angulo_line = f"\n\nÁNGULO DEL USUARIO: {angulo.strip()}\nTen muy en cuenta este ángulo al generar las 3 respuestas. Las respuestas deben argumentar desde esta posición, usando los datos verificados como munición."

    system_prompt = f"""Eres un verificador de hechos experto en economía, finanzas y política española y global.
También eres estratega de contenido para el nicho "Aesthetic Financiero / Despertar Económico" en Instagram y TikTok.

FECHA ACTUAL: {today}. Estamos en 2026. Usa SIEMPRE esta fecha como referencia.

CONTEXTO ACTUAL (abril 2026) que debes tener en cuenta al verificar:
- Guerra activa entre EE.UU./Israel e Irán desde febrero 2026. Estrecho de Ormuz afectado.
- El FMI revisó a la baja el crecimiento mundial (3,1%) y subió la inflación global al 4,4%.
- Inflación en España: 3,4% en marzo 2026 (subida desde 2,3% en febrero).
- Vivienda en España: +14,7% interanual. Solo el 36,7% de menores de 35 tiene piso en propiedad.
- Renta mediana de jóvenes (<35 años) en España cayó un 17%.
- Aranceles Trump: 34% a China, 20% a la UE. Europa respondió con represalias.
- Deuda pública mundial: 117% del PIB global según el FMI.
- SMI España 2026: 1.221€/mes.

VOZ Y FILOSOFÍA DE LA CUENTA (@contraelrelato):
El mensaje central es: el mundo está cambiando a una velocidad que la mayoría no percibe, y hay que prepararse.
El tono es el de alguien que ha visto los datos reales y los comparte con urgencia y autoridad.
NO es una cuenta política. El antagonista es el sistema, nunca una persona o partido concreto.

REGLAS DE VOZ:
- Siempre conecta el dato con el impacto en la vida real del lector
- Termina con una frase que haga pensar, no con una solución fácil
- Transforma datos técnicos en realidades cotidianas
- Máximo 4 líneas por respuesta. Cada línea debe poder sostenerse sola.
- Usa **negritas** para el dato más fuerte.
- Sin emojis salvo al principio si refuerza el impacto.

PROCESO:
1. Identifica las afirmaciones verificables del tweet.
2. Busca datos actuales para contrastarlas.
3. Si el tweet usa datos de 2024 o anteriores, indícalo en el veredicto.
4. Devuelve el resultado en el JSON exacto indicado abajo.

FORMATO DE SALIDA — devuelve ÚNICAMENTE este JSON, sin texto extra:
{{
  "verificacion": {{
    "veredicto": "VERDADERO | FALSO | PARCIALMENTE VERDADERO",
    "explicacion": "Explicación clara y concisa del veredicto.",
    "dato_correcto": "El dato exacto o matiz importante si lo hay.",
    "fuentes": ["url1", "url2"]
  }},
  "respuestas": [
    {{
      "tipo": "Amplificación",
      "descripcion": "Confirma y añade el dato más impactante.",
      "texto": "..."
    }},
    {{
      "tipo": "Corrección con autoridad",
      "descripcion": "Corrige o matiza posicionándote como fuente experta.",
      "texto": "..."
    }},
    {{
      "tipo": "Máximo alcance",
      "descripcion": "Diseñada para shares y guardados.",
      "texto": "..."
    }}
  ]
}}"""

    tools = [{
        "function_declarations": [{
            "name": "buscar_informacion",
            "description": "Busca en internet para verificar datos, estadísticas y afirmaciones concretas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": "Consulta de búsqueda para verificar un dato específico del tweet."
                    }
                },
                "required": ["consulta"]
            }
        }]
    }]

    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"

    contents = [{
        "role": "user",
        "parts": [{"text": f"Verifica este tweet y genera 3 respuestas:{angulo_line}\n\nTweet a verificar:\n\n\"{tweet}\""}]
    }]

    max_iterations = 8
    for _ in range(max_iterations):
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "tools": tools
        }

        for attempt in range(3):
            resp = requests.post(url, json=payload, timeout=30)
            if resp.ok:
                break
            if resp.status_code == 503 and attempt < 2:
                time.sleep(3)
                continue

        if not resp.ok:
            return _error_json("Error de conexión. Inténtalo de nuevo.")

        data = resp.json()
        candidate = data.get("candidates", [{}])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        finish = candidate.get("finishReason", "")

        # Check for function calls
        function_calls = [p for p in parts if "functionCall" in p]
        text_parts = [p for p in parts if "text" in p]

        if function_calls:
            contents.append({"role": "model", "parts": parts})
            tool_responses = []
            for fc in function_calls:
                name = fc["functionCall"]["name"]
                args = fc["functionCall"].get("args", {})
                result_text = search_web(args.get("consulta", ""))
                tool_responses.append({
                    "functionResponse": {
                        "name": name,
                        "response": {"content": result_text}
                    }
                })
            contents.append({"role": "user", "parts": tool_responses})

        elif text_parts:
            full_text = "".join(p["text"] for p in text_parts)
            if full_text.strip():
                return extract_json(full_text)
            break
        else:
            break

    return _error_json("No se pudo obtener respuesta. Inténtalo de nuevo.")


# ─── UI ────────────────────────────────────────────────────────────────────────

init_session()
api_key = get_api_key()

st.markdown("# ⚡ Verificador de Tweets")
st.markdown("<p style='color:#555; margin-top:-0.5rem;'>Aesthetic Financiero · Verifica datos · Genera respuestas</p>", unsafe_allow_html=True)
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Premium unlock
with st.expander("🔓 Código Premium — verificaciones ilimitadas"):
    code_input = st.text_input("", placeholder="Introduce tu código", label_visibility="collapsed")
    if st.button("Activar", key="activate"):
        valid_codes = get_premium_codes()
        if code_input.strip().upper() in valid_codes:
            st.session_state.is_premium = True
            st.success("Acceso premium activado.")
            st.rerun()
        else:
            st.error("Código incorrecto.")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Counter
remaining = queries_remaining()
if st.session_state.is_premium:
    st.markdown("<span class='premium-badge'>PREMIUM · ILIMITADO</span>", unsafe_allow_html=True)
elif remaining > 1:
    st.markdown(f"<p class='counter-free'>Verificaciones gratuitas restantes hoy: {remaining}/{FREE_LIMIT}</p>", unsafe_allow_html=True)
elif remaining == 1:
    st.markdown(f"<p class='counter-warning'>⚠ Te queda {remaining} verificación hoy.</p>", unsafe_allow_html=True)
else:
    st.markdown("<p class='counter-empty'>Has agotado tus verificaciones gratuitas de hoy. Vuelve mañana o activa un código premium.</p>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Input
st.markdown("### Tweet a verificar")
tweet_input = st.text_area(
    "",
    height=160,
    placeholder="Pega aquí el tweet...",
    label_visibility="collapsed"
)

st.markdown("### ¿Qué quieres argumentar?")
st.markdown("<p style='color:#444; font-size:0.82rem; margin-top:-0.8rem; margin-bottom:0.6rem;'>Opcional — dile a la IA tu posición. Ej: \"Quiero demostrar que subir el SMI no reduce la inflación\"</p>", unsafe_allow_html=True)
angulo_input = st.text_area(
    "",
    height=80,
    placeholder="Quiero demostrar que... / Quiero ir contra... / Mi argumento es que...",
    label_visibility="collapsed",
    key="angulo"
)

run = st.button("⚡  Verificar y generar respuestas", use_container_width=True, disabled=(remaining == 0 and not st.session_state.is_premium))

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Process
if run:
    if not api_key:
        st.error("API Key no configurada. Contacta con el administrador.")
    elif not tweet_input.strip():
        st.error("Pega un tweet para verificar.")
    else:
        with st.spinner("Buscando datos y analizando..."):
            result = verify_tweet(tweet_input.strip(), api_key, angulo_input.strip())

        if not st.session_state.is_premium:
            st.session_state.query_count += 1

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
