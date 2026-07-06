import streamlit as st
import asyncio
import edge_tts
import os
import subprocess
import uuid
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(page_title="Creador de Video en la Nube", layout="centered")

st.title("🎬 Editor de Video en la Nube")
st.write("Subí tus archivos y dejá que el servidor haga todo el trabajo pesado.")

if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
if "video_ready" not in st.session_state:
    st.session_state.video_ready = None

uid = st.session_state.user_id

VOICES = {
    "🇨🇴 Colombia - Salomé (Femenina)": "es-CO-SalomeNeural",
    "🇨🇴 Colombia - Gonzalo (Masculino)": "es-CO-GonzaloNeural",
    "🇦🇷 Argentina - Elena (Femenina)": "es-AR-ElenaNeural",
    "🇦🇷 Argentina - Tomás (Masculino)": "es-AR-TomasNeural",
    "🇲🇽 México - Dalia (Femenina)": "es-MX-DaliaNeural",
    "🇲🇽 México - Jorge (Masculino)": "es-MX-JorgeNeural",
    "🇪🇸 España - Álvaro (Locutor)": "es-ES-AlvaroNeural"
}

async def generate_voice_async(text, voice_id, output_path):
    communicate = edge_tts.Communicate(text, voice_id)
    await communicate.save(output_path)

def get_audio_duration(audio_path):
    cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{audio_path}'"
    try:
        duration = subprocess.check_output(cmd, shell=True).decode().strip()
        return float(duration)
    except:
        return 5.0

def split_text_by_images(text, num_images):
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    if not sentences:
        return ["Sin texto"] * num_images
    
    chunks = []
    chunk_size = max(1, len(sentences) // num_images)
    for i in range(num_images):
        if i == num_images - 1:
            chunk = ". ".join(sentences[i * chunk_size:]) + "."
        else:
            chunk = ". ".join(sentences[i * chunk_size:(i + 1) * chunk_size]) + "."
        chunks.append(chunk)
    return chunks

def overlay_text_on_image(image_file, text, text_color, font_size, index, uid):
    img = Image.open(image_file).convert("RGB")
    img = img.resize((1280, 720))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.load_default()
    except:
        font = None

    w, h = img.size
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line + " " + word) * (font_size * 0.4) < w - 100:
            current_line += " " + word if current_line else word
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
        
    y_offset = h - (len(lines) * font_size) - 60
    for line in lines:
        draw.text((w // 2 - len(line) * (font_size * 0.2) + 2, y_offset + 2), line, fill="black", font=font)
        draw.text((w // 2 - len(line) * (font_size * 0.2), y_offset), line, fill=text_color, font=font)
        y_offset += font_size + 5
        
    proc_path = f"img_{uid}_{index}.jpg"
    img.save(proc_path)
    return proc_path

st.header("🛠️ 1. Cargar Elementos")
uploaded_files = st.file_uploader("Fotos (1 a 30)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) > 30:
    st.error("¡Ey, te pasaste! El límite son 30 fotos.")
    uploaded_files = uploaded_files[:30]

text_input = st.text_area("✍️ 2. Guión o texto largo", placeholder="Escribe la narración completa...")

st.header("🎨 3. Personalización")
col1, col2 = st.columns(2)
with col1:
    text_color = st.color_picker("Color de letra", "#FFFFFF")
    font_size = st.slider("Tamaño de letra", 20, 80, 40)
with col2:
    voice_label = st.selectbox("Voz del Narrador", list(VOICES.keys()))
    voice_id = VOICES[voice_label]

st.write("---")

if st.button("🚀 Renderizar Video en la Nube", type="primary"):
    if not uploaded_files or not text_input:
        st.warning("Asegurate de subir las fotos y rellenar el texto, pues.")
    else:
        with st.spinner("El servidor está procesando el video... Esto no gasta batería de tu cel."):
            num_images = len(uploaded_files)
            text_chunks = split_text_by_images(text_input, num_images)
            
            file_list_name = f"list_{uid}.txt"
            file_list_content = ""
            
            for i, file in enumerate(uploaded_files):
                audio_path = f"audio_{uid}_{i}.mp3"
                asyncio.run(generate_voice_async(text_chunks[i], voice_id, audio_path))
                
                duration = get_audio_duration(audio_path)
                processed_img = overlay_text_on_image(file, text_chunks[i], text_color, font_size, i, uid)
                
                segment_output = f"seg_{uid}_{i}.mp4"
                
                cmd = f"ffmpeg -y -loop 1 -i '{processed_img}' -i '{audio_path}' -c:v libx264 -t {duration} -pix_fmt yuv420p -c:a aac -b:a 128k '{segment_output}'"
                subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                file_list_content += f"file '{segment_output}'\n"
                
                if os.path.exists(processed_img): os.remove(processed_img)
                if os.path.exists(audio_path): os.remove(audio_path)
            
            with open(file_list_name, "w") as f:
                f.write(file_list_content)
            
            final_output = f"final_{uid}.mp4"
            concat_cmd = f"ffmpeg -y -f concat -safe 0 -i {file_list_name} -c copy {final_output}"
            subprocess.run(concat_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            for i in range(num_images):
                seg = f"seg_{uid}_{i}.mp4"
                if os.path.exists(seg): os.remove(seg)
            if os.path.exists(file_list_name): os.remove(file_list_name)
            
            if os.path.exists(final_output):
                st.session_state.video_ready = final_output
                st.success("¡Listo mija! Video generado perfectamente.")

if st.session_state.video_ready and os.path.exists(st.session_state.video_ready):
    st.header("🎬 4. Resultado Final")
    with open(st.session_state.video_ready, "rb") as video_file:
        video_bytes = video_file.read()
        st.video(video_bytes)
        st.download_button(
            label="📥 Descargar Video a la Galería",
            data=video_bytes,
            file_name="video_nube_sincronizado.mp4",
            mime="video/mp4"
        )
