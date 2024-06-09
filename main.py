import sys
import os
import subprocess
import logging 
import configparser
import threading
import base64
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QComboBox,
    QLineEdit,
    QFileDialog,
    QListWidget,
    QProgressBar,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QStyleFactory,
    QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap

# Attempt to import PyQt6 styles, use Fusion if unavailable
try:
    from PyQt6 import QtQuickControls2
    QtQuickControls2.QQuickStyle.setStyle("Material")
except ImportError:
    QApplication.setStyle(QStyleFactory.create('Fusion'))

base64_icon = (
    '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'
)

# --- Constants ---
AUDIO_VIDEO_FILETYPES = [
    ("Audio files", "*.wav *.mp3 *.m4a *.ogg"),
    ("Video files", "*.mp4 *.mkv *.avi *.webm"),
    ("All files", "*.*"),
]
SUPPORTED_LANGUAGES = ["Auto Detect", "English", "Polish", "Japanese", "Spanish"]
WHISPER_MODELS = ["base", "base.en", "small", "small.en", "medium", "medium.en",
                 "large", "large-v2", "large-v3", "distil-large-v2", "distil-large-v3"]
TASK_OPTIONS = ["transcribe", "translate"]
OUTPUT_FORMAT_OPTIONS = ["txt", "vtt", "srt", "tsv", "json", "all"]
VAD_ALT_METHOD_OPTIONS = ["silero_v3", "silero_v4", "pyannote_v3",
                            "pyannote_onnx_v3", "auditok", "webrtc"]
COMPUTE_TYPE_OPTIONS = ["default", "auto", "int8", "int8_float16",
                        "int8_float32", "int8_bfloat16", "int16", "float16",
                        "float32", "bfloat16"]
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
            'exe_path': DEFAULT_VALUES['exe_path'],
            'sentence': 'False'  # Add sentence split option to config
        }
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)


def save_config(widget_dict):
    config['Settings']['language'] = widget_dict['language'].currentText()
    config['Settings']['model'] = widget_dict['model'].currentText()
    config['Settings']['task'] = widget_dict['task'].currentText()
    config['Settings']['output_format'] = widget_dict['output_format'].currentText()
    config['Settings']['output_dir'] = widget_dict['output_dir'].text()
    config['Settings']['ff_mdx_kim2'] = str(widget_dict['ff_mdx_kim2'].isChecked())
    config['Settings']['vad_filter'] = str(widget_dict['vad_filter'].isChecked())
    config['Settings']['vad_alt_method'] = widget_dict['vad_alt_method'].currentText()
    config['Settings']['word_timestamps'] = str(widget_dict['word_timestamps'].isChecked())
    config['Settings']['temperature'] = widget_dict['temperature'].text()
    config['Settings']['beam_size'] = widget_dict['beam_size'].text()
    config['Settings']['best_of'] = widget_dict['best_of'].text()
    config['Settings']['mdx_chunk'] = widget_dict['mdx_chunk'].text()
    config['Settings']['mdx_device'] = widget_dict['mdx_device'].text()
    config['Settings']['compute_type'] = widget_dict['compute_type'].currentText()
    config['Settings']['enable_logging'] = str(widget_dict['enable_logging'].isChecked())
    config['Settings']['sentence'] = str(widget_dict['sentence'].isChecked())  # Save sentence split option

    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


load_config()

logging.basicConfig(filename='transcription.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def enable_logging():
    return config.getboolean('Settings', 'enable_logging', fallback=True)


def validate_file_extension(filename):
    valid_extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.mp4',
                        '.mkv', '.avi', '.webm')
    return any(filename.lower().endswith(ext) for ext in valid_extensions)


def validate_numeric_input(value, min_value, max_value):
    try:
        numeric_value = float(value)
        return min_value <= numeric_value <= max_value
    except ValueError:
        return False


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


class TranscriptionWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, file_list, widget_dict):
        super().__init__()
        self.file_list = file_list
        self.widget_dict = widget_dict

    def run(self):
        try:
            self.run_transcription()
        except Exception as e:
            self.error_occurred.emit(f"An unexpected error occurred: {e}")
            if enable_logging():
                logging.error(
                    f"An unexpected error occurred during transcription: {e}")

    def run_transcription(self):
        if not self.file_list:
            self.error_occurred.emit("Please select at least one audio/video file or provide a link.")
            return

        language = self.widget_dict['language'].currentText()
        if language == "Auto Detect":
            language = None

        model = self.widget_dict['model'].currentText()
        task = self.widget_dict['task'].currentText()
        output_format = self.widget_dict['output_format'].currentText()
        output_dir = self.widget_dict['output_dir'].text() or "output"
        exe_path = config.get('Settings', 'exe_path',
                              fallback=DEFAULT_VALUES['exe_path']) or "faster-whisper-xxl.exe"

        ff_mdx_kim2 = self.widget_dict['ff_mdx_kim2'].isChecked()
        vad_filter = self.widget_dict['vad_filter'].isChecked()
        vad_alt_method = self.widget_dict['vad_alt_method'].currentText() if vad_filter else ""
        word_timestamps = self.widget_dict['word_timestamps'].isChecked()
        sentence = self.widget_dict['sentence'].isChecked()  # Get sentence split option value

        temperature = self.widget_dict['temperature'].text()
        if not validate_numeric_input(temperature, 0.0, 1.0):
            self.error_occurred.emit(
                "Temperature must be a number between 0.0 and 1.0.")
            return
        temperature = float(temperature)

        beam_size = self.widget_dict['beam_size'].text()
        if not validate_numeric_input(beam_size, 1, 100):
            self.error_occurred.emit(
                "Beam size must be an integer between 1 and 100.")
            return
        beam_size = int(beam_size)

        best_of = self.widget_dict['best_of'].text()
        if not validate_numeric_input(best_of, 1, 100):
            self.error_occurred.emit(
                "Best of must be an integer between 1 and 100.")
            return
        best_of = int(best_of)

        mdx_chunk = self.widget_dict['mdx_chunk'].text()
        if not validate_numeric_input(mdx_chunk, 1, 100):
            self.error_occurred.emit(
                "MDX chunk must be an integer between 1 and 100.")
            return
        mdx_chunk = int(mdx_chunk)

        mdx_device = self.widget_dict['mdx_device'].text()
        compute_type = self.widget_dict['compute_type'].currentText()

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        task_option = f"--task {task}" if task != "transcribe" else ""

        total_files = len(self.file_list)

        for index, file_path in enumerate(self.file_list, start=1):
            if file_path.startswith(("http://", "https://")):
                try:
                    filename = download_audio(file_path)
                except Exception as e:
                    self.error_occurred.emit(
                        f"Failed to download audio from {file_path}: {e}")
                    if enable_logging():
                        logging.error(
                            f"Failed to download audio from {file_path}: {e}")
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
                "--compute_type", compute_type,
            ]

            if language:
                command.extend(["--language", language])
            if ff_mdx_kim2:
                command.extend(
                    ["--ff_mdx_kim2", "--mdx_chunk", str(mdx_chunk), "--mdx_device", mdx_device])
            if vad_filter:
                command.extend(["--vad_filter", str(vad_filter)])
                if vad_alt_method:
                    command.extend(["--vad_alt_method", vad_alt_method])
            if word_timestamps:
                command.extend(["--word_timestamps", str(word_timestamps)])
            if sentence:  # Add sentence split option to command
                command.extend(["--sentence"])
            if temperature is not None:
                command.extend(["--temperature", str(temperature)])
            if beam_size is not None:
                command.extend(["--beam_size", str(beam_size)])
            if best_of is not None:
                command.extend(["--best_of", str(best_of)])

            command = [arg for arg in command if arg]

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
                logging.info(f"  Sentence Split: {sentence}")
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
                progress = int((index / total_files) * 100)
                self.progress_updated.emit(
                    progress, f"Progress: {index}/{total_files}")
                if enable_logging():
                    logging.info(
                        f"Transcription complete for {filename}.")
            except subprocess.CalledProcessError as e:
                self.error_occurred.emit(
                    f"An error occurred during transcription of {filename}: {e}")
                if enable_logging():
                    logging.error(
                        f"An error occurred during transcription of {filename}: {e}")

        self.finished.emit()

class Expander(QWidget):
    def __init__(self, label, target):
        super().__init__()
        self.label = label
        self.target = target
        self.collapsed = True
        self.init_ui()
        self.target.setVisible(False)
        self.update_header_label()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel()
        self.header.setStyleSheet("QLabel {font-weight: bold;}")
        self.header.mouseReleaseEvent = self.expand_collapse
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.target)
        self.setLayout(self.layout)
        self.update_header_label()

    def expand_collapse(self, event):
        self.collapsed = not self.collapsed
        self.target.setVisible(not self.collapsed)
        self.update_header_label()

    def update_header_label(self):
        if self.collapsed:
            self.header.setText(self.label + " ▼")
        else:
            self.header.setText(self.label + " ▲")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Whisper Transcription App")
        self.resize(450, 800)
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(base64_icon))
        self.setWindowIcon(QIcon(pixmap))

        self.widget_dict = {}
        self.create_widgets()
        self.create_layout()
        self.load_settings()

        self.setAcceptDrops(True)

    def create_widgets(self):
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_files)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_files)
        self.file_entry = QLineEdit()
        self.file_entry.setPlaceholderText("Enter file path or URL")
        self.add_file_button = QPushButton("Add")
        self.add_file_button.clicked.connect(self.add_file_from_entry)

        self.widget_dict['language'] = QComboBox()
        self.widget_dict['language'].addItems(SUPPORTED_LANGUAGES)
        self.widget_dict['model'] = QComboBox()
        self.widget_dict['model'].addItems(WHISPER_MODELS)
        self.widget_dict['task'] = QComboBox()
        self.widget_dict['task'].addItems(TASK_OPTIONS)
        self.widget_dict['output_format'] = QComboBox()
        self.widget_dict['output_format'].addItems(OUTPUT_FORMAT_OPTIONS)
        self.widget_dict['output_dir'] = QLineEdit()
        self.browse_output_dir_button = QPushButton("Browse")
        self.browse_output_dir_button.clicked.connect(self.browse_output_dir)

        self.widget_dict['ff_mdx_kim2'] = QCheckBox("Enable FF MDX Kim2")
        self.widget_dict['vad_filter'] = QCheckBox("Enable VAD Filter")
        self.widget_dict['vad_alt_method'] = QComboBox()
        self.widget_dict['vad_alt_method'].addItems(VAD_ALT_METHOD_OPTIONS)
        self.widget_dict['word_timestamps'] = QCheckBox("Enable Word Timestamps")
        self.widget_dict['sentence'] = QCheckBox("Split Lines into Sentences")
        self.widget_dict['compute_type'] = QComboBox()
        self.widget_dict['compute_type'].addItems(COMPUTE_TYPE_OPTIONS)
        self.widget_dict['temperature'] = QLineEdit()
        self.widget_dict['beam_size'] = QLineEdit()
        self.widget_dict['best_of'] = QLineEdit()
        self.widget_dict['mdx_chunk'] = QLineEdit()
        self.widget_dict['mdx_device'] = QLineEdit()
        self.widget_dict['enable_logging'] = QCheckBox("Enable Logging")

        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Progress: 0/0")

        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(lambda: save_config(self.widget_dict))

    def create_layout(self):
        main_layout = QVBoxLayout()

        file_selection_layout = QGridLayout()
        file_selection_layout.addWidget(QLabel("Audio/Video Files:"), 0, 0, 1, 2)
        file_selection_layout.addWidget(self.file_list_widget, 1, 0, 1, 2)
        file_selection_layout.addWidget(self.file_entry, 2, 0)
        file_selection_layout.addWidget(self.add_file_button, 2, 1)
        file_selection_layout.addWidget(self.browse_button, 3, 0)
        file_selection_layout.addWidget(self.clear_button, 3, 1)
        main_layout.addLayout(file_selection_layout)

        options_group_box = QGroupBox("Transcription Options")
        options_layout = QGridLayout()
        options_layout.addWidget(QLabel("Language:"), 0, 0)
        options_layout.addWidget(self.widget_dict['language'], 0, 1)
        options_layout.addWidget(QLabel("Model:"), 1, 0)
        options_layout.addWidget(self.widget_dict['model'], 1, 1)
        options_layout.addWidget(QLabel("Task:"), 2, 0)
        options_layout.addWidget(self.widget_dict['task'], 2, 1)
        options_layout.addWidget(QLabel("Output Format:"), 3, 0)
        options_layout.addWidget(self.widget_dict['output_format'], 3, 1)
        options_layout.addWidget(QLabel("Output Directory:"), 4, 0)
        options_layout.addWidget(self.widget_dict['output_dir'], 4, 1)
        options_layout.addWidget(self.browse_output_dir_button, 4, 2)
        options_group_box.setLayout(options_layout)
        main_layout.addWidget(options_group_box)

        advanced_options_layout = QGridLayout()
        advanced_options_layout.addWidget(self.widget_dict['ff_mdx_kim2'], 0, 0, 1, 2)
        advanced_options_layout.addWidget(self.widget_dict['vad_filter'], 1, 0)
        advanced_options_layout.addWidget(self.widget_dict['vad_alt_method'], 1, 1)
        advanced_options_layout.addWidget(self.widget_dict['word_timestamps'], 2, 0)
        advanced_options_layout.addWidget(self.widget_dict['sentence'], 2, 1)
        advanced_options_layout.addWidget(QLabel("Compute Type:"), 3, 0)
        advanced_options_layout.addWidget(self.widget_dict['compute_type'], 3, 1)
        advanced_options_layout.addWidget(QLabel("Temperature:"), 4, 0)
        advanced_options_layout.addWidget(self.widget_dict['temperature'], 4, 1)
        advanced_options_layout.addWidget(QLabel("Beam Size:"), 5, 0)
        advanced_options_layout.addWidget(self.widget_dict['beam_size'], 5, 1)
        advanced_options_layout.addWidget(QLabel("Best Of:"), 6, 0)
        advanced_options_layout.addWidget(self.widget_dict['best_of'], 6, 1)
        advanced_options_layout.addWidget(QLabel("MDX Chunk (seconds):"), 7, 0)
        advanced_options_layout.addWidget(self.widget_dict['mdx_chunk'], 7, 1)
        advanced_options_layout.addWidget(QLabel("MDX Device:"), 8, 0)
        advanced_options_layout.addWidget(self.widget_dict['mdx_device'], 8, 1)
        advanced_options_layout.addWidget(self.widget_dict['enable_logging'], 9, 0, 1, 2)

        advanced_section = Expander("Advanced Options", QWidget())
        advanced_section.target.setLayout(advanced_options_layout)
        main_layout.addWidget(advanced_section)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        main_layout.addLayout(progress_layout)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.transcribe_button)
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def browse_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio/Video Files", "/", " ".join([f"{desc} ({exts})" for desc, exts in AUDIO_VIDEO_FILETYPES])
        )
        self.file_list_widget.addItems(filenames)

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        self.widget_dict['output_dir'].setText(directory)

    def add_file_from_entry(self):
        file_path = self.file_entry.text().strip()
        if file_path:
            if validate_file_extension(file_path) or file_path.startswith(("http://", "https://")):
                self.file_list_widget.addItem(file_path)
                self.file_entry.clear()
            else:
                QMessageBox.warning(self, "Error", f"Invalid file path or unsupported file extension: {file_path}")
        else:
            QMessageBox.warning(self, "Error", "Input cannot be empty.")

    def clear_files(self):
        self.file_list_widget.clear()

    def load_settings(self):
        self.widget_dict['language'].setCurrentText(config.get('Settings', 'language', fallback=DEFAULT_VALUES['language']))
        self.widget_dict['model'].setCurrentText(config.get('Settings', 'model', fallback=DEFAULT_VALUES['model']))
        self.widget_dict['task'].setCurrentText(config.get('Settings', 'task', fallback=DEFAULT_VALUES['task']))
        self.widget_dict['output_format'].setCurrentText(config.get('Settings', 'output_format', fallback=DEFAULT_VALUES['output_format']))
        self.widget_dict['output_dir'].setText(config.get('Settings', 'output_dir', fallback=''))
        self.widget_dict['ff_mdx_kim2'].setChecked(config.getboolean('Settings', 'ff_mdx_kim2', fallback=True))
        self.widget_dict['vad_filter'].setChecked(config.getboolean('Settings', 'vad_filter', fallback=True))
        self.widget_dict['vad_alt_method'].setCurrentText(config.get('Settings', 'vad_alt_method', fallback=DEFAULT_VALUES['vad_alt_method']))
        self.widget_dict['word_timestamps'].setChecked(config.getboolean('Settings', 'word_timestamps', fallback=True))
        self.widget_dict['temperature'].setText(config.get('Settings', 'temperature', fallback=DEFAULT_VALUES['temperature']))
        self.widget_dict['beam_size'].setText(config.get('Settings', 'beam_size', fallback=DEFAULT_VALUES['beam_size']))
        self.widget_dict['best_of'].setText(config.get('Settings', 'best_of', fallback=DEFAULT_VALUES['best_of']))
        self.widget_dict['mdx_chunk'].setText(config.get('Settings', 'mdx_chunk', fallback=DEFAULT_VALUES['mdx_chunk']))
        self.widget_dict['mdx_device'].setText(config.get('Settings', 'mdx_device', fallback=DEFAULT_VALUES['mdx_device']))
        self.widget_dict['compute_type'].setCurrentText(config.get('Settings', 'compute_type', fallback=DEFAULT_VALUES['compute_type']))
        self.widget_dict['enable_logging'].setChecked(config.getboolean('Settings', 'enable_logging', fallback=True))
        self.widget_dict['sentence'].setChecked(config.getboolean('Settings', 'sentence', fallback=False))  # Load sentence split option

    def start_transcription(self):
        file_list = [self.file_list_widget.item(i).text() for i in range(self.file_list_widget.count())]

        self.transcription_worker = TranscriptionWorker(file_list, self.widget_dict)
        self.transcription_worker.progress_updated.connect(self.update_progress)
        self.transcription_worker.finished.connect(self.transcription_finished)
        self.transcription_worker.error_occurred.connect(self.show_error_message)
        self.transcription_worker.start()

    def update_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def transcription_finished(self):
        QMessageBox.information(self, "Success", "Transcription completed for all files!")
        if enable_logging():
            logging.info("Transcription completed for all files.")

    def show_error_message(self, error_message):
        QMessageBox.critical(self, "Error", error_message)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and validate_file_extension(file_path):
                    self.file_list_widget.addItem(file_path)
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(base64_icon))
    app.setWindowIcon(QIcon(pixmap))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
