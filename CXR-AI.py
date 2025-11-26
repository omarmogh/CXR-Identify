import streamlit as st
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go
import json
import re

# 1. CONFIGURATION
st.set_page_config(page_title="Interactive HF Radiology", layout="wide", page_icon="🩻")

# 2. SIDEBAR
st.sidebar.title("🩻 Interactive Mode")
st.sidebar.info("Hover over the image to see AI detections.")
api_key = st.sidebar.text_input("Enter Google API Key", type="password")

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

# 3. HELPER FUNCTION TO PARSE JSON
def parse_gemini_json(text):
    """
    Cleans and parses the JSON response from Gemini.
    """
    try:
        # Remove code blocks if present
        text = text.replace("```json", "").replace("```", "")
        return json.loads(text)
    except json.JSONDecodeError:
        return []

# 4. MAIN LOGIC
# --- UPDATED HEADER SECTION ---
st.markdown("### 🏥 Radiology Seminar Presentation") # Smaller, less bold header
st.title("🩻 Interactive X-Ray Analyzer")
st.markdown("Upload a CXR. **Hover over specific regions** (e.g., heart, lung bases) to reveal AI findings.")

uploaded_file = st.file_uploader("Choose an X-ray...", type=["jpg", "png", "jpeg"])

if uploaded_file and api_key:
    genai.configure(api_key=api_key)
    img = Image.open(uploaded_file)
    width, height = img.size
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("🤖 AI is analyzing coordinates... (This may take 10-15s)")
        
        try:
            model = genai.GenerativeModel(model_name=model_type)
            
            # --- PROMPT FOR COORDINATES ---
            prompt = """
            You are an expert Radiologist. Analyze this chest X-ray for signs of Heart Failure.
            
            Return your findings in strictly valid JSON format. 
            Do NOT write any conversational text. Only return the JSON list.
            
            For each finding (Cardiomegaly, Pleural Effusion, Kerley B Lines, Cephalization, Batwing Edema), 
            provide a bounding box in the format [ymin, xmin, ymax, xmax] on a scale of 0 to 1000.
            
            Example Format:
            [
                {"label": "Cardiomegaly", "box_2d": [500, 300, 900, 700], "description": "Enlarged cardiac silhouette"},
                {"label": "Right Pleural Effusion", "box_2d": [800, 100, 950, 400], "description": "Blunting of costophrenic angle"}
            ]
            
            If normal, return an empty list [].
            """
            
            response = model.generate_content([prompt, img])
            detections = parse_gemini_json(response.text)
            
            # --- BUILD PLOTLY INTERACTIVE IMAGE ---
            fig = go.Figure()
            
            # Add the X-Ray Image
            # hoverinfo='skip' ensures the annoying "Trace 0" or "x=100" text doesn't show up
            fig.add_trace(go.Image(z=img, hoverinfo='skip'))
            
            # Add Invisible Hover Zones
            if detections:
                for d in detections:
                    label = d.get("label", "Unknown")
                    box = d.get("box_2d", [0,0,0,0]) # [ymin, xmin, ymax, xmax] 0-1000
                    desc = d.get("description", "")
                    
                    # Convert normalized (0-1000) coords to pixels
                    y_min, x_min, y_max, x_max = box
                    
                    abs_y1 = (y_min / 1000) * height
                    abs_x1 = (x_min / 1000) * width
                    abs_y2 = (y_max / 1000) * height
                    abs_x2 = (x_max / 1000) * width
                    
                    # Create a closed path for the box
                    x_path = [abs_x1, abs_x2, abs_x2, abs_x1, abs_x1]
                    y_path = [abs_y1, abs_y1, abs_y2, abs_y2, abs_y1]

                    # Add an "Invisible" Filled Polygon
                    fig.add_trace(go.Scatter(
                        x=x_path,
                        y=y_path,
                        fill="toself",
                        mode="lines",
                        line=dict(color="rgba(0,0,0,0)"),       # Invisible border
                        fillcolor="rgba(255, 255, 255, 0.01)",  # 1% opacity fill (needed to catch mouse hover)
                        name=label,
                        text=label,
                        customdata=[desc],
                        hovertemplate="<b>%{text}</b><br><br>%{customdata}<extra></extra>", # This creates the pop-up text
                        showlegend=False
                    ))
            
            # Update Layout
            fig.update_layout(
                width=800, 
                height=800 * (height/width),
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis={'visible': False, 'range': [0, width]},
                yaxis={'visible': False, 'range': [height, 0], 'scaleanchor': 'x'}, # Invert Y for images
                
                # Make the hover tooltip BIGGER and cleaner
                hoverlabel=dict(
                    bgcolor="white", 
                    font=dict(color="black", size=18, family="Arial"), # Explicitly set text to black
                    bordercolor="black"
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # --- SIDEBAR TEXT REPORT (FOLDABLE) ---
            with col2:
                # UPDATED: Wrapped inside an expander to create the fold/hide toggle
                with st.expander("📋 Findings Log", expanded=True): 
                    if detections:
                        for d in detections:
                            st.write(f"**{d['label']}**")
                            st.caption(d['description'])
                    else:
                        st.write("No specific pathology detected.")
                        # st.write("Raw Output:", response.text) # Uncomment for debugging

        except Exception as e:
            st.error(f"Error: {e}")

elif not api_key:
    st.warning("Enter API Key to start.")
