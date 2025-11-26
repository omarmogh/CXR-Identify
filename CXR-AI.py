import streamlit as st
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go
import json
import re
import textwrap

# 1. CONFIGURATION
st.set_page_config(page_title="Interactive AI Radiology", layout="wide", page_icon="🩻")

# --- CALLBACK FUNCTION FOR PASSKEY ---
def check_passkey():
    if st.session_state.get("passkey_input") == "0000":
        st.session_state["google_api_key"] = "AIzaSyCDaBJ0bSub3S5VZoXBOViqyq3bFaHcIyg"

# 2. SIDEBAR
st.sidebar.title("🩻 Interactive Mode")
st.sidebar.info("Hover over the image to see AI detections.")

# --- API KEY INPUT ---
api_key = st.sidebar.text_input("Enter Google API Key", type="password", key="google_api_key")

# --- DYNAMIC MODEL LOADER ---
available_models = []
if api_key:
    try:
        genai.configure(api_key=api_key)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace("models/", "")
                if "exp" not in name: available_models.append(name)
        available_models.sort(key=lambda x: "flash" not in x)
    except: pass

if not available_models:
    available_models = ["gemini-1.5-pro", "gemini-1.5-flash"] 

model_type = st.sidebar.selectbox("Select Model (Pro recommended for coords)", available_models)

# --- SECRET PASSKEY ---
st.sidebar.markdown("---")
st.sidebar.text_input("Enter Passkey", type="password", key="passkey_input", on_change=check_passkey)

# 3. HELPER FUNCTION TO PARSE JSON
def parse_gemini_json(text):
    try:
        text = text.replace("```json", "").replace("```", "")
        return json.loads(text)
    except json.JSONDecodeError:
        return []

# 4. MAIN LOGIC
st.markdown("### 🏥 Radiology Seminar Presentation") 
st.title("🩻 General AI X-Ray Pathology Analyzer")
st.markdown("Upload a CXR. The AI references the **Fleischner Society Lexicon** to detect pathologies.")

uploaded_file = st.file_uploader("Choose an X-ray...", type=["jpg", "png", "jpeg"])

if uploaded_file and api_key:
    genai.configure(api_key=api_key)
    img = Image.open(uploaded_file)
    width, height = img.size
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("🤖 AI is analyzing for comprehensive pathology...")
        
        try:
            model = genai.GenerativeModel(model_name=model_type)
            
            # --- KNOWLEDGE BASE: RADIOLOGICAL LEXICON ---
            # This injects the "Medical Library" directly into the AI's context
            PATHOLOGY_LIBRARY = """
            1. AIRSPACE OPACITIES: Consolidation, Air bronchogram, Ground-glass opacity, Atelectasis (Lobar, Plate-like), Nodule (<3cm), Mass (>3cm), Cavitation, Miliary pattern.
            2. INTERSTITIAL SIGNS: Reticular pattern, Reticulonodular pattern, Kerley A/B/C lines, Honeycombing, Peribronchial cuffing, Septal thickening.
            3. PLEURAL ABNORMALITIES: Pleural effusion (Meniscus sign), Pneumothorax (Visceral pleural line, Deep sulcus sign), Hydropneumothorax, Pleural thickening/plaques, Empyema.
            4. MEDIASTINUM & HILA: Hilar adenopathy, Widened mediastinum, Tracheal deviation, Pneumomediastinum, Hiatal hernia.
            5. CARDIAC: Cardiomegaly (CTR > 0.5), Pericardial effusion (Water bottle sign), Dextrocardia, Enlarged LA/RA/LV/RV.
            6. BONES & SOFT TISSUE: Fractures (Rib, Clavicle, Spine), Lytic/Sclerotic lesions, Subcutaneous emphysema, Foreign bodies (Lines, Tubes, Pacemakers).
            7. DIAPHRAGM: Elevation (Phrenic nerve palsy), Flattening (COPD), Free air (Pneumoperitoneum/Chilaiditi).
            """

            # --- PROMPT ---
            prompt = f"""
            You are an expert Radiologist. Perform a SYSTEMATIC REVIEW of this chest X-ray.
            
            Reference this Medical Lexicon to ensure you check for ALL possibilities:
            {PATHOLOGY_LIBRARY}
            
            **INSTRUCTIONS:**
            - Check for ALL possibilities, including subtle or early signs.
            - List both definitive and suspected findings to ensure a comprehensive review.
            - Be extremely thorough.
            
            Return your findings in strictly valid JSON format. 
            Do NOT write any conversational text. Only return the JSON list.
            
            For each finding, provide a bounding box in the format [ymin, xmin, ymax, xmax] on a scale of 0 to 1000.
            
            Example Format:
            [
                {{"label": "Right Pneumothorax", "box_2d": [50, 600, 400, 900], "description": "Visible visceral pleural edge with absence of peripheral lung markings"}},
                {{"label": "Cardiomegaly", "box_2d": [500, 300, 900, 700], "description": "Enlarged cardiac silhouette (CTR > 0.5)"}}
            ]
            
            If the image is completely normal, return an empty list [].
            """
            
            response = model.generate_content([prompt, img])
            detections = parse_gemini_json(response.text)
            
            # --- PLOTLY CHART ---
            fig = go.Figure()
            fig.add_trace(go.Image(z=img, hoverinfo='skip'))
            
            if detections:
                for d in detections:
                    label = d.get("label", "Unknown")
                    box = d.get("box_2d", [0,0,0,0]) 
                    desc = d.get("description", "")
                    
                    # Wrap text to max 50 characters width per line
                    wrapped_desc = "<br>".join(textwrap.wrap(desc, width=50))
                    
                    y_min, x_min, y_max, x_max = box
                    abs_y1 = (y_min / 1000) * height
                    abs_x1 = (x_min / 1000) * width
                    abs_y2 = (y_max / 1000) * height
                    abs_x2 = (x_max / 1000) * width
                    
                    x_path = [abs_x1, abs_x2, abs_x2, abs_x1, abs_x1]
                    y_path = [abs_y1, abs_y1, abs_y2, abs_y2, abs_y1]

                    fig.add_trace(go.Scatter(
                        x=x_path, y=y_path,
                        fill="toself", mode="lines",
                        line=dict(color="rgba(0,0,0,0)"),
                        fillcolor="rgba(255, 255, 255, 0.01)",
                        name=label, text=label, customdata=[wrapped_desc],
                        hovertemplate="<b>%{text}</b><br><br>%{customdata}<extra></extra>",
                        showlegend=False
                    ))
            
            fig.update_layout(
                width=800, height=800 * (height/width),
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis={'visible': False, 'range': [0, width]},
                yaxis={'visible': False, 'range': [height, 0], 'scaleanchor': 'x'},
                hoverlabel=dict(bgcolor="white", font=dict(color="black", size=18, family="Arial"), bordercolor="black")
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                with st.expander("📋 Findings Log", expanded=True): 
                    if detections:
                        for d in detections:
                            st.write(f"**{d['label']}**")
                            st.caption(d['description'])
                    else:
                        st.write("No specific pathology detected.")

        except Exception as e:
            st.error(f"Error: {e}")

elif not api_key:
    st.warning("Enter API Key to start.")
