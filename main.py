import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
import subprocess
import os
import threading
import logging
from datetime import datetime
import configparser
import ttkbootstrap as ttb

# --- Constants ---
AUDIO_VIDEO_FILETYPES = [
    ("Audio files", "*.wav *.mp3 *.m4a *.ogg"),
    ("Video files", "*.mp4 *.mkv *.avi *.webm"),
    ("All files", "*.*"),
]
SUPPORTED_LANGUAGES = ["Auto Detect", "English", "Polish", "Japanese", "Spanish"]
WHISPER_MODELS = ["base", "base.en", "small", "small.en", "medium", "medium.en", "large", "large-v2", "large-v3", "distil-large-v2", "distil-large-v3"]
TASK_OPTIONS = ["transcribe", "translate"]
OUTPUT_FORMAT_OPTIONS = ["txt", "vtt", "srt", "tsv", "json", "all"]
VAD_ALT_METHOD_OPTIONS = ["silero_v3", "silero_v4", "pyannote_v3", "pyannote_onnx_v3", "auditok", "webrtc"]
COMPUTE_TYPE_OPTIONS = ["default", "auto", "int8", "int8_float16", "int8_float32", "int8_bfloat16", "int16", "float16", "float32", "bfloat16"]
DEFAULT_VALUES = {
    "language": SUPPORTED_LANGUAGES[0],
    "model": WHISPER_MODELS[7],
    "task": TASK_OPTIONS[0],
    "output_format": OUTPUT_FORMAT_OPTIONS[0],
    "vad_alt_method": "pyannote_v3",
    "compute_type": "auto",
    "temperature": "0.0",
    "beam_size": "5",
    "best_of": "5",
    "mdx_chunk": "15",
    "mdx_device": "cuda",
    "exe_path": "" 
}

CONFIG_FILE = "config.ini"
config = configparser.ConfigParser()

def load_config():
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        config['Settings'] = {
            'language': DEFAULT_VALUES['language'],
            'model': DEFAULT_VALUES['model'],
            'task': DEFAULT_VALUES['task'],
            'output_format': DEFAULT_VALUES['output_format'],
            'output_dir': '',
            'ff_mdx_kim2': 'True',
            'vad_filter': 'True',
            'vad_alt_method': DEFAULT_VALUES['vad_alt_method'],
            'word_timestamps': 'True',
            'temperature': DEFAULT_VALUES['temperature'],
            'beam_size': DEFAULT_VALUES['beam_size'],
            'best_of': DEFAULT_VALUES['best_of'],
            'mdx_chunk': DEFAULT_VALUES['mdx_chunk'],
            'mdx_device': DEFAULT_VALUES['mdx_device'],
            'compute_type': DEFAULT_VALUES['compute_type'],
            'enable_logging': 'True',
            'exe_path': DEFAULT_VALUES['exe_path'] 
        }
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

def save_config():
    config['Settings']['language'] = language_var.get()
    config['Settings']['model'] = model_var.get()
    config['Settings']['task'] = task_var.get()
    config['Settings']['output_format'] = output_format_var.get()
    config['Settings']['output_dir'] = output_dir_entry.get()
    config['Settings']['ff_mdx_kim2'] = str(ff_mdx_kim2_var.get())
    config['Settings']['vad_filter'] = str(vad_filter_var.get())
    config['Settings']['vad_alt_method'] = vad_alt_method_var.get()
    config['Settings']['word_timestamps'] = str(word_timestamps_var.get())
    config['Settings']['temperature'] = temperature_entry.get()
    config['Settings']['beam_size'] = beam_size_entry.get()
    config['Settings']['best_of'] = best_of_entry.get()
    config['Settings']['mdx_chunk'] = mdx_chunk_entry.get()
    config['Settings']['mdx_device'] = mdx_device_var.get()
    config['Settings']['compute_type'] = compute_type_var.get()
    config['Settings']['enable_logging'] = str(enable_logging_var.get())
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

load_config()

logging.basicConfig(filename='transcription.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def enable_logging():
    return config.getboolean('Settings', 'enable_logging', fallback=True)

class CreateToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)

    def enter(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = ttk.Label(self.tw, text=self.text, justify='left',
                          background='#2b3e50', relief='solid', borderwidth=1,
                          font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()

def browse_files():
    filenames = filedialog.askopenfilenames(
        initialdir="/",
        title="Select Audio/Video Files",
        filetypes=AUDIO_VIDEO_FILETYPES,
    )
    file_listbox.delete(0, tk.END)
    for filename in filenames:
        file_listbox.insert(tk.END, filename)

def browse_output_dir():
    directory = filedialog.askdirectory(
        initialdir="/",
        title="Select Output Directory",
    )
    output_dir_entry.delete(0, tk.END)
    output_dir_entry.insert(0, directory)

def validate_file_extension(filename):
    valid_extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.mp4', '.mkv', '.avi', '.webm')
    return any(filename.lower().endswith(ext) for ext in valid_extensions)

def validate_numeric_input(value, min_value, max_value):
    try:
        numeric_value = float(value)
        return min_value <= numeric_value <= max_value
    except ValueError:
        return False

def add_file_from_entry():
    file_path = file_entry.get().strip()
    if file_path:
        if validate_file_extension(file_path) or file_path.startswith(("http://", "https://")):
            file_listbox.insert(tk.END, file_path)
            file_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", f"Invalid file path or unsupported file extension: {file_path}")
    else:
        messagebox.showerror("Error", "Input cannot be empty.")

def transcribe(root):
    try:
        run_transcription(root)
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        if enable_logging():
            logging.error(f"An unexpected error occurred during transcription: {e}")

def run_transcription(root):
    file_list = file_listbox.get(0, tk.END)
    if not file_list:
        messagebox.showerror("Error", "Please select at least one audio/video file or provide a link.")
        return

    language = language_var.get()
    if language == "Auto Detect":
        language = None 
    
    model = model_var.get()
    task = task_var.get()
    output_format = output_format_var.get()
    output_dir = output_dir_entry.get() or "output"
    exe_path = config.get('Settings', 'exe_path', fallback=DEFAULT_VALUES['exe_path']) or "faster-whisper-xxl.exe" 

    ff_mdx_kim2 = ff_mdx_kim2_var.get()
    vad_filter = vad_filter_var.get()
    vad_alt_method = vad_alt_method_var.get() if vad_filter else ""
    word_timestamps = word_timestamps_var.get()

    temperature = temperature_entry.get()
    if not validate_numeric_input(temperature, 0.0, 1.0):
        messagebox.showerror("Error", "Temperature must be a number between 0.0 and 1.0.")
        return
    temperature = float(temperature)

    beam_size = beam_size_entry.get()
    if not validate_numeric_input(beam_size, 1, 100):
        messagebox.showerror("Error", "Beam size must be an integer between 1 and 100.")
        return
    beam_size = int(beam_size)

    best_of = best_of_entry.get()
    if not validate_numeric_input(best_of, 1, 100):
        messagebox.showerror("Error", "Best of must be an integer between 1 and 100.")
        return
    best_of = int(best_of)

    mdx_chunk = mdx_chunk_entry.get()
    if not validate_numeric_input(mdx_chunk, 1, 100):
        messagebox.showerror("Error", "MDX chunk must be an integer between 1 and 100.")
        return
    mdx_chunk = int(mdx_chunk)

    mdx_device = mdx_device_var.get()
    compute_type = compute_type_var.get()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    task_option = f"--task {task}" if task != "transcribe" else ""

    total_files = len(file_list)
    progress_var.set(0)
    progress_label.config(text=f"Progress: 0/{total_files}")

    for index, file_path in enumerate(file_list, start=1):
        if file_path.startswith(("http://", "https://")):
            try:
                filename = download_audio(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to download audio from {file_path}: {e}")
                if enable_logging():
                    logging.error(f"Failed to download audio from {file_path}: {e}")
                continue
        else:
            filename = file_path

        command = [
            exe_path,
            filename,
            "--model", model,
            task_option,
            "--output_dir", output_dir,
            "--output_format", output_format,
            "--sentence",
            "--compute_type", compute_type,
        ]

        if language:
            command.extend(["--language", language]) 

        if ff_mdx_kim2:
            command.extend(["--ff_mdx_kim2", "--mdx_chunk", str(mdx_chunk), "--mdx_device", mdx_device])

        if vad_filter:
            command.extend(["--vad_filter", str(vad_filter)])
            if vad_alt_method:
                command.extend(["--vad_alt_method", vad_alt_method])

        if word_timestamps:
            command.extend(["--word_timestamps", str(word_timestamps)])

        if temperature is not None:
            command.extend(["--temperature", str(temperature)])

        if beam_size is not None:
            command.extend(["--beam_size", str(beam_size)])

        if best_of is not None:
            command.extend(["--best_of", str(best_of)])

        command = [arg for arg in command if arg]  # Filter out any empty strings

        if enable_logging():
            logging.info("Selected Options:")
            logging.info(f"  File: {filename}")
            logging.info(f"  Language: {language}")
            logging.info(f"  Model: {model}")
            logging.info(f"  Task: {task}")
            logging.info(f"  Output Format: {output_format}")
            logging.info(f"  Output Directory: {output_dir}")
            logging.info(f"  FF MDX Kim2: {ff_mdx_kim2}")
            logging.info(f"  VAD Filter: {vad_filter}")
            logging.info(f"  VAD Alternative Method: {vad_alt_method}")
            logging.info(f"  Word Timestamps: {word_timestamps}")
            logging.info(f"  Temperature: {temperature}")
            logging.info(f"  Beam Size: {beam_size}")
            logging.info(f"  Best Of: {best_of}")
            logging.info(f"  MDX Chunk: {mdx_chunk}")
            logging.info(f"  MDX Device: {mdx_device}")
            logging.info(f"  Compute Type: {compute_type}")
            logging.info("Command:")
            logging.info(" ".join(command))

        try:
            subprocess.run(command, shell=True, check=True)
            progress = (index / total_files) * 100
            progress_var.set(progress)
            progress_label.config(text=f"Progress: {index}/{total_files}")
            root.update_idletasks()
            if enable_logging():
                logging.info(f"Transcription complete for {filename}.")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"An error occurred during transcription of {filename}: {e}")
            if enable_logging():
                logging.error(f"An error occurred during transcription of {filename}: {e}")

    messagebox.showinfo("Success", "Transcription completed for all files!")
    if enable_logging():
        logging.info("Transcription completed for all files.")

def on_drop(event, root):
    files = root.tk.splitlist(event.data)
    for file in files:
        if validate_file_extension(file):
            file_listbox.insert(tk.END, file)
        else:
            messagebox.showerror("Error", f"Invalid file extension: {file}")

def clear_files():
    file_listbox.delete(0, tk.END)

def download_audio(url):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)

    # Original filename preservation, using `yt-dlp` template options
    filename_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    command = [
        "yt-dlp",
        "-f", "bestaudio",
        "--output", filename_template,
        url
    ]

    if enable_logging():
        logging.info(f"Executing yt-dlp command: {' '.join(command)}")

    result = subprocess.run(command, check=True, capture_output=True)
    if enable_logging():
        logging.info(f"yt-dlp stdout: {result.stdout.decode('utf-8')}")
        logging.info(f"yt-dlp stderr: {result.stderr.decode('utf-8')}")

    output_filename = None
    for line in result.stdout.splitlines():
        if b"Destination:" in line:
            output_filename = line.decode('utf-8').split("Destination: ")[-1].strip()
            break

    if output_filename is None:
        raise Exception("Failed to locate the downloaded file.")

    if enable_logging():
        logging.info(f"Downloaded file location: {output_filename}")

    return output_filename

def create_main_window():
    root = TkinterDnD.Tk()
    style = ttb.Style(theme='superhero')  # Initialize ttkbootstrap style
    root.title("Whisper Transcription App")
    root.resizable(False, False)
    return root

def create_frames(root):
    file_frame = ttk.Frame(root)
    file_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

    options_frame = ttk.LabelFrame(root, text="Transcription Options")
    options_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

    output_dir_frame = ttk.Frame(root)
    output_dir_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

    advanced_options_frame = ttk.LabelFrame(root, text="Advanced Options")
    advanced_options_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

    progress_frame = ttk.Frame(root)
    progress_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

    button_frame = ttk.Frame(root)
    button_frame.grid(row=5, column=0, padx=10, pady=10, sticky="ew")

    return file_frame, options_frame, output_dir_frame, advanced_options_frame, progress_frame, button_frame

def create_file_selection_frame(file_frame, root):
    file_label = ttk.Label(file_frame, text="Audio/Video Files:")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    global file_listbox
    file_listbox = tk.Listbox(file_frame, selectmode=tk.MULTIPLE, height=8, width=90)
    file_listbox.grid(row=1, column=0, padx=5, pady=5, columnspan=2)

    # Create a new frame for manual input
    manual_entry_frame = ttk.Frame(file_frame)
    manual_entry_frame.grid(row=2, column=0, padx=5, pady=5, columnspan=2, sticky="ew")
    
    global file_entry
    file_entry = ttk.Entry(manual_entry_frame, width=70)
    file_entry.grid(row=0, column=0, padx=5, pady=5)

    add_file_button = ttk.Button(manual_entry_frame, text="Add", command=add_file_from_entry)
    add_file_button.grid(row=0, column=1, padx=5, pady=5)

    button_frame = ttk.Frame(file_frame)
    button_frame.grid(row=3, column=0, padx=5, pady=5, sticky="w")

    browse_button = ttk.Button(button_frame, text="Browse", command=browse_files)
    browse_button.grid(row=0, column=0, padx=5, pady=5)

    clear_button = ttk.Button(button_frame, text="Clear", command=clear_files)
    clear_button.grid(row=0, column=1, padx=5, pady=5)

    file_listbox.drop_target_register(DND_FILES)
    file_listbox.dnd_bind('<<Drop>>', lambda e: on_drop(e, root))

def create_output_dir_frame(output_dir_frame):
    output_dir_label = ttk.Label(output_dir_frame, text="Output Directory:")
    output_dir_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    global output_dir_entry
    output_dir_entry = ttk.Entry(output_dir_frame, width=50)
    output_dir_entry.grid(row=0, column=1, padx=5, pady=5)
    output_dir_entry.insert(0, config.get('Settings', 'output_dir', fallback=''))

    browse_output_dir_button = ttk.Button(output_dir_frame, text="Browse", command=browse_output_dir)
    browse_output_dir_button.grid(row=0, column=2, padx=5, pady=5)

def create_options_frame(options_frame):
    global language_var, model_var, task_var, output_format_var

    language_label = ttk.Label(options_frame, text="Language:")
    language_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
    CreateToolTip(language_label, "Select the language spoken in the audio.")

    language_var = tk.StringVar(value=config.get('Settings', 'language', fallback=DEFAULT_VALUES['language']))
    language_menu = ttk.OptionMenu(options_frame, language_var, language_var.get(), *SUPPORTED_LANGUAGES)
    language_menu.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    model_label = ttk.Label(options_frame, text="Model:")
    model_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
    CreateToolTip(model_label, "Select the Whisper model to use for transcription.")

    model_var = tk.StringVar(value=config.get('Settings', 'model', fallback=DEFAULT_VALUES['model']))
    model_menu = ttk.OptionMenu(options_frame, model_var, model_var.get(), *WHISPER_MODELS)
    model_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    task_label = ttk.Label(options_frame, text="Task:")
    task_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
    CreateToolTip(task_label, "Select the task: transcribe or translate.")

    task_var = tk.StringVar(value=config.get('Settings', 'task', fallback=DEFAULT_VALUES['task']))
    task_menu = ttk.OptionMenu(options_frame, task_var, task_var.get(), *TASK_OPTIONS)
    task_menu.grid(row=2, column=1, padx=5, pady=5, sticky="w")

    output_format_label = ttk.Label(options_frame, text="Output Format:")
    output_format_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
    CreateToolTip(output_format_label, "Select the format of the output file.")

    output_format_var = tk.StringVar(value=config.get('Settings', 'output_format', fallback=DEFAULT_VALUES['output_format']))
    output_format_menu = ttk.OptionMenu(options_frame, output_format_var, output_format_var.get(), *OUTPUT_FORMAT_OPTIONS)
    output_format_menu.grid(row=3, column=1, padx=5, pady=5, sticky="w")

def create_advanced_options_frame(advanced_options_frame):
    global ff_mdx_kim2_var, vad_filter_var, vad_alt_method_var, word_timestamps_var, compute_type_var
    global temperature_entry, beam_size_entry, best_of_entry, mdx_chunk_entry, mdx_device_var

    ff_mdx_kim2_var = tk.BooleanVar(value=config.getboolean('Settings', 'ff_mdx_kim2', fallback=True))
    ff_mdx_kim2_checkbox = ttk.Checkbutton(advanced_options_frame, text="Enable FF MDX Kim2", variable=ff_mdx_kim2_var)
    ff_mdx_kim2_checkbox.grid(row=0, column=0, sticky="w")
    CreateToolTip(ff_mdx_kim2_checkbox, "Enable high-quality vocals extraction using MDX-Net 'Kim_Vocal_2' model.")

    vad_filter_var = tk.BooleanVar(value=config.getboolean('Settings', 'vad_filter', fallback=True))
    vad_filter_checkbox = ttk.Checkbutton(advanced_options_frame, text="Enable VAD Filter", variable=vad_filter_var)
    vad_filter_checkbox.grid(row=1, column=0, sticky="w")
    CreateToolTip(vad_filter_checkbox, "Enable the Voice Activity Detection (VAD) filter.")

    vad_alt_method_var = tk.StringVar(value=config.get('Settings', 'vad_alt_method', fallback=DEFAULT_VALUES['vad_alt_method']))
    vad_alt_method_menu = ttk.OptionMenu(advanced_options_frame, vad_alt_method_var, vad_alt_method_var.get(), *VAD_ALT_METHOD_OPTIONS)
    vad_alt_method_menu.grid(row=1, column=1, sticky="w")
    CreateToolTip(vad_alt_method_menu, "Select the alternative VAD method to use.")

    word_timestamps_var = tk.BooleanVar(value=config.getboolean('Settings', 'word_timestamps', fallback=True))
    word_timestamps_checkbox = ttk.Checkbutton(advanced_options_frame, text="Enable Word Timestamps", variable=word_timestamps_var)
    word_timestamps_checkbox.grid(row=2, column=0, sticky="w")
    CreateToolTip(word_timestamps_checkbox, "Extract word-level timestamps.")

    compute_type_label = ttk.Label(advanced_options_frame, text="Compute Type:")
    compute_type_label.grid(row=3, column=0, sticky="w")
    CreateToolTip(compute_type_label, "Type of quantization to use (see https://opennmt.net/CTranslate2/quantization.html).")

    compute_type_var = tk.StringVar(value=config.get('Settings', 'compute_type', fallback=DEFAULT_VALUES['compute_type']))
    compute_type_menu = ttk.OptionMenu(advanced_options_frame, compute_type_var, compute_type_var.get(), *COMPUTE_TYPE_OPTIONS)
    compute_type_menu.grid(row=3, column=1, sticky="w")

    temperature_label = ttk.Label(advanced_options_frame, text="Temperature:")
    temperature_label.grid(row=4, column=0, sticky="w")
    CreateToolTip(temperature_label, "Set the temperature for sampling.")

    temperature_entry = ttk.Entry(advanced_options_frame, width=5)
    temperature_entry.grid(row=4, column=1, sticky="w")
    temperature_entry.insert(0, config.get('Settings', 'temperature', fallback=DEFAULT_VALUES['temperature']))

    beam_size_label = ttk.Label(advanced_options_frame, text="Beam Size:")
    beam_size_label.grid(row=5, column=0, sticky="w")
    CreateToolTip(beam_size_label, "Set the beam size for beam search.")

    beam_size_entry = ttk.Entry(advanced_options_frame, width=5)
    beam_size_entry.grid(row=5, column=1, sticky="w")
    beam_size_entry.insert(0, config.get('Settings', 'beam_size', fallback=DEFAULT_VALUES['beam_size']))

    best_of_label = ttk.Label(advanced_options_frame, text="Best Of:")
    best_of_label.grid(row=6, column=0, sticky="w")
    CreateToolTip(best_of_label, "Set the number of candidates when sampling with non-zero temperature.")

    best_of_entry = ttk.Entry(advanced_options_frame, width=5)
    best_of_entry.grid(row=6, column=1, sticky="w")
    best_of_entry.insert(0, config.get('Settings', 'best_of', fallback=DEFAULT_VALUES['best_of']))

    mdx_chunk_label = ttk.Label(advanced_options_frame, text="MDX Chunk (seconds):")
    mdx_chunk_label.grid(row=7, column=0, sticky="w")
    CreateToolTip(mdx_chunk_label, "Chunk size in seconds for MDX-Net filter. Smaller uses less memory, but can be slower and produce slightly lower quality.")

    mdx_chunk_entry = ttk.Entry(advanced_options_frame, width=5)
    mdx_chunk_entry.grid(row=7, column=1, sticky="w")
    mdx_chunk_entry.insert(0, config.get('Settings', 'mdx_chunk', fallback=DEFAULT_VALUES['mdx_chunk']))

    mdx_device_label = ttk.Label(advanced_options_frame, text="MDX Device:")
    mdx_device_label.grid(row=8, column=0, sticky="w")
    CreateToolTip(mdx_device_label, "Device to use for MDX-Net filter. Default is 'cuda' if CUDA device is detected, else is 'cpu'. If CUDA GPU is a second device then set 'cuda:1'.")

    mdx_device_var = tk.StringVar(value=config.get('Settings', 'mdx_device', fallback=DEFAULT_VALUES['mdx_device']))
    mdx_device_entry = ttk.Entry(advanced_options_frame, textvariable=mdx_device_var, width=10)
    mdx_device_entry.grid(row=8, column=1, sticky="w")

    global enable_logging_var
    enable_logging_var = tk.BooleanVar(value=config.getboolean('Settings', 'enable_logging', fallback=True))
    enable_logging_checkbox = ttk.Checkbutton(advanced_options_frame, text="Enable Logging", variable=enable_logging_var)
    enable_logging_checkbox.grid(row=9, column=0, sticky="w")
    CreateToolTip(enable_logging_checkbox, "Enable logging of transcription process and errors.")

def create_progress_frame(progress_frame):
    global progress_var, progress_label

    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, length=400)
    progress_bar.grid(row=0, column=0, padx=10, pady=10)

    progress_label = ttk.Label(progress_frame, text="Progress: 0/0")
    progress_label.grid(row=0, column=1, padx=5, pady=10)

def create_transcribe_button(root, button_frame):
    transcribe_button = ttk.Button(button_frame, text="Transcribe", command=lambda: threading.Thread(target=transcribe, args=(root,)).start())
    transcribe_button.grid(row=0, column=0, padx=10, pady=10)

    save_button = ttk.Button(button_frame, text="Save Settings", command=save_config)
    save_button.grid(row=0, column=1, padx=10, pady=10)

def main():
    root = create_main_window()
    file_frame, options_frame, output_dir_frame, advanced_options_frame, progress_frame, button_frame = create_frames(root)

    create_file_selection_frame(file_frame, root)
    create_output_dir_frame(output_dir_frame)
    create_options_frame(options_frame)
    create_advanced_options_frame(advanced_options_frame)
    create_progress_frame(progress_frame)
    create_transcribe_button(root, button_frame)

    root.mainloop()

if __name__ == "__main__":
    main()
