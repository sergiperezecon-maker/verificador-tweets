import streamlit as st
import anthropic
import json
import re
from duckduckgo_search import DDGS

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
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {
        "verificacion": {
            "veredicto": "ERROR",
            "explicacion": "No se pudo procesar la respuesta. Inténtalo de nuevo.",
            "dato_correcto": "",
            "fuentes": []
        },
        "respuestas": []
    }


def verify_tweet(tweet: str, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)

    tools = [{
        "name": "buscar_informacion",
        "description": "Busca en internet para verificar datos, estadísticas y afirmaciones concretas.",
        "input_schema": {
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

    system_prompt = """Eres un verificador de hechos experto en economía, finanzas y política española y global.
También eres estratega de contenido para el nicho "Aesthetic Financiero / Despertar Económico" en Instagram y TikTok.

PROCESO:
1. Identifica las afirmaciones verificables del tweet.
2. Usa buscar_informacion para contrastar los datos clave (busca en español e inglés si hace falta).
3. Devuelve el resultado en el JSON exacto indicado abajo.

ESTILO DE LAS RESPUESTAS:
- Tono oscuro, elegante, directo. Autoridad + urgencia.
- Frases cortas e impactantes. Máximo 4 líneas.
- Usa **negritas** para el dato más fuerte.
- Sin emojis salvo al principio si refuerza el impacto.

FORMATO DE SALIDA — devuelve ÚNICAMENTE este JSON, sin texto extra:
{
  "verificacion": {
    "veredicto": "VERDADERO | FALSO | PARCIALMENTE VERDADERO",
    "explicacion": "Explicación clara y concisa del veredicto.",
    "dato_correcto": "El dato exacto o matiz importante si lo hay.",
    "fuentes": ["url1", "url2"]
  },
  "respuestas": [
    {
      "tipo": "Amplificación",
      "descripcion": "Confirma y añade el dato más impactante.",
      "texto": "..."
    },
    {
      "tipo": "Corrección con autoridad",
      "descripcion": "Corrige o matiza posicionándote como fuente experta.",
      "texto": "..."
    },
    {
      "tipo": "Máximo alcance",
      "descripcion": "Diseñada para shares y guardados.",
      "texto": "..."
    }
  ]
}"""

    messages = [{"role": "user", "content": f'Verifica este tweet y genera 3 respuestas:\n\n"{tweet}"'}]
    max_iterations = 6

    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_text = search_web(block.input["consulta"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text
                    })
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return extract_json(block.text)
            break
        else:
            break

    return extract_json("")


# ─── UI ────────────────────────────────────────────────────────────────────────

st.markdown("# ⚡ Verificador de Tweets")
st.markdown("<p style='color:#555; margin-top:-0.5rem;'>Aesthetic Financiero · Verifica datos · Genera respuestas</p>", unsafe_allow_html=True)
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# API Key
api_key_saved = st.session_state.get("api_key", "")
with st.expander("🔑 API Key de Anthropic", expanded=not api_key_saved):
    st.markdown("<small style='color:#555'>Tu key nunca sale de tu ordenador. Se guarda solo en esta sesión.</small>", unsafe_allow_html=True)
    key_input = st.text_input("", type="password", value=api_key_saved, placeholder="sk-ant-api03-...")
    if key_input:
        st.session_state["api_key"] = key_input
        st.success("API Key guardada ✓")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Input
st.markdown("### Tweet a verificar")
tweet_input = st.text_area(
    "",
    height=160,
    placeholder="Pega aquí el tweet...",
    label_visibility="collapsed"
)
run = st.button("⚡  Verificar y generar respuestas", use_container_width=True)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Process
if run:
    if not st.session_state.get("api_key"):
        st.error("Añade tu API Key de Anthropic arriba.")
    elif not tweet_input.strip():
        st.error("Pega un tweet para verificar.")
    else:
        with st.spinner("Buscando datos y analizando..."):
            result = verify_tweet(tweet_input.strip(), st.session_state["api_key"])

        verif = result.get("verificacion", {})
        veredicto = verif.get("veredicto", "ERROR")

        # Verdict colors
        palette = {
            "VERDADERO":               ("#00e676", "#0a1f14", "#0d3022"),
            "FALSO":                   ("#ff5252", "#1f0a0a", "#300d0d"),
            "PARCIALMENTE VERDADERO":  ("#ffab40", "#1f1500", "#30200a"),
            "ERROR":                   ("#888888", "#111111", "#1a1a1a"),
        }
        text_color, bg_color, border_color = palette.get(veredicto, palette["ERROR"])

        # Verification block
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

        # Responses
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
                    # Copy-friendly code block
                    st.code(resp.get("texto", ""), language=None)
        else:
            st.warning("No se generaron respuestas. Revisa tu API Key o inténtalo de nuevo.")
