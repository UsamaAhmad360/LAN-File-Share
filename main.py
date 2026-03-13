import customtkinter as ctk
from tkinter import filedialog
from flask import Flask, send_file, render_template_string, request, redirect, url_for
import threading
import os
import socket
import qrcode
from PIL import Image, ImageTk
import zipfile
import io
import time

# ---------------------- CONFIG ----------------------
ctk.set_appearance_mode("dark")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------- FLASK SERVER ----------------------
app = Flask(__name__)
shared_files = []
file_types = {}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LAN File Share</title>
<style>
body{font-family:Arial;background:#111827;color:white;padding:20px;}
h2{text-align:center;color:#22c55e;}
.file-card{background:#1f2937;padding:12px;margin:10px 0;border-radius:10px;display:flex;justify-content:space-between;}
.file-card a{background:#22c55e;color:#111827;padding:6px 12px;border-radius:6px;text-decoration:none;font-weight:bold;}
.upload-link{display:block;text-align:center;margin-top:25px;color:#22c55e;}
</style>
</head>
<body>
<h2>Shared Files</h2>
{% for idx, name, type in data %}
<div class="file-card">
<div>{{name}}</div>
{% if type=="file" %}
<a href="/download/{{idx}}">Download</a>
{% else %}
<a href="/download_folder/{{idx}}">Download ZIP</a>
{% endif %}
</div>
{% endfor %}
<a href="/upload" class="upload-link">Upload Files</a>
</body>
</html>
"""

UPLOAD_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload Files</title>
<style>
body{font-family:Arial;background:#111827;color:white;padding:20px;}
h2{text-align:center;color:#22c55e;}
form{display:flex;flex-direction:column;gap:12px;align-items:center;}
input[type=file]{width:90%;padding:10px;border-radius:8px;border:none;background:#1f2937;color:white;}
button{width:50%;padding:10px;border-radius:8px;border:none;background:#22c55e;color:#111827;font-weight:bold;}
ul{margin-top:20px;}
a{display:block;margin-top:20px;text-align:center;color:#22c55e;}
</style>
</head>
<body>
<h2>Upload Files</h2>
<form method="POST" action="/upload" enctype="multipart/form-data">
<input type="file" name="file" multiple>
<button type="submit">Upload</button>
</form>

<h3>Uploaded Files:</h3>
<ul>
{% for f in files %}
<li>{{f}}</li>
{% endfor %}
</ul>

<a href="/">Back to Download Page</a>
</body>
</html>
"""

@app.route("/")
def index():
    names = [os.path.basename(f) for f in shared_files]
    types = [file_types[f] for f in shared_files]
    data = list(zip(range(len(names)), names, types))
    return render_template_string(HTML_PAGE, data=data)

@app.route("/download/<int:file_id>")
def download(file_id):
    return send_file(shared_files[file_id], as_attachment=True)

@app.route("/download_folder/<int:folder_id>")
def download_folder(folder_id):
    folder_path = shared_files[folder_id]

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, rel_path)

    zip_buffer.seek(0)
    folder_name = os.path.basename(folder_path)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"{folder_name}.zip"
    )

@app.route("/upload", methods=["GET","POST"])
def upload():
    if request.method == "POST":

        uploaded_files = request.files.getlist("file")

        for uploaded_file in uploaded_files:
            if uploaded_file:

                save_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
                uploaded_file.save(save_path)

                if save_path not in shared_files:
                    shared_files.append(save_path)
                    file_types[save_path] = "file"

        return redirect(url_for("upload"))

    uploaded_files_list = os.listdir(UPLOAD_FOLDER)
    return render_template_string(UPLOAD_HTML, files=uploaded_files_list)

# ---------------------- SERVER ----------------------

def run_server():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "127.0.0.1"
    return ip

def start_server():

    threading.Thread(target=run_server, daemon=True).start()

    ip = get_local_ip()
    url = f"http://{ip}:5000"

    link_label.configure(text=url)

    app_gui.after(200, lambda: generate_qr(url))

# ---------------------- QR CODE ----------------------

def generate_qr(url):

    global qr_img

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img = img.convert("RGB")
    img = img.resize((220,220))

    qr_img = ImageTk.PhotoImage(img)

    qr_label.configure(image=qr_img, text="")
    qr_label.image = qr_img

# ---------------------- FILE PICKERS ----------------------

def add_file():

    file = filedialog.askopenfilename()

    if file:
        shared_files.append(file)
        file_types[file] = "file"

        file_box.insert("end", os.path.basename(file)+"\n")

def add_folder():

    folder = filedialog.askdirectory()

    if folder:
        shared_files.append(folder)
        file_types[folder] = "folder"

        file_box.insert("end", os.path.basename(folder)+" (folder)\n")

# ---------------------- AUTO REFRESH ----------------------

def refresh_uploaded_files():

    while True:

        for f in os.listdir(UPLOAD_FOLDER):

            full_path = os.path.join(UPLOAD_FOLDER,f)

            if full_path not in shared_files:

                shared_files.append(full_path)
                file_types[full_path] = "file"

                app_gui.after(0, lambda fp=f: file_box.insert("end", fp+" (uploaded)\n"))

        time.sleep(2)

# ---------------------- GUI ----------------------

app_gui = ctk.CTk()
app_gui.geometry("520x750")
app_gui.title("LAN File Share")

title = ctk.CTkLabel(app_gui,text="LAN File Share",font=("Arial",22))
title.pack(pady=15)

file_box = ctk.CTkTextbox(app_gui,height=250)
file_box.pack(padx=20,pady=10,fill="both")

btn_frame = ctk.CTkFrame(app_gui)
btn_frame.pack(pady=10)

ctk.CTkButton(btn_frame,text="Add File",command=add_file).grid(row=0,column=0,padx=10)
ctk.CTkButton(btn_frame,text="Add Folder",command=add_folder).grid(row=0,column=1,padx=10)

ctk.CTkButton(app_gui,text="Start Server",command=start_server).pack(pady=15)

link_label = ctk.CTkLabel(app_gui,text="Server not started")
link_label.pack(pady=5)

qr_label = ctk.CTkLabel(app_gui,text="QR code will appear here")
qr_label.pack(pady=20)

threading.Thread(target=refresh_uploaded_files, daemon=True).start()

app_gui.mainloop()