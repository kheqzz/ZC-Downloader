import os
import signal
import subprocess
import time
import streamlit as st

st.set_page_config(page_title="Script Controller & Monitor", layout="wide")
st.title("🚀 Script Controller & Monitor")

PID_FILE = "process.pid"

# Helper untuk membaca PID aktif langsung dari sistem OS VPS
def get_active_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            # Cek apakah proses dengan PID ini benar-benar masih hidup di OS
            os.kill(pid, 0)
            return pid
        except (ValueError, OSError):
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    return None

current_pid = get_active_pid()

def count_lines_in_file(file_path: str) -> int:
    """Count the number of lines in a file."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    return 0

# --- BAGIAN 1: INPUT COMMAND / RUN SCRIPT ---
st.subheader("Run Script / Command")

col_cmd, col_btn, col_kill = st.columns([4, 1, 1])

with col_cmd:
    command = st.text_input(
        "Masukkan character:", 
        value="keqing", 
        placeholder="Contoh: keqing"
    )

with col_btn:
    st.write("")
    st.write("")
    run_pressed = st.button("▶️ Run Task", type="primary", use_container_width=True)

with col_kill:
    st.write("")
    st.write("")
    kill_pressed = st.button("🛑 Kill Task", type="secondary", use_container_width=True)

# LOGIKA RUN TASK
if run_pressed and command:
    if current_pid is not None:
        st.warning(f"Proses masih berjalan (PID: {current_pid}). Kill dulu sebelum menjalankan task baru.")
    else:
        try:
            with open("zerochan_api.log", "a", encoding="utf-8") as log_file:
                process = subprocess.Popen(
                    f"python -u zerochan_api_2.py {command}",
                    shell=True,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid
                )
                
                # Simpan PID ke file agar tidak hilang saat re-run
                with open(PID_FILE, "w") as f:
                    f.write(str(process.pid))

                st.success(f"Berhasil memicu perintah! (PID: {process.pid})")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"Gagal menjalankan perintah: {e}")

# LOGIKA KILL TASK
if kill_pressed:
    if current_pid is not None:
        try:
            # Mematikan seluruh kelompok proses (Group PID)
            os.killpg(os.getpgid(current_pid), signal.SIGTERM)
            
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
                
            st.success(f"Berhasil menghentikan proses dengan PID: {current_pid}")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menghentikan proses: {e}")
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    else:
        st.warning("Tidak ada proses yang sedang berjalan.")

# Indikator Status
if current_pid:
    st.info(f"🟢 Status: Script sedang berjalan (PID: {current_pid})")
else:
    st.caption("⚪ Status: Idle / Tidak ada proses berjalan")

st.divider()

# --- BAGIAN 2: LIVE MONITOR LOG ---
st.subheader("Live Log Monitor")

@st.fragment(run_every=2)
def render_logs():
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Done Log (`done.txt`)**")
        try:
            with open("done.txt", "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    st.code(content, language="text", height=350)
                else:
                    st.info("File done.txt masih kosong...")
        except FileNotFoundError:
            st.warning("File done.txt tidak ditemukan.")

    with col2:
        count = count_lines_in_file("zerochan_api.log")
        st.markdown(f"**Zerochan API Log (`zerochan_api.log`) (`Count {count}`)**")
        
        try:
            with open("zerochan_api.log", "r", encoding="utf-8") as f:
                content2 = f.read()
                if content2.strip():
                    st.code(content2, language="text", height=350)
                else:
                    st.info("File zerochan_api.log masih kosong...")
        except FileNotFoundError:
            st.warning("File zerochan_api.log tidak ditemukan.")

# Panggil fungsi fragment
render_logs()