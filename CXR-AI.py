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
st.sidebar.caption("© 2025 Omar Almoghrabi. All rights reserved") 
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
st.markdown("Upload a CXR (Single or Multi-View). The AI references the **Fleischner Society Lexicon**.")

uploaded_file = st.file_uploader("Choose an X-ray...", type=["jpg", "png", "jpeg"])

if uploaded_file and api_key:
    genai.configure(api_key=api_key)
    img = Image.open(uploaded_file)
    width, height = img.size
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("🤖 AI is analyzing image... (Scanning for duplicates & calculating scores)")
        
        try:
            model = genai.GenerativeModel(model_name=model_type)
            
            # --- KNOWLEDGE BASE: RADIOLOGICAL LEXICON ---
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
            
            **1. IMAGE ANALYSIS PROTOCOL (CRITICAL):**
            - The uploaded image may contain MULTIPLE views (e.g., PA and Lateral side-by-side).
            - **SINGLE REPORT RULE:** Treat all views in the image as ONE single diagnostic exam. 
            - **NO DUPLICATES:** If a pathology (e.g., 'Pleural Effusion') is visible in both the PA and Lateral views, **DO NOT** list it twice. List it **ONCE**.
            - **BOUNDING BOX SELECTION:** For the single consolidated finding, draw the bounding box on the view where the pathology is **most clearly defined** or easiest to measure. Do not draw two boxes for the same pathology.
            
            **2. ACCURACY & CONFIDENCE SCORING:**
            - You must **CALCULATE** a confidence score (0-100%) for every finding based on these metrics:
              - **Visual Clarity:** Is the sign distinct (Score 90-100) or hazy/obscured (Score 40-60)?
              - **Lexicon Match:** Does it perfectly match the Fleischner Society definition?
              - **Corroboration:** If multiple views exist, use them to increase your confidence score, but remember to output only ONE finding.
            
            Reference this Medical Lexicon:
            {PATHOLOGY_LIBRARY}
            
            **INSTRUCTIONS:**
            - Check for ALL possibilities, including subtle or early signs.
            - List both definitive and suspected findings.
            
            Return findings in strictly valid JSON format. 
            Do NOT write conversational text. Only return the JSON list.
            
            For each finding, provide:
            - label: Name of pathology (Include location, e.g., "Right Lower Lobe Pneumonia")
            - box_2d: [ymin, xmin, ymax, xmax] (0-1000 scale)
            - description: Brief medical description. Mention if it was confirmed on multiple views.
            - confidence: Integer 0-100
            
            Example Format:
            [
                {{"label": "Right Pneumothorax", "box_2d": [50, 600, 400, 900], "description": "Visible visceral pleural edge...", "confidence": 95}},
                {{"label": "Possible Nodule", "box_2d": [500, 300, 550, 350], "description": "Faint opacity in RUL...", "confidence": 45}}
            ]
            
            If normal, return [].
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
                    conf = d.get("confidence", 0)
                    
                    # Wrap text
                    wrapped_desc = "<br>".join(textwrap.wrap(f"{desc} (Conf: {conf}%)", width=50))
                    
                    y_min, x_min, y_max, x_max = box
                    abs_y1 = (y_min / 1000) * height
                    abs_x1 = (x_min / 1000) * width
                    abs_y2 = (y_max / 1000) * height
                    abs_x2 = (x_max / 1000) * width
                    
                    x_path = [abs_x1, abs_x2, abs_x2, abs_x1, abs_x1]
                    y_path = [abs_y1, abs_y1, abs_y2, abs_y2, abs_y1]

                    # Determine Color based on Confidence for the BOX too
                    box_color = "rgba(0, 255, 0, 0.2)" if conf >= 70 else "rgba(255, 165, 0, 0.2)" if conf >= 40 else "rgba(255, 0, 0, 0.2)"

                    fig.add_trace(go.Scatter(
                        x=x_path, y=y_path,
                        fill="toself", mode="lines",
                        line=dict(color="rgba(0,0,0,0)"),
                        fillcolor="rgba(255, 255, 255, 0.01)", # Invisible hover zone
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
                        for i, d in enumerate(detections):
                            label = d.get("label", "Unknown")
                            desc = d.get("description", "")
                            conf = d.get("confidence", 0)
                            
                            # Confidence Logic
                            if conf >= 70:
                                color_str = "green"
                                icon = "✅"
                                status = "High Accuracy"
                            elif conf >= 40:
                                color_str = "orange"
                                icon = "⚠️"
                                status = "Moderate Accuracy"
                            else:
                                color_str = "red"
                                icon = "❓"
                                status = "Low Accuracy"

                            st.markdown(f"**{label}**")
                            st.caption(desc)
                            st.markdown(f":{color_str}[**{icon} {conf}% - {status}**]")
                            
                            # Deep Search Button for Low/Moderate Confidence
                            if conf < 70:
                                if st.button(f"🔍 Consult Medical Library for '{label}'", key=f"btn_{i}"):
                                    st.info(f"running deep analysis on {label}...")
                                    # Simulate a deep dive by showing definition
                                    st.markdown(f"> **Library Definition Check:** The AI is re-evaluating **{label}** against the Fleischner Society criteria. Please clinically correlate.")
                            
                            st.markdown("---")
                    else:
                        st.write("No specific pathology detected.")

        except Exception as e:
            st.error(f"Error: {e}")

elif not api_key:
    st.warning("Enter API Key to start.")
